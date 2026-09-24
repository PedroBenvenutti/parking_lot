#!/usr/bin/env bash
# Sobe o sistema completo numa porta só (8000): API, WebSocket e a interface já compilada.
set -euo pipefail
cd "$(dirname "$0")/../backend"
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
