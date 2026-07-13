# knowledge-rag-proxy

Self-hosted REST proxy over [knowledge-rag](https://pypi.org/project/knowledge-rag/) with a [Vellum](https://www.vellum.ai/docs/extensibility) plugin for search and document upload.

**Full project context:** [AGENTS.md](AGENTS.md)

## Quick start

### Server

```bash
uv venv .venv
uv pip install -e ".[dev]"
cp .env.example .env
# edit .env — KRP_BEARER, KRP_DOCUMENTS_DIR, optional paths

export KRP_BEARER="your-secret-token"
export KRP_DOCUMENTS_DIR="$(pwd)/documents"
uv run uvicorn server.app:app --reload --port 8000
```

You set only `KRP_DOCUMENTS_DIR` — the folder to index, watch, and serve.

### Why we quietly redirect `KNOWLEDGE_RAG_DIR` to your temp dir

You may notice the embedded `knowledge-rag` library wants a `KNOWLEDGE_RAG_DIR` and, the very moment you `import` its config module, helpfully mkdir's `documents/`, `data/`, and `models_cache/` wherever that points — a global singleton with filesystem side effects at import time. Merely reading the config *writes to your disk*. Chef's kiss.

Since we override every real path afterwards anyway, `bootstrap_library_base()` sets `KNOWLEDGE_RAG_DIR` to `{temp}/knowledge-rag-proxy/base` **before** the import fires — unless you set `KNOWLEDGE_RAG_DIR` yourself. `{temp}` is `KRP_TMP_DIR` when set, otherwise the cross-platform system temp (`tempfile.gettempdir()`). Same base temp dir is used for in-progress uploads. Your actual documents folder stays pristine, with no surprise `documents/` nesting. Persistent state we *do* care about (ChromaDB, metadata, model cache) goes to a proper per-user app-data dir, not temp.

Moral: please don't ship global mutable config that touches the filesystem on import. Someone downstream has to write a paragraph like this one.

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

Phase 1 server + Phase 2 plugin tools (`krp_*`) are implemented. See [AGENTS.md](AGENTS.md) roadmap.
