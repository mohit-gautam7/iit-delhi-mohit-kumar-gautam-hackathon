"""Finance-adapted sentiment: VADER (Hutto & Gilbert, 2014) + finance lexicon + phrase rules + hedging.

VADER already handles negation ("not good"), intensifiers, capitalisation and "but" clauses.
We add domain vocabulary (e.g. "downgrade", "default", "beat"), neutralise words that VADER
scores but which are neutral in finance ("credit", "security", "trust", "interest"), apply
multi-word finance phrases, and dampen scores of hedged/unconfirmed language.
"""
from __future__ import annotations

import re
from functools import lru_cache

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

POSITIVE_THRESHOLD = 0.15  # wider neutral band than VADER's +/-0.05: finance text is terse
NEGATIVE_THRESHOLD = -0.15

FINANCE_LEXICON = {
    # negative
    "default": -3.0, "defaults": -3.0, "defaulted": -3.2, "bankruptcy": -3.5, "insolvency": -3.2,
    "insolvent": -3.2, "downgrade": -2.5, "downgraded": -2.5, "downgrades": -2.5, "plunge": -2.8,
    "plunges": -2.8, "plunged": -2.8, "slump": -2.3, "slumps": -2.3, "tumble": -2.3, "tumbles": -2.3,
    "selloff": -2.3, "sell-off": -2.3, "breach": -2.5, "breached": -2.5, "hack": -2.3, "hacked": -2.5,
    "ransomware": -3.0, "malware": -2.5, "outage": -2.2, "outages": -2.2, "disruption": -1.8,
    "disrupted": -1.8, "halted": -1.8, "halts": -1.8, "sanctions": -2.0, "tariffs": -1.5,
    "tariff": -1.5, "embargo": -2.2, "conflict": -2.0, "war": -2.9, "escalation": -1.8,
    "escalates": -1.8, "recession": -2.5, "inflation": -1.2, "layoffs": -2.0, "lawsuit": -1.8,
    "probe": -1.5, "fine": -1.2, "fined": -2.0, "fines": -1.5, "penalty": -1.8, "investigation": -1.5,
    "recall": -2.0, "recalls": -2.0, "delay": -1.3, "delayed": -1.3, "delays": -1.3,
    "shortfall": -2.0, "writedown": -2.2, "write-down": -2.2, "impairment": -2.0, "losses": -1.8,
    "loss": -1.6, "volatility": -1.2, "illiquid": -2.0, "outflows": -1.8, "contagion": -2.5,
    "miss": -1.8, "missed": -1.8, "misses": -1.8, "warns": -1.5, "bearish": -2.0, "crash": -3.0,
    "delisting": -2.5, "strike": -1.5, "shutdown": -2.0, "distressed": -2.3, "restructuring": -1.2,
    "widen": -1.0, "widened": -1.0, "widening": -1.0, "turmoil": -2.5, "blockade": -2.2,
    # positive
    "beat": 1.8, "beats": 1.8, "topped": 1.5, "surge": 2.2, "surges": 2.2, "surged": 2.2,
    "rally": 1.8, "rallies": 1.8, "soar": 2.4, "soars": 2.4, "upgrade": 2.2, "upgraded": 2.2,
    "upgrades": 2.2, "outperform": 1.8, "bullish": 2.0, "growth": 1.5, "profit": 1.6,
    "profits": 1.6, "robust": 1.8, "resilient": 1.6, "launch": 1.0, "launches": 1.0,
    "unveils": 1.0, "approved": 1.8, "expansion": 1.4, "synergies": 1.6, "dividend": 1.4,
    "buyback": 1.5, "ceasefire": 1.8, "easing": 1.0, "stabilises": 1.2, "stabilizes": 1.2,
    "recovery": 1.6, "restored": 1.5, "resolved": 1.4, "acquire": 0.6, "acquisition": 0.6,
}

# Words VADER scores but which are neutral in finance. They are REMOVED from the lexicon
# (not set to 0.0: VADER would still apply its ALL-CAPS emphasis to a zero-valued word).
NEUTRAL_WORDS = {"credit", "security", "cybersecurity", "trust", "interest", "share", "shares", "bank", "crude", "demand", "summit", "justice", "liquidity", "capital", "rating", "stake", "energy", "gained", "advanced", "united"}

# (pattern, compound adjustment) for multi-word expressions VADER cannot see.
PHRASES = [
    (r"\b(beat|beats|topped|exceeded)\b.{0,20}\b(estimates|expectations|forecasts|consensus)\b", 0.35),
    (r"\bmiss(ed|es)?\b.{0,20}\b(estimates|expectations|forecasts|consensus)\b", -0.35),
    (r"\b(raise[sd]?|lift(s|ed)?)\b.{0,15}\b(guidance|outlook|forecast)\b", 0.35),
    (r"\b(cut(s)?|lower(s|ed)?|slash(es|ed)?)\b.{0,15}\b(guidance|outlook|forecast)\b", -0.4),
    (r"\brecord (loss|losses)\b", -0.4),
    (r"\bmissed (a |its )?(coupon|interest|bond|loan)? ?payment", -0.5),
    (r"\brate (hike|hikes|increase)\b", -0.2),
    (r"\bspreads? widen", -0.25),
    (r"\b(no|not) (expected to have )?(a )?(material )?impact\b", 0.25),
]

HEDGES = re.compile(
    r"\b(may|might|could|reportedly|rumou?r(s|ed)?|unconfirmed|possible|possibly|allegedly|"
    r"speculation|sources say|considering|potential(ly)?|unverified)\b",
    re.IGNORECASE,
)


@lru_cache(maxsize=1)
def _analyzer() -> SentimentIntensityAnalyzer:
    sia = SentimentIntensityAnalyzer()
    sia.lexicon.update(FINANCE_LEXICON)
    for w in NEUTRAL_WORDS:
        sia.lexicon.pop(w, None)
    return sia


def label_for(score: float) -> str:
    if score >= POSITIVE_THRESHOLD:
        return "Positive"
    if score <= NEGATIVE_THRESHOLD:
        return "Negative"
    return "Neutral"


def analyze_sentiment(text: str) -> dict:
    """Return score in [-1, 1], label, and the evidence behind it."""
    sia = _analyzer()
    scores = sia.polarity_scores(text)
    compound = scores["compound"]
    lowered = text.lower()
    phrase_adj = sum(adj for pat, adj in PHRASES if re.search(pat, lowered))
    hedges = len(HEDGES.findall(text))
    hedge_factor = max(0.6, 0.85 ** hedges)
    score = max(-1.0, min(1.0, (compound + phrase_adj) * hedge_factor))
    tokens = re.findall(r"[a-z][a-z\-]+", lowered)
    drivers = sorted({t for t in tokens if abs(sia.lexicon.get(t, 0.0)) >= 1.0},
                     key=lambda t: -abs(sia.lexicon[t]))[:6]
    return {
        "score": round(score, 4),
        "label": label_for(score),
        "vader_compound": compound,
        "phrase_adjustment": round(phrase_adj, 3),
        "hedge_count": hedges,
        "hedge_factor": round(hedge_factor, 3),
        "mixed": scores["pos"] >= 0.12 and scores["neg"] >= 0.12,
        "drivers": drivers,
    }
