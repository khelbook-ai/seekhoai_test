"""Deterministic grading + answer-stripping for the richer interaction types (spec 04 §1).
These behave exactly like an MCQ: all-or-nothing correct, and the served payload never leaks
the answer."""
from app import interactions as I


def test_order_grading_and_no_leak():
    payload = {"items": [{"id": "a", "text": "1"}, {"id": "b", "text": "2"}, {"id": "c", "text": "3"}],
               "correct_order": ["a", "b", "c"]}
    assert I.grade("order", payload, {"order": ["a", "b", "c"]}) is True
    assert I.grade("order", payload, {"order": ["b", "a", "c"]}) is False
    assert I.grade("order", payload, {}) is False
    pub = I.public_payload("iid-1", "order", payload)
    assert "correct_order" not in pub            # answer stripped
    assert sorted(x["id"] for x in pub["items"]) == ["a", "b", "c"]
    assert [x["id"] for x in pub["items"]] != ["a", "b", "c"]  # not pre-solved


def test_blanks_grading_case_insensitive_and_no_leak():
    payload = {"segments": ["The ", {"blank": "b1"}, " exposes ", {"blank": "b2"}, "."],
               "blanks": [{"id": "b1", "answer": "MCP"}, {"id": "b2", "answer": "tools"}],
               "bank": ["MCP", "tools", "REST"]}
    assert I.grade("blanks", payload, {"answers": {"b1": "mcp", "b2": "Tools"}}) is True
    assert I.grade("blanks", payload, {"answers": {"b1": "MCP", "b2": "prompts"}}) is False
    assert I.grade("blanks", payload, {"answers": {"b1": "MCP"}}) is False   # incomplete
    pub = I.public_payload("iid-2", "blanks", payload)
    assert all("answer" not in b for b in pub["blanks"])   # answers stripped
    assert set(pub["bank"]) == {"MCP", "tools", "REST"}


def test_dragdrop_grading_and_no_leak():
    payload = {"boxes": [{"id": "box1", "label": "Client"}, {"id": "box2", "label": "Server"}],
               "entities": [{"id": "e1", "text": "Host"}, {"id": "e2", "text": "Provider"}, {"id": "e3", "text": "x"}],
               "correct_mapping": {"box1": "e1", "box2": "e2"}}
    assert I.grade("dragdrop", payload, {"mapping": {"box1": "e1", "box2": "e2"}}) is True
    assert I.grade("dragdrop", payload, {"mapping": {"box1": "e2", "box2": "e1"}}) is False
    assert I.grade("dragdrop", payload, {"mapping": {"box1": "e1"}}) is False
    pub = I.public_payload("iid-3", "dragdrop", payload)
    assert "correct_mapping" not in pub
    assert len(pub["entities"]) == 3


def test_generator_payload_validation():
    from app.agents.generators.interaction import _validate_payload
    # reversed/invalid order is rejected (None -> fallback)
    assert _validate_payload("order", {"items": [{"id": "a", "text": "x"}], "correct_order": ["a"]}) is None
    ok = _validate_payload("dragdrop", {"boxes": [{"id": "b1", "label": "L1"}, {"id": "b2", "label": "L2"}],
                                        "entities": [{"id": "e1", "text": "A"}, {"id": "e2", "text": "B"}],
                                        "correct_mapping": {"b1": "e1", "b2": "e2"}})
    assert ok and ok["correct_mapping"] == {"b1": "e1", "b2": "e2"}
