"""SurrealDB schema tests."""

from __future__ import annotations

import tempfile

import pytest

from server.engine.store import ensure_store_schema
from server.engine.store_schema import (
    analyzer_name,
    build_schema_statements,
    fulltext_index_name,
    parse_fulltext_languages,
)


def test_parse_fulltext_languages_defaults_to_english() -> None:
    assert parse_fulltext_languages(None) == ["english"]


def test_parse_fulltext_languages_accepts_snowball_language_names() -> None:
    assert set(parse_fulltext_languages("russian,english")) == {"russian", "english"}


def test_parse_fulltext_languages_rejects_unknown_language() -> None:
    with pytest.raises(ValueError, match="unsupported fulltext language"):
        parse_fulltext_languages("klingon")


def test_build_schema_statements_includes_doc_chunk_indexes_and_delete_event() -> None:
    statements = build_schema_statements(["russian", "english"], embedding_dimensions=1536)
    joined = "\n".join(statements)

    assert "DEFINE TABLE IF NOT EXISTS doc SCHEMAFULL" in joined
    assert "DEFINE FIELD IF NOT EXISTS chunk_count ON TABLE doc TYPE option<int>" in joined
    assert "DEFINE FIELD IF NOT EXISTS description ON TABLE doc TYPE option<string>" in joined
    assert "DEFINE FIELD IF NOT EXISTS breadcrumb ON TABLE chunk TYPE string" in joined
    assert "DEFINE FIELD IF NOT EXISTS search_text ON TABLE chunk TYPE string" in joined
    assert "DEFINE FIELD IF NOT EXISTS prefix ON TABLE chunk TYPE option<string>" in joined
    assert "DEFINE FIELD IF NOT EXISTS suffix ON TABLE chunk TYPE option<string>" in joined
    assert "DEFINE INDEX IF NOT EXISTS chunk_doc_index_unique ON TABLE chunk FIELDS doc, `index` UNIQUE" in joined
    assert "DEFINE EVENT IF NOT EXISTS doc_delete_chunks ON TABLE doc" in joined
    assert "DELETE chunk WHERE doc = $before.id" in joined
    assert analyzer_name("russian") in joined
    assert analyzer_name("english") in joined
    assert fulltext_index_name("russian") in joined
    assert fulltext_index_name("english") in joined
    assert "FIELDS search_text FULLTEXT" in joined
    assert "HNSW DIMENSION 1536" in joined


def test_ensure_store_schema_applies_to_embedded_database(monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = tempfile.mkdtemp()
    monkeypatch.setenv("GRIM_SURREAL_URL", f"surrealkv://{temp_root}/schema-test")
    monkeypatch.setenv("GRIM_EMBEDDING_DIMENSIONS", "4")
    monkeypatch.setenv("GRIM_FULLTEXT_LANGUAGES", "russian,english")

    store = ensure_store_schema()
    try:
        doc_rows = store.query("INFO FOR TABLE doc")
        chunk_rows = store.query("INFO FOR TABLE chunk")
        assert doc_rows
        assert chunk_rows
    finally:
        store.close()


def test_doc_delete_event_removes_related_chunks(monkeypatch: pytest.MonkeyPatch) -> None:
    temp_root = tempfile.mkdtemp()
    monkeypatch.setenv("GRIM_SURREAL_URL", f"surrealkv://{temp_root}/cascade-test")
    monkeypatch.setenv("GRIM_EMBEDDING_DIMENSIONS", "4")

    store = ensure_store_schema()
    try:
        document = store.query(
            "CREATE doc SET "
            "id = rand::uuid(), "
            "path = 'notes/a.md', "
            "created_at = time::now(), "
            "modified_at = time::now(), "
            "access_count = 0, "
            "size_bytes = 5, "
            "crc32 = $crc32, "
            "sha256 = $sha256, "
            "embedding_model = 'test'",
            {"crc32": b"\x00\x00\x00\x01", "sha256": b"x" * 32},
        )[0]
        document_id = document["id"]
        store.query(
            "CREATE chunk SET "
            "id = rand::uuid(), "
            "doc = $doc, "
            "`index` = 0, "
            "breadcrumb = 'note.md', "
            "content = 'hello', "
            "search_text = 'note.md\\nhello', "
            "embedding = [0.1, 0.2, 0.3, 0.4]",
            {"doc": document_id},
        )
        assert len(store.query("SELECT * FROM chunk")) == 1

        store.query("DELETE $document_id", {"document_id": document_id})
        assert store.query("SELECT * FROM chunk") == []
        assert store.query("SELECT * FROM doc") == []
    finally:
        store.close()
