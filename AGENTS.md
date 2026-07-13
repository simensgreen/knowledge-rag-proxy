# knowledge-rag-proxy

Monorepo: self-hosted REST proxy over `knowledge-rag` + Vellum marketplace plugin.

**Canonical context:** this file. Human overview: [README.md](README.md). Plugin install: [plugin/README.md](plugin/README.md).

## Scope

- Governs: entire repo root
- `server/` — Python FastAPI, deploy on user host
- `plugin/` — Vellum installable unit (`source.path: "plugin"` in marketplace)

## What this is

- Thin REST proxy embedding `knowledge-rag` (direct import, not MCP/subprocess)
- Vellum plugin calls server over any reachable `http://` or `https://` URL
- Generic document paths via `.env` — no OS/vendor assumptions
- Plugin distributable: `assistant plugins install` / marketplace catalog

## Goals

1. Search knowledge base from Vellum chat
2. Upload chat files → index on self-hosted server
3. Optional auto-index of user-configured directories (watchdog)
4. Marketplace-ready plugin package

## Roadmap

| Phase | Work | Path |
|-------|------|------|
| 0 | Scaffold + envs + AGENTS (done) | repo root |
| 1 | Server endpoints + knowledge-rag orchestrator (done) | `server/` |
| 2 | Plugin HTTP client + tools (done) | `plugin/` |
| 3 | Self-hosted deploy (systemd / launchd, backup) | `scripts/` |
| 4 | Marketplace PR | `vellum-ai/vellum-assistant` |

## Layout

| Path | Role |
|------|------|
| `server/app.py` | FastAPI app, lifespan, routers, exception handlers |
| `server/auth.py` | Bearer token validation (`KRP_BEARER`) |
| `server/env_config.py` | `.env` → knowledge-rag `config`; `bootstrap_library_base()` steers `KNOWLEDGE_RAG_DIR` to temp |
| `server/deps.py` | `get_orchestrator_dep()` for FastAPI Depends |
| `server/errors.py` | `ServiceError` → HTTP envelope |
| `server/responses.py` | `success()` / `error_response()` JSON helpers |
| `server/schemas.py` | Pydantic request models |
| `server/snippet.py` | Search result truncation |
| `server/paths.py` | Path boundary: `to_library_path` (add root prefix), `relativize`/`to_api_path` (strip prefix), `resolve_allowed_path` |
| `server/routes/knowledge.py` | 12 MCP tool routes + `/health` (GET read-only, POST mutating) |
| `server/routes/documents.py` | `/upload`, `/download`, `/move_document` |
| `server/services/knowledge.py` | MCP tool business logic |
| `server/services/documents.py` | Upload/download, path safety, indexing |
| `server/watcher.py` | DocumentWatcher on `documents_dir` |
| `server/startup.py` | Incremental `index_all()` at server startup |
| `server/patches.py` | Runtime patch: Unicode-aware BM25 tokenizer for knowledge-rag (Cyrillic/non-Latin keyword search) |
| `server/backup.py` | Optional remote backup (Phase 3) |
| `plugin/` | Vellum plugin root (marketplace `source.path`) |
| `plugin/hooks/init.ts` | Config validation + health check |
| `plugin/hooks/user-prompt-submit.ts` | Auto-upload supported chat attachments; inject parsed text |
| `plugin/tools/*.ts` | `krp_search_knowledge`, `krp_list_documents`, `krp_get_document`, `krp_upload_workspace`, `krp_upload_content`, `krp_download_document`, `krp_remove_document`, `krp_move_document` |
| `plugin/src/workspace.ts` | Workspace path sandbox + scratch writes |
| `plugin/src/tool_helpers.ts` | Shared tool boilerplate + error hints |
| `plugin/skills/knowledge-rag-proxy/SKILL.md` | On-demand instructions |
| `plugin/src/` | Shared config, client, state |
| `.env.example` | Server env template (no secrets) |
| `plugin/config.json` | Plugin config template (no secrets) |
| `tests/` | pytest for server |
| `scripts/` | deploy + backup stubs |
| `scripts/kb-proxy.service` | systemd unit (Linux) |
| `scripts/kb-proxy.plist` | launchd agent (macOS) |
| `scripts/run-server.sh` | uvicorn wrapper; loads `.env` for launchd |

