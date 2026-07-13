-- Course-assistant chat history (spec 04 §9, 06 §10). The in-course study assistant is now a
-- persistent, per-learner assistant: every question and its answer are stored so the panel can
-- restore the full conversation after a refresh, and so ONE assistant spans all of a learner's
-- courses (each row keeps the course it was asked in + a timestamp). New file; earlier
-- migrations are never edited.
CREATE TABLE IF NOT EXISTS assistant_messages (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users(id),
  course_id   uuid REFERENCES courses(id),
  session_id  uuid REFERENCES sessions(id),
  question    text NOT NULL,
  answer      text,
  grounded    boolean,                 -- did the course's own material match this question?
  sources     jsonb,                   -- course subtopics consulted
  created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_assistant_messages_user ON assistant_messages(user_id, created_at);
