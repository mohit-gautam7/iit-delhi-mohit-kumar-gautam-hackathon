"""Fictional entity universe used by the synthetic datasets, NLP entity linker and portfolio.

Every company below is invented for the hackathon demo. Any resemblance to a real
issuer is coincidental; no real or confidential client data is used.
"""

COMPANIES = [
    {"name": "Northwind Bank", "ticker": "NWBK", "sector": "Financials", "region": "US",
     "aliases": ["Northwind Bank", "Northwind"]},
    {"name": "Helix Energy Corp", "ticker": "HLXE", "sector": "Energy", "region": "US",
     "aliases": ["Helix Energy", "Helix"]},
    {"name": "Aurora Semiconductors", "ticker": "AURS", "sector": "Technology", "region": "APAC",
     "aliases": ["Aurora Semiconductors", "Aurora Semi", "Aurora"]},
    {"name": "Meridian Shipping", "ticker": "MRDS", "sector": "Industrials", "region": "EU",
     "aliases": ["Meridian Shipping", "Meridian"]},
    {"name": "Crestline Retail Group", "ticker": "CRST", "sector": "Consumer", "region": "US",
     "aliases": ["Crestline Retail", "Crestline"]},
    {"name": "Vantage Pharma", "ticker": "VNTP", "sector": "Healthcare", "region": "EU",
     "aliases": ["Vantage Pharma", "Vantage"]},
    {"name": "Orion Telecom", "ticker": "ORTL", "sector": "Telecom", "region": "EU",
     "aliases": ["Orion Telecom", "Orion"]},
    {"name": "Bluewater Utilities", "ticker": "BWUT", "sector": "Utilities", "region": "US",
     "aliases": ["Bluewater Utilities", "Bluewater"]},
    {"name": "Summit Steel Industries", "ticker": "SMST", "sector": "Materials", "region": "APAC",
     "aliases": ["Summit Steel"]},
    {"name": "Atlas Airlines", "ticker": "ATLA", "sector": "Industrials", "region": "US",
     "aliases": ["Atlas Airlines", "Atlas Air"]},
    {"name": "Quantum Payments", "ticker": "QPAY", "sector": "Financials", "region": "US",
     "aliases": ["Quantum Payments", "QuantumPay"]},
    {"name": "Granite Real Estate Trust", "ticker": "GRET", "sector": "Real Estate", "region": "US",
     "aliases": ["Granite Real Estate", "Granite REIT", "Granite"]},
]

BY_TICKER = {c["ticker"]: c for c in COMPANIES}
BY_NAME = {c["name"]: c for c in COMPANIES}

EVENT_TYPES = [
    "Geopolitical",
    "Macroeconomic",
    "Credit Event",
    "Merger & Acquisition",
    "Product Launch",
    "Earnings / Financial Results",
    "Regulatory / Legal",
    "Cybersecurity",
    "Operational Disruption",
    "Market / Liquidity",
]
UNCLASSIFIED = "Unclassified"
ALL_EVENT_LABELS = EVENT_TYPES + [UNCLASSIFIED]
SENTIMENT_LABELS = ["Positive", "Neutral", "Negative"]
SOURCE_TYPES = ["news", "social", "rss"]
