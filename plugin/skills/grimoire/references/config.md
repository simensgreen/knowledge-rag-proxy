# Config

## Plugin (`plugin/config.json`)

```json
{
  "baseUrl": "http://127.0.0.1:8000",
  "apiToken": "same-as-GRIM_BEARER"
}
```

## Server (`.env`)

Required: `GRIM_BEARER`, `GRIM_DOCUMENTS_DIR`.

Optional: `GRIM_TMP_DIR`, `GRIM_SURREAL_URL`, search/watcher vars, embedding/OCR provider triplets (Phase 2).
