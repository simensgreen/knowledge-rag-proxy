---
name: grimoire
description: Use Grimoire tools to search, upload, download, and manage documents on a self-hosted server.
---

# Grimoire

Self-hosted document knowledge base. Tools call the Grimoire REST API (`grim_*`).

## When to use

- Search indexed documents: `grim_search`
- Read indexed content: `grim_file`
- List files: `grim_list_files` (optional `path` regex filter)
- Upload: `grim_upload` (`workspace_path` or `content`+`filename`)
- Download to scratch: `grim_download`
- Remove: `grim_remove`
- Move: `grim_move`
- Index status: `grim_status`
- Convert to markdown (no save): `grim_markitdown`

## Config

Plugin `config.json`: `baseUrl`, `apiToken` (matches server `GRIM_BEARER`).

See [references/config.md](references/config.md) and [references/tools.md](references/tools.md).
