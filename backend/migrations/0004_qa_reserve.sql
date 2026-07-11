-- Q&A follow-up root-cause redesign + weakness remediation reserve (spec 04 §4, 05 §10).
-- New file; earlier migrations are never edited.

-- Every interaction now has a ROLE so the runtime can keep the main learning sequence
-- (MCQs) separate from follow-up Q&A that only appear after a wrong MCQ:
--   main            → shown in the normal course sequence (MCQs)
--   followup_seed   → the pre-generated first follow-up Q&A for a subtopic (spec 04 §4)
--   followup_probe  → a root-cause probe Q&A generated at runtime from the reserve
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS role text NOT NULL DEFAULT 'main';
CREATE INDEX IF NOT EXISTS idx_interactions_role ON interactions(subtopic_id, role);

-- Weakness Remediation Reserve (spec 05 §10): extra material scouted at BUILD time by
-- the Root-Cause Weakness agent and kept as backup so runtime probe Q&A can be generated
-- WITHOUT any web scraping / MCP calls (which would be far too slow mid-session).
ALTER TABLE subtopics ADD COLUMN IF NOT EXISTS reserve jsonb;

-- Which root-cause probe round produced a response (0 = seed follow-up, 1..N = probes).
ALTER TABLE responses ADD COLUMN IF NOT EXISTS probe_round int NOT NULL DEFAULT 0;

-- Clarification questions may accept MULTIPLE answers (spec 01 §3) — e.g. "which areas of
-- RL matter to you?" is naturally multi-select. Stored answer is the joined selection.
ALTER TABLE clarification_qas ADD COLUMN IF NOT EXISTS multi_select boolean NOT NULL DEFAULT false;
