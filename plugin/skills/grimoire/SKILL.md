---
name: grimoire
description: Use Grimoire tools to search, upload, download, and manage documents on a self-hosted server.
---

# Grimoire

Self-hosted document knowledge base. Tools call the Grimoire REST API under `/api/...` (`grim_*`).

## When to use

- Search indexed documents: `grim_search`
- Read/update file metadata: `grim_file_info` (pass `description` to update)
- Read/replace reconstructed markdown: `grim_update_content` (pass `markdown` to update)
- List files: `grim_list_files` (optional `path` regex filter)
- Write markdown inline: `grim_upload_content` (`path` + `markdown` + optional `description`)
- Upload a workspace file (including `.md`): `grim_upload_workspace` (`workspace_path` + optional `filedir`/`markdown`/`description`)
- Force reindex by path regex: `grim_reindex`
- Download to scratch: `grim_download`
- Remove: `grim_remove`
- Move: `grim_move`
- Index status: `grim_status` (poll until a path leaves `indexing.*` after upload/update/reindex)
- Convert to markdown (no save): `grim_markitdown`

## Config

Plugin `config.json`: `baseUrl`, `apiToken` (matches server `GRIM_BEARER`).

See [references/config.md](references/config.md) and [references/tools.md](references/tools.md).
