-- Round 3: user signup + personalization, content-reuse library, diagram search metadata,
-- cost-delta .md path. New file; earlier migrations are never edited.

-- Simple name-only signup (spec 01 §5). No auth/password — the point is to attribute a
-- learner's courses/answers/weaknesses so the Personalization agent can tune to them.
ALTER TABLE users ADD COLUMN IF NOT EXISTS name text;

-- A per-user, cross-course learning profile the Personalization agent maintains and the
-- Architect/Generators consume (spec 03 §13).
CREATE TABLE IF NOT EXISTS user_profiles (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users(id),
  summary_md  text,                                   -- human-readable "who this learner is"
  directives  jsonb,                                  -- structured tuning hints for generators
  signals     jsonb,                                  -- derived stats (weak areas, pace, accuracy)
  updated_at  timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id)
);

-- Content-reuse library (spec 05 §11). Every built subtopic is registered here so a later
-- course on a similar subtopic can REUSE the generated interactions/diagrams instead of
-- re-scouting and re-generating (huge time + token saving).
CREATE TABLE IF NOT EXISTS content_library (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subtopic_name     text,
  subtopic_norm     text,                             -- normalized key for matching
  topic_norm        text,
  domain            text,
  currency_mode     text,
  source_subtopic_id uuid REFERENCES subtopics(id),
  source_course_id  uuid REFERENCES courses(id),
  dl                int,
  mcq_count         int,
  qa_count          int,
  illustration_count int,
  keywords          jsonb,                            -- searchable terms (concepts, sources)
  created_at        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_library_norm ON content_library(subtopic_norm, domain);

-- Illustration/diagram search metadata (spec 05 §6) so figures are easy to find + reuse.
ALTER TABLE diagrams ADD COLUMN IF NOT EXISTS kind text;          -- diagram|chart|figure|schematic
ALTER TABLE diagrams ADD COLUMN IF NOT EXISTS caption text;
ALTER TABLE diagrams ADD COLUMN IF NOT EXISTS keywords jsonb;
ALTER TABLE diagrams ADD COLUMN IF NOT EXISTS subtopic_name text;

-- Where the human-readable cost-reconciliation .md was written (spec 06 §5).
ALTER TABLE courses ADD COLUMN IF NOT EXISTS cost_md_path text;

-- Interactions reused from the library point back at their origin (provenance for the UI).
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS reused_from uuid;
