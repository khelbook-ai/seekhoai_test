# Seekhai_test — Phase 0 scaffold

A running skeleton for the spec in `../seekhai-test-spec/`. Phase 0 ships the
**foundations + one vertical slice**: a single hand-authored AI question (the MCP
definition MCQ) rendered on the learning screen, with **Content**, **Hint**,
**scoring**, response capture, and the **content-feedback `.md`** pipeline — all
against **local Postgres**. No AI generation yet (that's Phase 2).

```
seekhai/
├── docker-compose.yml        # local Postgres only
├── backend/                  # FastAPI + LangGraph skeletons + MCP tool stubs
│   ├── config/               # settings.yaml + models.yaml (GLM/Gemini/Sonnet split)
│   ├── migrations/           # full schema (spec 06 §1)
│   ├── app/                  # config, db, blobstore, guardrail, scoring, api, graphs, mcp
│   ├── scripts/              # migrate.py, dev.sh
│   └── tests/                # scoring unit tests
└── frontend/                 # plain, big-text React learning screen (spec 07)
```

## Prerequisites
- Docker (for Postgres) — or your own local Postgres 16
- Python 3.11+
- Node 18+

## Run it

**1. Start Postgres**
```bash
docker compose up -d db
```

**2. Backend: migrate, seed, serve**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python scripts/migrate.py          # create the schema
python -m app.seed                 # insert the MCP definition MCQ
uvicorn app.main:app --reload --port 8000
```
(Or just `./scripts/dev.sh` after Postgres is up.)
API docs: http://localhost:8000/docs · health: http://localhost:8000/health

**3. Frontend**
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:5173 — answer the question, try **Content** and **Hint**
(watch the best-possible score drop by 1 per hint), submit, and leave content
feedback (written to `backend/data/feedback/understanding-mcp/mcp-fundamentals/…md`).

**4. Tests**
```bash
cd backend && pytest
```

## What's wired (and where to grow it)

| Piece | State | Spec | File |
|-------|-------|------|------|
| Full DB schema (incl. blobs, feedback_images, guardrail_events, cost cols) | ✅ real | 06 §1 | `migrations/0001_init.sql` |
| `models.yaml` (GLM/Gemini/Sonnet per-agent) | ✅ real config, no calls | 02 §4 | `config/models.yaml` |
| Config surface (scoring, adaptivity, scouting…) | ✅ real | 04 §8 | `config/settings.yaml` |
| Scoring (DL×2 − hints, floor, Q&A partial) | ✅ real + tested | 04 §3 | `app/scoring.py` |
| BlobStore (Postgres bytea, S3-swappable) | ✅ real | 02 §4 | `app/blobstore.py` |
| Content-feedback `.md` writer | ✅ real | 06 §2 | `app/feedback.py` |
| Prompt guardrail | 🟡 stub (logs events) | 03 §0 | `app/guardrail.py` |
| Observability façade | 🟡 no-op | 06 §3 | `app/observability.py` |
| Build + session LangGraph graphs | 🟡 skeleton | 02 §2/§3 | `app/graphs/` |
| MCP tool catalog (pdf/slides/vision/…) | 🟡 stubs, correct shapes | 05 §2 | `app/mcp/` |
| Learning slice (serve MCQ, hint, content, answer) | ✅ real | 08 Phase 0 | `app/api/learning.py` |
| Plain big-text UI | ✅ real | 07 | `frontend/src/` |

**Next (Phase 1):** intent + clarification + domain grounding agents, Course
Architect, Cost Estimator + approval gate — start filling the graph nodes in
`app/graphs/build_graph.py` and add real model calls behind `app/registry.py`.

## Notes
- **Model IDs in `models.yaml` are placeholders** — confirm each against its
  provider's current catalog before Phase 1 makes real calls.
- **Hints-used is client-reported on submit** for Phase 0 simplicity; Phase 3 moves
  hint-usage authority server-side (spec 04 §8).
