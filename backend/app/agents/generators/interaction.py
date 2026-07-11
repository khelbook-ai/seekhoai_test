"""Unified interaction generator (spec 03 §7, 04 §1). The agent CHOOSES the best interaction
format for each concept — mcq / order / blanks / dragdrop — and generates it. All formats are
scored like an MCQ (correct/incorrect) and escalate to the same Q&A root-cause loop on a wrong
answer. Non-mcq bodies are validated for internal consistency so the runtime can grade them
deterministically (no runtime LLM).
"""
from __future__ import annotations

from app.agents.generators.content import _common_args
from app.llm import complete_json
from app.prompts import render

VALID = {"mcq", "order", "blanks", "dragdrop"}


def generate_interaction(subtopic: dict, package: dict, intent: dict, dl: int,
                         course_id: str | None = None) -> dict:
    args = _common_args(subtopic, package, intent, dl)
    data, res = complete_json("interaction_generator", "You output only JSON.",
                              render("gen_interaction", **args), phase="generation",
                              max_tokens=3000, course_id=course_id)
    data = data if isinstance(data, dict) else {}
    t = (data.get("type") or "mcq").lower()
    if t not in VALID:
        t = "mcq"
    item = {"_type": t, "_dl": dl,
            "_gen": {"model": res.model, "tin": res.tokens_in, "tout": res.tokens_out,
                     "latency_ms": res.latency_ms},
            "question_md": data.get("question_md", ""),
            "content_panel_md": data.get("content_panel_md", ""),
            "hints": data.get("hints", [])}
    if t == "mcq":
        item["options"] = data.get("options", [])
    else:
        item["payload"] = _validate_payload(t, data)
        if item["payload"] is None:            # fell back — treat as mcq if options exist
            if data.get("options"):
                item["_type"] = "mcq"; item["options"] = data["options"]
            else:
                raise ValueError(f"invalid {t} payload and no mcq fallback")
    return item


def _validate_payload(t: str, d: dict) -> dict | None:
    try:
        if t == "order":
            items = [{"id": str(i["id"]), "text": i["text"]} for i in d["items"] if i.get("text")]
            ids = {i["id"] for i in items}
            order = [str(x) for x in d["correct_order"] if str(x) in ids]
            if len(items) < 2 or len(order) != len(items):
                return None
            return {"items": items, "correct_order": order}
        if t == "blanks":
            blanks = [{"id": str(b["id"]), "answer": str(b["answer"])} for b in d["blanks"] if b.get("answer")]
            segs = []
            for s in d["segments"]:
                if isinstance(s, dict) and s.get("blank"):
                    segs.append({"blank": str(s["blank"])})
                elif isinstance(s, str):
                    segs.append(s)
            bank = [str(w) for w in d.get("bank", []) if str(w).strip()]
            for b in blanks:                    # ensure each answer is in the bank
                if b["answer"] not in bank:
                    bank.append(b["answer"])
            bids = {b["id"] for b in blanks}
            if not blanks or not any(isinstance(s, dict) and s["blank"] in bids for s in segs):
                return None
            return {"segments": segs, "blanks": blanks, "bank": sorted(set(bank))}
        if t == "dragdrop":
            boxes = [{"id": str(b["id"]), "label": b["label"]} for b in d["boxes"] if b.get("label")]
            ents = [{"id": str(e["id"]), "text": e["text"]} for e in d["entities"] if e.get("text")]
            eids = {e["id"] for e in ents}
            mapping = {str(k): str(v) for k, v in d["correct_mapping"].items() if str(v) in eids}
            box_ids = {b["id"] for b in boxes}
            mapping = {k: v for k, v in mapping.items() if k in box_ids}
            if len(boxes) < 2 or len(mapping) != len(boxes):
                return None
            return {"boxes": boxes, "entities": ents, "correct_mapping": mapping}
    except (KeyError, TypeError, ValueError):
        return None
    return None
