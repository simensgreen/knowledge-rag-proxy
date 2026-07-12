---
name: knowledge-rag-proxy
description: >-
  Search and manage documents on a self-hosted knowledge-rag server. Use when
  the user wants to find information in their knowledge base, list indexed
  documents, or upload a file for indexing.
metadata:
  vellum:
    display-name: "knowledge-rag-proxy"
    activation-hints:
      - "User asks to search documents or find information in their knowledge base"
      - "User wants to list indexed documents"
      - "User uploads a file and wants it added to the knowledge base"
      - "User needs to configure baseUrl or store the API token in the credential vault"
    avoid-when:
      - "User wants general web search, not their private document index"
---

# knowledge-rag-proxy

Connects Vellum to a self-hosted `knowledge-rag-proxy` server over HTTP(S).

## Prerequisites

1. Server running with `KRP_BEARER` set (see root `AGENTS.md`).
2. Plugin `config.json`: `baseUrl` + `apiTokenCredentialRef` (vault alias only).
3. API token stored via `credential_store` secure prompt — never paste secrets in chat.
4. Credential `allowedDomains` must include the host from `baseUrl`.
5. Credential `allowedTools` should include `kb_search`, `kb_list`, `kb_upload`.

## Search

When the user asks to find information in their documents:

1. Call `kb_search` with a clear query.
2. Summarize hits with filepath, score, and relevant excerpt.

## List

When the user wants to see what is indexed:

1. Call `kb_list` with optional category or limit.

## Upload

When the user attaches a file to index:

1. Locate the file under the conversation attachments folder in the workspace.
2. Call `kb_upload` with `workspace_file_path` pointing at that file.
3. Confirm indexing once the server responds.

## Errors

If tools report server unavailable:

- Verify `baseUrl` in `config.json` is reachable from Vellum.
- Verify the credential vault entry matches `apiTokenCredentialRef` and `allowedDomains`.
- Verify the server has the same token in `KRP_BEARER`.
