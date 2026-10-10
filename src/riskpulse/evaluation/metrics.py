"""Reproducible evaluation of the event classifier and sentiment model on the labelled synthetic set.

Event classifier: grouped hold-out by template_id (StratifiedGroupKFold), so test sentences come
from templates never seen in training - this measures generalisation, not memorisation.
Sentiment: compares raw VADER (naive baseline) with the finance-adapted scorer against the
template-intended sentiment labels (no training involved).
All numbers are on synthetic data and say nothing about real-market predictive performance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.model_selection import StratifiedGroupKFold
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from ..config import DATA_DIR, LABELLED_FILE
from ..nlp.classifier import RANDOM_STATE, EventClassifier
from ..nlp.entities import mask_entities
from ..nlp.sentiment import analyze_sentiment, label_for
from ..universe import ALL_EVENT_LABELS, SENTIMENT_LABELS, UNCLASSIFIED

N_SPLITS = 4


def _scores(y_true, y_pred, labels) -> dict:
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "macro_f1": round(f1_score(y_true, y_pred, labels=labels, average="macro", zero_division=0), 4),
        "per_class": {k: {m: round(v, 4) for m, v in d.items()}
                      for k, d in classification_report(y_true, y_pred, labels=labels, output_dict=True,
                                                        zero_division=0).items() if k in labels},
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
        "labels": labels,
    }


def evaluate_classifier(df: pd.DataFrame) -> dict:
    sgkf = StratifiedGroupKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)
    folds = list(sgkf.split(df["text"], df["event_type"], df["template_id"]))
    train_idx, test_idx = folds[0]
    train, test = df.iloc[train_idx], df.iloc[test_idx]

    variants = {
        "hybrid": EventClassifier().fit(train["text"].tolist(), train["event_type"].tolist()),
        "ml_only": EventClassifier(use_rules=False).fit(train["text"].tolist(), train["event_type"].tolist()),
        "rules_only": EventClassifier(use_ml=False),
    }
    results, preds = {}, {}
    for name, clf in variants.items():
        out = [clf.predict(t) for t in test["text"]]
        preds[name] = out
        results[name] = _scores(test["event_type"].tolist(), [o["event_type"] for o in out], ALL_EVENT_LABELS)

    errors = []
    for (_, row), o in zip(test.iterrows(), preds["hybrid"]):
        if o["event_type"] != row["event_type"]:
            errors.append({"text": row["text"], "true": row["event_type"], "predicted": o["event_type"],
                           "confidence": o["confidence"], "secondary": o["secondary_event_type"],
                           "template_id": row["template_id"]})

    cv = []
    for tr, te in folds:
        clf = EventClassifier().fit(df.iloc[tr]["text"].tolist(), df.iloc[tr]["event_type"].tolist())
        p = [clf.predict(t)["event_type"] for t in df.iloc[te]["text"]]
        cv.append(f1_score(df.iloc[te]["event_type"], p, labels=ALL_EVENT_LABELS, average="macro", zero_division=0))

    hyb = preds["hybrid"]
    return {
        "split": {"method": f"StratifiedGroupKFold(n_splits={N_SPLITS}, groups=template_id, seed={RANDOM_STATE}), fold 0 held out",
                  "train_rows": len(train), "test_rows": len(test),
                  "train_templates": int(train["template_id"].nunique()), "test_templates": int(test["template_id"].nunique())},
        "variants": results,
        "grouped_cv_macro_f1": {"folds": [round(x, 4) for x in cv], "mean": round(float(np.mean(cv)), 4),
                                "std": round(float(np.std(cv)), 4)},
        "ambiguous_rate": round(float(np.mean([o["is_ambiguous"] for o in hyb])), 4),
        "mean_confidence_correct": round(float(np.mean([o["confidence"] for o, t in zip(hyb, test["event_type"]) if o["event_type"] == t] or [0])), 4),
        "mean_confidence_wrong": round(float(np.mean([o["confidence"] for o, t in zip(hyb, test["event_type"]) if o["event_type"] != t] or [0])), 4),
        "errors": errors,
    }


def evaluate_sentiment(df: pd.DataFrame) -> dict:
    vader = SentimentIntensityAnalyzer()  # untouched lexicon = naive baseline
    texts = [mask_entities(t) for t in df["text"]]
    naive = [label_for(vader.polarity_scores(t)["compound"]) for t in texts]
    adapted_scores = [analyze_sentiment(t)["score"] for t in texts]
    adapted = [label_for(s) for s in adapted_scores]
    y = df["sentiment_label"].tolist()
    examples = []
    for t, truth, n, a, s in list(zip(df["text"], y, naive, adapted, adapted_scores)):
        if n != a and len(examples) < 12:
            examples.append({"text": t, "true": truth, "naive_vader": n, "finance_adapted": a, "score": s})
    return {
        "naive_vader": _scores(y, naive, SENTIMENT_LABELS),
        "finance_adapted": _scores(y, adapted, SENTIMENT_LABELS),
        "rows": len(df),
        "score_range": [round(min(adapted_scores), 4), round(max(adapted_scores), 4)],
        "disagreement_examples": examples,
    }


CHALLENGE_FILE = DATA_DIR / "challenge_set.csv"


def evaluate_challenge(train_df: pd.DataFrame, path=CHALLENGE_FILE) -> dict:
    """Out-of-template stress test: 44 hand-written paraphrases that avoid most rule keywords."""
    ch = pd.read_csv(path)
    texts, labels = train_df["text"].tolist(), train_df["event_type"].tolist()
    variants = {"hybrid": EventClassifier().fit(texts, labels),
                "ml_only": EventClassifier(use_rules=False).fit(texts, labels),
                "rules_only": EventClassifier(use_ml=False)}
    out = {}
    for name, clf in variants.items():
        preds = [clf.predict(t) for t in ch["text"]]
        out[name] = _scores(ch["event_type"].tolist(), [p["event_type"] for p in preds], ALL_EVENT_LABELS)
        if name == "hybrid":
            out["hybrid_errors"] = [{"text": t, "true": y, "predicted": p["event_type"], "confidence": p["confidence"]}
                                    for t, y, p in zip(ch["text"], ch["event_type"], preds) if p["event_type"] != y]
    sent = [label_for(analyze_sentiment(mask_entities(t))["score"]) for t in ch["text"]]
    vader = SentimentIntensityAnalyzer()
    naive = [label_for(vader.polarity_scores(mask_entities(t))["compound"]) for t in ch["text"]]
    out["sentiment_finance_adapted"] = _scores(ch["sentiment_label"].tolist(), sent, SENTIMENT_LABELS)
    out["sentiment_naive_vader"] = _scores(ch["sentiment_label"].tolist(), naive, SENTIMENT_LABELS)
    out["rows"] = len(ch)
    return out


def evaluate_transformers(train_df: pd.DataFrame, path=CHALLENGE_FILE) -> dict:
    """Optional: FinBERT sentiment and hybrid + zero-shot fallback classification (local open models)."""
    from ..nlp import transformer
    if not transformer.available():
        return {"available": False, "note": "torch/transformers or model weights not installed"}
    ch = pd.read_csv(path)
    fb_lab = [label_for(r["score"]) for r in transformer.finbert_scores([mask_entities(t) for t in train_df["text"]])]
    fb_ch = [label_for(r["score"]) for r in transformer.finbert_scores([mask_entities(t) for t in ch["text"]])]
    clf = EventClassifier().fit(train_df["text"].tolist(), train_df["event_type"].tolist())
    preds, used = [], 0
    for t in ch["text"]:
        p = clf.predict(t)["event_type"]
        if p == UNCLASSIFIED:
            used += 1
            p = transformer.zero_shot_event(t)["event_type"]
        preds.append(p)
    return {
        "available": True,
        "models": {"sentiment": transformer.FINBERT, "zero_shot": transformer.ZERO_SHOT},
        "finbert_sentiment_labelled": _scores(train_df["sentiment_label"].tolist(), fb_lab, SENTIMENT_LABELS),
        "finbert_sentiment_challenge": _scores(ch["sentiment_label"].tolist(), fb_ch, SENTIMENT_LABELS),
        "hybrid_plus_zero_shot_challenge": _scores(ch["event_type"].tolist(), preds, ALL_EVENT_LABELS),
        "zero_shot_fallback_used": used,
        "errors_challenge": [{"text": t, "true": y, "predicted": p} for t, y, p in zip(ch["text"], ch["event_type"], preds) if p != y],
    }


def run_evaluation(path=LABELLED_FILE, include_transformers: bool = False) -> dict:
    df = pd.read_csv(path)
    return {
        "dataset": {"path": str(path.name), "rows": len(df), "templates": int(df["template_id"].nunique()),
                    "event_counts": df["event_type"].value_counts().to_dict(),
                    "sentiment_counts": df["sentiment_label"].value_counts().to_dict(), "is_synthetic": True},
        "event_classification": evaluate_classifier(df),
        "sentiment": evaluate_sentiment(df),
        "challenge_set": evaluate_challenge(df),
        "transformer_upgrade": evaluate_transformers(df) if include_transformers else {"available": False, "note": "not run"},
        "disclaimer": "Metrics are computed on synthetic, template-generated text. They demonstrate that the "
                      "pipeline works and generalises across held-out templates; they are not evidence of "
                      "real-world predictive performance.",
    }
