"""Generate all reproducible synthetic demo data (fixed seed). Run: python scripts/generate_demo_data.py

Writes to data/: news_sample.csv, social_sample.csv, labelled_events.csv, portfolio.csv,
upload_example.json, malformed_example.csv. Every record is fictional and flagged is_synthetic.
"""
from __future__ import annotations

import csv
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from riskpulse.universe import COMPANIES  # noqa: E402
from templates import AMOUNTS, BPS, HERO_NEWS, PCTS, PRODUCTS, QUARTERS, REGIONS, T  # noqa: E402

SEED = 42
DATA = ROOT / "data"
START = datetime(2026, 9, 21, tzinfo=timezone.utc)
WINDOW_HOURS = 14 * 24
NEWS_SOURCES = ["Synthetic Wire", "Synthetic Markets Desk", "Synthetic Business Daily"]
FILLERS = ["", "", "Further details were not immediately available.",
           "The company did not immediately respond to a request for comment.",
           "Analysts said they would review the update in the coming days."]


NEWS_PREFIX = ["", "", "", "Update: ", "Breaking: ", "Markets: "]
NEWS_SUFFIX = ["", "", "", ", analysts said", ", according to people familiar with the matter",
               " on Tuesday", " in early trading", ", sources said"]
SOCIAL_PREFIX = ["", "", "", "wow. ", "ok so ", "heads up: ", "ugh "]
SOCIAL_SUFFIX = ["", "", "", " #markets", " #finance", " thoughts?", " lol"]


def fill(tpl: str, rng: random.Random, style: str = "news") -> tuple[str, dict]:
    co, co2 = rng.sample(COMPANIES, 2)
    pre, suf = (NEWS_PREFIX, NEWS_SUFFIX) if style == "news" else (SOCIAL_PREFIX, SOCIAL_SUFFIX)
    text = rng.choice(pre) + tpl.format(co=co["name"], co2=co2["name"], tk=co["ticker"], pct=rng.choice(PCTS), bp=rng.choice(BPS),
                      amt=rng.choice(AMOUNTS), q=rng.choice(QUARTERS), region=rng.choice(REGIONS),
                      product=rng.choice(PRODUCTS)) + rng.choice(suf)
    return text, co


