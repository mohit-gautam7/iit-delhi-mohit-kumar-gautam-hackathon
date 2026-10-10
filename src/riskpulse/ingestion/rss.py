"""Optional public RSS/Atom feed adapter. Disabled by default; the demo runs fully offline.

Only use feeds whose terms permit programmatic reading. Fetched items are real (not synthetic)
and are labelled with ``is_synthetic = False``. Any network failure returns an error message
instead of raising, so the dashboard can degrade gracefully.
"""
from __future__ import annotations

import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

MAX_BYTES = 2 * 1024 * 1024


def _ts(text: str | None) -> str | None:
    if not text:
        return None
    try:
        return parsedate_to_datetime(text).isoformat()
    except (TypeError, ValueError):
        return text  # Atom feeds already use ISO-8601


def fetch_rss(url: str, timeout: float = 5.0, limit: int = 50) -> tuple[list[dict], str | None]:
    """Return ``(rows, error)``; rows use the news-adapter column names."""
    if not url.lower().startswith(("http://", "https://")):
        return [], "Only http(s) feed URLs are supported."
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "RiskPulseAI/0.1 (hackathon demo)"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - scheme checked above
            root = ET.fromstring(resp.read(MAX_BYTES))
    except Exception as exc:  # network, HTTP, parse errors: degrade gracefully
        return [], f"Feed unavailable ({type(exc).__name__}: {exc}). Continuing with bundled offline data."
    atom = "{http://www.w3.org/2005/Atom}"
    items = root.findall(".//item") or root.findall(f".//{atom}entry")
    channel = root.findtext("./channel/title") or root.findtext(f"{atom}title") or url
    rows = []
    for item in items[:limit]:
        rows.append({
            "headline": item.findtext("title") or item.findtext(f"{atom}title"),
            "body": item.findtext("description") or item.findtext(f"{atom}summary") or "",
            "published_at": _ts(item.findtext("pubDate") or item.findtext(f"{atom}updated")),
            "source_name": f"rss:{channel}"[:80],
            "is_synthetic": "false",
        })
    if not rows:
        return [], "Feed returned no items."
    return rows, None
