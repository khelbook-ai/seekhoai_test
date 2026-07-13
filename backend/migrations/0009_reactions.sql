-- Lightweight thumbs up/down reactions (spec 06 §8, 07). A single, low-friction feedback
-- channel that can be dropped anywhere in the UI: each row is one learner's up/down vote on a
-- target (an interaction, its content/hint panels, the answer feedback, a whole course, or a
-- named page). Distinct from content_feedback (.md prose) and application_feedback — this is a
-- one-click signal we can collect in as many places as possible. New file; earlier migrations
-- are never edited.
CREATE TABLE IF NOT EXISTS reactions (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users(id),
  target_kind text NOT NULL,                 -- interaction|content|hint|answer_feedback|review|course|dashboard|page
  target_id   text NOT NULL DEFAULT '',      -- interaction id / course id / page_key ('' when the kind is global)
  value       smallint NOT NULL,             -- 1 = up, -1 = down
  note        text,                          -- optional free text the learner can add with the vote
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

-- One vote per (user, target): re-voting flips/updates it rather than piling up rows.
CREATE UNIQUE INDEX IF NOT EXISTS uq_reactions_user_target
  ON reactions(user_id, target_kind, target_id);
CREATE INDEX IF NOT EXISTS idx_reactions_target ON reactions(target_kind, target_id);
