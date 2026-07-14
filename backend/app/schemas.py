"""Typed I/O contracts shared across agents (mirrors the JSON in specs 01/03/05).

These are intentionally permissive (extra fields allowed) — agent code validates the
fields it needs and tolerates model drift, matching the "parse defensively" rule (03).
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---- intake (spec 01) -------------------------------------------------------
class IntentProfile(BaseModel):
    orientation: Literal["technical", "business", "general"] = "general"
    seniority: Literal["junior", "mid", "high"] = "mid"
    confidence: float = 0.5
    evidence: list[str] = Field(default_factory=list)
    needs_clarification: bool = True


class DomainGrounding(BaseModel):
    domain: str = "general"
    example_entities: list[str] = Field(default_factory=list)
    framing: str = "general"
    must_ground: bool = False
    confidence: float = 0.5


class ClarificationQ(BaseModel):
    q: str
    options: list[str] = Field(default_factory=list)
    answer: str | None = None
    multi_select: bool = False   # true when several options may be chosen (spec 01 §3)


class CourseContext(BaseModel):
    user_id: str | None = None
    raw_prompt: str
    raw_role: str
    intent: IntentProfile
    domain_grounding: DomainGrounding
    clarifications: list[ClarificationQ] = Field(default_factory=list)
    currency_mode: Literal["fundamentals", "latest_research"] = "fundamentals"
    assumptions: list[str] = Field(default_factory=list)
    personalization: dict = Field(default_factory=dict)   # learner profile (spec 03 §13)
    seed_material: str = ""                                # text from an uploaded PDF/deck (spec 05 §12)


# ---- curriculum (spec 03 §4) ------------------------------------------------
class SubtopicPlan(BaseModel):
    name: str
    description: str = ""
    order: int = 1
    target_question_count: int = 5
    first_interaction: str = "definition_mcq"


class TopicPlan(BaseModel):
    name: str
    order: int = 1
    calibrated_dl: int = 2
    rationale: str = ""
    subtopics: list[SubtopicPlan] = Field(default_factory=list)


class Curriculum(BaseModel):
    title: str
    topics: list[TopicPlan] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)


# ---- cost (spec 03 §6 / §6b) ------------------------------------------------
class CostEstimate(BaseModel):
    currency: str = "USD"
    total_estimate: float = 0.0
    raw_estimate: float = 0.0                              # before history calibration
    buffer_pct: int = 15
    by_phase: dict[str, float] = Field(default_factory=dict)
    by_subtopic: list[dict[str, Any]] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    tokens_estimate: int = 0
    calibration: dict | None = None                        # from similar past builds (03 §6, 06 §5)
    est_completion_minutes: int = 0                        # avg learner time to finish (item 10)


# ---- content package (spec 05 §3) -------------------------------------------
class TextChunk(BaseModel):
    id: str
    source_id: str
    text: str
    section: str | None = None
    page: int | None = None


class Figure(BaseModel):
    image_ref: str | None = None
    source_id: str | None = None
    caption: str | None = None
    kind: str = "diagram"
    license_hint: str | None = None


class ContentPackage(BaseModel):
    subtopic_id: str
    coverage_map: dict[str, list[str]] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    extracted: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    domain_grounding: dict[str, Any] = Field(default_factory=dict)
    target_question_count: int = 5
    recency: dict[str, Any] = Field(default_factory=dict)


# ---- checks (spec 03 §8-10) -------------------------------------------------
class CheckResult(BaseModel):
    verdict: Literal["pass", "fail"] = "pass"
    issues: list[str] = Field(default_factory=list)
    regen_hint: str | None = None
