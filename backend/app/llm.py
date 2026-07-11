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

# Global throttle on concurrent provider calls. The build now fans out across subtopics AND
# interactions AND source extractions, so without a single global cap the nested pools could
# stampede the provider and trigger rate-limit backoff (which is SLOWER, not faster). This
# bounds total in-flight model/tool calls regardless of how many worker threads exist; it is
# purely a concurrency limit and changes no agent's inputs or ordering (alignment-neutral).
import threading as _threading

_sema: _threading.BoundedSemaphore | None = None
_sema_lock = _threading.Lock()


def _call_gate() -> _threading.BoundedSemaphore:
    global _sema
    if _sema is None:
        with _sema_lock:
            if _sema is None:
                from app.config import get_settings
                n = max(1, int(get_settings().section("build").get("max_concurrent_llm_calls", 8)))
                _sema = _threading.BoundedSemaphore(n)
    return _sema


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
    with _call_gate():                    # global concurrency cap (alignment-neutral throttle)
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


def web_search(query: str, max_results: int = 5, *, phase: str = "scouting",
               course_id: str | None = None) -> dict:
    """High-quality live web search via OpenRouter's built-in web plugin (Exa-backed).
    Returns {results: [{title, url, snippet}]}. Records real per-call cost to metrics.
    Raises on failure so callers can fall back to a secondary provider."""
    import httpx

    spec = get_model("web_search")
    key = os.getenv(spec.api_key_env)
    if not key:
        raise LLMError(f"Missing {spec.api_key_env} for web search")
    url = spec.base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": spec.model,
        "plugins": [{"id": "web", "max_results": max_results}],
        "messages": [{"role": "user", "content": f"Search the web for: {query}"}],
        "max_tokens": 40,
    }
    start = time.perf_counter()
    with trace_span("tool:web_search", model=spec.model, query=query[:80]), _call_gate():
        resp = httpx.post(url, headers={"Authorization": f"Bearer {key}",
                                        "HTTP-Referer": "http://localhost:5173",
                                        "X-Title": "Seekhai_test"}, json=body, timeout=60.0)
        resp.raise_for_status()
        data = resp.json()
    latency_ms = int((time.perf_counter() - start) * 1000)
    msg = data["choices"][0]["message"]
    results = []
    for a in (msg.get("annotations") or []):
        if a.get("type") == "url_citation":
            u = a.get("url_citation", {})
            results.append({"title": u.get("title"), "url": u.get("url"),
                            "snippet": (u.get("content") or "")[:400]})
    usage = data.get("usage", {}) or {}
    # OpenRouter reports actual cost (incl. the Exa search fee) — use it directly.
    cost = float(usage.get("cost") or 0.0)
    metrics.record(phase=phase, model=f"{spec.model}+web", tokens_in=usage.get("prompt_tokens", 0),
                   tokens_out=usage.get("completion_tokens", 0), latency_ms=latency_ms,
                   cost=cost, course_id=course_id)
    return {"results": results, "cost": cost}
