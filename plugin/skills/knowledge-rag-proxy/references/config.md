# Plugin config

Edit installed `config.json` (not committed). Required: `baseUrl`, `apiToken` (same value as server `KRP_BEARER`).

**Example excerpt** — minimal config:

```json
{
  "baseUrl": "http://127.0.0.1:8000",
  "apiToken": "your-secret-token"
}
```

Only `baseUrl` and `apiToken` are read. No other keys.

## Upload indexing behavior (server)

| Mode | When | Response `indexing` |
|------|------|---------------------|
| Watcher enabled | Default | `watcher` — filesystem watcher indexes after save |
| Watcher disabled (`KRP_WATCH_DISABLED=1`) | Dev / special deploy | `background` — per-file index scheduled after response |

`return_document=true` on `/upload` parses synchronously for LLM preview; it does not wait for embeddings/BM25.
