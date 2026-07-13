"""SurrealDB schema DDL for doc/chunk tables, analyzers, and indexes."""

from __future__ import annotations

import re

# Snowball languages supported by SurrealDB analyzers:
# https://surrealdb.com/docs/reference/query-language/statements/define/analyzer#snowballlanguage
SNOWBALL_LANGUAGES = frozenset(
    {
        "arabic",
        "danish",
        "dutch",
        "english",
        "french",
        "german",
        "greek",
        "hungarian",
        "italian",
        "norwegian",
        "portuguese",
        "romanian",
        "russian",
        "spanish",
        "swedish",
        "tamil",
        "turkish",
    }
)

SNOWBALL_LANGUAGES_DOC = (
    "https://surrealdb.com/docs/reference/query-language/statements/define/analyzer#snowballlanguage"
)

DEFAULT_FULLTEXT_LANGUAGES = ["english"]


def normalize_fulltext_language(token: str) -> str:
    normalized = token.strip().lower()
    if not normalized:
        raise ValueError("empty fulltext language token")
    if normalized in SNOWBALL_LANGUAGES:
        return normalized
    supported = ", ".join(sorted(SNOWBALL_LANGUAGES))
    raise ValueError(
        f"unsupported fulltext language: {token}. "
        f"Supported snowball languages: {supported}. "
        f"See {SNOWBALL_LANGUAGES_DOC}"
    )


def parse_fulltext_languages(raw: str | None) -> list[str]:
    if raw is None or not raw.strip():
        return list(DEFAULT_FULLTEXT_LANGUAGES)
    languages = list(
        set(normalize_fulltext_language(token) for token in raw.split(","))
    )
    if not languages:
        raise ValueError("GRIM_FULLTEXT_LANGUAGES is empty after parsing")
    return languages


def analyzer_name(language: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", language.lower()).strip("_")
    return f"{safe}_analyzer"


def fulltext_index_name(language: str) -> str:
    safe = re.sub(r"[^a-z0-9_]+", "_", language.lower()).strip("_")
    return f"chunk_search_{safe}"


def doc_table_statements() -> list[str]:
    return [
        "DEFINE TABLE IF NOT EXISTS doc SCHEMAFULL",
        "DEFINE FIELD IF NOT EXISTS id ON TABLE doc TYPE uuid READONLY",
        "DEFINE FIELD IF NOT EXISTS path ON TABLE doc TYPE string",
        "DEFINE FIELD IF NOT EXISTS created_at ON TABLE doc TYPE datetime",
        "DEFINE FIELD IF NOT EXISTS modified_at ON TABLE doc TYPE datetime",
        "DEFINE FIELD IF NOT EXISTS accessed_at ON TABLE doc TYPE option<datetime>",
        "DEFINE FIELD IF NOT EXISTS access_count ON TABLE doc TYPE int DEFAULT 0",
        "DEFINE FIELD IF NOT EXISTS size_bytes ON TABLE doc TYPE int",
        "DEFINE FIELD IF NOT EXISTS crc32 ON TABLE doc TYPE bytes",
        "DEFINE FIELD IF NOT EXISTS sha256 ON TABLE doc TYPE bytes",
        "DEFINE FIELD IF NOT EXISTS embedding_model ON TABLE doc TYPE string",
        "DEFINE FIELD IF NOT EXISTS chunk_count ON TABLE doc TYPE option<int>",
        "DEFINE FIELD IF NOT EXISTS description ON TABLE doc TYPE option<string>",
        "DEFINE INDEX IF NOT EXISTS doc_path_unique ON TABLE doc FIELDS path UNIQUE",
        (
            "DEFINE EVENT IF NOT EXISTS doc_delete_chunks ON TABLE doc "
            'WHEN $event = "DELETE" THEN { DELETE chunk WHERE doc = $before.id; }'
        ),
    ]


def chunk_table_statements() -> list[str]:
    return [
        "DEFINE TABLE IF NOT EXISTS chunk SCHEMAFULL",
        "DEFINE FIELD IF NOT EXISTS id ON TABLE chunk TYPE uuid READONLY",
        "DEFINE FIELD IF NOT EXISTS doc ON TABLE chunk TYPE record<doc>",
        "DEFINE FIELD IF NOT EXISTS `index` ON TABLE chunk TYPE int",
        "DEFINE FIELD IF NOT EXISTS breadcrumb ON TABLE chunk TYPE string",
        "DEFINE FIELD IF NOT EXISTS prefix ON TABLE chunk TYPE option<string>",
        "DEFINE FIELD IF NOT EXISTS suffix ON TABLE chunk TYPE option<string>",
        "DEFINE FIELD IF NOT EXISTS content ON TABLE chunk TYPE string",
        "DEFINE FIELD IF NOT EXISTS search_text ON TABLE chunk TYPE string",
        "DEFINE FIELD IF NOT EXISTS embedding ON TABLE chunk TYPE array<float>",
        "DEFINE INDEX IF NOT EXISTS chunk_doc_index_unique ON TABLE chunk FIELDS doc, `index` UNIQUE",
    ]


def analyzer_statements(language: str) -> list[str]:
    name = analyzer_name(language)
    return [
        "DEFINE ANALYZER IF NOT EXISTS "
        f"{name} TOKENIZERS blank, class FILTERS lowercase, snowball({language})"
    ]


def fulltext_index_statement(language: str, defer: bool) -> str:
    name = fulltext_index_name(language)
    analyzer = analyzer_name(language)
    defer_clause = " DEFER" if defer else ""
    return (
        "DEFINE INDEX IF NOT EXISTS "
        f"{name} ON TABLE chunk FIELDS search_text FULLTEXT ANALYZER {analyzer} BM25{defer_clause}"
    )


def embedding_index_statement(embedding_dimensions: int, defer: bool) -> str:
    defer_clause = " DEFER" if defer else ""
    return (
        "DEFINE INDEX IF NOT EXISTS chunk_embedding ON TABLE chunk FIELDS embedding "
        f"HNSW DIMENSION {embedding_dimensions} TYPE F32 DIST COSINE{defer_clause}"
    )


def schema_statement_fallbacks(statement: str) -> list[str]:
    candidates: list[str] = [statement]
    if " DEFER" in statement:
        candidates.append(statement.replace(" DEFER", ""))
    for candidate in list(candidates):
        if "FULLTEXT ANALYZER" in candidate:
            candidates.append(candidate.replace("FULLTEXT ANALYZER", "SEARCH ANALYZER"))
    for candidate in list(candidates):
        if " TYPE F32 " in candidate:
            candidates.append(candidate.replace(" TYPE F32", ""))
    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        unique_candidates.append(candidate)
    return unique_candidates


def build_schema_statements(
    fulltext_languages: list[str],
    embedding_dimensions: int,
    defer_indexes: bool = True,
) -> list[str]:
    statements: list[str] = []
    statements.extend(doc_table_statements())
    statements.extend(chunk_table_statements())
    for language in fulltext_languages:
        statements.extend(analyzer_statements(language))
    for language in fulltext_languages:
        statements.append(fulltext_index_statement(language, defer_indexes))
    statements.append(embedding_index_statement(embedding_dimensions, defer_indexes))
    return statements
