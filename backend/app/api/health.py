from fastapi import APIRouter

from app.db import fetchone

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    db_ok = True
    try:
        fetchone("SELECT 1 AS ok")
    except Exception:
        db_ok = False
    return {"status": "ok", "db": db_ok}
