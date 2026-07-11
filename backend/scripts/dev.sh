#!/usr/bin/env bash
# One-shot local bootstrap for the backend (after `docker compose up -d db`).
set -euo pipefail
cd "$(dirname "$0")/.."
python -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
python scripts/migrate.py
python -m app.seed
echo "Starting API on http://localhost:8000 (docs at /docs)"
uvicorn app.main:app --reload --port 8000
