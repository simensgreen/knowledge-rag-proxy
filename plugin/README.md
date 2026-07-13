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
| `grim_search` | `GET /search` |
| `grim_file` | `GET /file` |
| `grim_list_files` | `GET /list_files` |
| `grim_upload` | `POST /upload` |
| `grim_download` | `GET /download` |
| `grim_remove` | `POST /remove` |
| `grim_move` | `POST /move` |
| `grim_status` | `GET /status` |
| `grim_markitdown` | `POST /markitdown` |

`/health` is probed at plugin init only.

## Skill

[`skills/grimoire/SKILL.md`](skills/grimoire/SKILL.md)
