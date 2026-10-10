"""Hybrid event classifier: transparent keyword rules + TF-IDF / logistic-regression model.

* Rules give auditable evidence ("matched: 'downgrade', 'missed coupon'").
* The supervised model generalises beyond the keyword list.
* Combined probability = W_ML * p_ml + W_RULE * p_rule (rules normalised to a distribution).
* Low evidence returns "Unclassified" instead of forcing a confident label; close runner-ups
  are flagged as ambiguous with a secondary category.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from ..universe import EVENT_TYPES, UNCLASSIFIED
from .entities import mask_entities

RANDOM_STATE = 42
W_ML, W_RULE = 0.55, 0.45
MIN_ML_PROB_NO_RULES = 0.40   # without rule evidence the model alone must clear this (11 classes, chance ~0.09)
MIN_COMBINED_PROB = 0.30
AMBIGUITY_RATIO = 0.75        # runner-up within 75% of the winner => ambiguous

RULES: dict[str, list[tuple[str, float]]] = {
    "Geopolitical": [
        (r"sanction", 1.5), (r"embargo", 1.5), (r"\bwar\b", 1.5), (r"military", 1.2),
        (r"\bconflict", 1.0), (r"border", 0.8), (r"missile", 1.5), (r"invasion", 1.5),
        (r"geopolitic", 1.5), (r"tension", 0.8), (r"\bcoup\b", 1.5), (r"ceasefire", 1.2),
        (r"blockade", 1.2), (r"strait", 0.8), (r"diplomatic", 1.0), (r"election", 0.6),
        (r"tariff", 0.6), (r"trade war", 1.0), (r"export (ban|control)", 1.2),
    ],
    "Macroeconomic": [
        (r"inflation", 1.5), (r"\bcpi\b", 1.5), (r"\bgdp\b", 1.5), (r"central bank", 1.5),
        (r"interest rates?", 1.0), (r"rate (hike|cut|increase|decision)", 1.5),
        (r"unemployment", 1.2), (r"jobs report|payrolls", 1.2), (r"recession", 1.2),
        (r"monetary policy", 1.5), (r"basis points", 0.8), (r"fiscal", 1.0), (r"\bpmi\b", 1.2),
        (r"consumer (spending|confidence)", 1.0), (r"economy|economic", 0.8), (r"tariff", 0.4),
        (r"yield curve", 1.0), (r"devaluation", 1.0), (r"\brates? (unchanged|steady|on hold)", 1.2),
    ],
    "Credit Event": [
        (r"default", 1.5), (r"downgrad", 1.5), (r"credit rating", 1.2),
        (r"missed (a |its )?(coupon|interest|bond|loan|debt)", 1.8), (r"bankrupt", 1.8),
        (r"insolven", 1.8), (r"restructur", 1.0), (r"covenant", 1.2), (r"distressed", 1.0),
        (r"creditors", 1.0), (r"chapter 11", 1.8), (r"delinquen", 1.2), (r"non-performing", 1.2),
        (r"credit ?watch|negative watch", 1.2), (r"junk", 1.0), (r"debt (payment|obligation)", 0.8),
        (r"upgrad", 1.0), (r"rating (agency|affirmed)", 1.0), (r"investment grade", 1.0),
    ],
    "Merger & Acquisition": [
        (r"acquir", 1.5), (r"acquisition", 1.5), (r"merger", 1.5), (r"takeover", 1.5),
        (r"buyout", 1.5), (r"\bbid for\b", 1.2), (r"\bstake\b", 0.8), (r"tender offer", 1.5),
        (r"divest", 1.2), (r"spin-?off", 1.2), (r"combine|combination", 0.8), (r"all-stock|all-cash", 1.2),
    ],
    "Product Launch": [
        (r"launch", 1.5), (r"unveil", 1.5), (r"new (product|platform|chip|service|app|model|line)", 1.2),
        (r"roll(s|ed)? out|rollout", 1.0), (r"introduc", 0.8), (r"debut", 1.2),
        (r"next-generation|next generation", 1.2), (r"release[sd]? (a |its )?new", 1.0), (r"pre-orders?", 1.2),
    ],
    "Earnings / Financial Results": [
        (r"earnings", 1.5), (r"quarterly (results|profit|revenue)", 1.5), (r"revenue", 1.0),
        (r"\bprofit", 1.0), (r"\beps\b", 1.2), (r"guidance", 1.0), (r"\bq[1-4]\b", 1.0),
        (r"(beat|miss(ed)?)\b.{0,15}(estimates|expectations|consensus)", 1.5),
        (r"net income", 1.2), (r"margins?", 0.6), (r"dividend", 0.8), (r"full-year|annual results", 1.2),
    ],
    "Regulatory / Legal": [
        (r"regulator", 1.5), (r"regulatory", 1.2), (r"lawsuit", 1.5), (r"\bsued\b", 1.5),
        (r"\bfined?\b", 1.2), (r"penalt", 1.2), (r"antitrust", 1.5), (r"investigation", 1.0),
        (r"\bprobe\b", 1.2), (r"settlement", 1.0), (r"compliance", 1.0), (r"court", 1.2),
        (r"ruling", 1.0), (r"licen[cs]e", 0.8), (r"litigation", 1.5), (r"class action", 1.5),
        (r"watchdog", 1.2),
    ],
    "Cybersecurity": [
        (r"cyber", 1.8), (r"hack", 1.5), (r"data breach|breach of", 1.5), (r"ransomware", 2.0),
        (r"malware", 1.8), (r"phishing", 1.5), (r"ddos", 1.8), (r"vulnerabilit", 1.0),
        (r"exploit", 1.0), (r"leak(ed)? (data|records)|records (were )?exposed", 1.5),
        (r"unauthori[sz]ed access", 1.5), (r"customer data", 0.8),
    ],
    "Operational Disruption": [
        (r"outage", 1.5), (r"disrupt", 1.0), (r"\bstrike\b", 1.2), (r"shutdown|shut down", 1.2),
        (r"\bfire\b", 1.0), (r"explosion", 1.5), (r"supply chain", 1.2), (r"halt", 1.0),
        (r"recall", 1.2), (r"accident", 1.2), (r"flood", 1.2), (r"power failure", 1.5),
        (r"system failure|glitch", 1.2), (r"grounded", 1.5), (r"port congestion", 1.5),
        (r"production (halt|stoppage|line)", 1.2), (r"delays?\b", 0.6),
    ],
    "Market / Liquidity": [
        (r"liquidity", 1.5), (r"sell-?off", 1.5), (r"volatility", 1.2), (r"margin call", 1.8),
        (r"outflows", 1.5), (r"bank run", 1.8), (r"withdrawals", 1.0), (r"funding (stress|pressure|costs)", 1.5),
        (r"spreads? (widen|blow)", 1.5), (r"flash crash", 1.8), (r"trading halt", 1.2),
        (r"redemption", 1.2), (r"fire sale", 1.5), (r"\brepo\b", 1.2), (r"market turmoil|rout", 1.5),
        (r"bid-ask", 1.2),
    ],
}
_COMPILED = {k: [(re.compile(p, re.IGNORECASE), w) for p, w in v] for k, v in RULES.items()}


def rule_scores(text: str) -> tuple[dict[str, float], dict[str, list[str]]]:
    """Keyword evidence per category: summed weights and the matched snippets."""
    scores, evidence = {}, {}
    for cat, pats in _COMPILED.items():
        hits = [(m.group(0), w) for rx, w in pats if (m := rx.search(text))]
        if hits:
            scores[cat] = sum(w for _, w in hits)
            evidence[cat] = [h for h, _ in hits]
    return scores, evidence


@dataclass
class EventClassifier:
    labels: list[str] = field(default_factory=lambda: EVENT_TYPES + [UNCLASSIFIED])
    use_rules: bool = True
    use_ml: bool = True
    model: Pipeline | None = None

    def fit(self, texts: list[str], labels: list[str]) -> "EventClassifier":
        self.model = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1, stop_words="english")),
            ("lr", LogisticRegression(max_iter=3000, C=20.0, class_weight="balanced", random_state=RANDOM_STATE)),
        ])
        self.model.fit([mask_entities(t) for t in texts], labels)
        return self

    def _ml_probs(self, text: str) -> np.ndarray:
        probs = np.zeros(len(self.labels))
        if self.model is None or not self.use_ml:
            return probs
        p = self.model.predict_proba([mask_entities(text)])[0]
        for cls, val in zip(self.model.classes_, p):
            probs[self.labels.index(cls)] = val
        return probs

    def predict(self, text: str) -> dict:
        rs, evidence = rule_scores(text) if self.use_rules else ({}, {})
        p_rule = np.zeros(len(self.labels))
        if rs:
            total = sum(rs.values())
            for cat, s in rs.items():
                p_rule[self.labels.index(cat)] = s / total
        p_ml = self._ml_probs(text)

        if self.use_ml and self.model is not None and rs:
            combined = W_ML * p_ml + W_RULE * p_rule
        elif rs:
            combined = p_rule
        else:
            combined = p_ml

        order = np.argsort(combined)[::-1]
        top, second = self.labels[order[0]], self.labels[order[1]]
        top_p, second_p = float(combined[order[0]]), float(combined[order[1]])

        reason = ""
        if top_p == 0.0:
            top, reason = UNCLASSIFIED, "no event evidence found"
        elif not rs and top != UNCLASSIFIED and top_p < MIN_ML_PROB_NO_RULES:
            top, reason = UNCLASSIFIED, f"no keyword evidence and model probability {top_p:.2f} < {MIN_ML_PROB_NO_RULES}"
        elif top != UNCLASSIFIED and top_p < MIN_COMBINED_PROB:
            top, reason = UNCLASSIFIED, f"combined probability {top_p:.2f} < {MIN_COMBINED_PROB}"

        ambiguous = (
            top != UNCLASSIFIED and second != UNCLASSIFIED and second_p > 0 and second_p >= AMBIGUITY_RATIO * top_p
        )
        confidence = top_p * (0.85 if ambiguous else 1.0)
        if top == UNCLASSIFIED:
            confidence = float(combined[self.labels.index(UNCLASSIFIED)]) or (1.0 - top_p)
        return {
            "event_type": top,
            "secondary_event_type": second if ambiguous else None,
            "is_ambiguous": bool(ambiguous),
            "confidence": round(min(1.0, max(0.0, confidence)), 4),
            "rule_evidence": evidence.get(top, []),
            "all_rule_evidence": evidence,
            "ml_probability": round(float(p_ml[self.labels.index(top)]), 4) if self.use_ml else None,
            "unclassified_reason": reason,
            "probabilities": {lab: round(float(combined[i]), 4) for i, lab in enumerate(self.labels)},
        }
