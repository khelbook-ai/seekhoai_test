"""Content + application feedback persistence (spec 06 §2). Content feedback is mirrored
to a local .md tree keyed by course/subtopic, with uploaded images embedded inline and
linked to the text they refer to. Image bytes live in Postgres (blobs) AND are copied to
a `<id>.assets/` folder next to the .md so it renders standalone on disk.

  feedback/<course_slug>/<subtopic_slug>/<interaction_id>.md
  feedback/<course_slug>/<subtopic_slug>/<interaction_id>.assets/<n>.<ext>
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app.blobstore import get_blobstore
from app.config import get_settings
from app.db import execute

_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/svg+xml": "svg"}
_MAX_BYTES = 10 * 1024 * 1024
_ALLOWED = set(_EXT)


def slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return s or "untitled"


def store_feedback_image(data: bytes, mime: str, caption: str) -> dict:
    """Validate + store an uploaded image in blobs (D17). Returns a link dict for a
    subsequent save_*_feedback call."""
    if mime not in _ALLOWED:
        raise ValueError(f"unsupported image type {mime}")
    if len(data) > _MAX_BYTES:
        raise ValueError("image exceeds 10MB")
    blob_id = get_blobstore().put("feedback_image", mime, data)
    return {"blob_id": blob_id, "mime": mime, "caption": caption}


def _next_md_path(folder: Path, interaction_id: str) -> Path:
    base = folder / f"{interaction_id}.md"
    if not base.exists():
        return base
    i = 2
    while True:
        p = folder / f"{interaction_id}--{i:02d}.md"
        if not p.exists():
            return p
        i += 1


def save_content_feedback(
    *, interaction_id: str, user_id: str | None, course_name: str, subtopic_name: str,
    interaction_type: str, dl: int, feedback_md: str, image_links: list[dict] | None = None,
) -> str:
    image_links = image_links or []
    feedback_dir = get_settings().feedback_dir
    folder = feedback_dir / slugify(course_name) / slugify(subtopic_name)
    folder.mkdir(parents=True, exist_ok=True)
    path = _next_md_path(folder, interaction_id)
    assets = folder / f"{path.stem}.assets"

    # DB row first (so we have a feedback_id for feedback_images)
    row = execute(
        "INSERT INTO content_feedback (interaction_id, user_id, feedback_md, md_file_path) "
        "VALUES (%s,%s,%s,%s) RETURNING id",
        (interaction_id, user_id, feedback_md, str(path)),
    )
    feedback_id = str(row["id"])

    # write images to assets/ + feedback_images rows, build inline embeds
    embeds, fm_images = [], []
    if image_links:
        assets.mkdir(parents=True, exist_ok=True)
    for i, link in enumerate(image_links, start=1):
        got = get_blobstore().get(link["blob_id"])
        if got is None:
            continue
        mime, data = got
        ext = _EXT.get(mime, "png")
        rel = f"{assets.name}/{i:02d}.{ext}"
        (assets / f"{i:02d}.{ext}").write_bytes(data)
        caption = link.get("caption") or "attached image"
        execute(
            "INSERT INTO feedback_images (feedback_kind, feedback_id, blob_id, asset_path, caption, ordinal) "
            "VALUES ('content', %s, %s, %s, %s, %s)",
            (feedback_id, link["blob_id"], str(assets / f"{i:02d}.{ext}"), caption, i),
        )
        fm_images.append(f'  - file: "{rel}"\n    linked_text: "{caption}"')
        embeds.append(f"\n> re: {caption}\n![{caption}]({rel})\n")

    created = datetime.now(timezone.utc).isoformat()
    fm_img_block = ("images:\n" + "\n".join(fm_images) + "\n") if fm_images else "images: []\n"
    front_matter = (
        "---\n"
        f'course: "{course_name}"\n'
        f'subtopic: "{subtopic_name}"\n'
        f'interaction_id: "{interaction_id}"\n'
        f'interaction_type: "{interaction_type}"\n'
        f"dl: {dl}\n"
        f'user_id: "{user_id or ""}"\n'
        f'created_at: "{created}"\n'
        f"{fm_img_block}"
        "---\n\n"
    )
    path.write_text(front_matter + feedback_md.strip() + "\n" + "".join(embeds), encoding="utf-8")
    return str(path)


def save_application_feedback(*, page_key: str, user_id: str | None, feedback_md: str,
                             image_links: list[dict] | None = None) -> str:
    row = execute(
        "INSERT INTO application_feedback (page_key, user_id, feedback_md) "
        "VALUES (%s,%s,%s) RETURNING id",
        (page_key, user_id, feedback_md),
    )
    feedback_id = str(row["id"])
    for i, link in enumerate(image_links or [], start=1):
        execute(
            "INSERT INTO feedback_images (feedback_kind, feedback_id, blob_id, caption, ordinal) "
            "VALUES ('application', %s, %s, %s, %s)",
            (feedback_id, link["blob_id"], link.get("caption"), i),
        )
    return feedback_id
