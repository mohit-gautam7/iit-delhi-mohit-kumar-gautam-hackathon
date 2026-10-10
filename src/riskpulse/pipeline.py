"""End-to-end NLP risk engine: RawRecord -> entities -> sentiment -> event -> impact -> RiskSignal."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from functools import lru_cache

import pandas as pd

from .config import LABELLED_FILE, NEWS_FILE, PORTFOLIO_FILE, SOCIAL_FILE
from .ingestion import ingest
from .ingestion.adapters import clean_text, make_record_id
from .nlp.classifier import EventClassifier
from .nlp.entities import find_entities, mask_entities
from .nlp import transformer
from .nlp.sentiment import analyze_sentiment, label_for
from .portfolio.model import entity_weights, load_portfolio
from .schemas import IngestionReport, RawRecord, RiskSignal
from .scoring.impact import score_impact
from .universe import UNCLASSIFIED

MODEL_VERSION = "riskpulse-0.1 (vader+fin-lexicon | rules+tfidf-logreg | config-impact)"
MODEL_VERSION_TF = "riskpulse-0.1-tf (finbert | rules+tfidf-logreg+bart-mnli-fallback | config-impact)"
HIGH_IMPACT_THRESHOLD = 7  # impact > 7 is "high impact" and can trigger a stress test


def train_classifier(path=LABELLED_FILE) -> EventClassifier:
    df = pd.read_csv(path)
    return EventClassifier().fit(df["text"].tolist(), df["event_type"].tolist())


def _fmt_factors(f: dict) -> str:
    parts = [f"base {f['base_severity']:.1f}"]
    for key, name in [("intensity", "intensity"), ("breadth", "breadth"), ("exposure", "portfolio exposure"),
                      ("sentiment", "sentiment strength"), ("direction", "non-adverse tone"), ("uncertainty", "uncertainty"),
                      ("evidence_quality", "source reliability")]:
        v = f[key]
        if abs(v) >= 0.05:
            parts.append(f"{'+' if v > 0 else '-'} {name} {abs(v):.1f}")
    return " ".join(parts) + f" = {f['raw_total']:.1f}"


class RiskEngine:
    def __init__(self, classifier: EventClassifier, weights: dict[str, float] | None = None,
                 use_transformers: bool = False):
        self.classifier = classifier
        self.weights = weights or {}
        self.use_transformers = use_transformers and transformer.available()

    @classmethod
    def default(cls, use_transformers: bool = False) -> "RiskEngine":
        return cls(train_classifier(), entity_weights(load_portfolio(PORTFOLIO_FILE)), use_transformers)

    def analyze_record(self, rec: RawRecord, finbert: dict | None = None) -> RiskSignal:
        ents = find_entities(rec.text)
        primary = ents[0] if ents else None
        masked = mask_entities(rec.text)  # names like 'Helix Energy' must not carry tone
        sent = analyze_sentiment(masked)
        ev = self.classifier.predict(rec.text)
        sent_source, fallback = "finance-adapted VADER", None
        if self.use_transformers:
            fb = finbert or transformer.finbert_scores([masked])[0]
            score = max(-1.0, min(1.0, fb["score"] * sent["hedge_factor"]))
            sent.update(score=round(score, 4), label=label_for(score))
            sent_source = (f"FinBERT P(pos)={fb['probs'].get('positive', 0):.2f}, "
                           f"P(neg)={fb['probs'].get('negative', 0):.2f}")
            if ev["event_type"] == UNCLASSIFIED:
                fallback = transformer.zero_shot_event(rec.text)
                if fallback["event_type"] != UNCLASSIFIED:
                    ev.update(event_type=fallback["event_type"], confidence=round(fallback["score"], 4),
                              rule_evidence=[], is_ambiguous=False, secondary_event_type=None)
        weight = self.weights.get(primary["ticker"], 0.0) if primary else 0.0
        impact, factors = score_impact(
            rec.text, ev["event_type"], sent["score"], sent["hedge_count"],
            rec.source_type, rec.engagement, weight,
        )
        # confidence: classifier confidence, discounted for hedged language and weak sources
        conf = ev["confidence"] * (0.9 ** min(sent["hedge_count"], 3)) * (0.85 if rec.source_type == "social" else 1.0)

        why = []
        if ev["event_type"] == UNCLASSIFIED:
            why.append(f"No confident event category ({ev['unclassified_reason'] or 'model favours Unclassified'}).")
        else:
            kw = ", ".join(f"'{k}'" for k in ev["rule_evidence"][:4])
            if fallback and fallback["event_type"] == ev["event_type"]:
                why.append(f"Classified as {ev['event_type']} by zero-shot fallback (score {fallback['score']:.2f}; "
                           f"keyword/TF-IDF model found no confident category).")
            else:
                why.append(f"Classified as {ev['event_type']} (classifier confidence {ev['confidence']:.2f}"
                           + (f"; keywords {kw}" if kw else "; model-only evidence") + ").")
            if ev["is_ambiguous"]:
                why.append(f"Ambiguous: {ev['secondary_event_type']} is a close second.")
        drivers = ", ".join(sent["drivers"][:4])
        why.append(f"Sentiment {sent['label']} ({sent['score']:+.2f} via {sent_source}"
                   + (f"; drivers: {drivers}" if drivers else "") + ")"
                   + (" with mixed tone" if sent["mixed"] else "")
                   + (f"; {sent['hedge_count']} hedge word(s) dampen it" if sent["hedge_count"] else "") + ".")
        if primary:
            held = f", {weight:.1%} of synthetic portfolio" if weight else ", not held in portfolio"
            others = f" Also mentions {', '.join(e['ticker'] for e in ents[1:])}." if len(ents) > 1 else ""
            why.append(f"Entity: {primary['name']} ({primary['ticker']}{held}).{others}")
        else:
            why.append("No specific company identified (market-wide or unknown entity).")
        why.append(f"Impact {impact}/10: {_fmt_factors(factors)}.")
        if impact > HIGH_IMPACT_THRESHOLD:
            why.append(f"High impact (> {HIGH_IMPACT_THRESHOLD}): eligible to trigger a portfolio stress test.")

        return RiskSignal(
            signal_id="sig-" + rec.record_id.removeprefix("rec-"),
            record_id=rec.record_id,
            timestamp=rec.timestamp,
            source_type=rec.source_type,
            source_name=rec.source_name,
            entity=primary["name"] if primary else None,
            ticker=primary["ticker"] if primary else None,
            sector=primary["sector"] if primary else None,
            text=rec.text,
            sentiment_score=sent["score"],
            sentiment_label=sent["label"],
            event_type=ev["event_type"],
            secondary_event_type=ev["secondary_event_type"],
            is_ambiguous=ev["is_ambiguous"],
            impact_score=impact,
            confidence=round(min(1.0, conf), 4),
            explanation=" ".join(why),
            impact_factors=factors,
            is_synthetic=rec.is_synthetic,
            model_version=MODEL_VERSION_TF if self.use_transformers else MODEL_VERSION,
        )

    def analyze_records(self, records: list[RawRecord]) -> list[RiskSignal]:
        fins = (transformer.finbert_scores([mask_entities(r.text) for r in records])
                if self.use_transformers and records else [None] * len(records))
        signals = [self.analyze_record(r, f) for r, f in zip(records, fins)]
        ids = [s.signal_id for s in signals]
        assert len(ids) == len(set(ids)), "duplicate signal IDs"
        return signals

    def analyze_text(self, text: str, source_type: str = "news", source_name: str = "api",
                     timestamp: datetime | None = None, is_synthetic: bool = False) -> RiskSignal:
        ts = timestamp or datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        text = clean_text(text)
        rec = RawRecord(record_id=make_record_id(source_type, source_name, ts, text), source_type=source_type,
                        source_name=source_name, timestamp=ts, text=text, is_synthetic=is_synthetic)
        return self.analyze_record(rec)


@lru_cache(maxsize=2)
def default_engine(use_transformers: bool = False) -> RiskEngine:
    return RiskEngine.default(use_transformers)


def run_default_pipeline(extra_sources: list[tuple] | None = None,
                         use_transformers: bool = False) -> tuple[list[RiskSignal], IngestionReport]:
    sources = [(NEWS_FILE, "news", NEWS_FILE.name), (SOCIAL_FILE, "social", SOCIAL_FILE.name)]
    records, report = ingest(sources + (extra_sources or []))
    return default_engine(use_transformers).analyze_records(records), report


# ---------- exports ----------
EXPORT_COLUMNS = ["signal_id", "timestamp", "source_type", "source_name", "entity", "ticker", "sector", "text",
                  "sentiment_score", "sentiment_label", "event_type", "secondary_event_type", "is_ambiguous",
                  "impact_score", "confidence", "explanation", "is_synthetic", "record_id", "model_version"]


def signals_to_df(signals: list[RiskSignal]) -> pd.DataFrame:
    if not signals:
        return pd.DataFrame(columns=EXPORT_COLUMNS)
    df = pd.DataFrame([s.model_dump(mode="json") for s in signals])
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def signals_to_json(signals: list[RiskSignal]) -> str:
    return json.dumps([s.model_dump(mode="json") for s in signals], indent=2)


def signals_to_csv(signals: list[RiskSignal]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=EXPORT_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for s in signals:
        writer.writerow(s.model_dump(mode="json"))
    return buf.getvalue()
