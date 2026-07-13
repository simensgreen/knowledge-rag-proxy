# Plugin config

Edit installed `config.json` (not committed). Required: `baseUrl`, `apiToken` (same value as server `KRP_BEARER`).

**Example excerpt** — minimal config:

```json
{
  "baseUrl": "http://127.0.0.1:8000",
  "apiToken": "your-secret-token"
}
```

## Optional keys

| Key | Default | Purpose |
|-----|---------|---------|
| `autoIndexAttachments` | `true` | Auto-upload supported non-image chat attachments |
| `injectAttachmentDocument` | `true` | Inject parsed text into the turn (upload still runs when `false`) |
| `attachmentFiledir` | `vellum` | Base server subdir; files land in `<attachmentFiledir>/<conversationId>/<filename>` |
| `attachmentMaxInjectChars` | `20000` | Max parsed chars injected; overflow written to `scratch/knowledge-rag-proxy/injected/<conversationId>/...` |

## Upload indexing behavior (server)

| Mode | When | Response `indexing` |
|------|------|---------------------|
| Watcher enabled | Default | `watcher` — filesystem watcher indexes after save |
| Watcher disabled (`KRP_WATCH_DISABLED=1`) | Dev / special deploy | `background` — per-file index scheduled after response |

`return_document=true` on `/upload` parses synchronously for LLM preview; it does not wait for embeddings/BM25.
