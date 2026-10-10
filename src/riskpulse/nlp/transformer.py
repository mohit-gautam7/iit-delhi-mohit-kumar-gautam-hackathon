"""Optional transformer upgrade (open models, run locally, no API key):

* ProsusAI/finbert            - finance-tuned sentiment (score = P(positive) - P(negative))
* facebook/bart-large-mnli    - zero-shot event classification, used only as a FALLBACK when the
                                transparent hybrid classifier returns "Unclassified"

Requires ``pip install -r requirements-transformers.txt`` (torch + transformers) and the model
weights (downloaded once from Hugging Face, ~2 GB). Everything degrades gracefully: if the
libraries or weights are missing, ``available()`` is False and the baseline is used.
"""
from __future__ import annotations

import os
from functools import lru_cache

from ..universe import UNCLASSIFIED

FINBERT = os.getenv("RISKPULSE_FINBERT_MODEL", "ProsusAI/finbert")
ZERO_SHOT = os.getenv("RISKPULSE_ZERO_SHOT_MODEL", "facebook/bart-large-mnli")
ZERO_SHOT_MIN_SCORE = 0.35
HYPOTHESIS = "This news is about {}."
ZS_LABELS = {
    "Geopolitical": "geopolitics, war, sanctions or diplomacy",
    "Macroeconomic": "the macro economy, inflation, interest rates or jobs",
    "Credit Event": "credit risk, debt default, bankruptcy or a credit rating change",
    "Merger & Acquisition": "a merger, acquisition or sale of a business",
    "Product Launch": "a new product or service launch",
    "Earnings / Financial Results": "company earnings, sales or financial results",
    "Regulatory / Legal": "regulation, fines, lawsuits or courts",
    "Cybersecurity": "a cyberattack, hacking or data breach",
    "Operational Disruption": "an operational disruption such as an outage, strike, fire or recall",
    "Market / Liquidity": "financial market liquidity, fund outflows, sell-offs or a bank run",
    UNCLASSIFIED: "routine corporate news with no financial risk",
}
_INV = {v: k for k, v in ZS_LABELS.items()}


@lru_cache(maxsize=1)
def available() -> bool:
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        from huggingface_hub import try_to_load_from_cache
    except Exception:
        return False
    if os.getenv("HF_HUB_OFFLINE") == "1":
        return all(isinstance(try_to_load_from_cache(m, "config.json"), str) for m in (FINBERT, ZERO_SHOT))
    return True


@lru_cache(maxsize=1)
def _finbert():
    from transformers import pipeline
    return pipeline("text-classification", model=FINBERT, top_k=None, device=-1)


@lru_cache(maxsize=1)
def _zero_shot():
    from transformers import pipeline
    return pipeline("zero-shot-classification", model=ZERO_SHOT, device=-1)


def finbert_scores(texts: list[str]) -> list[dict]:
    """Return per-text {'score', 'probs'} with score = P(pos) - P(neg) in [-1, 1]."""
    out = []
    for res in _finbert()(texts, batch_size=32, truncation=True):
        probs = {r["label"].lower(): float(r["score"]) for r in res}
        out.append({"score": probs.get("positive", 0.0) - probs.get("negative", 0.0), "probs": probs})
    return out


def zero_shot_event(text: str) -> dict:
    res = _zero_shot()(text, list(ZS_LABELS.values()), hypothesis_template=HYPOTHESIS)
    label, score = _INV[res["labels"][0]], float(res["scores"][0])
    if score < ZERO_SHOT_MIN_SCORE:
        label = UNCLASSIFIED
    return {"event_type": label, "score": score,
            "ranking": {_INV[lab]: round(float(s), 4) for lab, s in zip(res["labels"], res["scores"])}}
