"""Apply SQL migrations in order. Tracks applied versions in schema_migrations.

Usage:  python scripts/migrate.py
Reads DATABASE_URL (or config/settings.yaml database.dsn).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg  # noqa: E402

from app.config import get_settings  # noqa: E402

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def main() -> None:
    dsn = get_settings().database_dsn
    files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations "
            "(version text PRIMARY KEY, applied_at timestamptz DEFAULT now())"
        )
        applied = {r[0] for r in conn.execute("SELECT version FROM schema_migrations").fetchall()}
        for f in files:
            version = f.stem
            if version in applied:
                print(f"skip  {version}")
                continue
            print(f"apply {version} ...")
            with conn.transaction():
                conn.execute(f.read_text(encoding="utf-8"))
                conn.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
            print(f"done  {version}")
    print("migrations complete")


if __name__ == "__main__":
    main()
