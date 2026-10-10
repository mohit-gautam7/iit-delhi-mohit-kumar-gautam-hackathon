"""Dictionary-based entity and ticker linking against the (fictional) company universe."""
from __future__ import annotations

import re

from ..universe import BY_TICKER, COMPANIES

# Aliases are matched case-sensitively on word boundaries, longest first, so "Helix Energy"
# wins over "Helix" and the lowercase word "summit" never maps to a company.
_ALIAS_PATTERNS = sorted(
    ((alias, c) for c in COMPANIES for alias in c["aliases"]), key=lambda x: -len(x[0])
)
_ALIAS_RE = re.compile("|".join(rf"\b{re.escape(a)}\b" for a, _ in _ALIAS_PATTERNS))
_ALIAS_TO_CO = {a: c for a, c in _ALIAS_PATTERNS}
_TICKER_RE = re.compile(r"(?<![A-Za-z])\$?(" + "|".join(BY_TICKER) + r")\b")


def find_entities(text: str) -> list[dict]:
    """Return companies mentioned, ordered by first mention. Each item: name, ticker, sector, matched."""
    hits: dict[str, tuple[int, str]] = {}
    for m in _ALIAS_RE.finditer(text):
        co = _ALIAS_TO_CO[m.group(0)]
        hits.setdefault(co["ticker"], (m.start(), m.group(0)))
    for m in _TICKER_RE.finditer(text):
        hits.setdefault(m.group(1), (m.start(), m.group(0)))
    ordered = sorted(hits.items(), key=lambda kv: kv[1][0])
    return [
        {"name": BY_TICKER[t]["name"], "ticker": t, "sector": BY_TICKER[t]["sector"], "matched": s}
        for t, (_, s) in ordered
    ]


def mask_entities(text: str) -> str:
    """Replace company names/tickers with a placeholder so the classifier learns events, not names."""
    return _TICKER_RE.sub("company", _ALIAS_RE.sub("company", text))
