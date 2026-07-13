# Tools

| Tool | API |
|------|-----|
| `grim_search` | `GET /search?query=&max_results?` |
| `grim_file` | `GET /file?path=` |
| `grim_list_files` | `GET /list_files?path=&limit=&offset=` (`path` = regex) |
| `grim_upload` | `POST /upload` |
| `grim_download` | `GET /download?path=` |
| `grim_remove` | `POST /remove` body `{path}` |
| `grim_move` | `POST /move` body `{source_path, dest_path}` |
| `grim_status` | `GET /status` |
| `grim_markitdown` | `POST /markitdown` |

Paths are root-relative to the server's `GRIM_DOCUMENTS_DIR`.
