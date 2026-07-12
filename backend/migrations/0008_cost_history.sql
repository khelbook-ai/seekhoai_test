-- Global cost-history utility (spec 03 §6, 06 §5). A cross-user / cross-session index of every
-- build's estimated-vs-actual cost, pointing at the human-readable reconciliation .md files.
-- When a NEW course is estimated, the Cost Estimator looks up SIMILAR past builds here and
-- calibrates the estimate by their actual/estimated ratio.
CREATE TABLE IF NOT EXISTS cost_history (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  course_id     uuid REFERENCES courses(id),
  title         text,
  domain        text,
  currency_mode text,
  keywords      jsonb,                       -- normalized signature terms for similarity
  estimated     numeric,
  actual        numeric,
  delta_pct     numeric,
  ratio         numeric,                      -- actual / estimated
  md_path       text,                         -- the reconciliation .md this row indexes
  created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cost_history_created ON cost_history(created_at DESC);
