# grimoire

Monorepo: self-hosted REST document knowledge base + Vellum marketplace plugin.

**Human overview:** [README.md](README.md). **Plugin install:** [plugin/README.md](plugin/README.md).

## Scope

- Governs: entire repo root
- `server/` — Python FastAPI: SurrealDB index, markitdown, embedding HTTP, coalescing index queue + watcher
- `plugin/` — Vellum installable unit (`@simensgreen/grimuire_vellum`)

## What this is

- Thin REST API under `/api/...` over a documents folder (`GRIM_DOCUMENTS_DIR`)
- API writes files / submits queue tasks; worker indexes asynchronously
- Watcher + startup reconciliation also submit tasks to the same queue

## Layout

| Path | Role |
|------|------|
| `server/app.py` | FastAPI app, lifespan (store, queue, worker, watcher, reconcile) |
| `server/startup.py` | Fail-fast probes: documents dir, embedding provider, stored embedding dims |
| `server/routes/api.py` | API routes (`/api` prefix) |
| `server/services/` | Route logic + `index_queue.py`, `indexing.py`, `reconcile.py` |
| `server/engine/` | `protocols.py`, `markitdown_parser.py`, `ingest/`, `embedding.py`, `doc_store.py` (CRUD + hybrid search), `store.py`, `store_schema.py`, `store_models.py` |
| `server/watcher.py` | watchdog → `IndexQueue.submit` |
| `server/env_config.py` | `.env` → `GRIM_*` config |
| `server/paths.py` | Path boundary: `to_relative_path` sanitizes inbound paths once; DB/queue store root-relative |
| `server/auth.py` | Bearer (`GRIM_BEARER`) |
| `plugin/tools/grim_*.ts` | Tools 1:1 with API |
| `plugin/src/client.ts` | HTTP client |
| `tests/` | pytest |

## API (`/api/...`)

Bearer on all when `GRIM_BEARER` is set; if unset, auth is disabled. Success: `{status:"success",...}`. Errors: `{status:"error",message,hint?}`. Paths without `/api` prefix are 404.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/api/health` | `{ok}` — liveness only |
| GET | `/api/search` | `?query=`, `max_results?` |
| GET | `/api/file_info` | `?path=` — full StoredDoc metadata (+ `description`) |
| POST | `/api/file_info` | `?path=&description=` — update description only |
| GET | `/api/file_content` | `?path=` — join `chunk.content` |
| POST | `/api/file_content` | `?path=` + body `{markdown}` — queue `reindex_markdown` |
| POST | `/api/reindex` | `?path=` regex — queue forced `reindex` for every indexed doc matching (`string::matches`) |
| GET | `/api/list_files` | `?path=` regex, `limit?`, `offset?` — slim view |
| POST | `/api/upload` | multipart `file`, `filedir?`, `markdown?`, `description?` — FS (+ optional queue) |
| GET | `/api/download` | `?path=` |
| POST | `/api/remove` | `?path=` — FS only; watcher queues delete |
| POST | `/api/move` | `?source_path=&dest_path=` — FS + queue `move` |
| GET | `/api/status` | `{documents, chunks, failed, unsupported, indexing}` |
| POST | `/api/markitdown` | multipart `file` — preview only |

**Query vs body:** POST params go in the query string; only bulk content stays in the body (multipart `file`/`markdown` on upload/markitdown, JSON `{markdown}` on file_content).

**`indexing`:** `null` when idle, else `{debounced[], processing[], pending[]}`.

**`list_files` item:** `path, created_at, modified_at, size_bytes, chunk_count` (no `id`/access stats/checksums/`embedding_model`/`description`; use GET `/api/file_info` for those).

**Path regex:** `list_files` and `reindex` filter `doc.path` in SurrealDB via `string::matches(path, $pattern)` (partial match); both operate on indexed docs, not the disk tree.

**`status` failed vs unsupported:** both are docs with `chunk_count=None`; split by `Parser.is_supported(suffix)` at request time (`failed` = supported-but-failed/retryable, `unsupported` = unparseable format).

All path fields are root-relative to `GRIM_DOCUMENTS_DIR`. Inbound API paths are canonicalized to root-relative once at the boundary (`paths.to_relative_path`); `doc.path`, queue tasks, and responses all carry that form, so nothing downstream re-sanitizes.

## Startup fail-fast (`server/startup.py`, called in lifespan before worker)

- `probe_documents_dir` — `GRIM_DOCUMENTS_DIR` exists and is readable
- `probe_embedding_provider` — embeds a test phrase; fails if unreachable or returned size != `GRIM_EMBEDDING_DIMENSIONS`
- `verify_stored_embedding_dimensions` — fails if any stored `chunk.embedding` length != `GRIM_EMBEDDING_DIMENSIONS` (model/dim changed → recreate the surreal data dir)

## Indexing model

- Producers: upload(+markdown/description), file_content POST, reindex POST, move POST, watcher, startup reconcile
- `IndexQueue.submit(task)` always debounces (`GRIM_WATCH_DEBOUNCE`, default 10s) and coalesces by `path`
- Single worker runs `indexing.process_task`; `index` skips when sha256 unchanged; `reindex` always rebuilds
- On task failure: `mark_failed` sets `chunk_count=None` + current checksums; logs error
- Unsupported formats are recorded (not skipped): worker `mark_failed`s them with `chunk_count=None` (no parse attempt, warning log)
- Startup reconcile: new files → `index`; `chunk_count=None` + supported → forced `reindex` (retry); `chunk_count=None` + unsupported → left as-is (no retry)

## Plugin tools (1:1)

`grim_search`, `grim_file`, `grim_list_files`, `grim_upload`, `grim_download`, `grim_remove`, `grim_move`, `grim_status`, `grim_markitdown`

`/api/health` — init hook only. Plugin URLs still need `/api` prefix update (follow-up).

## Secrets

| Layer | Storage | Usage |
|-------|---------|-------|
| Plugin | `apiToken` in installed `plugin/config.json` | `Authorization: Bearer` on every request |
| Server | `GRIM_BEARER` in `.env` | Same value as plugin `apiToken` |

## Server config (`.env`)

### Required

| Variable | Purpose |
|----------|---------|
| `GRIM_DOCUMENTS_DIR` | Documents root (must exist) |
| `GRIM_EMBEDDING_DIMENSIONS` | Embedding vector size (e.g. `1536`) |
| `GRIM_EMBEDDING_BASE_URL` | OpenAI-compatible embeddings API base URL |
| `GRIM_EMBEDDING_TOKEN` | Embeddings API token |

### Optional paths

| Variable | Default |
|----------|---------|
| `GRIM_BEARER` | Bearer token; if unset, auth is disabled |
| `GRIM_TMP_DIR` | system temp |
| `GRIM_SURREAL_URL` | `surrealkv://{app_data}/surreal` via platformdirs |
| `GRIM_SURREAL_NAMESPACE` | `grimoire` |
| `GRIM_SURREAL_DATABASE` | `main` |
| `GRIM_FULLTEXT_LANGUAGES` | comma-separated snowball languages; default `english` |
| `GRIM_WATCH_DEBOUNCE` | debounce seconds for index queue; default `10` |

