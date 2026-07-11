# 08 — Roadmap & Open Decisions

## Delivery phases

Build in this order. Each phase ships a working vertical slice and names its spec dependencies.

### Phase 0 — Foundations
*Depends on: `02`, `06`.*
- Repo scaffold, `models.yaml`, config surface (`04 §8`).
- Postgres schema + migrations (`06 §1`, incl. `blobs`, `feedback_images`, `guardrail_events`,
  cost columns). **Local blob storage** (`BlobStore` → Postgres `bytea`) + local `.md`/asset
  directory wired.
- MCP server skeleton (tool catalog stubbed, `05 §2`).
- **Prompt Guardrail** component wired at all input points (`03 §0`) — cheap to add early.
- **Session/build graph separation + Postgres checkpointer** so replay is token-free from day
  one (`06 §6`).
- Observability façade (LangSmith default) (`06 §3`).
- **Slice:** one hardcoded AI subtopic → one DL2 definition MCQ with Content + Hint + scoring,
  rendered on the learning screen. No generation yet.

### Phase 1 — Intake & planning
*Depends on: `01`, `02`, `03 §4–6`, `07 §3–4`.*
- Intent + Clarification + Domain grounding agents.
- Course Architect (curriculum + per-topic DL calibration).
- Cost Estimator + **cost-approval HITL gate**.
- Course-creation page + cost-approval screen.
- **Slice:** prompt+role → clarification → curriculum → cost → approval, all persisted.

### Phase 2 — Content pipeline (the core; largest phase)
*Depends on: `03 §5–10`, `05`, `06`.*
- Course Scout + the **MCP extractor catalog** (`web_scrape`, `paper_downloader`, `pdf_extractor`,
  `slides_extractor`, `doc_extractor`, `html_article_extractor`, `illustration_scraper`,
  `vision_image_extractor`, `transcript_extractor`, … + format router) (`05 §2`).
- **Content Package** handoff so generators read only scouted material (`05 §3`).
- **Scouting Comprehensiveness Auditor** (Sonnet-class) + scout-again loop (`05 §4`).
- Content/MCQ/Q&A/Hint/Diagram generators.
- Option, Domain, and Verification (Gemini) checkers + regen loops.
- **Cost Reconciliation** (actual vs estimate + reason) (`03 §6b`).
- Course-population/curriculum view with **counts** (MCQs, illustrations, sources) and cost delta.
- **Slice:** approved curriculum → comprehensively scouted → generated, checked, verified content
  visible in the population UI, with real counts and a cost reconciliation.

### Phase 3 — Learning engine
*Depends on: `03 §11–12`, `04`.*
- Full interaction runtime, hint ladder, content panels, scoring.
- MCQ→Q&A escalation + Q&A Grader.
- Adaptive Controller (DL adaptation) + weakness tracking.
- Progress & weakness dashboard.
- **Slice:** a learner completes a subtopic end-to-end with adaptive difficulty and sees
  weaknesses.

### Phase 4 — Feedback & observability polish
*Depends on: `06`, `07`.*
- Content-feedback `.md` pipeline (course/subtopic folders) **with image upload + text-linking**
  embedded inline (`06 §2`).
- Application feedback on relevant pages, with images and the **"restart with content"** control
  (token-free replay, `06 §6`).
- Grader-output cache so re-running the same Q&A answer during testing doesn't re-spend.
- Full metric capture incl. generation speed; LangSmith dashboards + optional Phoenix eval.

### Phase 5 — "Stay current" path
*Depends on: `05 §2`.*
- End-to-end recent-papers flow: date-filtered scouting → paper download → vision figure
  extraction → grounded generation → verification.
- **Slice:** "keep me current on recent RL" produces a course built from fresh papers, with
  real paper figures attached to questions.

---

## Open decisions

Defaults are chosen so the build isn't blocked; confirm or override, then edit the cited spec.

| # | Decision | Default | Where |
|---|----------|---------|-------|
| D1 | Score floor — allow negative item scores? | Clamp at **0** | `04 §3` |
| D2 | Does a wrong MCQ score 0, with the escalated Q&A scored separately? | **Yes** | `04 §3–4` |
| D3 | Q&A partial-credit mapping | full 1.0 / partial 0.5 / incorrect 0 | `04 §3` |
| D4 | DL adaptation thresholds (promote/demote) | promote after 2, demote after 2 | `04 §5` |
| D5 | Weakness threshold definition | wrong MCQ or Q&A below full | `04 §6` |
| D6 | Max clarification questions & zero-question condition | 10 max; 0 if confidence ≥0.85 & unambiguous | `01 §3` |
| D7 | Who edits `target_question_count` — Architect only, or user-adjustable in population UI? | Architect sets; **not** user-editable in v1 | `05 §6`, `03 §4` |
| D8 | When no source figure exists, generate an SVG schematic? | **Yes**, with provenance recorded | `05 §4` |
| D9 | Checker regen retries before human-review flag | 2 | `04 §8`, `05 §1` |
| D10 | Observability: LangSmith primary, Phoenix pluggable? | **Yes** | `06 §3` |
| D11 | Auth / multi-tenant scope for early phases | Single tester group, light auth | `README` scope |
| D12 | "Tester" vs "student" roles — same person early on? | Same person can do both; role tag on feedback | `06 §2`, `07` |
| D13 | Course-completion criteria (when is a course "done") | All subtopics attempted; **define pass bar later** | `04` |
| D14 | Cost currency + whether to also show token counts | USD + show tokens | `03 §6` |
| D15 | `MAX_SCOUT_ROUNDS` before a subtopic is marked "partially sourced" | 3 | `05 §4` |
| D16 | Cache runtime grader outputs (keyed by interaction+answer) for token-free testing | **Yes** | `06 §6` |
| D17 | Feedback image upload limits (types, size, count per entry) | png/jpg/webp, ≤10MB, ≤10/entry | `06 §2`, `07` |
| D18 | "Restart with content" default — resume last session vs fresh session | Offer both; default **resume** | `06 §6`, `07 §3` |
| D19 | Guardrail strictness + whether a trusted tester can override a block | Strict; tester override with logged reason | `03 §0` |
| D20 | Which extractor formats to build first for AI courses | pdf + html + slides + vision figures first | `05 §2` |
| D21 | Scouting Auditor pass threshold (`score` to accept) | 0.8 | `05 §4` |

### Things intentionally deferred (not now)
- Non-AI subjects, native mobile, multi-language content, billing/payments.
- **Cloud hosting / AWS / S3** — everything runs locally (local Postgres + local filesystem).
  Binary storage is behind a `BlobStore` interface so S3 can return later with no caller changes.

---

## Definition of done (per interaction, as a quality bar)
An interaction is "ready" when: it has 4 valid options (MCQ) or a rubric (Q&A); a personalized
content panel; a 3-rung hint ladder; an optional question-level diagram with provenance; it has
passed Option + Domain + Verification checks (or is explicitly flagged for human review); and
its generation metrics (model, tokens, latency) are recorded.
