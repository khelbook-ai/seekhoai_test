-- Seekhai_test — initial schema (spec 06 §1). Local Postgres, all data + blobs.
CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()

-- Blobs: single home for all binary artefacts (diagrams, figures, feedback images).
CREATE TABLE blobs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  kind        text NOT NULL,                     -- diagram|figure|feedback_image|source_pdf|...
  mime        text NOT NULL,
  bytes       bytea NOT NULL,
  byte_len    int  NOT NULL,
  sha256      text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Users & persona ------------------------------------------------------------
CREATE TABLE users (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  role_raw    text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE intent_profiles (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid REFERENCES users(id),
  orientation      text,                          -- technical|business|general
  seniority        text,                          -- junior|mid|high
  confidence       numeric,
  domain_grounding jsonb,
  created_at       timestamptz NOT NULL DEFAULT now()
);

-- Course creation ------------------------------------------------------------
CREATE TABLE courses (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             uuid REFERENCES users(id),
  title               text,
  raw_prompt          text,
  currency_mode       text,                        -- fundamentals|latest_research
  curriculum          jsonb,
  accepted            boolean,
  cost_estimate       jsonb,
  cost_approved       boolean,
  cost_actual         numeric,                      -- reconciliation (spec 03 §6b)
  cost_delta_abs      numeric,
  cost_delta_pct      numeric,
  cost_reconciliation jsonb,
  status              text,
  created_at          timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE clarification_qas (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id  uuid REFERENCES courses(id),
  ordinal    int,
  question   text,
  options    jsonb,
  answer     text
);

CREATE TABLE topics (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id     uuid REFERENCES courses(id),
  name          text,
  ordinal       int,
  calibrated_dl int,
  rationale     text
);

CREATE TABLE subtopics (
  id                    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  topic_id              uuid REFERENCES topics(id),
  name                  text,
  description           text,
  ordinal               int,
  target_question_count int,
  source_manifest       jsonb,
  partially_sourced     boolean DEFAULT false      -- set by scouting auditor (spec 05 §4)
);

CREATE TABLE sources (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subtopic_id  uuid REFERENCES subtopics(id),
  url          text,
  type         text,                                -- paper|doc|article|video|repo|illustration
  title        text,
  published    date,
  license_hint text,
  scraped_at   timestamptz,
  meta         jsonb
);

-- Generated content ----------------------------------------------------------
CREATE TABLE interactions (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subtopic_id      uuid REFERENCES subtopics(id),
  type             text NOT NULL,                   -- mcq|qa
  dl               int  NOT NULL,
  ordinal          int,
  question_md      text,
  diagram_ref      uuid REFERENCES blobs(id),       -- nullable
  content_panel_md text,
  qa_rubric        jsonb,
  answer_key       text,
  gen_model        text,
  gen_latency_ms   int,                             -- generation speed capture (spec 06)
  gen_tokens_in    int,
  gen_tokens_out   int,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE mcq_options (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interaction_id uuid REFERENCES interactions(id),
  label          char(1),                           -- A|B|C|D
  text           text,
  is_correct     boolean,
  char_len       int
);

CREATE TABLE hints (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interaction_id uuid REFERENCES interactions(id),
  level          int,                               -- 1|2|3
  text_md        text
);

CREATE TABLE diagrams (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interaction_id uuid REFERENCES interactions(id),
  blob_id        uuid REFERENCES blobs(id),
  provenance     text,                              -- sourced|generated
  source_url     text,
  license_hint   text
);

-- Checks & verification ------------------------------------------------------
CREATE TABLE check_runs (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interaction_id uuid REFERENCES interactions(id),
  checker        text,                              -- option|domain|verification
  verdict        text,
  issues         jsonb,
  model          text,
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- Learning sessions ----------------------------------------------------------
CREATE TABLE sessions (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid REFERENCES users(id),
  course_id  uuid REFERENCES courses(id),
  started_at timestamptz NOT NULL DEFAULT now(),
  ended_at   timestamptz
);

CREATE TABLE responses (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id        uuid REFERENCES sessions(id),
  interaction_id    uuid REFERENCES interactions(id),
  user_answer       text,
  is_correct        boolean,
  band              text,                            -- full|partial|incorrect (qa)
  dl                int,
  hints_used        int,
  score_awarded     int,
  graded_by         text,
  grade_feedback_md text,
  escalated_from    uuid,                            -- the mcq this qa followed
  responded_at      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE weaknesses (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users(id),
  subtopic_id uuid REFERENCES subtopics(id),
  error_count int DEFAULT 0,
  last_seen   timestamptz
);

-- Feedback -------------------------------------------------------------------
CREATE TABLE content_feedback (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  interaction_id uuid REFERENCES interactions(id),
  user_id        uuid REFERENCES users(id),
  feedback_md    text,
  md_file_path   text,                              -- mirror on local disk
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE application_feedback (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  page_key    text,
  user_id     uuid REFERENCES users(id),
  feedback_md text,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE feedback_images (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  feedback_kind text,                               -- content|application
  feedback_id   uuid,
  blob_id       uuid REFERENCES blobs(id),
  asset_path    text,                               -- local path when mirrored next to a .md
  caption       text,                               -- text this image is linked to
  ordinal       int,
  created_at    timestamptz NOT NULL DEFAULT now()
);

-- Guardrails -----------------------------------------------------------------
CREATE TABLE guardrail_events (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users(id),
  entry_point text,                                 -- course_prompt|clarify|qa_answer|content_feedback|app_feedback
  raw_len     int,
  allow       boolean,
  category    text,                                 -- injection|off_topic|safety|pii|length|null
  action      text,                                 -- blocked|sanitized|allowed
  created_at  timestamptz NOT NULL DEFAULT now()
);

-- Metrics --------------------------------------------------------------------
CREATE TABLE generation_metrics (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id      uuid,
  interaction_id uuid,
  phase          text,                              -- scouting|generation|checking|verification
  model          text,
  tokens_in      int,
  tokens_out     int,
  latency_ms     int,
  cost           numeric,
  created_at     timestamptz NOT NULL DEFAULT now()
);

-- Helpful indexes
CREATE INDEX idx_subtopics_topic     ON subtopics(topic_id);
CREATE INDEX idx_interactions_subt   ON interactions(subtopic_id);
CREATE INDEX idx_options_interaction ON mcq_options(interaction_id);
CREATE INDEX idx_hints_interaction   ON hints(interaction_id);
CREATE INDEX idx_responses_session   ON responses(session_id);
CREATE INDEX idx_metrics_course      ON generation_metrics(course_id);
