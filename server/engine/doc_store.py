"""SurrealDB CRUD for doc/chunk records."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from server.engine.ingest.models import PreparedDocument
from server.engine.store import SurrealStore
from server.engine.store_models import StoredChunk, StoredDoc, record_id_to_str, to_record_id

logger = logging.getLogger(__name__)

# HNSW search breadth: keep it >= candidate pool so recall stays high on small pools.
_VECTOR_EF_MIN = 64
# Fetch more candidates than requested so rank fusion has room to reorder.
_CANDIDATE_MULTIPLIER = 4
# Reciprocal-rank-fusion constant; 60 is the value from the original RRF paper.
_RRF_K = 60


def _as_rows(result: Any) -> list[dict[str, Any]]:
    if result is None:
        return []
    if isinstance(result, list):
        if not result:
            return []
        if isinstance(result[0], dict):
            return result
        flattened: list[dict[str, Any]] = []
        for item in result:
            if isinstance(item, list):
                flattened.extend(row for row in item if isinstance(row, dict))
            elif isinstance(item, dict):
                flattened.append(item)
        return flattened
    if isinstance(result, dict):
        return [result]
    return []


def _first_row(result: Any) -> dict[str, Any] | None:
    rows = _as_rows(result)
    return rows[0] if rows else None


def _fuse_rankings(
    vector_hits: list[dict[str, Any]],
    fulltext_hits: list[dict[str, Any]],
    limit: int,
) -> list[dict[str, Any]]:
    fused_scores: dict[str, float] = {}
    rows_by_chunk: dict[str, dict[str, Any]] = {}
    for ranking in (vector_hits, fulltext_hits):
        for rank, row in enumerate(ranking):
            chunk_id = record_id_to_str(row.get("id"))
            rows_by_chunk.setdefault(chunk_id, row)
            fused_scores[chunk_id] = fused_scores.get(chunk_id, 0.0) + 1.0 / (_RRF_K + rank + 1)

    ranked_chunks = sorted(fused_scores.items(), key=lambda item: item[1], reverse=True)
    results: list[dict[str, Any]] = []
    for chunk_id, score in ranked_chunks[:limit]:
        row = rows_by_chunk[chunk_id]
        path = str(row.get("path") or "")
        results.append(
            {
                "path": path,
                "content": str(row.get("content") or ""),
                "breadcrumb": row.get("breadcrumb"),
                "chunk_index": row.get("chunk_index"),
                "score": round(score, 6),
            }
        )
    return results


class DocStore:
    def __init__(self, store: SurrealStore) -> None:
        self.store = store

    def get_doc_by_path(self, path: str) -> StoredDoc | None:
        rows = _as_rows(
            self.store.query("SELECT * FROM doc WHERE path = $path LIMIT 1", {"path": path})
        )
        if not rows:
            return None
        return StoredDoc.model_validate(rows[0])

    def list_all_docs(self) -> list[StoredDoc]:
        rows = _as_rows(self.store.query("SELECT * FROM doc"))
        return [StoredDoc.model_validate(row) for row in rows]

    def list_documents(
        self,
        path_regex: str | None,
        limit: int,
        offset: int,
    ) -> tuple[list[StoredDoc], int]:
        if path_regex:
            rows = _as_rows(
                self.store.query(
                    "SELECT * FROM doc WHERE string::matches(path, $pattern) ORDER BY path ASC",
                    {"pattern": path_regex},
                )
            )
        else:
            rows = _as_rows(self.store.query("SELECT * FROM doc ORDER BY path ASC"))
        documents = [StoredDoc.model_validate(row) for row in rows]
        total = len(documents)
        return documents[offset : offset + limit], total

    def matching_doc_paths(self, path_regex: str) -> list[str]:
        """Indexed doc paths whose path matches the given regex (SurrealDB `string::matches`)."""
        rows = _as_rows(
            self.store.query(
                "SELECT path FROM doc WHERE string::matches(path, $pattern) ORDER BY path ASC",
                {"pattern": path_regex},
            )
        )
        return [str(row["path"]) for row in rows if row.get("path")]

    def search(
        self,
        query_text: str,
        query_embedding: list[float],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Hybrid search: HNSW vector KNN fused with BM25 fulltext via reciprocal rank fusion."""
        logger.debug("Hybrid search limit=%d query=%r", limit, query_text)
        candidate_pool = max(limit * _CANDIDATE_MULTIPLIER, 20)
        vector_hits = self._vector_search(query_embedding, candidate_pool)
        fulltext_hits = self._fulltext_search(query_text, candidate_pool)
        results = _fuse_rankings(vector_hits, fulltext_hits, limit)
        logger.info(
            "Hybrid search matched %d chunks (vector=%d, fulltext=%d)",
            len(results),
            len(vector_hits),
            len(fulltext_hits),
        )
        return results

    def _vector_search(self, query_embedding: list[float], pool: int) -> list[dict[str, Any]]:
        if not query_embedding:
            return []
        ef_search = max(_VECTOR_EF_MIN, pool)
        sql = (
            "SELECT id, content, breadcrumb, doc.path AS path, `index` AS chunk_index, "
            f"vector::distance::knn() AS distance FROM chunk WHERE embedding <|{pool},{ef_search}|> "
            "$vector ORDER BY distance ASC"
        )
        try:
            return _as_rows(self.store.query(sql, {"vector": query_embedding}))
        except Exception as error:  # noqa: BLE001 - degrade to fulltext-only on backend quirks
            logger.warning("Vector search failed, falling back to fulltext only: %s", error)
            return []

    def _fulltext_search(self, query_text: str, pool: int) -> list[dict[str, Any]]:
        if not query_text:
            return []
        sql = (
            "SELECT id, content, breadcrumb, doc.path AS path, `index` AS chunk_index, "
            "search::score(0) AS score FROM chunk WHERE search_text @0@ $query "
            "ORDER BY score DESC LIMIT $pool"
        )
        try:
            return _as_rows(self.store.query(sql, {"query": query_text, "pool": pool}))
        except Exception as error:  # noqa: BLE001 - degrade to vector-only on backend quirks
            logger.warning("Fulltext search failed, falling back to vector only: %s", error)
            return []

    def count_stats(self) -> dict[str, int]:
        documents_row = _first_row(self.store.query("SELECT count() AS count FROM doc GROUP ALL"))
        chunks_row = _first_row(self.store.query("SELECT count() AS count FROM chunk GROUP ALL"))
        return {
            "documents": int((documents_row or {}).get("count") or 0),
            "chunks": int((chunks_row or {}).get("count") or 0),
        }

    def failed_doc_paths(self) -> list[str]:
        """Paths of docs the worker could not index (chunk_count is NONE)."""
        rows = _as_rows(self.store.query("SELECT path FROM doc WHERE chunk_count = NONE"))
        return [str(row["path"]) for row in rows if row.get("path")]

    def embedding_dimensions_in_use(self) -> list[int]:
        """Distinct embedding vector lengths currently stored in the chunk table."""
        rows = _as_rows(
            self.store.query("SELECT array::len(embedding) AS dim FROM chunk GROUP BY dim")
        )
        dimensions = {int(row["dim"]) for row in rows if isinstance(row.get("dim"), int)}
        return sorted(dimensions)

    def update_description(self, path: str, description: str | None) -> StoredDoc | None:
        now = datetime.now(timezone.utc)
        rows = _as_rows(
            self.store.query(
                "UPDATE doc SET description = $description, modified_at = $modified_at "
                "WHERE path = $path RETURN AFTER",
                {"path": path, "description": description, "modified_at": now},
            )
        )
        if not rows:
            return None
        return StoredDoc.model_validate(rows[0])

    def get_markdown_content(self, path: str) -> str | None:
        document = self.get_doc_by_path(path)
        if document is None:
            return None
        rows = _as_rows(
            self.store.query(
                "SELECT `index`, content FROM chunk WHERE doc = $doc_id ORDER BY `index` ASC",
                {"doc_id": to_record_id(document.id)},
            )
        )
        return "".join(str(row.get("content") or "") for row in rows)

    def upsert_prepared(self, prepared: PreparedDocument, *, preserve_description: bool = True) -> StoredDoc:
        existing = self.get_doc_by_path(prepared.doc.path)
        description = prepared.doc.description
        if preserve_description and existing is not None and prepared.doc.description is None:
            description = existing.description

        if existing is None:
            document = self._create_doc(prepared, description=description)
            self._insert_chunks(document.id, prepared.chunks)
            return document

        now = datetime.now(timezone.utc)
        rows = _as_rows(
            self.store.query(
                "UPDATE $doc_id SET "
                "modified_at = $modified_at, "
                "size_bytes = $size_bytes, "
                "crc32 = $crc32, "
                "sha256 = $sha256, "
                "embedding_model = $embedding_model, "
                "chunk_count = $chunk_count, "
                "description = $description "
                "RETURN AFTER",
                {
                    "doc_id": to_record_id(existing.id),
                    "modified_at": now,
                    "size_bytes": prepared.doc.size_bytes,
                    "crc32": prepared.doc.crc32,
                    "sha256": prepared.doc.sha256,
                    "embedding_model": prepared.doc.embedding_model,
                    "chunk_count": prepared.doc.chunk_count,
                    "description": description,
                },
            )
        )
        document = StoredDoc.model_validate(rows[0] if rows else existing.model_dump())
        self._replace_chunks_for_doc(document.id, prepared.chunks)
        return document

    def replace_chunks(self, doc_id: str, chunks: list[StoredChunk]) -> StoredDoc | None:
        now = datetime.now(timezone.utc)
        rows = _as_rows(
            self.store.query(
                "UPDATE $doc_id SET chunk_count = $chunk_count, modified_at = $modified_at RETURN AFTER",
                {"doc_id": to_record_id(doc_id), "chunk_count": len(chunks), "modified_at": now},
            )
        )
        if not rows:
            return None
        self._replace_chunks_for_doc(doc_id, chunks)
        return StoredDoc.model_validate(rows[0])

    def rename_path(self, source_path: str, dest_path: str) -> StoredDoc | None:
        now = datetime.now(timezone.utc)
        rows = _as_rows(
            self.store.query(
                "UPDATE doc SET path = $dest_path, modified_at = $modified_at "
                "WHERE path = $source_path RETURN AFTER",
                {
                    "source_path": source_path,
                    "dest_path": dest_path,
                    "modified_at": now,
                },
            )
        )
        if not rows:
            return None
        return StoredDoc.model_validate(rows[0])

    def remove_by_path(self, path: str) -> bool:
        document = self.get_doc_by_path(path)
        if document is None:
            return False
        self.store.query("DELETE $doc_id", {"doc_id": to_record_id(document.id)})
        return True

    def mark_failed(
        self,
        path: str,
        *,
        size_bytes: int,
        crc32: bytes,
        sha256: bytes,
        embedding_model: str,
    ) -> StoredDoc:
        existing = self.get_doc_by_path(path)
        now = datetime.now(timezone.utc)
        if existing is None:
            rows = _as_rows(
                self.store.query(
                    "CREATE doc SET "
                    "id = rand::uuid(), "
                    "path = $path, "
                    "created_at = $now, "
                    "modified_at = $now, "
                    "access_count = 0, "
                    "size_bytes = $size_bytes, "
                    "crc32 = $crc32, "
                    "sha256 = $sha256, "
                    "embedding_model = $embedding_model, "
                    "chunk_count = NONE "
                    "RETURN AFTER",
                    {
                        "path": path,
                        "now": now,
                        "size_bytes": size_bytes,
                        "crc32": crc32,
                        "sha256": sha256,
                        "embedding_model": embedding_model,
                    },
                )
            )
            return StoredDoc.model_validate(rows[0])

        rows = _as_rows(
            self.store.query(
                "UPDATE $doc_id SET "
                "modified_at = $now, "
                "size_bytes = $size_bytes, "
                "crc32 = $crc32, "
                "sha256 = $sha256, "
                "embedding_model = $embedding_model, "
                "chunk_count = NONE "
                "RETURN AFTER",
                {
                    "doc_id": to_record_id(existing.id),
                    "now": now,
                    "size_bytes": size_bytes,
                    "crc32": crc32,
                    "sha256": sha256,
                    "embedding_model": embedding_model,
                },
            )
        )
        return StoredDoc.model_validate(rows[0] if rows else existing.model_dump())

    def _create_doc(self, prepared: PreparedDocument, *, description: str | None) -> StoredDoc:
        rows = _as_rows(
            self.store.query(
                "CREATE $doc_id SET "
                "path = $path, "
                "created_at = $created_at, "
                "modified_at = $modified_at, "
                "access_count = 0, "
                "size_bytes = $size_bytes, "
                "crc32 = $crc32, "
                "sha256 = $sha256, "
                "embedding_model = $embedding_model, "
                "chunk_count = $chunk_count, "
                "description = $description "
                "RETURN AFTER",
                {
                    "doc_id": to_record_id(prepared.doc.id),
                    "path": prepared.doc.path,
                    "created_at": prepared.doc.created_at,
                    "modified_at": prepared.doc.modified_at,
                    "size_bytes": prepared.doc.size_bytes,
                    "crc32": prepared.doc.crc32,
                    "sha256": prepared.doc.sha256,
                    "embedding_model": prepared.doc.embedding_model,
                    "chunk_count": prepared.doc.chunk_count,
                    "description": description,
                },
            )
        )
        if rows:
            return StoredDoc.model_validate(rows[0])
        return prepared.doc.model_copy(update={"description": description})

    def _replace_chunks_for_doc(self, doc_id: str, chunks: list[StoredChunk]) -> None:
        doc_record_id = to_record_id(doc_id)
        self.store.query(
            "DELETE chunk WHERE doc = $doc_id",
            {"doc_id": doc_record_id},
        )
        self._insert_chunks(doc_id, chunks)

    def _insert_chunks(self, doc_id: str, chunks: list[StoredChunk]) -> None:
        doc_record_id = to_record_id(doc_id)
        for chunk in chunks:
            self.store.query(
                "CREATE $chunk_id SET "
                "doc = $doc_id, "
                "`index` = $index, "
                "breadcrumb = $breadcrumb, "
                "prefix = $prefix, "
                "suffix = $suffix, "
                "content = $content, "
                "search_text = $search_text, "
                "embedding = $embedding",
                {
                    "chunk_id": to_record_id(chunk.id),
                    "doc_id": doc_record_id,
                    "index": chunk.chunk_index,
                    "breadcrumb": chunk.breadcrumb,
                    "prefix": chunk.prefix,
                    "suffix": chunk.suffix,
                    "content": chunk.content,
                    "search_text": chunk.search_text,
                    "embedding": chunk.embedding,
                },
            )
            logger.debug(
                "Inserted chunk %s for doc %s index=%d",
                record_id_to_str(chunk.id),
                record_id_to_str(doc_id),
                chunk.chunk_index,
            )