No `GRIM_DATA_DIR`. No `GRIM_WATCH_DISABLED`.

### Provider config

Each: `GRIM_{SERVICE}_BASE_URL`, `_TOKEN`, optional `_MODEL`. `EMBEDDING` required. `OCR` wires markitdown-ocr (default model `google/gemini-2.5-flash`).

### Other

`GRIM_DOCS`, `GRIM_LOG_LEVEL`

### SurrealDB schema (`doc`, `chunk`)

Applied on startup (`server/engine/store_schema.py`).

**`doc`:** `id` (uuid, readonly), `path` (unique), `created_at`, `modified_at`, `accessed_at?`, `access_count` (default 0), `size_bytes`, `crc32`, `sha256`, `embedding_model`, `chunk_count?` (`None` on index failure), `description?`.

**`chunk`:** `id` (uuid, readonly), `doc` (`record<doc>`), `` `index` `` (int), `breadcrumb`, `prefix?`, `suffix?`, `content`, `search_text`, `embedding` (`array<float>`).

**Indexes:** `doc.path` UNIQUE; `(chunk.doc, chunk.index)` UNIQUE; per-language FULLTEXT on `chunk.search_text`; HNSW on `chunk.embedding`. **Event:** `doc_delete_chunks` deletes chunks on `doc` DELETE.

### Ingest (`server/engine/ingest/`)

| File | Role |
|------|------|
| `prepare.py` | `prepare_markdown` (markdown + `doc_id` → embedded `StoredChunk`s), `prepare_file` (path + optional markdown → `PreparedDocument`; skips markitdown when markdown supplied or file is `.md`/`.markdown`) |
| `chunker.py` | `chunk_markdown` — markdown-aware split with reconstruct invariant; block boundaries from `markdown-it-py` `token.map` |
| `chunk_text.py` | `build_breadcrumb`, `build_search_text`, `greedy_take`, `reconstruct_document` |
| `models.py` | `Chunk`, `PreparedDocument` |

`search_text = breadcrumb + "\n" + (\n + prefix)? + content + (\n + suffix)?`. `prepare_markdown` calls `embedder.embed()` once with all `search_text` values; `OpenAIEmbeddingProvider.embed` internally splits into `EMBEDDING_BATCH_SIZE` (256) HTTP calls and retries each batch with exponential backoff on transient `APIError` (local backends like LM Studio drop the model connection under load). Import: `from server.engine.ingest import prepare_file, prepare_markdown, PreparedDocument`.

## Commands

```bash
uv venv .venv
uv pip install -e ".[dev]"
cp .env.example .env

export GRIM_BEARER="your-token"
export GRIM_DOCUMENTS_DIR="/path/to/documents"
uv run uvicorn server.app:app --reload --port 8000

uv run pytest tests/

cd plugin && npm install && npx tsc --noEmit
```

## Boundaries

- **Always:** `GRIM_DOCUMENTS_DIR`; paths via `.env`; `GRIM_` prefix for proxy-owned vars
- **Ask first:** exposing the server without `GRIM_BEARER` (auth off) beyond trusted/local networks
- **Never:** commit secrets; leak absolute paths in API responses

## Gotchas

- Upload/remove/move are fire-and-forget for indexing: poll `GET /api/status` until path leaves `indexing.*`
- `POST /api/file_info` / GET content/info may 404 until the worker finishes indexing
- `GET /api/search` is hybrid: HNSW vector KNN + BM25 fulltext fused by reciprocal rank fusion (`DocStore.search`); each half degrades to the other if a backend index errors
- Plugin package name: `@simensgreen/grimuire_vellum`
- Breaking change from knowledge-rag-proxy: `KRP_*` → `GRIM_*`, API under `/api/`, tools `krp_*` → `grim_*`
