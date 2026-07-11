"""Format router (spec 05 §2). Lightweight (non-LLM) dispatch from a fetched source's
detected MIME/type to the right extractor(s). A single source may trigger several
(e.g. a PDF → pdf_extractor AND vision_image_extractor for figures). Unknown formats
fall back to file_fetcher + best-effort vision/ocr and are flagged for review.
"""
from __future__ import annotations

from app.mcp import tools


def extract_url(url: str, source_type: str | None = None) -> dict:
    """Route a URL to extractor(s). Returns a merged extractor-shaped dict."""
    low = url.lower().split("?")[0]
    if source_type == "paper" or "arxiv.org" in low or low.endswith(".pdf"):
        dl = tools.paper_downloader(url) if ("arxiv" in low or low.endswith(".pdf")) else tools.file_fetcher(url)
        if dl.get("error"):
            return dict(dl, flagged=True)
        ref = dl.get("pdf_ref") or dl.get("blob_ref")
        out = tools.pdf_extractor(ref)
        out["_blob_ref"] = ref
        out["_source_url"] = url
        return out
    if low.endswith((".pptx",)):
        f = tools.file_fetcher(url)
        return tools.slides_extractor(f["blob_ref"]) if not f.get("error") else dict(f, flagged=True)
    if low.endswith((".docx",)):
        f = tools.file_fetcher(url)
        return tools.doc_extractor(f["blob_ref"]) if not f.get("error") else dict(f, flagged=True)
    if low.endswith(".ipynb"):
        f = tools.file_fetcher(url)
        return tools.notebook_extractor(f["blob_ref"]) if not f.get("error") else dict(f, flagged=True)
    # default: HTML article
    return tools.html_article_extractor(url)


def figures_for(url: str, blob_ref: str | None) -> list[dict]:
    """Best-effort figure extraction: vision on a PDF blob, else illustration scrape."""
    figs: list[dict] = []
    if blob_ref:
        v = tools.vision_image_extractor(blob_ref, page=0, source_url=url)
        if not v.get("error"):
            figs.extend(v.get("figures", []))
    if not figs and url and not url.lower().endswith(".pdf"):
        ill = tools.illustration_scraper(url)
        if not ill.get("error"):
            for im in ill.get("images", [])[:4]:
                figs.append({"image_ref": None, "caption": im.get("caption") or im.get("alt"),
                             "kind": "illustration", "source_url": im.get("url"),
                             "license_hint": im.get("license_hint")})
    return figs
