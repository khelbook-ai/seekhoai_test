"""Model registry (spec 02 §4 / 03). Resolve an agent -> model config.

Agent code always asks the registry for its model, never hardcodes an ID. Pricing
(USD per 1M tokens) rides along so the Cost Estimator (03 §6) and per-call cost
capture (06) share one source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.config import get_models


@dataclass(frozen=True)
class ModelSpec:
    agent: str
    provider: str
    model: str
    klass: str
    base_url: str
    api_key_env: str
    price_in: float   # USD per 1M input tokens
    price_out: float  # USD per 1M output tokens

    def cost(self, tokens_in: int, tokens_out: int) -> float:
        return (tokens_in / 1_000_000) * self.price_in + (tokens_out / 1_000_000) * self.price_out


def get_model(agent: str) -> ModelSpec:
    cfg = get_models()
    agents = cfg["agents"]
    if agent not in agents:
        raise KeyError(f"No model configured for agent '{agent}' in models.yaml")
    a = agents[agent]
    provider = cfg["providers"][a["provider"]]
    price = cfg.get("pricing", {}).get(a["model"], {})
    return ModelSpec(
        agent=agent,
        provider=a["provider"],
        model=a["model"],
        klass=a.get("class", "fast"),
        base_url=provider["base_url"],
        api_key_env=provider["api_key_env"],
        price_in=float(price.get("input", 0.0)),
        price_out=float(price.get("output", 0.0)),
    )


def price_for(model_id: str) -> tuple[float, float]:
    """(input, output) USD per 1M tokens for a raw model id, or (0,0) if unpriced."""
    p = get_models().get("pricing", {}).get(model_id, {})
    return float(p.get("input", 0.0)), float(p.get("output", 0.0))
