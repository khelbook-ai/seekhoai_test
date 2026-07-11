"""BlobStore interface (spec 02 §4). Default backend: local Postgres bytea.

Keeping binaries behind this interface means a local-dir or S3 backend can be
added later without changing any caller. Phase 0 ships the Postgres backend only.
"""
from __future__ import annotations

import hashlib
from typing import Protocol

from app.db import execute, fetchone


class BlobStore(Protocol):
    def put(self, kind: str, mime: str, data: bytes) -> str: ...
    def get(self, blob_id: str) -> tuple[str, bytes] | None: ...


class PostgresBlobStore:
    """Stores blobs in the local `blobs` table as bytea."""

    def put(self, kind: str, mime: str, data: bytes) -> str:
        row = execute(
            """
            INSERT INTO blobs (kind, mime, bytes, byte_len, sha256)
            VALUES (%s, %s, %s, %s, %s) RETURNING id
            """,
            (kind, mime, data, len(data), hashlib.sha256(data).hexdigest()),
        )
        return str(row["id"])

    def get(self, blob_id: str) -> tuple[str, bytes] | None:
        row = fetchone("SELECT mime, bytes FROM blobs WHERE id = %s", (blob_id,))
        if row is None:
            return None
        return row["mime"], bytes(row["bytes"])


def get_blobstore() -> BlobStore:
    # switch on settings.storage.blob_backend when a second backend exists
    return PostgresBlobStore()
