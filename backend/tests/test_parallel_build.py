"""Bounded-concurrency subtopic build (spec 02 §5). Stubs the heavy per-subtopic work so
the dispatch logic can be tested without a DB or LLM: every subtopic must be built exactly
once, reconciliation runs once at the end, and workers actually overlap."""
import threading
import time

from app import pipeline


def _setup(monkeypatch, n_subtopics, max_workers):
    monkeypatch.setattr(pipeline, "get_course", lambda cid: {"currency_mode": "fundamentals"})
    monkeypatch.setattr(pipeline, "_load_intent", lambda cid: ({"orientation": "general"}, {"domain": "x"}))
    monkeypatch.setattr(pipeline, "list_subtopics",
                        lambda cid: [{"subtopic_id": i, "name": f"st{i}"} for i in range(n_subtopics)])
    monkeypatch.setattr(pipeline.events, "emit", lambda *a, **k: None)
    monkeypatch.setattr(pipeline.cost_reconciliation, "reconcile",
                        lambda cid, notes="": {"actual": 0.0, "estimated": 0.0, "delta_pct": 0})

    class _S:
        def section(self, key):
            return {"max_concurrent_subtopics": max_workers}
    monkeypatch.setattr(pipeline, "get_settings", lambda: _S())


def test_all_subtopics_built_once_and_overlap(monkeypatch):
    built, lock = [], threading.Lock()
    live, peak = {"n": 0}, {"n": 0}

    def fake_build(course_id, st, si, total, *a, **k):
        with lock:
            live["n"] += 1
            peak["n"] = max(peak["n"], live["n"])
        time.sleep(0.05)                       # force overlap window
        with lock:
            built.append(st["name"]); live["n"] -= 1

    monkeypatch.setattr(pipeline, "_build_subtopic", fake_build)
    _setup(monkeypatch, n_subtopics=6, max_workers=4)

    pipeline.run_content_pipeline("course-x")

    assert sorted(built) == [f"st{i}" for i in range(6)]   # each built exactly once
    assert peak["n"] >= 2                                    # genuinely ran in parallel


def test_single_worker_is_sequential(monkeypatch):
    built = []
    monkeypatch.setattr(pipeline, "_build_subtopic",
                        lambda cid, st, si, total, *a, **k: built.append(st["name"]))
    _setup(monkeypatch, n_subtopics=3, max_workers=1)

    pipeline.run_content_pipeline("course-y")
    assert built == ["st0", "st1", "st2"]                   # in order, no pool


def test_one_failure_does_not_abort_build(monkeypatch):
    built = []

    def fake_build(course_id, st, si, total, *a, **k):
        if st["name"] == "st1":
            raise RuntimeError("boom")
        built.append(st["name"])

    reconciled = []
    monkeypatch.setattr(pipeline, "_build_subtopic", fake_build)
    _setup(monkeypatch, n_subtopics=4, max_workers=3)
    monkeypatch.setattr(pipeline.cost_reconciliation, "reconcile",
                        lambda cid, notes="": reconciled.append(cid) or {"actual": 0.0, "estimated": 0.0, "delta_pct": 0})

    pipeline.run_content_pipeline("course-z")                # must NOT raise
    assert set(built) == {"st0", "st2", "st3"}               # survivors built
    assert reconciled == ["course-z"]                        # build still finalizes
