# knowledge-rag-proxy (Vellum plugin)

Vellum plugin that talks to a self-hosted [knowledge-rag-proxy](https://github.com/simensgreen/knowledge-rag-proxy) server.

## Install

From the marketplace (after catalog PR merges):

```bash
assistant plugins install knowledge-rag-proxy
```

Untrusted dev install from this monorepo:

```bash
assistant plugins install https://github.com/simensgreen/knowledge-rag-proxy/tree/main/plugin --name knowledge-rag-proxy
```

## Configure

### 1. Deploy the server

Run the Python server on a host reachable from Vellum (any `http://` or `https://` URL). Set the same Bearer token on the server:

```bash
export KRP_BEARER="your-secret-token"
```

See root `AGENTS.md` for server setup.

### 2. Edit plugin config

After install, edit `~/.vellum/workspace/plugins/knowledge-rag-proxy/config.json`:

```json
{
  "baseUrl": "https://kb.example.com",
  "apiToken": "your-secret-token",
  "autoIndexAttachments": true,
  "injectAttachmentDocument": true,
  "attachmentFiledir": "vellum",
  "attachmentMaxInjectChars": 20000
}
```

`baseUrl` must not have a trailing slash. `apiToken` is the same value as `KRP_BEARER` on the server; the plugin sends it as `Authorization: Bearer` on every request.

Optional keys: `autoIndexAttachments` (default `true`) auto-uploads supported chat attachments; `injectAttachmentDocument` (default `true`) injects knowledge-rag's parsed text into the turn (upload still runs when false); `attachmentFiledir` (default `vellum`) is the base server subdir for those uploads (files land in `<attachmentFiledir>/<conversationId>/<filename>`); `attachmentMaxInjectChars` (default `20000`) caps injected parsed text in the prompt.

> **Why not the Vellum credential vault?** The vault (CES) only injects credentials into the `bash` tool and built-in integrations — never into a plugin's in-process `fetch`. So the plugin must hold the token itself. It stays inside the plugin process and is never returned to the LLM (the model only sees tool results). Keep `config.json` out of git and readable only by your user (it is your own machine, single-user, and the server is typically on `localhost`).

Docs: [Security & Permissions](https://www.vellum.ai/docs/developer-guide/security)

## Tools

| Tool | Risk | Description |
|------|------|-------------|
| `krp_search_knowledge` | low | Hybrid search over indexed documents |
| `krp_list_documents` | low | List documents with filters and pagination (`limit` default 50) |
| `krp_get_document` | low | Fetch full parsed content by root-relative filepath |
| `krp_upload_workspace` | medium | Upload a file already in the Vellum workspace |
| `krp_upload_content` | medium | Upload generated text content with a filename |
| `krp_download_document` | low | Download to workspace scratch; returns metadata + `workspace_path` |
| `krp_remove_document` | high | Remove from index and disk (default `delete_file: true`) |
| `krp_move_document` | medium | Move or rename a file within the documents root |

### File flows

- **Upload from workspace:** `krp_upload_workspace` with `workspace_path` (chat attachment, scratch, or path from `file_read`). Do not paste file bytes. Default is save-only; the server watcher indexes later. Set `return_document=true` to wait for parsing and receive parsed text.
- **Upload generated text:** `krp_upload_content` with `content` + `filename`. Same `return_document` semantics.
- **Chat attachments:** supported non-image files attached in chat are auto-uploaded by the `user-prompt-submit` hook (when `autoIndexAttachments` is true). Parsed text is injected into the turn when `injectAttachmentDocument` is true (default).
- **Download:** `krp_download_document` writes to `scratch/knowledge-rag-proxy/downloads/...` and returns `workspace_path` only. Use built-in `file_read` to read the file.

### Errors

Failed tool calls return JSON `{ status: "error", message, hint }` with actionable hints from the server or client validation.

## Skill

On-demand instructions for agents: [`skills/knowledge-rag-proxy/SKILL.md`](skills/knowledge-rag-proxy/SKILL.md) (workflows, tool picker, pitfalls). Tool parameters: [`skills/knowledge-rag-proxy/references/tools.md`](skills/knowledge-rag-proxy/references/tools.md).

## Upgrade

```bash
assistant plugins upgrade knowledge-rag-proxy
```

`config.json` and `data/` are preserved across upgrades.
