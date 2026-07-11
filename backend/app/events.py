"""Build-event log (spec 05 §9, 07 §5). A technical, tester-facing trace of what the
course-build pipeline is doing — tool use, MCP scraping, generation, checks, verification.
Persisted so the UI can poll it live while a background build runs. Never raises into
the caller's path; a null course_id is a no-op (e.g. isolated unit tests).
"""
from __future__ import annotations

import json

from app.db import execute, fetchall


def emit(course_id: str | None, phase: str, kind: str, message: str,
         meta: dict | None = None) -> None:
    if not course_id:
        return
    try:
        execute(
            "INSERT INTO build_events (course_id, phase, kind, message, meta) "
            "VALUES (%s,%s,%s,%s,%s)",
            (course_id, phase, kind, message, json.dumps(meta) if meta else None),
        )
    except Exception:
        pass


def since(course_id: str, after_id: int = 0, limit: int = 500) -> list[dict]:
    rows = fetchall(
        "SELECT id, phase, kind, message, meta, created_at FROM build_events "
        "WHERE course_id = %s AND id > %s ORDER BY id LIMIT %s",
        (course_id, after_id, limit),
    )
    return [{"id": r["id"], "phase": r["phase"], "kind": r["kind"], "message": r["message"],
             "meta": r["meta"], "at": r["created_at"].isoformat()} for r in rows]
