"""Load settings.yaml + models.yaml. Single source of config (spec 02 §4)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


def _load_yaml(name: str) -> dict[str, Any]:
    with open(CONFIG_DIR / name, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@dataclass(frozen=True)
class ScoringConfig:
    base_multiplier: int
    hint_penalty: int
    score_floor: int
    qa_partial_credit: dict[str, float]


class Settings:
    """Thin typed accessor over settings.yaml, with env overrides."""

    def __init__(self) -> None:
        self._raw = _load_yaml("settings.yaml")

    @property
    def database_dsn(self) -> str:
        return os.getenv("DATABASE_URL", self._raw["database"]["dsn"])

    @property
    def data_dir(self) -> Path:
        return Path(self._raw["storage"]["data_dir"]).resolve()

    @property
    def feedback_dir(self) -> Path:
        return Path(self._raw["storage"]["feedback_dir"]).resolve()

    @property
    def blob_backend(self) -> str:
        return self._raw["storage"]["blob_backend"]

    @property
    def scoring(self) -> ScoringConfig:
        s = self._raw["scoring"]
        return ScoringConfig(
            base_multiplier=s["base_multiplier"],
            hint_penalty=s["hint_penalty"],
            score_floor=s["score_floor"],
            qa_partial_credit=s["qa_partial_credit"],
        )

    def section(self, key: str) -> dict[str, Any]:
        return self._raw.get(key, {})


@lru_cache
def get_settings() -> Settings:
    return Settings()


@lru_cache
def get_models() -> dict[str, Any]:
    return _load_yaml("models.yaml")
