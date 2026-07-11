"""Unified LLM client (spec 02 §4, 03). Every agent call goes through here.

All providers are reached via OpenRouter's OpenAI-compatible API using the `openai`
SDK (base_url from models.yaml). Each call:
  - resolves the model from the registry (never a hardcoded id),
  - records model/tokens/latency/cost to generation_metrics (02 §5, 06),
  - wraps in an observability span (06 §3),
  - parses strict JSON with ONE retry on malformed output (03 shared conventions).
"""
from __future__ import annotations

import base64
import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app import metrics
from app.observability import trace_span
from app.registry import ModelSpec, get_model

_clients: dict[str, OpenAI] = {}


class LLMError(RuntimeError):
    pass


def _client(spec: ModelSpec) -> OpenAI:
    key = os.getenv(spec.api_key_env)
    if not key:
        raise LLMError(
            f"Missing API key env {spec.api_key_env} for provider {spec.provider}. "
            "Set it before making model calls."
        )
    if spec.provider not in _clients:
        _clients[spec.provider] = OpenAI(
            base_url=spec.base_url,
            api_key=key,
            default_headers={
                "HTTP-Referer": "http://localhost:5173",
                "X-Title": "Seekhai_test",
            },
        )
    return _clients[spec.provider]


@dataclass
class LLMResult:
    text: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    cost: float
    model: str


def _do_call(spec: ModelSpec, messages: list[dict], max_tokens: int, temperature: float) -> LLMResult:
    client = _client(spec)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    def _invoke():
        return client.chat.completions.create(
            model=spec.model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    start = time.perf_counter()
    resp = _invoke()
    latency_ms = int((time.perf_counter() - start) * 1000)
    text = (resp.choices[0].message.content or "").strip()
    usage = resp.usage
    tin = getattr(usage, "prompt_tokens", 0) or 0
    tout = getattr(usage, "completion_tokens", 0) or 0
    cost = spec.cost(tin, tout)
    return LLMResult(text=text, tokens_in=tin, tokens_out=tout,
                     latency_ms=latency_ms, cost=cost, model=spec.model)


def complete_text(
    agent: str,
    system: str,
    user: str | list[dict],
    *,
    phase: str = "generation",
    max_tokens: int = 4096,
    temperature: float = 0.3,
    course_id: str | None = None,
    interaction_id: str | None = None,
) -> LLMResult:
    """Free-text completion. `user` may be a string or a list of OpenAI content parts
    (for vision). Records metrics + trace."""
    spec = get_model(agent)
    content = user if isinstance(user, list) else [{"type": "text", "text": user}]
    messages = [{"role": "system", "content": system}, {"role": "user", "content": content}]
    with trace_span(f"llm:{agent}", model=spec.model, phase=phase):
        res = _do_call(spec, messages, max_tokens, temperature)
    metrics.record(phase=phase, model=res.model, tokens_in=res.tokens_in,
                   tokens_out=res.tokens_out, latency_ms=res.latency_ms, cost=res.cost,
                   course_id=course_id, interaction_id=interaction_id)
    return res


_JSON_RE = re.compile(r"\{.*\}|\[.*\]", re.DOTALL)


def _extract_json(text: str) -> Any:
    """Parse JSON, tolerating ```json fences and surrounding prose."""
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.DOTALL).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = _JSON_RE.search(t)
        if m:
            return json.loads(m.group(0))
        raise


def complete_json(
    agent: str,
    system: str,
    user: str | list[dict],
    *,
    phase: str = "generation",
    max_tokens: int = 4096,
    temperature: float = 0.2,
    course_id: str | None = None,
    interaction_id: str | None = None,
) -> tuple[Any, LLMResult]:
    """Strict-JSON completion with ONE reprompt on malformed output (03 conventions).
    Returns (parsed_json, LLMResult-of-the-accepted-call)."""
    sys = system + (
        "\n\nRespond with ONLY valid JSON — no markdown fences, no prose before or "
        "after. The response must be parseable by json.loads."
    )
    res = complete_text(agent, sys, user, phase=phase, max_tokens=max_tokens,
                        temperature=temperature, course_id=course_id, interaction_id=interaction_id)
    try:
        return _extract_json(res.text), res
    except (json.JSONDecodeError, ValueError):
        # one retry with an explicit correction turn
        retry_user = (
            (user if isinstance(user, str) else "see prior content")
            + "\n\nYour previous reply was not valid JSON:\n"
            + res.text[:1500]
            + "\n\nReturn ONLY the corrected JSON."
        )
        res2 = complete_text(agent, sys, retry_user, phase=phase, max_tokens=max_tokens,
                             temperature=0.0, course_id=course_id, interaction_id=interaction_id)
        return _extract_json(res2.text), res2


def image_part(data: bytes, mime: str = "image/png") -> dict:
    """Build an OpenAI vision content part from raw image bytes (data: URI)."""
    b64 = base64.standard_b64encode(data).decode("ascii")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
