import csv
import io
import json

import pandas as pd
import pytest
from pydantic import ValidationError

from riskpulse.config import LABELLED_FILE
from riskpulse.nlp.entities import find_entities, mask_entities
from riskpulse.nlp.sentiment import analyze_sentiment
from riskpulse.pipeline import default_engine, run_default_pipeline, signals_to_csv, signals_to_json
from riskpulse.schemas import RiskSignal
from riskpulse.scoring.impact import score_impact
from riskpulse.universe import ALL_EVENT_LABELS, EVENT_TYPES


@pytest.fixture(scope="module")
def engine():
    return default_engine()


@pytest.fixture(scope="module")
def signals():
    return run_default_pipeline()[0]


@pytest.mark.parametrize("text,label", [
    ("company beat earnings estimates and raised guidance", "Positive"),
    ("company defaulted on its bonds and filed for bankruptcy", "Negative"),
    ("company will hold its annual general meeting on Thursday", "Neutral"),
])
def test_sentiment_labels(text, label):
    assert analyze_sentiment(text)["label"] == label


def test_sentiment_bounds_on_all_labelled_text():
    for t in pd.read_csv(LABELLED_FILE)["text"]:
        assert -1.0 <= analyze_sentiment(mask_entities(t))["score"] <= 1.0


def test_negation_and_hedging():
    assert analyze_sentiment("The company did not default")["score"] > analyze_sentiment("The company defaulted")["score"]
    plain = analyze_sentiment("company downgraded to junk")
    hedged = analyze_sentiment("company reportedly could be downgraded to junk")
    assert abs(hedged["score"]) < abs(plain["score"]) and hedged["hedge_count"] == 2


def test_company_names_carry_no_tone():
    # "Energy" / "Trust" are positive words in VADER; masking removes that bias
    assert analyze_sentiment(mask_entities("Helix Energy Corp schedules its investor call"))["label"] == "Neutral"
    assert analyze_sentiment(mask_entities("Granite Real Estate Trust schedules its investor call"))["label"] == "Neutral"


def test_entity_and_ticker_linking():
    ents = find_entities("Helix Energy Corp and $MRDS face sanctions; the summit ended")
    assert [e["ticker"] for e in ents] == ["HLXE", "MRDS"]
    assert find_entities("Leaders met at the summit") == []


@pytest.mark.parametrize("text,event", [
    ("Sanctions widen after military clashes at the border", "Geopolitical"),
    ("Central bank raises interest rates as inflation climbs", "Macroeconomic"),
    ("Orion Telecom downgraded to junk after missing a coupon payment", "Credit Event"),
    ("Atlas Airlines agrees to acquire a regional rival in an all-cash takeover", "Merger & Acquisition"),
    ("Aurora Semiconductors unveils a next-generation chip", "Product Launch"),
    ("Crestline Retail Q3 earnings beat estimates as revenue rises", "Earnings / Financial Results"),
    ("Regulator fines Northwind Bank over compliance failures", "Regulatory / Legal"),
    ("Ransomware attack and data breach hit Quantum Payments", "Cybersecurity"),
    ("Fire halts production at the Summit Steel plant", "Operational Disruption"),
    ("Bond market sell-off deepens as liquidity dries up", "Market / Liquidity"),
])
def test_each_supported_event_category(engine, text, event):
    assert engine.classifier.predict(text)["event_type"] == event


def test_unknown_event_is_unclassified(engine):
    out = engine.classifier.predict("Bluewater Utilities refreshes its corporate logo")
    assert out["event_type"] == "Unclassified"


def test_signal_schema_ranges_and_categories(signals):
    assert len(signals) > 200
    for s in signals:
        assert -1 <= s.sentiment_score <= 1 and 1 <= s.impact_score <= 10 and 0 <= s.confidence <= 1
        assert s.event_type in ALL_EVENT_LABELS and s.explanation
        assert s.signal_id.startswith("sig-") and s.is_synthetic
        if s.is_ambiguous:
            assert s.secondary_event_type in EVENT_TYPES
    assert len({s.signal_id for s in signals}) == len(signals)
    assert len({s.event_type for s in signals}) >= 10


def test_schema_rejects_invalid_values(signals):
    base = signals[0].model_dump()
    for field, bad in [("sentiment_score", 1.5), ("impact_score", 11), ("impact_score", 0), ("confidence", 1.2),
                       ("event_type", "Weather"), ("sentiment_label", "Bullish"), ("timestamp", "yesterday")]:
        with pytest.raises(ValidationError):
            RiskSignal(**{**base, field: bad})


def test_impact_factors_and_monotonicity():
    t = "Helix Energy defaults on its loans"
    news, f = score_impact(t, "Credit Event", -0.8, 0, "news")
    social, _ = score_impact(t, "Credit Event", -0.8, 0, "social")
    hedged, _ = score_impact(t, "Credit Event", -0.8, 3, "news")
    milder, _ = score_impact(t, "Credit Event", -0.2, 0, "news")
    held, _ = score_impact(t, "Credit Event", -0.8, 0, "news", entity_weight=0.12)
    positive, _ = score_impact(t, "Credit Event", 0.8, 0, "news")
    assert social <= news and hedged <= news and milder <= news and held >= news and positive < news
    assert abs(sum(v for k, v in f.items() if k != "raw_total") - f["raw_total"]) < 1e-6
    assert score_impact("logo refresh", "Unclassified", 0.9, 0, "news")[0] <= 2
    assert score_impact("war war war " * 5, "Geopolitical", -1, 0, "news", entity_weight=1)[0] == 10


def test_high_impact_is_not_just_negative_sentiment(signals):
    negative_low = [s for s in signals if s.sentiment_label == "Negative" and s.impact_score <= 5]
    assert negative_low, "negative sentiment alone must not imply high impact"


def test_json_and_csv_serialisation(signals):
    data = json.loads(signals_to_json(signals))
    assert len(data) == len(signals) and data[0]["signal_id"] == signals[0].signal_id
    rows = list(csv.DictReader(io.StringIO(signals_to_csv(signals))))
    assert len(rows) == len(signals) and {"sentiment_score", "impact_score", "explanation"} <= set(rows[0])
    RiskSignal(**data[0])  # round-trips through the schema


def test_analyze_text_free_input(engine):
    s = engine.analyze_text("Meridian Shipping files for Chapter 11 bankruptcy protection")
    assert s.ticker == "MRDS" and s.event_type == "Credit Event" and s.impact_score >= 8 and not s.is_synthetic
