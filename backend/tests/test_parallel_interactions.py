"""Interaction-level parallelism within a subtopic (spec 02 §5). Stubs generation + checkers
so we test the dispatch guarantees without LLM/DB: order is preserved (definition MCQ stays
first) and each interaction is isolated (no cross-item 'fix'-hint bleed → agents stay aligned).
"""
import threading
import time

from app import pipeline


def _patch(monkeypatch, gen_calls, seen_desc, lock):
    # plan: definition MCQ first, then a QA, then an MCQ (order must be preserved)
    specs = [{"kind": "mcq", "dl": 1, "definition": True},
             {"kind": "qa", "dl": 1, "definition": False},
             {"kind": "mcq", "dl": 2, "definition": False}]
    monkeypatch.setattr(pipeline.gen, "plan_interactions", lambda pkg: specs)
    monkeypatch.setattr(pipeline.events, "emit", lambda *a, **k: None)

    def fake_mcq(st, package, intent, dl, *, definition=False, course_id=None):
        with lock:
            gen_calls.append(("mcq", dl, definition))
            seen_desc.append(st["description"])   # record the description each item sees
        time.sleep(0.03)                          # force overlap
        return {"_type": "mcq", "_dl": dl, "question_md": f"q{dl}",
                "options": [{"text": t, "is_correct": i == 0} for i, t in enumerate("abcd")]}

    def fake_qa(st, package, intent, dl, *, course_id=None):
        with lock:
            gen_calls.append(("qa", dl, False)); seen_desc.append(st["description"])
        time.sleep(0.03)
        return {"_type": "qa", "_dl": dl, "question_md": "open", "qa_rubric": {}}

    monkeypatch.setattr(pipeline.gen, "generate_mcq", fake_mcq)
    monkeypatch.setattr(pipeline.gen, "generate_qa", fake_qa)
    # checkers always pass → no regen, so 'description' must stay pristine for every item
    monkeypatch.setattr(pipeline.semantic, "domain_check", lambda *a, **k: {"on_domain": True})
    monkeypatch.setattr(pipeline.semantic, "verify", lambda *a, **k: {"verdict": "pass"})

    class _S:
        def section(self, key):
            return {"max_regen_retries": 2, "max_concurrent_interactions": 4}
    monkeypatch.setattr(pipeline, "get_settings", lambda: _S())


def test_order_preserved_and_items_isolated(monkeypatch):
    gen_calls, seen_desc, lock = [], [], threading.Lock()
    _patch(monkeypatch, gen_calls, seen_desc, lock)

    st = {"name": "Sub", "description": "BASE"}
    results = pipeline._generate_and_check(st, {"_dl": 1}, {"orientation": "general"},
                                           {"domain": "x"}, "course-1")

    # order preserved: definition MCQ first, QA second, MCQ third
    assert [r["_type"] for r in results] == ["mcq", "qa", "mcq"]
    # every interaction saw the pristine base description — no cross-item 'fix' bleed
    assert set(seen_desc) == {"BASE"}
    # the caller's subtopic dict was not mutated by any worker
    assert st["description"] == "BASE"
    # definition MCQ got a valid answer_key from the option checker (integrity invariant)
    assert results[0]["answer_key"] in ("A", "B", "C", "D")
