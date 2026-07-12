# knowledge-rag-proxy (Vellum plugin)

Vellum plugin that talks to a self-hosted [knowledge-rag-proxy](https://github.com/simensgreen/knowledge-rag-proxy) server.

## Install

From the marketplace (after catalog PR merges):

```bash
assistant plugins install knowledge-rag-proxy
```

Untrusted dev install from this monorepo:

```bash
assistant plugins install https://github.com/simensgreen/knowledge-rag-proxy/tree/main/plugin --name knowledge-rag-proxy
```

## Configure

### 1. Deploy the server

Run the Python server on a host reachable from Vellum (any `http://` or `https://` URL). Set the same Bearer token on the server:

```bash
export KB_PROXY_API_KEY="your-secret-token"
```

See root `AGENTS.md` for server setup.

### 2. Store the API token in the Vellum credential vault

**Never** put the raw token in `config.json` or chat.

1. Ask your assistant to use `credential_store` (secure prompt) to save the token.
2. Use alias `knowledge-rag-proxy/api_token` (or another name you reference in config).
3. Set `allowedDomains` to the host from your `baseUrl` (e.g. `kb.example.com` or `*.example.com`).
4. Restrict `allowedTools` to: `kb_search`, `kb_list`, `kb_upload`.

The Credential Execution Service injects `Authorization: Bearer` on outbound requests to matching domains. Plugin code does not read plaintext secrets.

Docs: [Security & Permissions](https://www.vellum.ai/docs/developer-guide/security)

### 3. Edit plugin config

After install, edit `~/.vellum/workspace/plugins/knowledge-rag-proxy/config.json`:

```json
{
  "baseUrl": "https://kb.example.com",
  "apiTokenCredentialRef": "knowledge-rag-proxy/api_token"
}
```

`baseUrl` must not have a trailing slash. `apiTokenCredentialRef` is the vault alias only.

## Tools

| Tool | Risk | Description |
|------|------|-------------|
| `kb_search` | low | Hybrid search over indexed documents |
| `kb_list` | low | List documents in the index |
| `kb_upload` | medium | Upload a file from the conversation workspace for indexing |

## Upgrade

```bash
assistant plugins upgrade knowledge-rag-proxy
```

`config.json` and `data/` are preserved across upgrades.
