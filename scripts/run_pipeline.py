"""Run ingestion + NLP on the bundled (or given) files and export signals.

Usage: python scripts/run_pipeline.py [--extra FILE ...] [--transformers]
Writes data/sample_signals.json, data/sample_signals.csv and data/ingestion_report.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from riskpulse.config import DATA_DIR  # noqa: E402
from riskpulse.pipeline import HIGH_IMPACT_THRESHOLD, run_default_pipeline, signals_to_csv, signals_to_json  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--extra", nargs="*", default=[], help="additional CSV/JSON files (source type auto-detected)")
    ap.add_argument("--transformers", action="store_true", help="use optional FinBERT + zero-shot models")
    ap.add_argument("--out", default=str(DATA_DIR), help="output directory")
    args = ap.parse_args()

    extra = [(Path(f), None, Path(f).name) for f in args.extra]
    signals, report = run_default_pipeline(extra, use_transformers=args.transformers)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "sample_signals.json").write_text(signals_to_json(signals), encoding="utf-8")
    (out / "sample_signals.csv").write_text(signals_to_csv(signals), encoding="utf-8")
    (out / "ingestion_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print(f"rows read {report.rows_read} | accepted {report.accepted} | rejected {report.rejected} | "
          f"duplicates {report.duplicates}")
    for issue in report.issues[:10]:
        print(f"  issue: {issue.source} row {issue.row}: {issue.reason}")
    print("by source:", dict(Counter(s.source_type for s in signals)))
    print("by event:", dict(Counter(s.event_type for s in signals).most_common()))
    print("by sentiment:", dict(Counter(s.sentiment_label for s in signals)))
    high = [s for s in signals if s.impact_score > HIGH_IMPACT_THRESHOLD]
    print(f"high impact (> {HIGH_IMPACT_THRESHOLD}): {len(high)}")
    top = max(signals, key=lambda s: (s.impact_score, -s.sentiment_score))
    print("example signal:\n" + json.dumps(top.model_dump(mode="json"), indent=2)[:1500])


if __name__ == "__main__":
    main()
