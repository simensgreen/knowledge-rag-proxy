"""Search result snippet truncation (from knowledge-rag MCP)."""

from __future__ import annotations


def make_snippet(content: str, max_chars: int = 500) -> str:
    """Truncate content at a natural break point."""
    if len(content) <= max_chars:
        return content
    truncated = content[:max_chars]
    min_pos = int(max_chars * 0.6)
    last_newline = truncated.rfind("\n", min_pos)
    if last_newline > min_pos:
        return truncated[:last_newline].rstrip() + "\n..."
    for separator in (". ", "? ", "! ", "; "):
        last_separator = truncated.rfind(separator, min_pos)
        if last_separator > min_pos:
            return truncated[: last_separator + len(separator) - 1] + " ..."
    last_space = truncated.rfind(" ", min_pos)
    if last_space > min_pos:
        return truncated[:last_space] + " ..."
    return truncated + "..."
