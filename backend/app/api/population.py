"""Course population / curriculum view (spec 05 §8, 06 §4, 07 §5). Counts are DERIVED
from persisted rows (not denormalised) and recomputed on read."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import fetchall, fetchone
from app.store import get_course

router = APIRouter(prefix="/api/courses", tags=["population"])


def _counts_where(course_id: str) -> str:
    return (
        "FROM interactions i JOIN subtopics s ON i.subtopic_id = s.id "
        "JOIN topics t ON s.topic_id = t.id WHERE t.course_id = %s")


@router.get("/{course_id}/population")
def population(course_id: str) -> dict:
    course = get_course(course_id)
    if course is None:
        raise HTTPException(404, "course not found")

    mcq = fetchone(f"SELECT count(*) n {_counts_where(course_id)} AND i.type='mcq'", (course_id,))["n"]
    qa = fetchone(f"SELECT count(*) n {_counts_where(course_id)} AND i.type='qa'", (course_id,))["n"]

    diag_rows = fetchall(
        """SELECT d.provenance, count(*) n FROM diagrams d
           JOIN interactions i ON d.interaction_id = i.id
           JOIN subtopics s ON i.subtopic_id = s.id JOIN topics t ON s.topic_id = t.id
           WHERE t.course_id = %s GROUP BY d.provenance""", (course_id,))
    diagrams = {r["provenance"]: r["n"] for r in diag_rows}

    src_rows = fetchall(
        """SELECT so.type, count(*) n FROM sources so
           JOIN subtopics s ON so.subtopic_id = s.id JOIN topics t ON s.topic_id = t.id
           WHERE t.course_id = %s GROUP BY so.type""", (course_id,))
    sources_by_format = {r["type"] or "other": r["n"] for r in src_rows}
    total_sources = sum(sources_by_format.values())

    newest = fetchone(
        """SELECT max(so.published) d FROM sources so
           JOIN subtopics s ON so.subtopic_id = s.id JOIN topics t ON s.topic_id = t.id
           WHERE t.course_id = %s""", (course_id,))["d"]

    flagged = fetchall(
        """SELECT DISTINCT i.id, i.question_md FROM check_runs cr
           JOIN interactions i ON cr.interaction_id = i.id
           JOIN subtopics s ON i.subtopic_id = s.id JOIN topics t ON s.topic_id = t.id
           WHERE t.course_id = %s AND cr.verdict = 'fail'""", (course_id,))

    # per-subtopic
    subs = fetchall(
        """SELECT s.id, s.name, s.description, s.partially_sourced, s.audit_score, s.audit_gaps,
                  t.name topic_name, t.calibrated_dl, t.ordinal t_ord, s.ordinal s_ord
           FROM subtopics s JOIN topics t ON s.topic_id = t.id
           WHERE t.course_id = %s ORDER BY t.ordinal, s.ordinal""", (course_id,))
    per_subtopic = []
    for st in subs:
        sid = st["id"]
        smcq = fetchone("SELECT count(*) n FROM interactions WHERE subtopic_id=%s AND type='mcq'", (sid,))["n"]
        sqa = fetchone("SELECT count(*) n FROM interactions WHERE subtopic_id=%s AND type='qa'", (sid,))["n"]
        sdiag = fetchone(
            "SELECT count(*) n FROM diagrams d JOIN interactions i ON d.interaction_id=i.id "
            "WHERE i.subtopic_id=%s", (sid,))["n"]
        ssrc = fetchall("SELECT url, title, type, published FROM sources WHERE subtopic_id=%s", (sid,))
        per_subtopic.append({
            "subtopic_id": str(sid), "name": st["name"], "description": st["description"],
            "topic": st["topic_name"], "calibrated_dl": st["calibrated_dl"],
            "mcqs": smcq, "qa": sqa, "illustrations": sdiag,
            "partially_sourced": st["partially_sourced"], "audit_score": float(st["audit_score"]) if st["audit_score"] is not None else None,
            "audit_gaps": st["audit_gaps"] or [],
            "sources": [{"url": s["url"], "title": s["title"], "type": s["type"],
                         "published": s["published"].isoformat() if s["published"] else None} for s in ssrc],
        })

    est = course.get("cost_estimate") or {}
    return {
        "course_id": course_id, "title": course["title"], "status": course["status"],
        "totals": {
            "mcqs": mcq, "qa": qa,
            "illustrations": {"total": sum(diagrams.values()),
                              "sourced": diagrams.get("sourced", 0),
                              "generated": diagrams.get("generated", 0)},
            "sources": {"total": total_sources, "by_format": sources_by_format},
            "newest_source": newest.isoformat() if newest else None,
            "flagged_for_review": len(flagged),
        },
        "cost": {
            "estimated": est.get("total_estimate"),
            "actual": float(course["cost_actual"]) if course["cost_actual"] is not None else None,
            "delta_abs": float(course["cost_delta_abs"]) if course["cost_delta_abs"] is not None else None,
            "delta_pct": float(course["cost_delta_pct"]) if course["cost_delta_pct"] is not None else None,
            "reconciliation": course["cost_reconciliation"],
        },
        "flagged_items": [{"interaction_id": str(f["id"]), "question": f["question_md"]} for f in flagged],
        "subtopics": per_subtopic,
    }