## Architecture

```
Vellum (plugin tools) --HTTP(S) w/ Authorization: Bearer--> Self-hosted FastAPI --> knowledge-rag
```

## Secrets (two layers)

| Layer | Storage | Usage |
|-------|---------|-------|
| Plugin | `apiToken` in installed `plugin/config.json` (not committed; user-readable only) | Plugin reads it and sets `Authorization: Bearer` on every request (`plugin/src/client.ts`). Token stays in the plugin process; never returned to the LLM (model sees only tool results). |
| Server | env `KRP_BEARER` in `.env` (not committed) | FastAPI `verify_bearer_token` on **all** routes including `/health`. Same value as the plugin's `apiToken`. |

Why not the Vellum credential vault (CES): CES injects credentials only into the `bash` tool and built-in integrations (via the script-proxy `HTTP_PROXY`/MITM path), **never into a plugin's in-process `fetch`**. `@vellumai/plugin-api` exposes no credential accessor and `ToolContext` gives no auth hook. So `apiTokenCredentialRef` + injection templates cannot reach our `fetch`; the plugin holds the token itself. This is acceptable for a single-user, self-hosted (often `localhost`) server. See `docs/architecture/integrations.md` (Script Proxy) and `docs/credential-execution-service.md` in the installed Vellum CLI.

> **TODO (revisit when Vellum adds authenticated fetch for plugins):** the plaintext `apiToken` in `config.json` is a stopgap only because plugin `fetch` is off the CES injection path. As soon as `@vellumai/plugin-api` exposes a credential-aware fetch/accessor (or CES intercepts plugin `fetch`), drop `apiToken` and move the secret back to the vault: read the credential ref instead of the raw token, and let CES inject `Authorization: Bearer`. Check the plugin-api surface on each Vellum upgrade.

Setup:

1. Copy `.env.example` → `.env`; set `KRP_BEARER`, `KRP_DOCUMENTS_DIR`, optional paths
2. Edit installed `plugin/config.json`: `baseUrl` + `apiToken` (same value as `KRP_BEARER`)

