#!/usr/bin/env bash
# Launch knowledge-rag-proxy via uvicorn. Sources .env from repo root.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if [[ -f "${ROOT_DIR}/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "${ROOT_DIR}/.env"
  set +a
fi

exec "${ROOT_DIR}/.venv/bin/uvicorn" server.app:app --host 0.0.0.0 --port 8000
