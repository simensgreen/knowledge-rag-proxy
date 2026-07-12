# knowledge-rag-proxy

Self-hosted REST proxy over [knowledge-rag](https://pypi.org/project/knowledge-rag/) with a [Vellum](https://www.vellum.ai/docs/extensibility) plugin for search and document upload.

**Full project context:** [AGENTS.md](AGENTS.md)

## Quick start

### Server

```bash
uv venv .venv
uv pip install -e ".[dev]"
cp config.example.yaml config.yaml
# edit config.yaml — set your document paths

export KB_PROXY_API_KEY="your-secret-token"
uv run uvicorn server.app:app --reload --port 8000
```

### Plugin

```bash
cd plugin
bun install
bunx tsc --noEmit
```

Install into Vellum (dev):

```bash
assistant plugins install https://github.com/simensgreen/knowledge-rag-proxy/tree/main/plugin --name knowledge-rag-proxy
```

Then configure `baseUrl`, store the API token in the Vellum credential vault, and set `apiTokenCredentialRef` in `config.json`. See [plugin/README.md](plugin/README.md).

## Repo layout

- `server/` — Python FastAPI proxy
- `plugin/` — Vellum plugin (marketplace unit)
- `tests/` — server pytest
- `scripts/` — deploy/backup stubs

## Status

Phase 0 scaffold: stub endpoints and plugin surfaces. Implementation tracked in [AGENTS.md](AGENTS.md) roadmap.
