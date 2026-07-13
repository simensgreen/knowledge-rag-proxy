# Tool errors

Failed `krp_*` calls return JSON:

```json
{
  "status": "error",
  "message": "Human-readable cause",
  "hint": "What to fix before retrying"
}
```

Always read **hint** first; it is tailored to the failure.

## Common cases

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Plugin not initialized | Missing/invalid config | Set `baseUrl` and `apiToken` in `config.json`; restart assistant |
| 401 Missing Bearer | No `apiToken` in config | Set `apiToken` = `KRP_BEARER` |
| 401 Invalid Bearer | Token mismatch | Align `apiToken` with server `KRP_BEARER` |
| 404 document not found | Wrong or stale `filepath` | Call `krp_list_documents` |
| 400 path / `..` | Path escapes documents root | Use root-relative path without `..` |
| 400 file already exists | Upload target taken | Different `filedir` or remove existing file |
| 400 unsupported format | Extension not parsed by server | Convert or use supported type |
| 400 destination exists | Move target occupied | Pick another `dest_filepath` |
| Timeout / unreachable | Server down or wrong `baseUrl` | Check server process and URL |
| 503 | Server misconfigured | Check `KRP_BEARER`, `KRP_DOCUMENTS_DIR` on server |

## Retry policy

1. Fix the issue named in `hint`.
2. Do not retry delete/move without confirming paths with `krp_list_documents`.
3. Do not paste secrets into chat to "fix" auth — edit `config.json` locally.
