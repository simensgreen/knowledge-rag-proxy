# grimoire

Self-hosted document knowledge base with a [Vellum](https://www.vellum.ai/docs/extensibility) plugin (`@simensgreen/grimuire_vellum`).

**Full project context:** [AGENTS.md](AGENTS.md)

## Quick start

### Server

```bash
uv venv .venv
uv pip install -e ".[dev]"
cp .env.example .env
# edit .env — GRIM_BEARER, GRIM_DOCUMENTS_DIR

export GRIM_BEARER="your-secret-token"
export GRIM_DOCUMENTS_DIR="$(pwd)/documents"
uv run uvicorn server.app:app --reload --port 8000
```

### Plugin

```bash
cd plugin
bun install
bunx tsc --noEmit
```

```bash
assistant plugins install https://github.com/simensgreen/grimoire/tree/main/plugin --name grimoire
```

Configure `baseUrl` and `apiToken` in the installed `plugin/config.json` (same value as `GRIM_BEARER`).

## API (10 routes)

`GET /health`, `GET /search`, `GET /file`, `GET /list_files`, `POST /upload`, `GET /download`, `POST /remove`, `POST /move`, `GET /status`, `POST /markitdown`

Plugin tools `grim_*` map 1:1 to these routes (`/health` is init probe only).

## Layout

- `server/` — FastAPI app + `server/engine/` (ingest, SurrealDB, markitdown)
- `plugin/` — Vellum plugin
- `tests/` — pytest
