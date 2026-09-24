#!/usr/bin/env bash
# Roda uma vez, quando o Codespace é criado.
set -euo pipefail

cd backend
python -m venv .venv
.venv/bin/pip install -q -r requirements.txt
[ -f .env ] || cp .env.example .env
.venv/bin/alembic upgrade head
.venv/bin/python seed.py
cd ..

cd frontend
npm install
# Gera frontend/dist: o FastAPI serve a interface na mesma porta 8000.
npm run build
cd ..

echo
echo "Pronto! Para iniciar:  bash .devcontainer/start.sh"
