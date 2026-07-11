"""Seekhai_test backend — app entrypoint (full spec)."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import courses, feedback, health, learning, population

app = FastAPI(title="Seekhai_test", version="1.0.0")

# Local dev: Vite frontend on :5173 talks to this on :8000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(courses.router)
app.include_router(population.router)
app.include_router(learning.router)
app.include_router(feedback.router)


@app.get("/")
def root() -> dict:
    return {"name": "Seekhai_test", "docs": "/docs"}
