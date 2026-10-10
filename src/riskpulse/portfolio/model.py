"""Synthetic wholesale-banking portfolio: loading, validation and simple aggregates."""
from __future__ import annotations

import pandas as pd

ASSET_CLASSES = ["Loan", "Corporate Bond", "Government Bond", "Equity", "FX", "Derivative"]
NUMERIC = ["notional_usd", "market_value_usd", "modified_duration", "spread_duration", "pd_1y", "lgd", "beta", "delta"]
REQUIRED = ["position_id", "name", "asset_class", "instrument_type", "currency"] + NUMERIC


def load_portfolio(source) -> pd.DataFrame:
    """Load and validate a portfolio CSV (path or buffer). Missing numeric values become 0."""
    df = pd.read_csv(source)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"portfolio is missing columns: {missing}")
    df = df.copy()
    for c in NUMERIC:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0).astype(float)
    for c in ["issuer", "ticker", "sector", "rating", "underlying", "region"]:
        if c not in df.columns:
            df[c] = ""
        df[c] = df[c].fillna("").astype(str)
    bad = sorted(set(df["asset_class"]) - set(ASSET_CLASSES))
    if bad:
        raise ValueError(f"unknown asset classes: {bad}")
    if df["position_id"].duplicated().any():
        raise ValueError("duplicate position_id values")
    if ((df["pd_1y"] < 0) | (df["pd_1y"] > 1) | (df["lgd"] < 0) | (df["lgd"] > 1)).any():
        raise ValueError("pd_1y and lgd must be within [0, 1]")
    return df


def entity_weights(df: pd.DataFrame) -> dict[str, float]:
    """Share of total absolute market value held per ticker (derivatives excluded)."""
    cash = df[df["asset_class"] != "Derivative"]
    total = cash["market_value_usd"].abs().sum()
    if total == 0:
        return {}
    by = cash[cash["ticker"] != ""].groupby("ticker")["market_value_usd"].apply(lambda s: s.abs().sum())
    return (by / total).round(6).to_dict()


def summary_by_asset_class(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("asset_class").agg(positions=("position_id", "count"),
                                       market_value_usd=("market_value_usd", "sum"),
                                       notional_usd=("notional_usd", "sum"))
    g["weight"] = g["market_value_usd"] / df["market_value_usd"].sum()
    return g.reindex([a for a in ASSET_CLASSES if a in g.index]).reset_index()
