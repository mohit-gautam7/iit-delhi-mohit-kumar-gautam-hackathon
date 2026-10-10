"""Source adapters: read CSV/JSON, validate, normalise, de-duplicate and assign stable IDs.

Two independent adapters are provided:
  * news   - article-style records (headline + body, publisher, published_at)
  * social - short posts (text, platform, handle, created_at, likes/reposts)
An optional RSS adapter (see ``rss.py``) feeds the news path.
"""
from __future__ import annotations

import csv
import io
import json
import re
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Union

from pydantic import ValidationError

from ..schemas import IngestionIssue, IngestionReport, RawRecord

NAMESPACE = uuid.UUID("6f1c2a9e-4b7d-4c1e-9a55-2f0d8e7b3c11")
MAX_TEXT_CHARS = 5000
MAX_FILE_BYTES = 5 * 1024 * 1024

# Column aliases accepted by each adapter (first match wins).
NEWS_FIELDS = {
    "timestamp": ["published_at", "timestamp", "date", "datetime"],
    "title": ["headline", "title"],
    "body": ["body", "text", "content", "summary"],
    "source_name": ["source_name", "publisher", "source"],
    "author": ["author", "byline"],
}
SOCIAL_FIELDS = {
    "timestamp": ["created_at", "timestamp", "date", "datetime"],
    "body": ["text", "content", "post", "body"],
    "source_name": ["platform", "source_name", "source"],
    "author": ["handle", "author", "user", "username"],
}

DataInput = Union[str, Path, bytes, list, dict]


def _pick(row: dict, aliases: list[str]):
    for key in aliases:
        val = row.get(key)
        if val is not None and str(val).strip() != "" and str(val).lower() != "nan":
            return val
    return None


def clean_text(text: str) -> str:
    """NFKC-normalise, strip control characters and collapse whitespace."""
    text = unicodedata.normalize("NFKC", str(text))
    text = "".join(ch for ch in text if ch == "\n" or unicodedata.category(ch)[0] != "C")
    return re.sub(r"\s+", " ", text).strip()[:MAX_TEXT_CHARS]


def dedupe_key(text: str) -> str:
    """Normalised form used for duplicate detection (ignores RT, @handles, URLs, case, punctuation)."""
    t = text.lower()
    t = re.sub(r"https?://\S+", " ", t)
    t = re.sub(r"^\s*rt\b[:\s]*", " ", t)
    t = re.sub(r"@\w+", " ", t)
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return " ".join(t.split())


def parse_timestamp(value) -> datetime:
    """Parse ISO-8601-ish timestamps; naive values are assumed to be UTC."""
    if value is None:
        raise ValueError("missing timestamp")
    s = str(value).strip().replace("Z", "+00:00")
    ts = datetime.fromisoformat(s)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    ts = ts.astimezone(timezone.utc)
    if not 2000 <= ts.year <= 2100:
        raise ValueError(f"timestamp out of supported range: {value}")
    return ts


def _as_bool(value, default: bool) -> bool:
    if value is None or str(value).strip() == "":
        return default
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _as_int(value) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


