-- Richer interaction types (spec 04 §1): order-the-steps, fill-in-the-blanks, and drag-drop
-- architecture diagrams. All are scored exactly like an MCQ (correct/incorrect) and escalate
-- to the same Q&A root-cause loop on a wrong answer. The chosen agent picks the type per
-- concept. Type-specific structure + the correct answer live in `payload` (answers are stripped
-- before the interaction is served to the learner).
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS payload jsonb;
