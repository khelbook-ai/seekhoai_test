-- Guided code walkthrough interaction (spec 04 §1, 07 §2). A read-only, stepped code tour
-- for technical learners: file tree + syntax-highlighted viewer where each concept step
-- highlights the relevant line ranges. Followed by a paired MCQ that tests the code.
-- Stored on the interaction itself (type='walkthrough'); the paired MCQ is a normal row.
ALTER TABLE interactions ADD COLUMN IF NOT EXISTS walkthrough jsonb;
