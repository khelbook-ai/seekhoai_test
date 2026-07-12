# Seekhai_test — Product & Engineering Spec

> Adaptive, agent-driven learning tool. A user states a **topic** and their **role**;
> Seekhai_test researches the topic on the live web, builds a calibrated course, and
> teaches entirely through interactions (MCQ, Q&A, diagrams) with per-question hints,
> content panels, scoring, and weakness tracking.

This repository is written **spec-first**. Each file under `specs/` is a self-contained
module you can hand to Claude Code (or GLM 5.2) one at a time. Implement in the order
given by `specs/08-roadmap.md`. Treat these documents as the **source of truth** — when
code and spec disagree, fix one of them deliberately, don't let them drift.

---

## How to use this in Claude Code (spec-driven development)

1. **Read `README.md` + `specs/08-roadmap.md` first.** They define scope, phases and the
   open decisions you must resolve before or during each phase.
2. **Resolve open decisions** in `specs/08-roadmap.md#open-decisions`. Several defaults are
   already chosen; confirm or override them, then update the relevant spec file so the
   decision is recorded in one place.
3. **Work phase by phase.** Each phase in the roadmap names the spec sections it depends on
   and the vertical slice it should ship. Don't build agents before the data model exists.
4. **Keep specs authoritative.** When you change behaviour, edit the spec in the same PR.
   Ask Claude Code to "update the spec to match" whenever you deviate.
5. **Generate tasks from specs.** Each agent in `specs/03-agents.md` and each table in
   `specs/06-data-and-feedback.md` maps to a discrete implementation task.

---

## Spec index

| File | Covers |
|------|--------|
| `specs/01-personas-and-intent.md` | Intent classification, seniority, clarification questioning, domain grounding |
| `specs/02-architecture-and-orchestration.md` | System architecture, LangGraph graphs, state objects, tech stack |
| `specs/03-agents.md` | Contract (I/O, model, prompts, failure modes) for every agent |
| `specs/04-interaction-and-scoring.md` | Interaction engine: MCQ, Q&A, hints, content panel, scoring, escalation, adaptivity, weaknesses |
| `specs/05-content-pipeline-and-tools.md` | Course scouting, generation, option/domain/accuracy checkers, diagram sourcing |
| `specs/06-data-and-feedback.md` | Postgres schema, feedback `.md` files, capture requirements, observability |
| `specs/07-frontend-ui.md` | UI/UX spec: layout, typography, button placement, screens |
| `specs/08-roadmap.md` | Delivery phases + open decisions |

---

## Vision (one paragraph)

Most learning tools dump content and quiz afterwards. Seekhai_test inverts that: the very
first thing a learner sees on a topic is a question, and every piece of content is served
*in service of* an interaction the learner is trying to complete. The system meets each
learner where they are — a VP at a bank and a junior ML engineer asking about the same
topic get different framing, difficulty, and examples — and it stays current by researching
the live web (including fresh research papers and their figures) at build time.

---

## Scope

**In scope (now):** AI-related courses only (LLMs, RL, agents, ML systems, etc.). The
Course Architect, Scout, and generators are tuned for AI sources (arXiv, official docs,
reputable AI blogs). Single-tenant / small tester group is fine for early phases.

**Packaging:** the whole app runs locally via **Docker Compose** — three services (`db`
Postgres, `backend` FastAPI, `frontend` nginx-served SPA). The backend applies migrations on
startup; the frontend proxies `/api` to the backend (single origin, no CORS). `docker compose
up --build` after setting `OPENROUTER_API_KEY` is the shipping path. This is still local-first
(no cloud dependency).

**Explicitly out of scope (for now):**
- Non-AI subjects. Do **not** invest in generalising the curriculum engine.
- **Cloud hosting / AWS / S3.** Everything runs locally: **local PostgreSQL** for all data and
  binary blobs, and the local filesystem for the `.md` feedback tree. Binary storage sits
  behind a `BlobStore` interface so S3 can be added later without touching callers.
- Native mobile apps (web-responsive is enough).
- Multi-language content (English only for v1; the name is bilingual but content is EN).
- Payment/billing (cost estimation is shown to the user but not charged).

---

## Glossary

| Term | Meaning |
|------|---------|
| **DL** | Difficulty Level, one of `DL1` (easy), `DL2` (medium), `DL3` (hard). |
| **Interaction** | A single learning unit the learner acts on: an MCQ or a Q&A item. Diagrams, hints and the content panel attach to an interaction. |
| **Content panel** | Per-interaction explanatory material ("how it works", definitions) revealed via the **Content** button. |
| **Hint ladder** | The 3 escalating hints attached to an interaction (general → specific → answer). |
| **Persona** | The learner's classified orientation (technical / business / general) × seniority (junior / mid / high) + domain grounding. |
| **Domain grounding** | The concrete domain the content must be framed in, inferred from the role (e.g. "VP of AmEx" → American Express, credit cards, payments). |
| **Course build** | The offline pipeline that turns an approved curriculum into generated, checked, verified content. |
| **Learning session** | The runtime loop where a learner works through interactions. |
| **Content feedback** | A human (usually the learner/tester) commenting on the *quality of a specific interaction's content*. Persisted as `.md`. |
| **Application feedback** | A tester commenting on *how a page/flow works or should work*. |
| **Weakness** | A topic/subtopic where the learner repeatedly errs; tracked and surfaced. |
| **Content Package** | The fully-extracted, self-contained material the Scout hands to the generators per subtopic — the contract that keeps scouting and generation in sync (`05 §3`). |
| **Scouting Auditor** | An independent Sonnet-class LLM that gates generation until a subtopic's Content Package is genuinely comprehensive (`05 §4`). |
| **Prompt Guardrail** | Always-on checks (injection, off-topic, safety, PII) at every free-text input point (`03 §0`). |
| **Token-free replay** | Restarting/resuming a built course serves persisted content only — no regeneration, no token spend (`06 §6`). |
| **Cost reconciliation** | Post-build comparison of actual vs estimated cost, with the reason for the delta (`03 §6b`, `06 §5`). |
