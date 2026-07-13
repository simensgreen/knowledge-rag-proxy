"""Text helpers for chunking and search_text assembly."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from server.engine.ingest.models import Chunk

BlockKind = Literal["prose", "code"]

TARGET_CHUNK_CHARS = 1800
PREFIX_SUFFIX_CHARS = 250

SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


def build_breadcrumb(filename: str, headings: list[tuple[int, str]]) -> str:
    lines = [Path(filename).name]
    for level, text in headings:
        lines.append("#" * level + " " + text)
    return "\n".join(lines)


def build_search_text(
    breadcrumb: str,
    content: str,
    *,
    prefix: str | None = None,
    suffix: str | None = None,
) -> str:
    text = breadcrumb + "\n"
    if prefix:
        text += "\n" + prefix
    text += content
    if suffix:
        text += "\n" + suffix
    return text


def reconstruct_document(chunks: list[Chunk]) -> str:
    ordered = sorted(chunks, key=lambda chunk: chunk.chunk_index)
    return "".join(chunk.content for chunk in ordered)


def prose_sentence_units(text: str) -> list[tuple[int, int]]:
    if not text:
        return []
    spans: list[tuple[int, int]] = []
    start = 0
    for match in SENTENCE_BOUNDARY.finditer(text):
        end = match.end()
        if end > start:
            spans.append((start, end))
        start = end
    if start < len(text):
        spans.append((start, len(text)))
    if not spans:
        spans.append((0, len(text)))
    return spans


def code_line_units(text: str) -> list[tuple[int, int]]:
    if not text:
        return []
    spans: list[tuple[int, int]] = []
    start = 0
    while start <= len(text):
        newline = text.find("\n", start)
        if newline == -1:
            if start < len(text) or (start == len(text) and text.endswith("\n")):
                spans.append((start, len(text)))
            break
        spans.append((start, newline + 1))
        start = newline + 1
    if not spans and text:
        spans.append((0, len(text)))
    return spans


def word_units(text: str) -> list[tuple[int, int]]:
    if not text:
        return []
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in re.finditer(r"\S+", text):
        if match.start() > cursor:
            spans.append((cursor, match.start()))
        spans.append((match.start(), match.end()))
        cursor = match.end()
    if cursor < len(text):
        spans.append((cursor, len(text)))
    if not spans:
        spans.append((0, len(text)))
    return spans


def hard_cut_units(text: str, max_chars: int) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        spans.append((start, end))
        start = end
    return spans


def units_for_text(text: str, block_kind: BlockKind) -> list[tuple[int, int]]:
    if block_kind == "code":
        return code_line_units(text)
    return prose_sentence_units(text)


def subdivide_unit(
    text: str,
    unit: tuple[int, int],
    max_chars: int,
    block_kind: BlockKind,
) -> list[tuple[int, int]]:
    segment = text[unit[0] : unit[1]]
    if len(segment) <= max_chars:
        return [unit]

    if block_kind == "prose":
        local_words = word_units(segment)
        multi_word = len(local_words) > 1 or (
            local_words and len(segment[local_words[0][0] : local_words[0][1]]) < len(segment)
        )
        if multi_word:
            expanded: list[tuple[int, int]] = []
            for word_start, word_end in local_words:
                word_unit = (unit[0] + word_start, unit[0] + word_end)
                expanded.extend(subdivide_unit(text, word_unit, max_chars, "code"))
            return expanded

    return [(unit[0] + start, unit[0] + end) for start, end in hard_cut_units(segment, max_chars)]


def expand_units(
    text: str,
    units: list[tuple[int, int]],
    max_chars: int,
    block_kind: BlockKind,
) -> list[tuple[int, int]]:
    expanded: list[tuple[int, int]] = []
    for unit in units:
        segment = text[unit[0] : unit[1]]
        if len(segment) <= max_chars:
            expanded.append(unit)
            continue
        expanded.extend(subdivide_unit(text, unit, max_chars, block_kind))
    return expanded


def greedy_pack_spans(
    text: str,
    units: list[tuple[int, int]],
    max_chars: int,
    block_kind: BlockKind,
) -> list[tuple[int, int]]:
    if not text:
        return []
    if not units:
        units = [(0, len(text))]

    resolved_units = expand_units(text, units, max_chars, block_kind)
    chunks: list[tuple[int, int]] = []
    chunk_start: int | None = None
    chunk_end: int | None = None

    for unit_start, unit_end in resolved_units:
        unit_len = unit_end - unit_start
        if unit_len > max_chars:
            for hard_start, hard_end in hard_cut_units(text[unit_start:unit_end], max_chars):
                absolute = (unit_start + hard_start, unit_start + hard_end)
                if chunk_start is None:
                    chunk_start, chunk_end = absolute
                    continue
                if chunk_end == absolute[0] and (absolute[1] - chunk_start) <= max_chars:
                    chunk_end = absolute[1]
                else:
                    chunks.append((chunk_start, chunk_end))
                    chunk_start, chunk_end = absolute
            continue

        if chunk_start is None:
            chunk_start, chunk_end = unit_start, unit_end
            continue

        if unit_start == chunk_end and (unit_end - chunk_start) <= max_chars:
            chunk_end = unit_end
            continue

        chunks.append((chunk_start, chunk_end))
        chunk_start, chunk_end = unit_start, unit_end

    if chunk_start is not None and chunk_end is not None:
        chunks.append((chunk_start, chunk_end))

    return chunks


def greedy_take(
    text: str,
    max_chars: int,
    *,
    block_kind: BlockKind,
    from_end: bool,
) -> str:
    if not text or max_chars <= 0:
        return ""

    units = units_for_text(text, block_kind)
    resolved = expand_units(text, units, max_chars, block_kind)
    if not resolved:
        return text[-max_chars:] if from_end else text[:max_chars]

    selected: list[tuple[int, int]] = []
    total = 0
    ordered = list(reversed(resolved)) if from_end else resolved

    for unit_start, unit_end in ordered:
        unit_len = unit_end - unit_start
        if unit_len > max_chars:
            segment = text[unit_start:unit_end]
            return segment[-max_chars:] if from_end else segment[:max_chars]

        if total + unit_len > max_chars:
            break
        if from_end:
            selected.insert(0, (unit_start, unit_end))
        else:
            selected.append((unit_start, unit_end))
        total += unit_len

    if not selected:
        return text[-max_chars:] if from_end else text[:max_chars]

    if from_end:
        return text[selected[0][0] :]
    return text[: selected[-1][1]]


def apply_prefix_suffix(chunks: list[Chunk], block_kind: BlockKind) -> list[Chunk]:
    if len(chunks) <= 1:
        return chunks

    updated: list[Chunk] = []
    for index, chunk in enumerate(chunks):
        prefix = None
        suffix = None
        if index > 0:
            prefix = greedy_take(
                chunks[index - 1].content,
                PREFIX_SUFFIX_CHARS,
                block_kind=block_kind,
                from_end=True,
            ) or None
        if index + 1 < len(chunks):
            suffix = greedy_take(
                chunks[index + 1].content,
                PREFIX_SUFFIX_CHARS,
                block_kind=block_kind,
                from_end=False,
            ) or None
        updated.append(
            Chunk(
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                breadcrumb=chunk.breadcrumb,
                prefix=prefix,
                suffix=suffix,
            )
        )
    return updated


def spans_to_chunks(
    text: str,
    spans: list[tuple[int, int]],
    breadcrumb: str,
    start_index: int,
    block_kind: BlockKind,
) -> list[Chunk]:
    raw_chunks = [
        Chunk(
            chunk_index=start_index + offset,
            content=text[start:end],
            breadcrumb=breadcrumb,
        )
        for offset, (start, end) in enumerate(spans)
    ]
    return apply_prefix_suffix(raw_chunks, block_kind)
