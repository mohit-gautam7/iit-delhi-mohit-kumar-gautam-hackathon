import json
from datetime import timezone

from riskpulse.config import NEWS_FILE, SOCIAL_FILE
from riskpulse.ingestion import clean_text, dedupe_key, detect_source_type, fetch_rss, ingest, parse_timestamp

NEWS_CSV = (b"published_at,source_name,headline,body,is_synthetic\n"
            b"2026-10-01T10:00:00Z,Wire,Helix Energy downgraded to junk,,true\n")
SOCIAL_CSV = (b"created_at,platform,handle,text,likes,reposts,is_synthetic\n"
              b"2026-10-01T11:00:00Z,SynthSocial,@a,$MRDS missed a coupon payment,10,2,true\n")


def test_bundled_news_and_social_both_ingest():
    records, report = ingest([(NEWS_FILE, "news", "n"), (SOCIAL_FILE, "social", "s")])
    kinds = {r.source_type for r in records}
    assert kinds == {"news", "social"}
    assert report.accepted == len(records) > 200
    assert report.rejected == 0
    assert all(r.is_synthetic for r in records)
    assert all(r.timestamp.tzinfo is not None for r in records)


def test_social_adapter_fields():
    (rec,), _ = ingest([(SOCIAL_CSV, "social", "s.csv")])
    assert rec.source_name == "SynthSocial" and rec.author == "@a" and rec.engagement == 12


def test_empty_file_reports_issue_not_crash():
    records, report = ingest([(b"", "news", "empty.csv")])
    assert records == [] and "empty" in report.issues[0].reason


def test_missing_text_and_bad_timestamp_rejected():
    bad = (b"published_at,headline,body\n"
           b"2026-10-01T10:00:00Z,,\n"          # no text
           b"not-a-date,Valid headline here,\n"  # invalid timestamp
           b",Another headline,\n"               # missing timestamp
           b"2026-10-01 12:00:00,Good headline,\n")
    records, report = ingest([(bad, "news", "bad.csv")])
    assert len(records) == 1 and report.rejected == 3
    reasons = " ".join(i.reason for i in report.issues)
    assert "missing text" in reasons and "missing timestamp" in reasons


def test_malformed_json_reported():
    records, report = ingest([(b"[{\"headline\": ", "news", "bad.json")])
    assert records == [] and "malformed JSON" in report.issues[0].reason


def test_json_list_and_records_wrapper():
    rows = [{"published_at": "2026-10-01T10:00:00Z", "headline": "Regulator fines Orion Telecom"}]
    a, _ = ingest([(json.dumps(rows).encode(), None, "feed.json")])
    b, _ = ingest([(json.dumps({"records": rows}).encode(), None, "feed.json")])
    assert len(a) == len(b) == 1 and a[0].record_id == b[0].record_id


def test_duplicates_detected_across_files_and_reposts():
    repost = SOCIAL_CSV + b"2026-10-01T12:00:00Z,SynthSocial,@b,RT @a: $MRDS missed a coupon payment!!,0,0,true\n"
    records, report = ingest([(repost, "social", "s"), (SOCIAL_CSV, "social", "s2")])
    assert len(records) == 1 and report.duplicates == 2
    assert records[0].author == "@a"  # earliest kept


def test_ids_unique_and_deterministic():
    r1, _ = ingest([(NEWS_FILE, "news", "n"), (SOCIAL_FILE, "social", "s")])
    r2, _ = ingest([(NEWS_FILE, "news", "n"), (SOCIAL_FILE, "social", "s")])
    ids = [r.record_id for r in r1]
    assert len(ids) == len(set(ids))
    assert ids == [r.record_id for r in r2]
    # same text from two different source types is kept once (dedupe) but IDs embed provenance
    n, _ = ingest([(NEWS_CSV, "news", "x")])
    s, _ = ingest([(b"created_at,text\n2026-10-01T10:00:00Z,Helix Energy downgraded to junk\n", "social", "y")])
    assert n[0].record_id != s[0].record_id


def test_timestamp_normalised_to_utc():
    assert parse_timestamp("2026-10-01T10:00:00+05:30").hour == 4
    assert parse_timestamp("2026-10-01 10:00:00").tzinfo == timezone.utc


def test_source_detection_and_synthetic_flag_default():
    assert detect_source_type([{"handle": "@x", "text": "t"}]) == "social"
    assert detect_source_type([{"headline": "h"}]) == "news"
    recs, _ = ingest([(b"published_at,headline\n2026-10-01T10:00:00Z,Uploaded headline\n", None, "u.csv")])
    assert recs[0].is_synthetic is False  # unknown provenance is never labelled synthetic


def test_clean_text_and_dedupe_key():
    assert clean_text("a\x00b \n\t c") == "ab c"
    assert len(clean_text("x" * 10_000)) == 5000
    assert dedupe_key("RT @bob: Hello, WORLD https://t.co/x") == dedupe_key("hello world")


def test_rss_degrades_gracefully():
    rows, err = fetch_rss("file:///etc/passwd")
    assert rows == [] and "http" in err
    rows, err = fetch_rss("http://127.0.0.1:9/feed.xml", timeout=1)
    assert rows == [] and "unavailable" in err.lower()
