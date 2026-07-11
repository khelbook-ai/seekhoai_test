-- Full-spec build additions (specs 03/05/06). New file; 0001_init.sql is never edited.

-- Grader-output cache (D16): re-running the same Q&A answer during testing must not
-- re-spend tokens. Keyed by (interaction, normalized answer).
CREATE TABLE IF NOT EXISTS grader_cache (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interaction_id uuid REFERENCES interactions(id),
  answer_norm    text NOT NULL,
  band           text,                       -- full|partial|incorrect
  rubric_hits    jsonb,
  rubric_misses  jsonb,
  feedback_md    text,
  created_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (interaction_id, answer_norm)
);

-- Scouting Auditor results per subtopic (spec 05 §4). `partially_sourced` already
-- exists on subtopics (0001); add the auditor score + gaps for the population UI.
ALTER TABLE subtopics ADD COLUMN IF NOT EXISTS audit_score numeric;
ALTER TABLE subtopics ADD COLUMN IF NOT EXISTS audit_gaps  jsonb;

-- LangGraph Postgres checkpointer thread id for a course build (spec 02 §2 / 06 §6).
ALTER TABLE courses ADD COLUMN IF NOT EXISTS build_thread_id text;

-- Provenance for generated diagrams already lives in `diagrams` (0001). Add an index
-- for the population counts that group by provenance.
CREATE INDEX IF NOT EXISTS idx_diagrams_interaction ON diagrams(interaction_id);
CREATE INDEX IF NOT EXISTS idx_sources_subtopic     ON sources(subtopic_id);
CREATE INDEX IF NOT EXISTS idx_checkruns_interaction ON check_runs(interaction_id);
CREATE INDEX IF NOT EXISTS idx_weaknesses_user       ON weaknesses(user_id);
