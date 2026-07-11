"""Checkers (spec 03 §8-10, 05 §7). Option (deterministic), Domain (strong), and
Content Verification (Gemini, independent). Each approves, requests regen within the
retry budget, or escalates to human review — never silently drops an item."""