def read_rows(data: DataInput, fmt: str | None = None, label: str = "input") -> list[dict]:
    """Read CSV or JSON from a path, raw bytes or already-parsed rows. Raises ValueError on bad input."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("records", [data])
    if isinstance(data, (str, Path)):
        path = Path(data)
        fmt = fmt or path.suffix.lstrip(".").lower()
        raw = path.read_bytes()
    else:
        raw = data
    if len(raw) > MAX_FILE_BYTES:
        raise ValueError(f"{label}: file larger than {MAX_FILE_BYTES // 1024 // 1024} MB")
    content = raw.decode("utf-8-sig", errors="replace")
    if not content.strip():
        raise ValueError(f"{label}: file is empty")
    fmt = (fmt or "").lower()
    if fmt == "json" or (not fmt and content.lstrip()[:1] in "[{"):
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label}: malformed JSON ({exc.msg} at line {exc.lineno})") from exc
        rows = parsed.get("records", [parsed]) if isinstance(parsed, dict) else parsed
        if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
            raise ValueError(f"{label}: JSON must be a list of objects or {{'records': [...]}}")
        return rows
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise ValueError(f"{label}: CSV has no header row")
    return list(reader)


def detect_source_type(rows: list[dict]) -> str:
    """Guess the adapter from column names (social posts carry handle/platform/created_at)."""
    cols = {k.lower() for r in rows[:5] for k in r}
    if cols & {"handle", "platform", "created_at", "reposts", "likes"}:
        return "social"
    return "news"


def _news_row(row: dict, label: str) -> dict:
    title = _pick(row, NEWS_FIELDS["title"])
    body = _pick(row, NEWS_FIELDS["body"])
    if title is None and body is None:
        raise ValueError("missing text: need headline and/or body")
    title = clean_text(title) if title else None
    body = clean_text(body) if body else ""
    text = f"{title}. {body}".strip(" .") if title and body and not body.startswith(title) else (body or title)
    return {
        "source_name": clean_text(_pick(row, NEWS_FIELDS["source_name"]) or label),
        "timestamp": parse_timestamp(_pick(row, NEWS_FIELDS["timestamp"])),
        "text": text,
        "title": title,
        "author": _pick(row, NEWS_FIELDS["author"]),
        "engagement": 0,
    }


def _social_row(row: dict, label: str) -> dict:
    body = _pick(row, SOCIAL_FIELDS["body"])
    if body is None:
        raise ValueError("missing text")
    author = _pick(row, SOCIAL_FIELDS["author"])
    return {
        "source_name": clean_text(_pick(row, SOCIAL_FIELDS["source_name"]) or label),
        "timestamp": parse_timestamp(_pick(row, SOCIAL_FIELDS["timestamp"])),
        "text": clean_text(body),
        "title": None,
        "author": clean_text(author) if author else None,
        "engagement": _as_int(row.get("likes")) + _as_int(row.get("reposts")),
    }


ADAPTERS = {"news": _news_row, "rss": _news_row, "social": _social_row}


def make_record_id(source_type: str, source_name: str, ts: datetime, text: str) -> str:
    key = f"{source_type}|{source_name}|{ts.isoformat()}|{dedupe_key(text)}"
    return "rec-" + str(uuid.uuid5(NAMESPACE, key))


def ingest(sources: Iterable[tuple], default_synthetic: bool = False) -> tuple[list[RawRecord], IngestionReport]:
    """Ingest several sources. Each source is ``(data, source_type | None, label)``.

    Bad rows are skipped and reported (never raised) so one malformed record cannot stop a run.
    Duplicates are detected globally across all sources on the normalised text; the earliest
    record is kept.
    """
    report = IngestionReport()
    candidates: list[RawRecord] = []
    for data, source_type, label in sources:
        report.files.append(label)
        try:
            rows = read_rows(data, label=label)
        except (ValueError, OSError) as exc:
            report.issues.append(IngestionIssue(source=label, reason=str(exc)))
            continue
        if not rows:
            report.issues.append(IngestionIssue(source=label, reason="no records found"))
            continue
        stype = source_type or detect_source_type(rows)
        adapter = ADAPTERS[stype]
        for i, row in enumerate(rows, start=1):
            report.rows_read += 1
            try:
                fields = adapter({str(k).strip().lower(): v for k, v in row.items() if k is not None}, label)
                record = RawRecord(
                    record_id=make_record_id(stype, fields["source_name"], fields["timestamp"], fields["text"]),
                    source_type=stype,
                    is_synthetic=_as_bool(row.get("is_synthetic"), default_synthetic),
                    **fields,
                )
            except (ValueError, ValidationError, TypeError) as exc:
                msg = exc.errors()[0]["msg"] if isinstance(exc, ValidationError) else str(exc)
                report.issues.append(IngestionIssue(source=label, row=i, reason=msg))
                report.rejected += 1
                continue
            candidates.append(record)

    candidates.sort(key=lambda r: r.timestamp)
    seen: set[str] = set()
    records: list[RawRecord] = []
    for rec in candidates:
        key = dedupe_key(rec.text)
        if key in seen:  # record_id embeds this key, so IDs are unique too
            report.duplicates += 1
            continue
        seen.add(key)
        records.append(rec)
    report.accepted = len(records)
    return records, report