Docs: [Security](https://www.vellum.ai/docs/developer-guide/security), [Privacy](https://www.vellum.ai/docs/trust-security/privacy-and-data)

**Never:** commit `config.json`/`.env` with a real token; paste the token into chat; return it from a tool. **Never:** `credentials reveal` antipattern.

## Server API

14 routes. Bearer required on all. Success: HTTP `200` + `{status: "success", ...}`. Errors: HTTP code + `{status: "error", message, hint?}`.

Method convention: **GET = read-only** (params via query string, `Cache-Control: private, max-age=300` on cacheable ones); **POST = mutating or complex body** (JSON body). Volatile GETs (`/health`, `/get_reindex_status`) send `Cache-Control: no-store`.

Path convention: **every `filepath`/`source` in requests and responses is relative to `KRP_DOCUMENTS_DIR`.** [`server/paths.py`](server/paths.py) is the only crossing point — `to_library_path()` adds the root prefix before a knowledge-rag call, `relativize()` strips it (and rewrites nested `source`/`filepath`/`top_result`) from every response. Absolute filesystem paths (and the host's home layout) never reach the client/LLM; error messages report the client's relative path, not the library's absolute one. `..` or any path escaping the root → `400`.

### MCP tools (1:1 names)

| Method | Path | Params | Cache |
|--------|------|--------|-------|
| GET | `/health` | — | no-store |
| GET | `/search_knowledge` | `?query=` (req), `max_results?`, `category?`, `hybrid_alpha?`, `min_score?`, `snippet_mode?` | 5 min |
| GET | `/get_document` | `?filepath=` | 5 min |
| GET | `/list_categories` | — | 5 min |
| GET | `/list_documents` | `?category=`, `path?` (root-relative dir prefix), `limit?` (default 50, ≥1), `offset?` (default 0, ≥0) | 5 min |
| GET | `/get_index_stats` | — | 5 min |
| GET | `/search_similar` | `?filepath=` (req), `max_results?` | 5 min |
| GET | `/get_reindex_status` | — | no-store |
| POST | `/reindex_documents` | body `{force?, full_rebuild?}` | — |
| POST | `/update_document` | body `{filepath, content}` | — |
| POST | `/remove_document` | body `{filepath, delete_file?}` | — |

### File proxy

| Method | Path | Request | Response |
|--------|------|---------|----------|
| POST | `/upload` | multipart: `file`, optional `filedir`, `category`, `return` (bool) | `{status, filepath, format, indexing}`; `return=true` adds parsed `document` (no embeddings); watcher indexes saved files |
| GET | `/download` | `?filepath=` | `FileResponse` or JSON error |
| POST | `/move_document` | body `{source_filepath, dest_filepath}` | `{status, source_filepath, dest_filepath, chunks_removed?, chunks_added?, ...}` |

### Error policy (HTTP codes)

| Code | When |
|------|------|
| `200` | Success (empty search: `result_count: 0`) |
| `400` | Invalid input, path `..`/outside scope, file exists (`upload`), unsupported format |
| `401` | Missing/invalid Bearer |
| `404` | File/document not found in scope |
| `422` | Invalid JSON/multipart schema |
| `503` | `KRP_BEARER` not set or orchestrator unavailable |
| `500` | Unhandled server error |

`download`: `400` for `..`/outside allowed dirs; `404` when path is in scope but file missing on disk.

### upload `filedir` + `return`

- `filedir` (optional): target **directory** under `KRP_DOCUMENTS_DIR`, may be nested (e.g. `notes/2026`). Omitted → the root of `KRP_DOCUMENTS_DIR`. The file keeps its own uploaded name (only the bare name is used, so a name with separators can't escape `filedir`); if the multipart part has no filename, it is saved as `<YYYYmmdd-HHMMSS>.bin`. `..`/outside scope → `400`; existing target file → `400` (no overwrite). Created subdirs are made as needed.
- `return` (bool multipart field, parsed by FastAPI): default `false` → validate + save only; response has `indexing:"watcher"` (or `indexing:"background"` when `KRP_WATCH_DISABLED=1`). `true` → also parse synchronously and add a `document` block (parsed content from knowledge-rag, same shape as `get_document`); does not wait for embeddings/BM25. Indexing is normally triggered by the filesystem watcher after save; when the watcher is disabled, `/upload` schedules a per-file background index for that file only.
- Streaming (`server/services/documents.py`): the upload is copied in 1 MB chunks (never whole in RAM) into the **temp dir** (`KRP_TMP_DIR` or the system default, via `get_temp_dir()`) — keeping the in-progress file out of the watched folder and away from iCloud/Dropbox sync. Finalize via `os.replace` (atomic when temp + docs share a filesystem). Cross-filesystem (`EXDEV`, e.g. Linux tmpfs `/tmp`) falls back to staging a `<name>.download` copy inside the destination dir then atomic-renaming it, so the watched folder only ever sees the finished file appear. Blocking copy runs in a threadpool.

## Server config (`.env` only)

Copy [`.env.example`](.env.example) → `.env` (gitignored). No YAML.

[`server/env_config.py`](server/env_config.py) applies `KRP_*` vars to knowledge-rag at startup (before orchestrator init).

### Required

| Variable | Purpose |
|----------|---------|
| `KRP_BEARER` | Bearer token for all API routes |
| `KRP_DOCUMENTS_DIR` | Folder to index, watch, upload to, download from. Must already exist (never auto-created) |

### Paths (optional)

| Variable | Default |
|----------|---------|
| `KRP_TMP_DIR` | `{tmp}` (`tempfile.gettempdir()`) — base temp dir for in-progress uploads and `KNOWLEDGE_RAG_DIR` scaffolding; created if missing |
| `KNOWLEDGE_RAG_DIR` | `{KRP_TMP_DIR}/knowledge-rag-proxy/base` — internal knowledge-rag `BASE_DIR` (library var, not `KRP_`-prefixed) |
| `KRP_DATA_DIR` | `{app_data}/db` |
| `KRP_MODELS_CACHE_DIR` | `{app_data}/models_cache` |

- One folder for content: `KRP_DOCUMENTS_DIR` is watched, uploaded to, and downloaded from. No separate uploads dir. Relative paths resolve against CWD.
- `KNOWLEDGE_RAG_DIR` is **internal, throwaway library scaffolding**, decoupled from the indexed folder: `mcp_server.config` eagerly creates `{KNOWLEDGE_RAG_DIR}/{documents,data,models_cache}` at import. The proxy overrides every real path afterwards. When unset, `bootstrap_library_base()` sets it to `{KRP_TMP_DIR or system temp}/knowledge-rag-proxy/base` — keeping the scaffolding out of `KRP_DOCUMENTS_DIR`, app-data, and protected dirs.
- `KRP_TMP_DIR` (`get_temp_dir()`) overrides the base temp dir for both the in-progress-upload staging and `KNOWLEDGE_RAG_DIR`; unset → system temp. Set it to keep temp work off a synced/tmpfs volume.
- `{app_data}` is a per-user OS data dir via [`platformdirs`](https://pypi.org/project/platformdirs/) with app name `knowledge-rag-proxy`: macOS `~/Library/Application Support/…`, Linux `~/.local/share/…`, Windows `%LOCALAPPDATA%\…`.
- `KRP_DATA_DIR`/`KRP_MODELS_CACHE_DIR` resolve against CWD. `chroma_dir` is always `{KRP_DATA_DIR}/chroma_db`.

### Models & search (optional)

| Variable | Default (knowledge-rag built-in) |
|----------|----------------------------------|
| `KRP_EMBEDDING_MODEL` | `intfloat/multilingual-e5-large` (~100 languages); override e.g. `BAAI/bge-small-en-v1.5` for English-only + speed |
| `KRP_EMBEDDING_DIMENSIONS` | `1024` (matches default model); `384` for `bge-small-en-v1.5` |
| `KRP_CHUNK_SIZE` | `1000` |
| `KRP_CHUNK_OVERLAP` | `200` |
| `KRP_RERANKER_ENABLED` | `true` |
| `KRP_RERANKER_MODEL` | `Xenova/ms-marco-MiniLM-L-6-v2` |
| `KRP_RERANKER_TOP_K_MULTIPLIER` | `3` |
| `KRP_SEARCH_DEFAULT_RESULTS` | `5` |
| `KRP_SEARCH_MAX_RESULTS` | `20` |
| `KRP_COLLECTION_NAME` | `knowledge_base` |

### Advanced (optional JSON in `.env`)

| Variable | Format |
|----------|--------|
| `KRP_CATEGORY_MAPPINGS` | JSON object `{"subdir":"category"}` |
| `KRP_KEYWORD_ROUTES` | JSON object `{"keyword":["route",...]}` |

## Data flow

1. `KRP_DOCUMENTS_DIR` → startup `index_all()` → vector store; watcher re-indexes on changes
2. Vellum upload → `krp_upload_workspace` / `krp_upload_content` → `POST /upload` (save-only by default; watcher indexes)
3. Chat attachment → `user-prompt-submit` hook → `POST /upload return=true` (parse for LLM) + watcher indexes
4. User query → `krp_search_knowledge` → `GET /search_knowledge?query=...`
5. Download → `krp_download_document` → `GET /download` → scratch path in workspace

## Commands

```bash
# Python env
uv venv .venv
uv pip install -e ".[dev]"
cp .env.example .env
# edit .env — KRP_BEARER, KRP_DOCUMENTS_DIR, optional paths

# Server dev
export KRP_BEARER="your-token"
export KRP_DOCUMENTS_DIR="/path/to/your/documents"
uv run uvicorn server.app:app --reload --port 8000

# Optional: API docs at /docs
export KRP_DOCS=1

# Server tests
uv run pytest tests/

# Plugin typecheck (bun preferred; npm fallback if bun missing)
cd plugin && bun install && bunx tsc --noEmit
# cd plugin && npm install && npx tsc --noEmit

# Plugin dev install (untrusted)
assistant plugins install https://github.com/simensgreen/knowledge-rag-proxy/tree/main/plugin --name knowledge-rag-proxy
```

## Boundaries

- **Always:** `baseUrl` + `apiToken` in plugin config (token = `KRP_BEARER`; keep `config.json` out of git); `KRP_BEARER` + `KRP_DOCUMENTS_DIR` on server; paths via `.env`; proxy-owned env vars use `KRP_` prefix
- **Never:** commit secrets, `.env`, or real URLs/tokens; hardcode OS-specific paths in code/docs; YAML config for server
- **Ask first:** marketplace PR; disabling Bearer on write endpoints

## Vellum plugin contract

- Layout: `package.json`, `hooks/`, `tools/`, `skills/`, optional `src/`
- Manifest: `@simensgreen/knowledge-rag-proxy`, `peerDependencies["@vellumai/plugin-api"]`
- Tools: default export `{ description, input_schema, execute }` → `{ content, isError }`; prefix `krp_`
- Tool names: `krp_search_knowledge`, `krp_list_documents`, `krp_get_document`, `krp_upload_workspace`, `krp_upload_content`, `krp_download_document`, `krp_remove_document`, `krp_move_document`
- Docs: https://www.vellum.ai/docs/extensibility
- Marketplace: PR to `vellum-ai/vellum-assistant/plugins/marketplace.json` with `source.path: "plugin"` and pinned commit SHA

## Env vars (quick index)

Proxy-owned: `KRP_*`. Library: `KNOWLEDGE_RAG_DIR` (optional/internal, not `KRP_`-prefixed).

| Name | Required | Purpose |
|------|----------|---------|
| `KRP_BEARER` | yes | Bearer token |
| `KRP_DOCUMENTS_DIR` | yes | Folder to index/watch/upload/download; must exist (never auto-created) |
| `KRP_TMP_DIR` | no | Base temp dir for uploads + library scaffolding (default system temp); created if missing |
| `KNOWLEDGE_RAG_DIR` | no | Internal knowledge-rag `BASE_DIR` (throwaway); default `{KRP_TMP_DIR}/knowledge-rag-proxy/base` |
| `KRP_DATA_DIR` | no | ChromaDB + metadata (default `{app_data}/db`) |
| `KRP_MODELS_CACHE_DIR` | no | Embedding model cache (default `{app_data}/models_cache`) |
| `KRP_WATCH_DISABLED` | no | Set `1` to disable watcher |
| `KRP_WATCH_DEBOUNCE` | no | Watcher debounce seconds (default `10`) |
| `KRP_DOCS` | no | Set `1`/`true` for `/docs`, `/redoc`, `/openapi.json` |

See [Server config (`.env` only)](#server-config-env-only) for model/search/advanced vars.

## Gotchas

- knowledge-rag's BM25 keyword tokenizer is ASCII-only (`[a-z0-9]...`), so Cyrillic/non-Latin text is invisible to keyword search (`hybrid_alpha=0` returns 0) even though it parses and stores fine. `server/patches.py` (`apply_unicode_tokenizer_patch()`, called in `server/app.py` before the orchestrator builds the index) swaps in a Unicode-aware tokenizer. The BM25 index is rebuilt in memory from stored chunks on every start, so a **restart** re-tokenizes existing docs — no ChromaDB reindex needed. Remove the patch if knowledge-rag fixes this upstream (check on version bumps from `knowledge_rag-4.5.0`)
- Changing `KRP_EMBEDDING_MODEL` or `KRP_EMBEDDING_DIMENSIONS` invalidates the existing ChromaDB vectors (dimension mismatch). Run `POST /reindex_documents` with `{"full_rebuild": true}` after switching models, or delete `{KRP_DATA_DIR}/chroma_db` and restart
- `/health` requires Bearer (same as all routes)
- `KRP_DOCUMENTS_DIR` must be set before server import (validated in `bootstrap_library_base()`) — no silent default
- `bootstrap_library_base()` runs before `mcp_server` import and sets `KNOWLEDGE_RAG_DIR` to `{KRP_TMP_DIR or system temp}/knowledge-rag-proxy/base` when unset (explicit `KNOWLEDGE_RAG_DIR` wins), because `mcp_server.config` creates `{BASE_DIR}/{documents,data,models_cache}` at import time — this base is throwaway (all real paths are overridden), so temp keeps that scaffolding out of the indexed folder, app-data, and TCC-protected dirs
- `apply_env_config()` runs at import; knowledge-rag ignores `config.yaml` if present — proxy uses `.env` only. It creates only `db`/`chroma`/`models_cache` (app-managed); `KRP_DOCUMENTS_DIR` is never auto-created
- Uploads/downloads/watch share the one `KRP_DOCUMENTS_DIR` folder — no separate uploads dir; `db`/`models_cache` default to a per-user app-data dir (`platformdirs`)
- All API paths are root-relative — knowledge-rag returns absolute paths, so every service function routes them through `server/paths.py` (`to_library_path` inbound, `relativize` outbound). Add a new path-returning field to `_PATH_KEYS` in `server/paths.py` or it leaks the absolute path
- Startup `index_all()` in `server/startup.py` probes `KRP_DOCUMENTS_DIR` with `os.scandir` and raises `RuntimeError` if unreadable. `os.walk` in knowledge-rag's `parse_directory` silently ignores access errors, so a macOS TCC-protected folder (`~/Documents`, `~/Desktop`, `~/Downloads`) would otherwise index zero files and report success. Since the proxy never auto-creates `KRP_DOCUMENTS_DIR`, a failing probe reflects a real access problem. Grant Full Disk Access or move the folder out of protected locations.
- Plugin health at init is best-effort; unreachable server logs warning, tools return structured errors with hints at call time
- Plugin `user-prompt-submit` hook auto-uploads supported non-image chat attachments (`autoIndexAttachments` in config, default on); when `injectAttachmentDocument` is true (default), streams file bytes and calls `/upload return=true` for parsed text injection, else save-only; falls back to save-only on timeout; when injected text exceeds `attachmentMaxInjectChars`, full text is written to `scratch/knowledge-rag-proxy/injected/<conversationId>/...` and the injection cites that workspace path for `file_read`
- Plugin config optional keys: `autoIndexAttachments` (default `true`), `injectAttachmentDocument` (default `true`), `attachmentFiledir` (default `vellum`; attachments upload to `<attachmentFiledir>/<conversationId>/<filename>`), `attachmentMaxInjectChars` (default `20000`)
- Plugin tool errors return JSON `{status, message, hint}` — server hints are passed through; client adds hints for init/health/workspace validation
- Download tool writes to `scratch/knowledge-rag-proxy/downloads/`; tool result is metadata only (use `file_read` for content)
- `scripts/run-server.sh` sources `.env` for launchd

## macOS launchd (manual install)

Edit paths in `scripts/kb-proxy.plist`, then:

```bash
mkdir -p logs
chmod +x scripts/run-server.sh
cp scripts/kb-proxy.plist ~/Library/LaunchAgents/local.knowledge-rag-proxy.plist
launchctl bootstrap gui/"$(id -u)" ~/Library/LaunchAgents/local.knowledge-rag-proxy.plist
launchctl kickstart -k gui/"$(id -u)"/local.knowledge-rag-proxy
```

Stop/unload:

```bash
launchctl bootout gui/"$(id -u)" ~/Library/LaunchAgents/local.knowledge-rag-proxy.plist
```
