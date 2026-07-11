# Claude Code — Kickoff Instructions for Seekhai_test

Use this file as a running script for prompting Claude Code. Give the steps **in
order**, one at a time, and don't move to the next step until the current one is
confirmed working. Copy each numbered block as-is into Claude Code.

---

## 0. One-time setup (before opening Claude Code)

1. Unzip `seekhai-project.zip` and `seekhai-test-spec.zip`.
2. Place them as **siblings** in the same parent folder:
   ```
   some-folder/
   ├── seekhai/                 ← open THIS in Claude Code
   └── seekhai-test-spec/
   ```
3. Open `seekhai/` (not the parent) as the Claude Code working directory.

---

## 1. Orientation

```
Read README.md in this repo, and read all the files in ../seekhai-test-spec/specs/
so you understand the full product spec. This repo is a Phase 0 scaffold — get
oriented before changing anything.
```

## 2. Verify the environment runs as-is

```
Get this running exactly as the README describes: start Postgres with
docker-compose, run the backend migration and seed scripts, start the FastAPI
backend, and start the Vite frontend. Fix anything that's broken due to my local
environment (Python/Node versions, missing tools, port conflicts) but don't change
the architecture. Tell me once I can open http://localhost:5173 and answer the
seeded MCP question.
```

## 3. Confirm the tests pass locally

```
Run the backend test suite (pytest in backend/) and confirm all scoring tests
pass in my environment.
```

## 4. Sanity-check before building forward

```
Before we move to Phase 1, walk me through: which parts of the code are real
logic vs. stubs (per the table in README.md), and confirm the model IDs in
backend/config/models.yaml — I need to check those against the current
GLM/Gemini/Anthropic catalogs before any real model calls happen.
```

## 5. Start Phase 1 (only after 2–4 are confirmed working)

```
Now implement Phase 1 from specs/08-roadmap.md: the Prompt Guardrail (replace the
stub in app/guardrail.py with real classification), Intent Classification,
Clarification, and Domain Grounding agents from specs/01-personas-and-intent.md,
the Course Architect and Cost Estimator from specs/03-agents.md, and wire the
cost-approval HITL gate into app/graphs/build_graph.py. Build the course-creation
page and cost-approval screen per specs/07-frontend-ui.md §3–4. Ask me before
adding any new dependency or changing the DB schema — if the schema needs to
change, write a new migration file rather than editing 0001_init.sql.
```

---

## Standing rules — repeat/pin these throughout the whole build

Paste these once near the start of the session (or into a `CLAUDE.md` in the repo
root so Claude Code picks them up automatically every session):

```
- Keep specs and code in sync — if you deviate from a spec file, update that spec
  file in the same change and tell me why.
- Never hardcode a model ID or prompt string in agent logic — resolve models from
  config/models.yaml and keep prompts in a prompts/ folder.
- This is local-only — no AWS/S3 calls anywhere.
- Every agent call must record model, tokens in/out, latency, and cost
  (generation_metrics table) — this is a hard requirement, not optional polish.
- The build graph and the session graph stay separate. Learning-session code must
  never trigger content regeneration.
```

---

## Later phases (for reference — don't hand these over yet)

Once Phase 1 is solid and reviewed, use the same pattern for the remaining
phases in `specs/08-roadmap.md`:

- **Phase 2** — content pipeline: MCP extractor catalog, Content Package handoff,
  Scouting Comprehensiveness Auditor, generators, checkers, cost reconciliation.
- **Phase 3** — learning engine: hint ladder, MCQ→Q&A escalation, Q&A grader,
  adaptive controller, weakness tracking, dashboard.
- **Phase 4** — feedback polish: image upload + text-linking in `.md` feedback,
  "restart with content" token-free replay, full observability.
- **Phase 5** — live "stay current" path: recent-paper scouting → figure
  extraction → grounded generation.

For each, the prompt shape is the same: *"Implement Phase N from
specs/08-roadmap.md, using [specific spec files] for the contracts. Ask me before
[schema changes / new dependencies / anything not in the spec]."*
