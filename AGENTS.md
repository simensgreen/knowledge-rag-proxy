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
- Generic document paths via `config.yaml` — no OS/vendor assumptions
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
| 1 | Server endpoints + knowledge-rag orchestrator | `server/` |
| 2 | Plugin HTTP client + multipart upload | `plugin/` |
| 3 | Self-hosted deploy (systemd / launchd, backup) | `scripts/` |
| 4 | Marketplace PR | `vellum-ai/vellum-assistant` |

## Layout

| Path | Role |
|------|------|
| `server/app.py` | FastAPI app, 6 routes, Bearer auth stub |
| `server/watcher.py` | Optional file watcher (Phase 1) |
| `server/backup.py` | Optional remote backup (Phase 3) |
| `plugin/` | Vellum plugin root (marketplace `source.path`) |
| `plugin/hooks/init.ts` | Config validation + health check |
| `plugin/tools/*.ts` | `kb_search`, `kb_list`, `kb_upload` |
| `plugin/skills/knowledge-rag-proxy/SKILL.md` | On-demand instructions |
| `plugin/src/` | Shared config, client, state |
| `config.example.yaml` | Server config template |
| `plugin/config.json` | Plugin config template (no secrets) |
| `tests/` | pytest for server |
| `scripts/` | deploy + backup stubs |
| `scripts/kb-proxy.service` | systemd unit (Linux) |
| `scripts/kb-proxy.plist` | launchd agent (macOS) |
| `scripts/run-server.sh` | uvicorn wrapper; loads `.env` for launchd |

## Architecture

```
Vellum (plugin tools) --HTTP(S)--> Self-hosted FastAPI --> knowledge-rag
         ^
         Credential vault (CES) injects Bearer on matching domains
```

## Secrets (two layers)

| Layer | Storage | Usage |
|-------|---------|-------|
| Plugin | Vellum credential vault via `credential_store` | User saves Bearer token with secure prompt. `config.json` holds only `apiTokenCredentialRef` (e.g. `knowledge-rag-proxy/api_token`). Set `allowedDomains` = host from `baseUrl`, `allowedTools` = `kb_search`, `kb_list`, `kb_upload`. CES injects `Authorization: Bearer` — plugin never reads plaintext. |
| Server | env `KB_PROXY_API_KEY` in `.env` (not committed) | FastAPI `verify_bearer_token` on protected routes. Same token value as vault entry. |

Setup:

1. Deploy server, set `KB_PROXY_API_KEY` in `.env`
2. In Vellum: `credential_store` → alias `knowledge-rag-proxy/api_token`
3. Edit installed `plugin/config.json`: `baseUrl` + `apiTokenCredentialRef`

Docs: [Security](https://www.vellum.ai/docs/developer-guide/security), [Privacy](https://www.vellum.ai/docs/trust-security/privacy-and-data)

**Never:** raw tokens in `config.json`, chat, git, or plugin source. **Never:** `credentials reveal` antipattern.

## Server API (stub / Phase 1 target)

| Method | Path | Auth | Request | Response |
|--------|------|------|---------|----------|
| GET | `/health` | none | — | `{ok, version, documents}` |
| POST | `/search` | Bearer | `{query, max_results?, category?}` | `{hits: [{filepath, content, score, category}]}` |
| POST | `/upload` | Bearer | multipart: `file`, optional `category` | `{status, filepath}` |
| GET | `/list` | Bearer | `?category=&limit=` | `{documents: [...], total}` |
| GET | `/stats` | Bearer | — | `{total_documents, total_chunks, categories, bm25_ready}` |
| POST | `/reindex` | Bearer | `{force?: bool}` | `{indexed, chunks_added, skipped}` |

## Server config (`config.yaml`)

Copy `config.example.yaml` → `config.yaml` (gitignored). User-defined paths only:

- `paths.documents_dir` — directories to index
- `paths.data_dir` — ChromaDB + metadata
- `paths.uploads_dir` — chat upload landing zone
- `watcher.debounce_seconds` — optional auto-reindex delay
- `category_mappings`, `keyword_routes` — optional

## Data flow

1. Configured dirs → watchdog → `orch.index_all()` → vector store
2. Vellum upload → `kb_upload` → `POST /upload` → watcher → index
3. User query → `kb_search` → `POST /search` → hybrid search results

## Commands

```bash
# Python env
uv venv .venv
uv pip install -e ".[dev]"
cp config.example.yaml config.yaml

# Server dev (set token first)
export KB_PROXY_API_KEY="your-token"
uv run uvicorn server.app:app --reload --port 8000

# Server tests
uv run pytest tests/

# Plugin typecheck (bun preferred; npm fallback if bun missing)
cd plugin && bun install && bunx tsc --noEmit
# cd plugin && npm install && npx tsc --noEmit

# Plugin dev install (untrusted)
assistant plugins install https://github.com/simensgreen/knowledge-rag-proxy/tree/main/plugin --name knowledge-rag-proxy
```

## Boundaries

- **Always:** `baseUrl` + `apiTokenCredentialRef` in plugin config (ref only); vault for token; `KB_PROXY_API_KEY` on server; paths in `config.yaml`
- **Never:** commit secrets, `config.yaml`, or real URLs/tokens; hardcode OS-specific paths in code/docs
- **Ask first:** marketplace PR; disabling Bearer on write endpoints

## Vellum plugin contract

- Layout: `package.json`, `hooks/`, `tools/`, `skills/`, optional `src/`
- Manifest: `@simensgreen/knowledge-rag-proxy`, `peerDependencies["@vellumai/plugin-api"]`
- Tools: default export `{ description, input_schema, execute }` → `{ content, isError }`
- Docs: https://www.vellum.ai/docs/extensibility
- Marketplace: PR to `vellum-ai/vellum-assistant/plugins/marketplace.json` with `source.path: "plugin"` and pinned commit SHA

## Env vars (names only)

| Name | Where | Purpose |
|------|-------|---------|
| `KB_PROXY_API_KEY` | server `.env` | Bearer token validated on API routes |

## Gotchas

- `/health` is unauthenticated in scaffold (load balancer friendly); Phase 1 may change
- Protected routes return `501` until Phase 1 implements orchestrator
- Plugin health at init is best-effort; unreachable server logs warning, tools error at call time
- `kb_upload` throws until Phase 2 multipart implementation

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
