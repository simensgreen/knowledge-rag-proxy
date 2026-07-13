# grimoire

Monorepo: self-hosted REST document knowledge base + Vellum marketplace plugin.

**Human overview:** [README.md](README.md). **Plugin install:** [plugin/README.md](plugin/README.md).

## Scope

- Governs: entire repo root
- `server/` — Python FastAPI (Phase 1: stub engine/parser; Phase 2: SurrealDB + markitdown + HTTP providers)
- `plugin/` — Vellum installable unit (`@simensgreen/grimuire_vellum`)

## What this is

- Thin REST API over a documents folder (`GRIM_DOCUMENTS_DIR`)
- Vellum plugin calls server over `http://` or `https://`
- Phase 1 scaffold: protocols + `StubEngine` / `StubParser` (no real indexing/search yet)
- Phase 2: SurrealDB hybrid search, markitdown parsing, embedding/OCR HTTP providers, watcher

## Layout

| Path | Role |
|------|------|
| `server/app.py` | FastAPI app, lifespan, exception handlers |
| `server/routes/api.py` | 10 API routes |
| `server/services/` | Route business logic |
| `server/engine/` | `protocols.py`, `stub_engine.py`, `stub_parser.py`, `models.py` |
| `server/env_config.py` | `.env` → `GRIM_*` config |
| `server/paths.py` | Path boundary (`path` root-relative) |
| `server/auth.py` | Bearer (`GRIM_BEARER`) |
| `plugin/tools/grim_*.ts` | Tools 1:1 with API |
| `plugin/src/client.ts` | HTTP client |
| `tests/` | pytest |

## API (10 routes)

Bearer on all. Success: `{status:"success",...}`. Errors: `{status:"error",message,hint?}`.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/health` | `{ok, version}` |
| GET | `/search` | `?query=`, `max_results?` |
| GET | `/file` | `?path=` |
| GET | `/list_files` | `?path=` regex, `limit?`, `offset?` |
| POST | `/upload` | multipart `file`, `filedir?` |
| GET | `/download` | `?path=` |
| POST | `/remove` | `{path}` — file + index |
| POST | `/move` | `{source_path, dest_path}` |
| GET | `/status` | `{documents, chunks, indexing}` |
| POST | `/markitdown` | multipart `file` — preview only |

All path fields are root-relative to `GRIM_DOCUMENTS_DIR`. No `category` concept.

## Plugin tools (1:1)

`grim_search`, `grim_file`, `grim_list_files`, `grim_upload`, `grim_download`, `grim_remove`, `grim_move`, `grim_status`, `grim_markitdown`

`/health` — init hook only.

## Secrets

| Layer | Storage | Usage |
|-------|---------|-------|
| Plugin | `apiToken` in installed `plugin/config.json` | `Authorization: Bearer` on every request |
| Server | `GRIM_BEARER` in `.env` | Same value as plugin `apiToken` |

## Server config (`.env`)

### Required

| Variable | Purpose |
|----------|---------|
| `GRIM_BEARER` | Bearer token |
| `GRIM_DOCUMENTS_DIR` | Documents root (must exist) |

### Optional paths

| Variable | Default |
|----------|---------|
| `GRIM_TMP_DIR` | system temp |
| `GRIM_SURREAL_URL` | `surrealkv://{app_data}/surreal` via platformdirs |

No `GRIM_DATA_DIR`.

### Provider triplets (Phase 2)

Each: `GRIM_{SERVICE}_PROVIDER`, `_BASE_URL`, `_TOKEN`, optional `_MODEL` for `EMBEDDING` and `OCR`.

### Other

`GRIM_CHUNK_SIZE`, `GRIM_CHUNK_OVERLAP`, `GRIM_SEARCH_*`, `GRIM_WATCH_*`, `GRIM_DOCS`, `GRIM_LOG_LEVEL`

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

- **Always:** `GRIM_BEARER` + `GRIM_DOCUMENTS_DIR`; paths via `.env`; `GRIM_` prefix for proxy-owned vars
- **Never:** commit secrets; leak absolute paths in API responses
- **Phase 1:** no real SurrealDB/markitdown/provider HTTP in production path — stubs only

## Gotchas

- Phase 1 `StubEngine` returns canned search/list/file data; uploads/downloads use real filesystem
- Watcher is stubbed in Phase 1 (`GRIM_WATCH_DISABLED` still honored)
- Plugin package name: `@simensgreen/grimuire_vellum`
- Breaking change from knowledge-rag-proxy: `KRP_*` → `GRIM_*`, API paths renamed, tools `krp_*` → `grim_*`
