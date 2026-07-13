"""Runtime patches for the embedded knowledge-rag library.

knowledge-rag's BM25 keyword index tokenizes with an ASCII-only regex
(``[a-z0-9][-a-z0-9]*[a-z0-9]``), so Cyrillic (and any non-Latin) text is
dropped from the keyword index and from path-metadata scoring. Keyword search
for Russian terms therefore returns nothing even though the text is stored and
parsed correctly. We swap in a Unicode-aware tokenizer at startup.

The library ships as a normal (non-editable) PyPI package, so editing its files
would be lost on reinstall; the patch lives here instead. The BM25 index is
rebuilt in memory from stored chunks on every server start
(``KnowledgeOrchestrator._ensure_bm25_index``), so a restart re-tokenizes
existing documents with the new tokenizer -- no ChromaDB reindex needed.

Remove this module if knowledge-rag ships a Unicode-aware tokenizer upstream.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

# Runs of Unicode word characters (letters/digits of any script, so Cyrillic is
# included), joined by internal hyphens, excluding the underscore. Mirrors the
# original tokenizer's intent (lowercase alphanumeric, keep hyphenated terms)
# without restricting to ASCII.
_TOKEN_RE = re.compile(r"[^\W_]+(?:-[^\W_]+)*")


def _unicode_tokenize(_self: Any, text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _unicode_metadata_path_score(query: str, metadata: Dict[str, Any]) -> float:
    """Unicode-aware reimplementation of knowledge-rag's ``_metadata_path_score``.

    Scoring weights are copied verbatim from the library so behaviour is
    identical for Latin queries and merely extended to non-Latin scripts.
    """
    query_terms = _TOKEN_RE.findall(query.lower())
    if not query_terms:
        return 0.0

    source = str(metadata.get("source", ""))
    filename = str(metadata.get("filename", ""))
    path_text = f"{source} {filename}".lower()
    path_tokens = set(_TOKEN_RE.findall(path_text))
    if not path_tokens:
        return 0.0

    score = 0.0
    for term in query_terms:
        if term in path_tokens:
            score += 0.0006
        elif term in path_text:
            score += 0.0003

    query_phrase = query.strip().lower()
    if query_phrase and query_phrase in path_text:
        score += 0.0012

    return min(score, 0.003)


def apply_unicode_tokenizer_patch() -> None:
    """Swap knowledge-rag's ASCII-only BM25 tokenizer for a Unicode-aware one.

    Must run before the BM25 index is built (i.e. before the orchestrator indexes
    or serves a search). Reassigning the class method and the module-level
    function is enough: both are resolved at call time.
    """
    from mcp_server import server as knowledge_rag_server

    knowledge_rag_server.BM25Index._tokenize = _unicode_tokenize
    knowledge_rag_server._metadata_path_score = _unicode_metadata_path_score
