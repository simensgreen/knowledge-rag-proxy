---
name: knowledge-rag-proxy
description: "Self-hosted knowledge-base search, upload, and document management via krp_* tools. Triggers: krp, knowledge-rag-proxy, search my documents, kbase, index file, upload to knowledge base."
metadata:
  vellum:
    display-name: "knowledge-rag-proxy"
    activation-hints:
      - "User asks to search documents or find information in their knowledge base"
      - "User wants to list, read, upload, download, move, or delete indexed documents"
      - "User attached a file and wants it in the knowledge base"
      - "User needs baseUrl or apiToken in the plugin config"
    avoid-when:
      - "User wants general web search, not their private document index"
      - "User asks about unrelated server admin without touching the knowledge base"
---

# knowledge-rag-proxy

Operate the **knowledge-rag-proxy** (`krp_*`) tools against a self-hosted REST server. Paths are always **root-relative** to the server's documents folder (`KRP_DOCUMENTS_DIR`), never absolute host paths.

## When to use

Load this skill when the user works with their **private indexed document library**: search, list, read, upload, download, move, or delete.

Also load when **krp_* tools fail repeatedly**, you are unsure which tool or parameters to use, or you consider **proactively indexing** a note or file for the user's future search.

**Do not use for:** general web search, unrelated coding tasks, or questions that do not need the knowledge base.

## Prerequisites

Before any `krp_*` call:

1. Server is running with `KRP_BEARER` and `KRP_DOCUMENTS_DIR` set (see repo root `AGENTS.md`).
2. Plugin `config.json` has `baseUrl` and `apiToken` (same value as `KRP_BEARER`). Never paste the token into chat.

Optional plugin keys: see [references/config.md](references/config.md).

## Workflow

### 1. Pick the right tool

| User intent | Tool | Notes |
|-------------|------|-------|
| Find information in indexed docs | `krp_search_knowledge` | Start here for Q&A |
| See what is indexed | `krp_list_documents` | `limit` default 50; use `path` filter |
| Read full parsed content | `krp_get_document` | After search/list gives a `filepath` |
| Upload file on disk in workspace | `krp_upload_workspace` | Pass `workspace_path`; never paste bytes |
| Upload text written in chat | `krp_upload_content` | `content` + `filename` with extension |
| Download server file to workspace | `krp_download_document` | Then `file_read` on returned `workspace_path` |
| Move or rename | `krp_move_document` | Both paths include filename |
| Delete from index/disk | `krp_remove_document` | Only when user explicitly asks |

Full parameters and risk levels: [references/tools.md](references/tools.md).

### 2. Search

1. Call `krp_search_knowledge` with a short query (1–3 keywords or a phrase).
2. Optional: `category`, `max_results` (default 5), `hybrid_alpha` (default 0.3), `min_score`, `snippet_mode` (default true).
3. Present results with **filepath**, **score**, and excerpt. Use `filepath` for follow-up `krp_get_document` if the user needs the full text.

### 3. List and paginate

1. Call `krp_list_documents` with optional `category`, `path` (directory prefix), `limit`, `offset`.
2. When `total` > `limit`, increase `offset` for the next page.

### 4. Upload

**File already in workspace** (scratch, attachment path, `file_read` path):

1. Call `krp_upload_workspace` with `workspace_path`.
2. Optional: `filedir`, `category`, `return_document`.
3. Default (`return_document=false`): save-only; server watcher indexes later.
4. `return_document=true`: wait for **parsing only** (not embeddings); response includes parsed `document.content`.

**Generated text in chat:**

1. Call `krp_upload_content` with `content` and `filename` (supported extension, e.g. `notes.md`).
2. Same `return_document` semantics as workspace upload.

**Chat attachments (automatic):**

The `user-prompt-submit` hook uploads supported non-image attachments to `vellum/<conversationId>/<filename>` when `autoIndexAttachments` is true. When `injectAttachmentDocument` is true (default), parsed text is injected into the turn; if truncated, full text is written under `scratch/knowledge-rag-proxy/injected/<conversationId>/...` with the path cited for `file_read`.

