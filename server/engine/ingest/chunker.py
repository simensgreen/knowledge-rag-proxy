"""Markdown-aware document chunking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from markdown_it import MarkdownIt

from server.engine.ingest.chunk_text import (
    TARGET_CHUNK_CHARS,
    apply_prefix_suffix,
    build_breadcrumb,
    code_line_units,
    greedy_pack_spans,
    prose_sentence_units,
    spans_to_chunks,
)
from server.engine.ingest.models import Chunk

BlockKind = Literal["prose", "code"]
MarkdownBlockKind = Literal["heading", "paragraph", "code", "list", "table"]

_markdown = MarkdownIt("commonmark").enable("table")

# markdown-it emits one opening token per top-level block; map it to our kinds.
_BLOCK_KIND_BY_TOKEN: dict[str, MarkdownBlockKind] = {
    "heading_open": "heading",
    "paragraph_open": "paragraph",
    "fence": "code",
    "code_block": "code",
    "bullet_list_open": "list",
    "ordered_list_open": "list",
    "table_open": "table",
    "blockquote_open": "paragraph",
    "hr": "paragraph",
    "html_block": "paragraph",
}


@dataclass(frozen=True)
class MarkdownBlock:
    kind: MarkdownBlockKind
    text: str
    heading_level: int | None = None
    heading_title: str | None = None


def parse_markdown_blocks(markdown: str) -> list[MarkdownBlock]:
    lines = markdown.splitlines(keepends=True)
    tokens = _markdown.parse(markdown)
    blocks: list[MarkdownBlock] = []
    cursor = 0

    for position, token in enumerate(tokens):
        if token.level != 0 or token.nesting < 0 or token.map is None:
            continue
        kind = _BLOCK_KIND_BY_TOKEN.get(token.type)
        if kind is None:
            continue

        start, end = token.map
        # Blank lines and other gaps between blocks are not covered by any token;
        # emit them verbatim so join(content) reconstructs the source byte for byte.
        if start > cursor:
            gap = "".join(lines[cursor:start])
            if gap:
                blocks.append(MarkdownBlock(kind="paragraph", text=gap))

        heading_level = None
        heading_title = None
        if kind == "heading":
            heading_level = int(token.tag[1:]) if token.tag[1:].isdigit() else None
            inline = tokens[position + 1] if position + 1 < len(tokens) else None
            heading_title = inline.content if inline is not None and inline.type == "inline" else None

        blocks.append(
            MarkdownBlock(
                kind=kind,
                text="".join(lines[start:end]),
                heading_level=heading_level,
                heading_title=heading_title,
            )
        )
        cursor = max(cursor, end)

    if cursor < len(lines):
        trailing = "".join(lines[cursor:])
        if trailing:
            blocks.append(MarkdownBlock(kind="paragraph", text=trailing))

    return blocks


def split_text(
    text: str,
    breadcrumb: str,
    start_index: int,
    block_kind: BlockKind,
) -> list[Chunk]:
    if not text:
        return []
    if len(text) <= TARGET_CHUNK_CHARS:
        return [
            Chunk(
                chunk_index=start_index,
                content=text,
                breadcrumb=breadcrumb,
            )
        ]

    units = prose_sentence_units(text) if block_kind == "prose" else code_line_units(text)
    spans = greedy_pack_spans(text, units, TARGET_CHUNK_CHARS, block_kind)
    return spans_to_chunks(text, spans, breadcrumb, start_index, block_kind)


def split_list_items(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    tokens = _markdown.parse(text)
    # Only top-level items (level 1); nested sub-lists stay grouped with their parent item.
    item_starts = [
        token.map[0]
        for token in tokens
        if token.type == "list_item_open" and token.level == 1 and token.map is not None
    ]
    if len(item_starts) <= 1:
        return [text] if text else []

    item_starts[0] = 0  # absorb any lines before the first item to keep reconstruction exact
    items: list[str] = []
    for position, start in enumerate(item_starts):
        end = item_starts[position + 1] if position + 1 < len(item_starts) else len(lines)
        item = "".join(lines[start:end])
        if item:
            items.append(item)
    return items


def split_table_rows(text: str) -> list[str]:
    return [line for line in text.splitlines(keepends=True) if line]


def split_table_columns(row: str) -> list[str]:
    lines = row.splitlines(keepends=True)
    if not lines:
        return [row]
    body = lines[-1].rstrip("\n")
    prefix = "".join(lines[:-1])
    parts = [part.strip() for part in body.strip("|").split("|")]
    columns: list[str] = []
    rebuilt: list[str] = []
    trailing_newline = "\n" if row.endswith("\n") else ""
    for part in parts:
        rebuilt.append(part)
        cell_body = "| " + " | ".join(rebuilt) + " |"
        cell = prefix + cell_body + trailing_newline
        columns.append(cell)
    return columns


def greedy_pack_strings(units: list[str]) -> list[str]:
    packed: list[str] = []
    for unit in units:
        if not packed:
            packed.append(unit)
            continue
        if len(packed[-1]) + len(unit) <= TARGET_CHUNK_CHARS:
            packed[-1] += unit
        else:
            packed.append(unit)
    return packed


def expand_oversized_texts(
    texts: list[str],
    breadcrumb: str,
    block_kind: BlockKind,
) -> list[str]:
    expanded: list[str] = []
    for text in texts:
        if len(text) <= TARGET_CHUNK_CHARS:
            expanded.append(text)
            continue
        split_chunks = split_text(text, breadcrumb, 0, block_kind)
        expanded.extend(chunk.content for chunk in split_chunks)
    return expanded


def chunks_from_texts(
    texts: list[str],
    breadcrumb: str,
    start_index: int,
    block_kind: BlockKind,
) -> list[Chunk]:
    raw = [
        Chunk(
            chunk_index=start_index + offset,
            content=text,
            breadcrumb=breadcrumb,
        )
        for offset, text in enumerate(texts)
    ]
    return apply_prefix_suffix(raw, block_kind)


def split_list(
    text: str,
    breadcrumb: str,
    start_index: int,
) -> list[Chunk]:
    if len(text) <= TARGET_CHUNK_CHARS:
        return [
            Chunk(
                chunk_index=start_index,
                content=text,
                breadcrumb=breadcrumb,
            )
        ]

    items = split_list_items(text)
    packed = greedy_pack_strings(items)
    expanded = expand_oversized_texts(packed, breadcrumb, "prose")
    return chunks_from_texts(expanded, breadcrumb, start_index, "prose")


def split_table(
    text: str,
    breadcrumb: str,
    start_index: int,
) -> list[Chunk]:
    if len(text) <= TARGET_CHUNK_CHARS:
        return [
            Chunk(
                chunk_index=start_index,
                content=text,
                breadcrumb=breadcrumb,
            )
        ]

    rows = split_table_rows(text)
    packed_rows = greedy_pack_strings(rows)
    expanded_rows: list[str] = []
    for row in packed_rows:
        if len(row) <= TARGET_CHUNK_CHARS:
            expanded_rows.append(row)
            continue
        columns = split_table_columns(row)
        column_packed = greedy_pack_strings(columns)
        expanded_rows.extend(expand_oversized_texts(column_packed, breadcrumb, "prose"))

    return chunks_from_texts(expanded_rows, breadcrumb, start_index, "prose")


def chunk_block(
    block: MarkdownBlock,
    breadcrumb: str,
    start_index: int,
) -> list[Chunk]:
    if block.kind == "code":
        return split_text(block.text, breadcrumb, start_index, "code")
    if block.kind == "list":
        return split_list(block.text, breadcrumb, start_index)
    if block.kind == "table":
        return split_table(block.text, breadcrumb, start_index)
    return split_text(block.text, breadcrumb, start_index, "prose")


def chunk_markdown(markdown: str, filename: str) -> list[Chunk]:
    blocks = parse_markdown_blocks(markdown)
    headings: list[tuple[int, str]] = []
    chunks: list[Chunk] = []
    next_index = 0

    for block in blocks:
        if block.kind == "heading" and block.heading_level is not None:
            level = block.heading_level
            title = block.heading_title or block.text.strip().lstrip("#").strip()
            while headings and headings[-1][0] >= level:
                headings.pop()
            headings.append((level, title))

        breadcrumb = build_breadcrumb(filename, headings)
        block_chunks = chunk_block(block, breadcrumb, next_index)
        chunks.extend(block_chunks)
        next_index += len(block_chunks)

    for index, chunk in enumerate(chunks):
        if chunk.chunk_index != index:
            chunks[index] = Chunk(
                chunk_index=index,
                content=chunk.content,
                breadcrumb=chunk.breadcrumb,
                prefix=chunk.prefix,
                suffix=chunk.suffix,
            )

    return chunks
