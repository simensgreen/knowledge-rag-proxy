# Tools

| Tool | API |
|------|-----|
| `grim_search` | `GET /api/search?query=&max_results?` |
| `grim_file_info` | `GET /api/file_info?path=` or `POST /api/file_info?path=&description=` |
| `grim_update_content` | `GET /api/file_content?path=` or `POST /api/file_content?path=` + `{markdown}` |
| `grim_list_files` | `GET /api/list_files?path=&limit=&offset=` (`path` = regex on indexed docs) |
| `grim_upload_workspace` | `POST /api/upload` multipart from `workspace_path` (+ optional `filedir`/`markdown`/`description`) |
| `grim_upload_content` | `POST /api/upload` with inline `path` + `markdown` (+ optional `description`) |
| `grim_reindex` | `POST /api/reindex?path=` (`path` = regex; may queue many docs) |
| `grim_download` | `GET /api/download?path=` |
| `grim_remove` | `POST /api/remove?path=` |
| `grim_move` | `POST /api/move?source_path=&dest_path=` |
| `grim_status` | `GET /api/status` |
| `grim_markitdown` | `POST /api/markitdown` |

Paths are root-relative to the server's `GRIM_DOCUMENTS_DIR`.

Upload / update / reindex are fire-and-forget for indexing: poll `grim_status` until the path leaves `indexing.*`.
