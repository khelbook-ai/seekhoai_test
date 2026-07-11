"""Prompt loader (spec 03 shared conventions). Prompts live in prompts/<agent>.md,
versioned, so they can be iterated without code changes. Never inline prompt strings
in agent logic — call load(<agent>).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=128)
def load(name: str) -> str:
    path = PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"No prompt file for '{name}' at {path}")
    return path.read_text(encoding="utf-8")


def render(name: str, **kw: object) -> str:
    """Load a prompt and substitute {placeholders} with str.format. Missing keys raise."""
    return load(name).format(**kw)
