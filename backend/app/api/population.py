"""Course population / curriculum view (spec 05 §8, 06 §4, 07 §5). Counts are DERIVED
from persisted rows (not denormalised) and recomputed on read."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.db import fetchall, fetchone
from app.store import get_course

router = APIRouter(prefix="/api/courses", tags=["population"])


def _completion_minutes(course_id: str) -> dict:
    """Average learner time to finish, from the ACTUAL built interactions (spec 07, item 10)."""
    ct = get_settings().section("completion_time")
    rows = fetchall(
        """SELECT i.type, count(*) n FROM interactions i JOIN subtopics s ON i.subtopic_id=s.id
           JOIN topics t ON s.topic_id=t.id WHERE t.course_id=%s AND i.role='main'
           GROUP BY i.type""", (course_id,))
    minutes, scored = 0.0, 0
    for r in rows:
        minutes += r["n"] * float(ct.get(r["type"], 1.5))
        if r["type"] != "walkthrough":
            scored += r["n"]
    # allow for some wrong answers triggering a follow-up Q&A
    minutes += scored * float(ct.get("followup_allowance", 0.4)) * float(ct.get("qa", 2.5))
    return {"minutes": int(round(minutes))}


def _counts_where(course_id: str) -> str:
    return (
        "FROM interactions i JOIN subtopics s ON i.subtopic_id = s.id "
        "JOIN topics t ON s.topic_id = t.id WHERE t.course_id = %s")


@router.get("/{course_id}/illustrations")
def illustrations(course_id: str, limit: int = 12) -> dict:
    """Diagrams/illustrations for a course, with metadata — shown early to make the course
    feel exciting (spec 07 §5) and searchable (spec 05 §6)."""
    rows = fetchall(
        """SELECT d.blob_id, d.provenance, d.kind, d.caption, d.subtopic_name, d.source_url
           FROM diagrams d JOIN interactions i ON d.interaction_id = i.id
           JOIN subtopics s ON i.subtopic_id = s.id JOIN topics t ON s.topic_id = t.id
           WHERE t.course_id = %s AND d.blob_id IS NOT NULL
           ORDER BY d.provenance DESC LIMIT %s""", (course_id, limit))
    return {"illustrations": [
        {"blob_id": str(r["blob_id"]), "provenance": r["provenance"], "kind": r["kind"],
         "caption": r["caption"], "subtopic": r["subtopic_name"], "source_url": r["source_url"]}
        for r in rows]}


@router.get("/{course_id}/population")
def population(course_id: str) -> dict:
    course = get_course(course_id)
    if course is None:
        raise HTTPException(404, "course not found")

    # Interactions by type in the MAIN learner sequence (mcq/order/blanks/dragdrop/walkthrough),
    # plus follow-up Q&A counted separately (they only appear after a wrong answer).
    by_type = {r["type"]: r["n"] for r in fetchall(
        f"SELECT i.type, count(*) n {_counts_where(course_id)} AND i.role='main' GROUP BY i.type",
        (course_id,))}
    followups = fetchone(
        f"SELECT count(*) n {_counts_where(course_id)} AND i.role LIKE 'followup%%'", (course_id,))["n"]
    mcq = by_type.get("mcq", 0)

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
        sbytype = {r["type"]: r["n"] for r in fetchall(
            "SELECT type, count(*) n FROM interactions WHERE subtopic_id=%s AND role='main' GROUP BY type", (sid,))}
        sfollow = fetchone("SELECT count(*) n FROM interactions WHERE subtopic_id=%s AND role LIKE 'followup%%'", (sid,))["n"]
        smcq = sbytype.get("mcq", 0)
        sdiag = fetchone(
            "SELECT count(*) n FROM diagrams d JOIN interactions i ON d.interaction_id=i.id "
            "WHERE i.subtopic_id=%s", (sid,))["n"]
        ssrc = fetchall("SELECT url, title, type, published FROM sources WHERE subtopic_id=%s", (sid,))
        per_subtopic.append({
            "subtopic_id": str(sid), "name": st["name"], "description": st["description"],
            "topic": st["topic_name"], "calibrated_dl": st["calibrated_dl"],
            "mcqs": smcq, "by_type": sbytype, "followups": sfollow, "illustrations": sdiag,
            "partially_sourced": st["partially_sourced"], "audit_score": float(st["audit_score"]) if st["audit_score"] is not None else None,
            "audit_gaps": st["audit_gaps"] or [],
            "sources": [{"url": s["url"], "title": s["title"], "type": s["type"],
                         "published": s["published"].isoformat() if s["published"] else None} for s in ssrc],
        })

    # Build progress (spec 07 §5): subtopics with generated content vs total.
    total_subs = len(subs)
    built_subs = fetchone(
        """SELECT count(DISTINCT s.id) n FROM subtopics s JOIN topics t ON s.topic_id = t.id
           JOIN interactions i ON i.subtopic_id = s.id AND i.role = 'main'
           WHERE t.course_id = %s""", (course_id,))["n"]
    progress_pct = round(100 * built_subs / total_subs) if total_subs else (100 if course["status"] == "built" else 0)
    if course["status"] == "built":
        progress_pct = 100

    est = course.get("cost_estimate") or {}
    return {
        "course_id": course_id, "title": course["title"], "status": course["status"],
        "progress": {"pct": progress_pct, "built_subtopics": built_subs, "total_subtopics": total_subs},
        "completion": _completion_minutes(course_id),
        "totals": {
            "mcqs": mcq, "qa": followups, "by_type": by_type, "followups": followups,
            "interactions_total": sum(by_type.values()),
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