Prefer the hook for user-attached files; call upload tools only when the model must index something else explicitly.

**Proactive upload (agent initiative):**

You may upload a file or note to the knowledge base **without an explicit user request** when you judge it will be useful for the user later as a searchable document — e.g. a summary, decision log, spec draft, or reusable reference you produced in the session.

1. Use `krp_upload_workspace` or `krp_upload_content` with default save-only (`return_document=false`).
2. Pick a sensible `filedir` and filename; avoid overwriting — check `krp_list_documents` when unsure.
3. Tell the user briefly what you indexed and where (`filepath`).
4. **Never** upload secrets, credentials, tokens, or ephemeral scratch the user did not intend to keep.
5. **Never** delete or move documents proactively — only upload unless the user explicitly asks otherwise.

### 5. Download

1. Call `krp_download_document` with root-relative `filepath`.
2. Read `workspace_path` from the result (under `scratch/knowledge-rag-proxy/downloads/`).
3. Use built-in `file_read` on `workspace_path` — do not paste file bytes into chat.

### 6. Move / delete

- **Move:** `krp_move_document` with `source_filepath` and `dest_filepath` (both include filename). Fails if destination exists.
- **Delete:** `krp_remove_document` only when the user explicitly requests deletion. Default `delete_file=true`.

## Output contract

After successful tool calls, summarize for the user:

- **Search:** query, hit count, each hit as `filepath` + score + short excerpt; offer full read via `krp_get_document` when needed.
- **List:** total, page size, and a compact table or bullet list of `source` paths.
- **Upload:** server `filepath`, `indexing` (`watcher` or `background`), and parsed excerpt only when `return_document=true`.
- **Download:** `workspace_path` and size; do not dump raw bytes in chat.
- **Errors:** quote `message` and follow `hint` before retrying. See [references/errors.md](references/errors.md).

## Common pitfalls

- Using absolute filesystem paths — all `filepath` values are root-relative on the server.
- Pasting file bytes into chat or tool args — use `krp_upload_workspace` with `workspace_path`.
- Using `krp_upload_content` for files already on disk — use `krp_upload_workspace`.
- Expecting upload to block until search-ready — default upload is save-only; indexing is async (watcher or background).
- Calling `krp_remove_document` without explicit user consent — high risk, default deletes the file.
- Ignoring `hint` on tool errors — it names the fix (token, path, server state); load this skill if errors persist.
- Searching immediately after upload — allow a short delay for watcher/indexing unless `return_document` was used for parse-only preview.
- Proactive upload of sensitive or throwaway content — index only durable reference material the user would want to find later.

## Verification checklist

- [ ] Tool choice matches intent (search vs list vs upload path vs content).
- [ ] Paths are root-relative; workspace paths for upload/download are workspace-relative.
- [ ] Upload defaults to save-only unless parsed text is required now.
- [ ] Errors surfaced with both `message` and `hint`.
- [ ] Delete/move only when the user asked for that action.

## Examples

### Example 1 — Search then read

**Input:** "Find notes about deployment in my knowledge base."

**Output:** Call `krp_search_knowledge` with `query: "deployment"`. Summarize top hits with filepath and score. If user wants full text, call `krp_get_document` with the chosen `filepath`.

### Example 2 — Upload workspace file

**Input:** "Index the plan at scratch/plan.md."

**Output:** Call `krp_upload_workspace` with `workspace_path: "scratch/plan.md"`. Report returned `filepath` and `indexing`. Do not set `return_document` unless the user needs parsed text immediately.

### Example 3 — Proactive upload

**Input:** (No explicit request; agent finished a durable architecture note in scratch.)

**Output:** Call `krp_upload_content` with the note text and a clear filename under e.g. `filedir: "agent-notes"`. Default save-only. Tell the user: "Indexed as `agent-notes/architecture.md` for later search."
