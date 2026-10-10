"""Evaluate the event classifier and sentiment models. Writes data/evaluation_report.json.

Usage: python scripts/evaluate_model.py [--transformers]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from riskpulse.config import DATA_DIR  # noqa: E402
from riskpulse.evaluation.metrics import run_evaluation  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--transformers", action="store_true", help="also evaluate FinBERT + zero-shot (slow, optional)")
    args = ap.parse_args()
    rep = run_evaluation(include_transformers=args.transformers)
    (DATA_DIR / "evaluation_report.json").write_text(json.dumps(rep, indent=2), encoding="utf-8")

    ec = rep["event_classification"]
    print("Event classification - held-out templates:", ec["split"])
    for name, v in ec["variants"].items():
        print(f"  {name:<11} accuracy {v['accuracy']:.3f}  macro-F1 {v['macro_f1']:.3f}")
    cv = ec["grouped_cv_macro_f1"]
    print(f"  hybrid grouped {len(cv['folds'])}-fold CV macro-F1 {cv['mean']:.3f} +/- {cv['std']:.3f}")
    ch = rep["challenge_set"]
    print(f"Challenge set ({ch['rows']} hand-written paraphrases):")
    for name in ["hybrid", "ml_only", "rules_only"]:
        print(f"  {name:<11} accuracy {ch[name]['accuracy']:.3f}  macro-F1 {ch[name]['macro_f1']:.3f}")
    s = rep["sentiment"]
    print(f"Sentiment ({s['rows']} labelled rows): naive VADER acc {s['naive_vader']['accuracy']:.3f} "
          f"-> finance-adapted acc {s['finance_adapted']['accuracy']:.3f} "
          f"(macro-F1 {s['naive_vader']['macro_f1']:.3f} -> {s['finance_adapted']['macro_f1']:.3f})")
    tf = rep["transformer_upgrade"]
    if tf.get("available"):
        print(f"Transformer upgrade: FinBERT sentiment acc labelled {tf['finbert_sentiment_labelled']['accuracy']:.3f}, "
              f"challenge {tf['finbert_sentiment_challenge']['accuracy']:.3f}; hybrid+zero-shot challenge acc "
              f"{tf['hybrid_plus_zero_shot_challenge']['accuracy']:.3f} (fallback used {tf['zero_shot_fallback_used']}x)")
    print("Saved data/evaluation_report.json")


if __name__ == "__main__":
    main()
