# 01 — Personas & Intent

This module turns the learner's raw input (`topic prompt` + `role`) into a **Persona** that
steers every downstream agent: how content is framed, what examples are used, and how
difficulty is calibrated.

The intake produces three things before any curriculum is built:

1. **Intent profile** — orientation + seniority.
2. **Domain grounding** — the concrete world the content lives in.
3. **Clarified requirements** — the answers to up to 10 disambiguating questions.

> **Guardrails first.** The course-creation prompt (and every later free-text input) passes
> through the **Prompt Guardrail** (`03-agents.md §0`) *before* intent classification runs:
> injection/jailbreak, off-topic/abuse, safety, and PII checks. A blocked prompt is returned to
> the UI with a clear reason and never reaches the agents.

---

## 1. Intent profile

Two independent axes.

### Orientation
| Value | Signal | Effect on content |
|-------|--------|-------------------|
| `technical` | "AI engineer", "ML researcher", "data scientist", code-heavy phrasing | Precise, mechanism-first, math/code where relevant, arXiv-grade sources |
| `business` | "VC", "VP", "PM", "founder", "investor", ROI/strategy phrasing | Framed around decisions, tradeoffs, cost, market impact; fewer internals |
| `general` | student, hobbyist, unclear role, "curious about" | Plain-language, analogy-first, gentle ramp |

### Seniority
| Value | Signal | Effect |
|-------|--------|--------|
| `junior` | "student", "just starting", "beginner", intern | Start heavier at DL1, more scaffolding, more content-panel depth |
| `mid` | practitioner language, some jargon used correctly | Balanced DL1→DL2 |
| `high` | "VP", "lead", "principal", "10 years", senior titles | Skew DL2→DL3, terse content, assume fundamentals |

**Output contract** (`IntentProfile`):
```json
{
  "orientation": "technical | business | general",
  "seniority": "junior | mid | high",
  "confidence": 0.0,
  "evidence": ["short quoted signals from the user input"],
  "needs_clarification": true
}
```

`confidence < CLARIFY_THRESHOLD` (default `0.7`) sets `needs_clarification = true`, which
forces the Clarification step to run even if the prompt looks complete.

---

## 2. Domain grounding

The **Content Domain** the material must be set in, inferred from role + prompt. This is
distinct from the *topic*: the topic is "MCP"; the domain grounding is the world the
examples come from.

Example: input role = *"VP of AmEx"*, topic = *"how LLMs work"* →
```json
{
  "domain": "American Express / credit cards / payments / financial services",
  "example_entities": ["cardholder data", "fraud detection", "transaction streams"],
  "framing": "business",
  "must_ground": true,
  "confidence": 0.82
}
```

Downstream:
- The **Content Generation** agents must set examples, MCQ scenarios and Q&A prompts inside
  this domain wherever the topic allows.
- The **Domain Checker Agent** (see `03-agents.md`) later validates generated content
  against this grounding and triggers regeneration if the content drifted to generic
  examples.

If `must_ground` is false (e.g. a plain "student"), grounding is neutral/general and the
Domain Checker only enforces topical relevance, not a specific business domain.

---

## 3. Clarification questioning ("Ask User Question Agent")

Before the curriculum is built, ask **at most 10** questions to disambiguate intent. Ask
**fewer** when the prompt is already unambiguous — down to **zero** questions if
`IntentProfile.confidence ≥ 0.85` **and** the topic is concrete **and** domain grounding is
resolved.

### Behaviour
- The agent first computes an **ambiguity score** across dimensions: scope breadth, depth
  expectation, orientation certainty, domain certainty, prior-knowledge, goal (exam prep vs
  overview vs staying current), and time budget.
- It generates the **smallest set** of questions that maximally reduces ambiguity, ranked
  by information gain. It stops early once residual ambiguity is below `AMBIGUITY_FLOOR`.
- Questions are **single-select, multi-select, or short-answer**, phrased for the learner's
  orientation, and rendered as tappable options in the UI (see `07-frontend-ui.md`). A question
  sets **`multi_select: true`** when it naturally admits several answers at once — e.g. *"which
  areas of recent RL progress matter most to you?"* (RLHF / offline & model-based / multi-agent
  / broad survey) — where forcing one choice would lose real signal. Either/or questions stay
  single-select. Multi-select answers are stored as the joined selection (`06 §1`).
- Hard cap: **10**. Never exceed it even if ambiguity remains — proceed and let the
  Course Architect make reasonable assumptions, recording them.

### Question bank dimensions (examples, not a fixed list)
| Dimension | Example question |
|-----------|------------------|
| Goal | "Are you preparing for something specific, or building a working understanding?" |
| Depth | "Do you want intuition, or mechanism-level detail?" |
| Prior knowledge | "Have you worked with <adjacent concept> before?" |
| Currency | "Should this focus on the latest research, or the established fundamentals?" |
| Scope | "Whole area, or one part of it?" |
| Time | "Quick tour or thorough course?" |

### Output contract
```json
{
  "questions_asked": [{"q": "...", "options": ["..."], "multi_select": false, "answer": "..."}],
  "residual_ambiguity": 0.0,
  "assumptions_made": ["if capped early, what the Architect should assume"]
}
```

All questions and answers are persisted (`clarification_qas`, see `06-data-and-feedback.md`)
because they are direct evidence of user intent and are useful for later eval.

---

## 4. Combined intake output

The intake phase emits a single `CourseContext` object consumed by the Course Architect:

```json
{
  "user_id": "...",
  "raw_prompt": "I'm a VP at AmEx, teach me how LLMs work",
  "raw_role": "VP of AmEx",
  "intent": { "orientation": "business", "seniority": "high", "confidence": 0.88 },
  "domain_grounding": { "domain": "American Express / payments", "must_ground": true },
  "clarifications": [ { "q": "...", "answer": "..." } ],
  "currency_mode": "fundamentals | latest_research",
  "assumptions": ["..."]
}
```

`currency_mode = latest_research` is the trigger for the live-web research path (fetch recent
papers, extract figures) described in `05-content-pipeline-and-tools.md`.
