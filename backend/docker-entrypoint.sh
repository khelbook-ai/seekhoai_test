#!/bin/sh
# Wait for Postgres, apply migrations, then start the API. Idempotent: migrations skip
# already-applied versions, so restarting the container is safe.
set -e

echo "[entrypoint] waiting for database at ${DATABASE_URL:-<unset>} ..."
python - <<'PY'
import os, time, sys
import psycopg
dsn = os.environ.get("DATABASE_URL", "postgresql://seekhai:seekhai@db:5432/seekhai")
for _ in range(60):
    try:
        psycopg.connect(dsn, connect_timeout=3).close()
        print("[entrypoint] database is ready")
        sys.exit(0)
    except Exception as e:
        print(f"[entrypoint] db not ready yet: {e}")
        time.sleep(2)
print("[entrypoint] database never became reachable", file=sys.stderr)
sys.exit(1)
PY

echo "[entrypoint] running migrations ..."
python scripts/migrate.py

echo "[entrypoint] starting API on :8000 ..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
