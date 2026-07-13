---
name: knowledge-rag-proxy
description: >-
  Search and manage documents on a self-hosted knowledge-rag server. Use when
  the user wants to find information in their knowledge base, list indexed
  documents, upload files, download, move, or delete documents.
metadata:
  vellum:
    display-name: "knowledge-rag-proxy"
    activation-hints:
      - "User asks to search documents or find information in their knowledge base"
      - "User wants to list indexed documents"
      - "User uploads a file and wants it added to the knowledge base"
      - "User wants to download, move, rename, or delete a document in the knowledge base"
      - "User needs to configure baseUrl or the API token in the plugin config"
    avoid-when:
      - "User wants general web search, not their private document index"
---

# knowledge-rag-proxy

Connects Vellum to a self-hosted `knowledge-rag-proxy` server over HTTP(S).

## Prerequisites

1. Server running with `KRP_BEARER` set (see root `AGENTS.md`).
2. Plugin `config.json`: `baseUrl` + `apiToken` (same value as `KRP_BEARER`). The plugin sends it as `Authorization: Bearer`; keep `config.json` out of git. Never paste the token into chat.

## Search

When the user asks to find information in their documents:

1. Call `krp_search_knowledge` with a clear query.
2. Summarize hits with filepath, score, and relevant excerpt.

## List

When the user wants to see what is indexed:

1. Call `krp_list_documents` with optional `category`, `path`, `limit` (default 50), or `offset`.
2. Use pagination (`offset`) when `total` exceeds `limit`.

## Read full document

1. Call `krp_get_document` with a root-relative `filepath` from list results.

## Upload

**File already in workspace** (attachment, scratch, `file_read` path):

1. Call `krp_upload_workspace` with `workspace_path`.
2. Optional: `filedir`, `category`, `return_document`.

**Generated or edited text in chat:**

1. Call `krp_upload_content` with `content` and `filename`.
2. Do not use for files already on disk — use `krp_upload_workspace`.

## Download

1. Call `krp_download_document` with root-relative `filepath`.
2. Tool returns `workspace_path` under `scratch/knowledge-rag-proxy/downloads/`.
3. Use built-in `file_read` on `workspace_path` if content is needed — do not paste file bytes into chat.

## Move / rename

1. Call `krp_move_document` with full root-relative `source_filepath` and `dest_filepath`.
2. Fails if destination already exists.

## Delete

Only when the user explicitly asks:

1. Call `krp_remove_document` with `filepath` (default removes from disk and index).

## Errors

Tool errors return JSON with `message` and `hint`. Read `hint` and fix the request (paths, credentials, server state) before retrying.

If tools report server unavailable:

- Verify `baseUrl` in `config.json` is reachable from Vellum.
- Verify `apiToken` in `config.json` equals `KRP_BEARER` on the server.
