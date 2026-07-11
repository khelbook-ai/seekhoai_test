"""Observability façade (spec 06 §3). LangSmith primary, Phoenix pluggable, `none`
default. Every agent/tool call wraps in `trace_span(...)`. Swapping the backend
(none|langsmith|phoenix) happens here only; callers never change.

Generation metrics (tokens/latency/cost) are captured separately in app.metrics and
mirrored to Postgres regardless of the tracing backend — that is the hard requirement
(02 §5); the tracer is an optional overlay.
"""
from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Iterator

from app.config import get_settings

_ls_client = None


def _backend() -> str:
    return get_settings().section("observability").get("backend", "none")


def _langsmith():
    global _ls_client
    if _ls_client is None:
        from langsmith import Client  # imported lazily; optional dependency at runtime

        _ls_client = Client()
    return _ls_client


@contextmanager
def trace_span(name: str, **attrs) -> Iterator[dict]:
    backend = _backend()
    start = time.perf_counter()
    span: dict = {"name": name, "attrs": attrs}
    try:
        yield span
    finally:
        span["latency_ms"] = int((time.perf_counter() - start) * 1000)
        if backend == "langsmith":
            try:
                _langsmith().create_run(
                    name=name,
                    run_type="chain",
                    inputs=attrs,
                    outputs={k: v for k, v in span.items() if k != "attrs"},
                    project_name=get_settings().section("observability").get("project", "seekhai"),
                )
            except Exception:
                pass
        # backend == "phoenix": plug an OTEL exporter here (kept pluggable per 06 §3).


def log_metrics(**kw) -> None:
    """Thin hook mirrored by app.metrics.record; kept for façade completeness."""
    if _backend() == "langsmith":
        try:
            _langsmith().create_run(name="metrics", run_type="tool", inputs=kw, outputs=kw)
        except Exception:
            pass


def log_eval(name: str, score: float, **kw) -> None:
    """Offline-eval hook (Phoenix-oriented, 06 §3). No-op unless a backend is wired."""
    if _backend() in ("langsmith", "phoenix"):
        try:
            _langsmith().create_run(name=f"eval:{name}", run_type="tool",
                                    inputs=kw, outputs={"score": score})
        except Exception:
            pass
