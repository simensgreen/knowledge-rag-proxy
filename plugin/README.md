# grimoire (Vellum plugin)

Vellum plugin (`@simensgreen/grimuire_vellum`) for a self-hosted Grimoire server.

## Install

```bash
assistant plugins install https://github.com/simensgreen/grimoire/tree/main/plugin --name grimoire
```

## Configure

### Server

```bash
export GRIM_BEARER="your-secret-token"
export GRIM_DOCUMENTS_DIR="/path/to/documents"
```

See root [AGENTS.md](../AGENTS.md).

### Plugin config

```json
{
  "baseUrl": "http://127.0.0.1:8000",
  "apiToken": "your-secret-token"
}
```

`apiToken` must match `GRIM_BEARER`. Only `baseUrl` and `apiToken` are supported.

## Tools (1:1 with API)

| Tool | API |
|------|-----|
| `grim_search` | `GET /api/search` |
| `grim_file_info` | `GET`/`POST /api/file_info` |
| `grim_update_content` | `GET`/`POST /api/file_content` |
| `grim_list_files` | `GET /api/list_files` |
| `grim_upload_workspace` | `POST /api/upload` (workspace file) |
| `grim_upload_content` | `POST /api/upload` (inline markdown) |
| `grim_reindex` | `POST /api/reindex` |
| `grim_download` | `GET /api/download` |
| `grim_remove` | `POST /api/remove` |
| `grim_move` | `POST /api/move` |
| `grim_status` | `GET /api/status` |
| `grim_markitdown` | `POST /api/markitdown` |

`/api/health` is probed at plugin init only.

## Skill

[`skills/grimoire/SKILL.md`](skills/grimoire/SKILL.md)
