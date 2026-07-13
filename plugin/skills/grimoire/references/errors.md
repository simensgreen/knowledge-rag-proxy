# Errors

Tools return JSON `{status:"error", message, hint?}` on failure.

Common fixes:

- **401** — `apiToken` in plugin config must match `GRIM_BEARER` on the server
- **404** — path not found; use `grim_list_files`
- **400** — bad path, regex, or unsupported upload format
