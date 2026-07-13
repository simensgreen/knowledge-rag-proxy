# krp_* tool reference

All tools append: if unsure which tool/params to use or calls keep failing, load `skills/knowledge-rag-proxy/SKILL.md`.

All tools return JSON. Success: `{ "status": "success", ... }`. Failure: `{ "status": "error", "message", "hint?" }` with `isError: true` on the tool result.

Paths on the server are **root-relative** to `KRP_DOCUMENTS_DIR` (e.g. `notes/plan.md`, `vellum/<conversationId>/report.pdf`).

## krp_search_knowledge

**Risk:** low  
**When:** User asks to find information in indexed documents.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `query` | yes | — | Non-empty search text (keywords or short phrase) |
| `max_results` | no | 5 | Max hits |
| `category` | no | — | Category filter |
| `hybrid_alpha` | no | 0.3 | 0 = keyword BM25, 1 = semantic; blend in between |
| `min_score` | no | 0 | Minimum relevance score |
| `snippet_mode` | no | true | Truncate chunk text in results |

**Returns:** `query`, `result_count`, `results[]` with `content`, `score`, `source` (filepath).

## krp_list_documents

**Risk:** low  
**When:** User wants an inventory of indexed files.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `category` | no | — | Filter by category |
| `path` | no | — | Root-relative directory prefix (e.g. `notes`, `vellum`) |
| `limit` | no | 50 | Page size |
| `offset` | no | 0 | Pagination offset |

**Returns:** `total`, `count`, `offset`, `limit`, `documents[]` with `source`, `category`, `format`, `chunks`.

## krp_get_document

**Risk:** low  
**When:** Full parsed content of one indexed file is needed.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `filepath` | yes | Root-relative path from list/search results |

**Returns:** `document` with `content`, `filename`, `format`, `metadata`, `keywords`, `chunk_count`.

## krp_upload_workspace

**Risk:** medium  
**When:** A file already exists in the Vellum workspace (attachment, scratch, path from `file_read`).

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `workspace_path` | yes | — | Path relative to workspace root |
| `filedir` | no | — | Target directory under documents root on server |
| `category` | no | — | Indexing category |
| `return_document` | no | false | If true, parse synchronously and return `document`; else save-only |

**Returns:** `filepath`, `format`, `indexing` (`watcher` or `background`). With `return_document=true`: also `document` (parsed text, no embedding wait).

**Never:** paste file bytes — the tool streams from disk via `workspace_path`.

## krp_upload_content

**Risk:** medium  
**When:** Text was generated or edited in chat and should be saved as a new file.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `content` | yes | — | Text to save |
| `filename` | yes | — | Server filename with supported extension (e.g. `notes.md`) |
| `filedir` | no | — | Target directory under documents root |
| `category` | no | — | Indexing category |
| `return_document` | no | false | Same as workspace upload |

**Do not use** for files already on disk — use `krp_upload_workspace`.

**Proactive use:** agent may upload durable notes/specs the user will want to search later, without an explicit user request — see hub **Proactive upload** section. Default save-only.

## krp_download_document

**Risk:** low  
**When:** A server file should be read in the workspace.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `filepath` | yes | Root-relative server path |

**Returns:** `filepath`, `workspace_path` (under `scratch/knowledge-rag-proxy/downloads/...`), `size_bytes`, `media_type`.

Use `file_read` on `workspace_path` for content.

## krp_move_document

**Risk:** medium  
**When:** User asks to move or rename a file within the documents root.

| Parameter | Required | Description |
|-----------|----------|-------------|
| `source_filepath` | yes | Current path including filename |
| `dest_filepath` | yes | New path including filename |

Fails with 400 if destination exists. Re-indexes at destination when format is supported.

## krp_remove_document

**Risk:** high  
**When:** User **explicitly** asks to delete a document.

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `filepath` | yes | — | Root-relative path to remove |
| `delete_file` | no | true | Also delete file from disk |

**Never** call without explicit user request to delete.
