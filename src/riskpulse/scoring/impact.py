"""Transparent, configurable impact scoring (1-10). See config/scoring.yaml for every weight."""
from __future__ import annotations

import math
import re

from ..config import scoring_config
from ..nlp.sentiment import NEGATIVE_THRESHOLD, POSITIVE_THRESHOLD


def score_impact(
    text: str,
    event_type: str,
    sentiment_score: float,
    hedge_count: int,
    source_type: str,
    engagement: int = 0,
    entity_weight: float = 0.0,
    cfg: dict | None = None,
) -> tuple[int, dict[str, float]]:
    """Return ``(impact_score, factor_contributions)``; contributions sum to the raw score."""
    cfg = cfg or scoring_config()
    lowered = text.lower()

    base = float(cfg["base_severity"].get(event_type, cfg["base_severity"]["Unclassified"]))

    ic = cfg["intensity"]
    hits = sum(1 for kw in ic["keywords"] if re.search(rf"\b{re.escape(kw)}", lowered))
    intensity = min(ic["cap"], hits * ic["per_keyword"])

    bc = cfg["breadth"]
    breadth = 0.0
    if any(re.search(rf"\b{re.escape(t)}\b", lowered) for t in bc["market_wide_terms"]):
        breadth += bc["market_wide_bonus"]
    if event_type in bc["broad_event_types"]:
        breadth += bc["broad_event_bonus"]

    ec = cfg["exposure"]
    exposure = ec["max_bonus"] * min(1.0, max(0.0, entity_weight) / ec["full_weight"])

    sc = cfg["sentiment"]
    weight = sc["negative_weight"] if sentiment_score < 0 else sc["positive_weight"]
    sentiment = abs(sentiment_score) * weight

    dc = cfg["direction"]
    if sentiment_score >= POSITIVE_THRESHOLD:
        direction = -dc["positive_discount"]
    elif sentiment_score > NEGATIVE_THRESHOLD:
        direction = -dc["neutral_discount"]
    else:
        direction = 0.0

    uc = cfg["uncertainty"]
    uncertainty = -min(uc["cap"], hedge_count * uc["per_hedge_penalty"])

    ev = cfg["evidence"]
    reliability = ev["source_reliability"].get(source_type, 0.6)
    if source_type == "social" and engagement >= ev["engagement_corroboration"]:
        reliability = min(1.0, reliability + 0.2)
    evidence = -(1.0 - reliability) * ev["low_reliability_penalty"]

    if event_type == "Unclassified":  # no event => only base severity counts
        intensity = breadth = exposure = sentiment = direction = 0.0

    factors = {
        "base_severity": base,
        "intensity": intensity,
        "breadth": breadth,
        "exposure": round(exposure, 3),
        "sentiment": round(sentiment, 3),
        "direction": direction,
        "uncertainty": uncertainty,
        "evidence_quality": round(evidence, 3),
    }
    factors = {k: v + 0.0 for k, v in factors.items()}  # normalise -0.0 to 0.0 for display
    raw = sum(factors.values())
    factors["raw_total"] = round(raw, 3)
    return int(min(10, max(1, math.floor(raw + 0.5)))), factors  # round half up