def ts(rng: random.Random) -> str:
    return (START + timedelta(minutes=rng.randrange(WINDOW_HOURS * 60))).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_csv(path: Path, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def labelled(rng: random.Random, per_template: int = 4) -> list[dict]:
    rows, seen = [], set()
    for tid, (event, sentiment, style, tpl) in enumerate(T):
        for _ in range(per_template * 6):
            text, _ = fill(tpl, rng, style)
            if text not in seen:
                seen.add(text)
                rows.append({"text": text, "event_type": event, "sentiment_label": sentiment,
                             "style": style, "template_id": f"T{tid:03d}", "is_synthetic": "true"})
            if sum(r["template_id"] == f"T{tid:03d}" for r in rows) >= per_template:
                break
    return rows


def news(rng: random.Random, n: int = 120) -> list[dict]:
    rows = [{"article_id": f"N-H{i:02d}", "published_at": t, "source_name": src, "headline": h, "body": b,
             "author": "RiskPulse synthetic generator", "is_synthetic": "true"}
            for i, (t, src, h, b) in enumerate(HERO_NEWS)]
    pool = [t for t in T if t[2] == "news"]
    for i in range(n):
        _, _, _, tpl = rng.choice(pool)
        text, _ = fill(tpl, rng, "news")
        rows.append({"article_id": f"N{i:04d}", "published_at": ts(rng), "source_name": rng.choice(NEWS_SOURCES),
                     "headline": text, "body": rng.choice(FILLERS), "author": "RiskPulse synthetic generator",
                     "is_synthetic": "true"})
    return rows


def social(rng: random.Random, n: int = 130, reposts: int = 10) -> list[dict]:
    pool = [t for t in T if t[2] == "social"]
    rows = []
    for i in range(n):
        _, _, _, tpl = rng.choice(pool)
        text, _ = fill(tpl, rng, "social")
        rows.append({"post_id": f"S{i:04d}", "created_at": ts(rng), "platform": "SynthSocial",
                     "handle": f"@trader_{rng.randrange(100, 999)}", "text": text,
                     "likes": rng.choice([0, 3, 12, 40, 150, 900]), "reposts": rng.choice([0, 1, 5, 30, 200]),
                     "is_synthetic": "true"})
    # reposts of earlier posts: exercise duplicate detection ("RT @handle:" prefix is ignored)
    for j, src in enumerate(rng.sample(rows, reposts)):
        t = datetime.fromisoformat(src["created_at"].replace("Z", "+00:00")) + timedelta(minutes=rng.randrange(5, 240))
        rows.append({**src, "post_id": f"S-RT{j:02d}", "created_at": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "handle": f"@reposter_{rng.randrange(100, 999)}", "text": f"RT {src['handle']}: {src['text']}",
                     "likes": 0, "reposts": 0})
    rng.shuffle(rows)
    return rows


def portfolio() -> list[dict]:
    """Illustrative ~USD 1bn wholesale-banking book. Amounts are invented for the demo."""
    P = []

    def add(pid, name, ac, it, issuer="", ticker="", sector="", region="US", ccy="USD", rating="", notional=0.0,
            mv=0.0, dur=0.0, sdur=0.0, pd=0.0, lgd=0.0, beta=0.0, delta=0.0, underlying=""):
        P.append({"position_id": pid, "name": name, "asset_class": ac, "instrument_type": it, "issuer": issuer,
                  "ticker": ticker, "sector": sector, "region": region, "currency": ccy, "rating": rating,
                  "notional_usd": notional, "market_value_usd": mv, "modified_duration": dur, "spread_duration": sdur,
                  "pd_1y": pd, "lgd": lgd, "beta": beta, "delta": delta, "underlying": underlying,
                  "is_synthetic": "true"})

    # Loans (carrying value = EAD), floating unless a duration is given
    add("LN01", "Northwind Bank revolving credit facility", "Loan", "Revolving Credit Facility", "Northwind Bank", "NWBK", "Financials", rating="A", notional=60e6, mv=60e6, pd=0.004, lgd=0.40)
    add("LN02", "Helix Energy term loan B", "Loan", "Term Loan", "Helix Energy Corp", "HLXE", "Energy", rating="BB", notional=85e6, mv=85e6, pd=0.020, lgd=0.45)
    add("LN03", "Meridian Shipping vessel financing", "Loan", "Asset-Backed Loan", "Meridian Shipping", "MRDS", "Industrials", "EU", "EUR", "BB-", 70e6, 70e6, pd=0.030, lgd=0.35)
    add("LN04", "Crestline Retail working capital loan", "Loan", "Term Loan", "Crestline Retail Group", "CRST", "Consumer", rating="BBB-", notional=55e6, mv=55e6, pd=0.012, lgd=0.45)
    add("LN05", "Atlas Airlines aircraft-backed loan", "Loan", "Asset-Backed Loan", "Atlas Airlines", "ATLA", "Industrials", rating="BB", notional=65e6, mv=65e6, pd=0.025, lgd=0.30)
    add("LN06", "Granite REIT fixed-rate mortgage loan", "Loan", "Commercial Real Estate Loan", "Granite Real Estate Trust", "GRET", "Real Estate", rating="BBB", notional=80e6, mv=80e6, dur=3.5, pd=0.015, lgd=0.35)
    add("LN07", "Summit Steel export finance", "Loan", "Trade Finance", "Summit Steel Industries", "SMST", "Materials", "APAC", "USD", "BB+", 45e6, 45e6, pd=0.018, lgd=0.40)
    add("LN08", "Quantum Payments term loan", "Loan", "Term Loan", "Quantum Payments", "QPAY", "Financials", rating="BBB", notional=40e6, mv=40e6, pd=0.010, lgd=0.45)
    # Corporate bonds
    add("CB01", "Aurora Semiconductors 4.25% 2031", "Corporate Bond", "Senior Unsecured Bond", "Aurora Semiconductors", "AURS", "Technology", "APAC", "USD", "A-", 30e6, 29.4e6, 4.6, 4.5)
    add("CB02", "Orion Telecom 3.5% 2033 (EUR)", "Corporate Bond", "Senior Unsecured Bond", "Orion Telecom", "ORTL", "Telecom", "EU", "EUR", "BBB", 35e6, 33.6e6, 6.1, 6.0)
    add("CB03", "Bluewater Utilities 5.0% 2036", "Corporate Bond", "Senior Secured Bond", "Bluewater Utilities", "BWUT", "Utilities", rating="A", notional=30e6, mv=31.2e6, dur=7.8, sdur=7.6)
    add("CB04", "Meridian Shipping 7.75% 2029", "Corporate Bond", "High Yield Bond", "Meridian Shipping", "MRDS", "Industrials", "EU", "USD", "B+", 25e6, 24.1e6, 2.8, 2.7)
    add("CB05", "Helix Energy 6.0% 2030", "Corporate Bond", "High Yield Bond", "Helix Energy Corp", "HLXE", "Energy", rating="BB", notional=25e6, mv=25.6e6, dur=3.4, sdur=3.3)
    add("CB06", "Northwind Bank 4.0% 2028 senior", "Corporate Bond", "Senior Unsecured Bond", "Northwind Bank", "NWBK", "Financials", rating="A", notional=30e6, mv=29.7e6, dur=1.9, sdur=1.9)
    add("CB07", "Vantage Pharma 3.75% 2032 (EUR)", "Corporate Bond", "Senior Unsecured Bond", "Vantage Pharma", "VNTP", "Healthcare", "EU", "EUR", "A+", 25e6, 24.5e6, 5.4, 5.3)
    add("CB08", "Crestline Retail 5.5% 2030", "Corporate Bond", "Senior Unsecured Bond", "Crestline Retail Group", "CRST", "Consumer", rating="BBB-", notional=20e6, mv=19.6e6, dur=3.6, sdur=3.5)
    # Government bonds (synthetic sovereign issuers)
    add("GB01", "US Treasury 2Y", "Government Bond", "Sovereign Bond", "US Treasury", rating="AA+", notional=60e6, mv=59.6e6, dur=1.9)
    add("GB02", "US Treasury 10Y", "Government Bond", "Sovereign Bond", "US Treasury", rating="AA+", notional=50e6, mv=48.5e6, dur=8.4)
    add("GB03", "Euro-area sovereign 10Y (EUR)", "Government Bond", "Sovereign Bond", "Euro-area sovereign", region="EU", ccy="EUR", rating="AAA", notional=40e6, mv=38.8e6, dur=8.9)
    add("GB04", "Japan sovereign 5Y (JPY)", "Government Bond", "Sovereign Bond", "Japan sovereign", region="APAC", ccy="JPY", rating="A+", notional=25e6, mv=25.1e6, dur=4.8)
    # Equities
    add("EQ01", "Northwind Bank common stock", "Equity", "Common Stock", "Northwind Bank", "NWBK", "Financials", mv=14e6, beta=1.15)
    add("EQ02", "Helix Energy common stock", "Equity", "Common Stock", "Helix Energy Corp", "HLXE", "Energy", mv=12e6, beta=0.95)
    add("EQ03", "Aurora Semiconductors common stock", "Equity", "Common Stock", "Aurora Semiconductors", "AURS", "Technology", "APAC", mv=16e6, beta=1.35)
    add("EQ04", "Meridian Shipping common stock (EUR)", "Equity", "Common Stock", "Meridian Shipping", "MRDS", "Industrials", "EU", "EUR", mv=8e6, beta=1.25)
    add("EQ05", "Vantage Pharma common stock (EUR)", "Equity", "Common Stock", "Vantage Pharma", "VNTP", "Healthcare", "EU", "EUR", mv=10e6, beta=0.70)
    add("EQ06", "Quantum Payments common stock", "Equity", "Common Stock", "Quantum Payments", "QPAY", "Financials", mv=11e6, beta=1.40)
    add("EQ07", "Granite REIT units", "Equity", "REIT Units", "Granite Real Estate Trust", "GRET", "Real Estate", mv=9e6, beta=1.05)
    add("EQ08", "Orion Telecom common stock (EUR)", "Equity", "Common Stock", "Orion Telecom", "ORTL", "Telecom", "EU", "EUR", mv=7e6, beta=0.80)
    # FX cash exposures (USD value of foreign-currency balances)
    add("FX01", "EUR cash balance", "FX", "Currency Balance", region="EU", ccy="EUR", notional=18e6, mv=18e6)
    add("FX02", "GBP cash balance", "FX", "Currency Balance", region="EU", ccy="GBP", notional=12e6, mv=12e6)
    add("FX03", "JPY cash balance", "FX", "Currency Balance", region="APAC", ccy="JPY", notional=10e6, mv=10e6)
    # Derivatives (MV = current mark; P&L via delta / duration on notional)
    add("DV01", "Equity index future (short hedge)", "Derivative", "Equity Index Future", notional=40e6, mv=0.0, beta=1.0, delta=-1.0, underlying="EQ_INDEX")
    add("DV02", "Aurora Semiconductors call options", "Derivative", "Equity Option", "Aurora Semiconductors", "AURS", "Technology", "APAC", notional=10e6, mv=1.2e6, beta=1.35, delta=0.55, underlying="AURS")
    add("DV03", "5Y USD interest rate swap (pay fixed)", "Derivative", "Interest Rate Swap", notional=100e6, mv=0.8e6, dur=4.6, delta=-1.0, underlying="USD_RATES")
    add("DV04", "CDS protection bought on Meridian Shipping", "Derivative", "Credit Default Swap", "Meridian Shipping", "MRDS", "Industrials", "EU", rating="B+", notional=15e6, mv=0.3e6, sdur=4.2, delta=-1.0, underlying="MRDS")
    add("DV05", "Brent-style crude oil future (long)", "Derivative", "Commodity Future", notional=12e6, mv=0.0, delta=1.0, underlying="oil")
    add("DV06", "EUR/USD forward (short EUR hedge)", "Derivative", "FX Forward", region="EU", ccy="EUR", notional=25e6, mv=0.1e6, delta=-1.0, underlying="EURUSD")
    return P


def main() -> None:
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)
    lab = labelled(rng)
    write_csv(DATA / "labelled_events.csv", lab)
    nws = news(rng)
    write_csv(DATA / "news_sample.csv", nws)
    soc = social(rng)
    write_csv(DATA / "social_sample.csv", soc)
    write_csv(DATA / "portfolio.csv", portfolio())

    upload = [{"published_at": "2026-10-04T08:30:00Z", "source_name": "Synthetic Upload Feed",
               "headline": "Orion Telecom suffers nationwide network outage after power failure at data centre",
               "body": "Services were restored after nine hours.", "is_synthetic": True},
              {"published_at": "2026-10-04T09:10:00Z", "source_name": "Synthetic Upload Feed",
               "headline": "Regulator fines Northwind Bank $450 million over anti-money-laundering failures",
               "body": "", "is_synthetic": True},
              {"published_at": "2026-10-04T10:45:00Z", "source_name": "Synthetic Upload Feed",
               "headline": "Granite Real Estate Trust reports Q3 results in line with consensus",
               "body": "Guidance maintained.", "is_synthetic": True}]
    (DATA / "upload_example.json").write_text(json.dumps(upload, indent=2), encoding="utf-8")

    malformed = [
        {"article_id": "BAD1", "published_at": "2026-10-03T10:00:00Z", "source_name": "Synthetic Wire", "headline": "", "body": "", "is_synthetic": "true"},
        {"article_id": "BAD2", "published_at": "not-a-date", "source_name": "Synthetic Wire", "headline": "Helix Energy plunges after guidance cut", "body": "", "is_synthetic": "true"},
        {"article_id": "BAD3", "published_at": "", "source_name": "Synthetic Wire", "headline": "Atlas Airlines grounded by system outage", "body": "", "is_synthetic": "true"},
        {"article_id": "OK1", "published_at": "2026-10-03 11:00:00", "source_name": "Synthetic Wire", "headline": "Vantage Pharma launches new oncology drug in Europe", "body": "", "is_synthetic": "true"},
        {"article_id": "DUP1", "published_at": "2026-10-03T12:00:00Z", "source_name": "Synthetic Wire", "headline": "Vantage Pharma launches new oncology drug in Europe!", "body": "", "is_synthetic": "true"},
    ]
    write_csv(DATA / "malformed_example.csv", malformed)
    print(f"templates={len(T)} labelled={len(lab)} news={len(nws)} social={len(soc)} portfolio={len(portfolio())}")


if __name__ == "__main__":
    main()
