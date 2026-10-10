"""Event-driven portfolio stress engine (single source of truth for dashboard, API, scripts, reports).

P&L components per position (USD), all first-order and additive so totals reconcile exactly:
  rates          -ModDur x dy x MV                        (dy = rate_shock_bp / 10,000)
  credit_spread  -SpreadDur x ds x MV                     (ds = spread widening in decimals)
  equity         MV x (beta x market_move + sector_move + k x entity_move)
  fx             MV x fx_move[currency]                   (foreign value vs USD; cross-terms ignored)
  commodity      delta x notional x commodity_move        (commodity futures)
  credit_loss    -EAD x (PD_s x LGD_s - PD_0 x LGD_0)     (loans; EAD = carrying value)
  liquidity      -haircut[asset_class] x (MV + market P&L)  (applied last, avoids double counting)
Derivatives use delta / duration sensitivities on notional and are flagged as approximated.
"""
from __future__ import annotations

import copy
import io
import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..config import scenario_config
from .model import ASSET_CLASSES

COMPONENTS = ["rates", "credit_spread", "equity", "fx", "commodity", "credit_loss", "liquidity"]
COMPONENT_LABELS = {
    "rates": "Interest rates", "credit_spread": "Credit spreads", "equity": "Equity prices",
    "fx": "FX rates", "commodity": "Commodities", "credit_loss": "Expected credit loss", "liquidity": "Liquidity haircut",
}
EXACT_METHODS = {"Equity", "FX", "Equity Index Future", "Commodity Future", "FX Forward"}


def rating_bucket(rating: str) -> str | None:
    r = (rating or "").upper().strip()
    if not r:
        return None
    if r.startswith("AA") or r == "AAA":
        return "AAA_AA"
    if r.startswith("BBB"):
        return "BBB"
    if r.startswith("A"):
        return "A"
    return "HY"


def scenarios() -> dict:
    return scenario_config()["scenarios"]


def settings() -> dict:
    return scenario_config()["settings"]


def scenario_for_event(event_type: str) -> str | None:
    for key, scn in scenarios().items():
        if event_type in scn["event_types"]:
            return key
    return None


def evaluate_trigger(signal, threshold: float | None = None) -> dict:
    """Decide whether a signal triggers a stress test and which scenario it maps to."""
    s = signal if isinstance(signal, dict) else signal.model_dump()
    threshold = settings()["trigger_threshold"] if threshold is None else threshold
    key = scenario_for_event(s["event_type"])
    impact = s["impact_score"]
    who = f" for {s['entity']} ({s['ticker']})" if s.get("ticker") else ""
    if key is None:
        return {"triggered": False, "scenario_key": None,
                "rationale": f"Event type '{s['event_type']}' has no mapped scenario; no stress test."}
    name = scenarios()[key]["name"]
    if impact > threshold:
        return {"triggered": True, "scenario_key": key,
                "rationale": f"{s['event_type']} signal{who} has impact {impact} > threshold {threshold:g}: "
                             f"auto-selected scenario '{name}'."}
    return {"triggered": False, "scenario_key": key,
            "rationale": f"Impact {impact} is not above threshold {threshold:g}; scenario '{name}' can still be run manually."}


def pick_demo_signal(signals, threshold: float | None = None):
    """Highest-impact triggered signal; ties -> most negative sentiment, then earliest. None if none trigger."""
    trig = [s for s in signals if evaluate_trigger(s, threshold)["triggered"]]
    return sorted(trig, key=lambda s: (-s.impact_score, s.sentiment_score, s.timestamp))[0] if trig else None


def _deep_update(base: dict, upd: dict) -> dict:
    for k, v in (upd or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_update(base[k], v)
        else:
            base[k] = v
    return base


def effective_scenario(key_or_dict, impact: float | None = None, overrides: dict | None = None,
                       scale_with_impact: bool | None = None) -> tuple[dict, float]:
    """Base scenario + overrides, then scaled by impact severity. Returns (params, scale)."""
    st = settings()
    base = copy.deepcopy(scenarios()[key_or_dict] if isinstance(key_or_dict, str) else key_or_dict)
    p = _deep_update(base, copy.deepcopy(overrides or {}))
    use_scale = st["scale_with_impact"] if scale_with_impact is None else scale_with_impact
    scale = 1.0
    if use_scale and impact:
        scale = float(np.clip(impact / st["reference_impact"], st["scale_floor"], st["scale_cap"]))
    if scale != 1.0:
        for k in ["equity_shock_pct", "rate_shock_bp", "lgd_add"]:
            p[k] = p.get(k, 0.0) * scale
        for k in ["sector_equity_shocks_pct", "credit_spread_shock_bp", "fx_shocks_pct",
                  "commodity_shocks_pct", "liquidity_haircut_pct"]:
            p[k] = {kk: vv * scale for kk, vv in (p.get(k) or {}).items()}
        p["pd_multiplier"] = 1 + (p.get("pd_multiplier", 1.0) - 1) * scale
        p["sector_pd_multiplier"] = {kk: 1 + (vv - 1) * scale for kk, vv in (p.get("sector_pd_multiplier") or {}).items()}
        ent = p.get("entity_shock") or {}
        p["entity_shock"] = {"equity_pct": ent.get("equity_pct", 0.0) * scale,
                             "spread_bp": ent.get("spread_bp", 0.0) * scale,
                             "pd_multiplier": 1 + (ent.get("pd_multiplier", 1.0) - 1) * scale}
    return p, scale


@dataclass
class StressResult:
    scenario_key: str
    scenario_name: str
    params: dict
    scale: float
    entity_ticker: str | None
    positions: pd.DataFrame
    initial_value: float
    stressed_value: float
    pnl: float
    pnl_pct: float
    by_asset_class: pd.DataFrame
    by_component: pd.DataFrame
    trigger: dict = field(default_factory=dict)
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "scenario_key": self.scenario_key, "scenario_name": self.scenario_name,
            "severity_scale": round(self.scale, 4), "entity_ticker": self.entity_ticker,
            "initial_value_usd": round(self.initial_value, 2), "stressed_value_usd": round(self.stressed_value, 2),
            "pnl_usd": round(self.pnl, 2), "pnl_pct": round(self.pnl_pct, 6),
            "trigger": self.trigger, "effective_parameters": self.params, "assumptions": self.assumptions,
            "by_asset_class": json.loads(self.by_asset_class.round(2).to_json(orient="records")),
            "by_component": json.loads(self.by_component.round(2).to_json(orient="records")),
            "positions": json.loads(self.positions.round(2).to_json(orient="records")),
            "is_synthetic": True,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def positions_csv(self) -> str:
        buf = io.StringIO()
        self.positions.round(2).to_csv(buf, index=False)
        return buf.getvalue()


def _method(row) -> str:
    ac, it = row["asset_class"], row["instrument_type"]
    if ac == "Equity":
        return "Revaluation: MV x (1 + price move)"
    if ac == "FX":
        return "Revaluation: MV x FX move"
    if ac == "Government Bond":
        return "Duration approx: -ModDur x dy (convexity ignored)"
    if ac == "Corporate Bond":
        return "Duration approx: -ModDur x dy - SpreadDur x ds"
    if ac == "Loan":
        return "Expected-loss change: EAD x dPD x LGD" + (" + duration on fixed rate" if row["modified_duration"] else "")
    return {
        "Equity Index Future": "Linear: delta x notional x index move",
        "Equity Option": "Delta approx (gamma/vega ignored)",
        "Interest Rate Swap": "DV01 approx: -delta x ModDur x dy x notional",
        "Credit Default Swap": "CS01 approx: -delta x SpreadDur x ds x notional",
        "Commodity Future": "Linear: delta x notional x commodity move",
        "FX Forward": "Linear: delta x notional x FX move",
    }.get(it, "Not modelled")


def run_stress_test(portfolio: pd.DataFrame, scenario, impact: float | None = None,
                    entity_ticker: str | None = None, sentiment_score: float | None = None,
                    overrides: dict | None = None, scale_with_impact: bool | None = None,
                    trigger: dict | None = None) -> StressResult:
    """Apply a scenario to every relevant position and reconcile the totals."""
    key = scenario if isinstance(scenario, str) else scenario.get("key", "custom")
    p, scale = effective_scenario(scenario, impact, overrides, scale_with_impact)
    affected_classes = set(p.get("affected_asset_classes", ASSET_CLASSES))
    ent = p.get("entity_shock") or {}
    sign = -1.0 if (p.get("sentiment_sign") and sentiment_score is not None and sentiment_score > 0) else 1.0
    tickers = portfolio.set_index("ticker")["sector"].to_dict() if entity_ticker else {}
    entity_sector = tickers.get(entity_ticker) if entity_ticker else None
    if entity_ticker and entity_sector is None:
        from ..universe import BY_TICKER  # entity not held: still allow sector contagion
        entity_sector = BY_TICKER.get(entity_ticker, {}).get("sector")
    dy = p.get("rate_shock_bp", 0.0) / 10_000.0

    rows = []
    for _, r in portfolio.iterrows():
        ac, it = r["asset_class"], r["instrument_type"]
        mv, notional = r["market_value_usd"], r["notional_usd"]
        ref_ticker = r["ticker"] or r["underlying"]
        is_entity = bool(entity_ticker) and ref_ticker == entity_ticker
        same_sector = bool(entity_sector) and r["sector"] == entity_sector and not is_entity
        k = 1.0 if is_entity else (p.get("sector_contagion", 0.0) if same_sector else 0.0)
        eq_move = (p.get("equity_shock_pct", 0.0) * (r["beta"] or 1.0)
                   + (p.get("sector_equity_shocks_pct") or {}).get(r["sector"], 0.0)
                   + k * ent.get("equity_pct", 0.0) * sign)
        bucket = rating_bucket(r["rating"])
        ds = ((p.get("credit_spread_shock_bp") or {}).get(bucket, 0.0)
              * (p.get("sector_spread_multiplier") or {}).get(r["sector"], 1.0)
              + k * ent.get("spread_bp", 0.0)) / 10_000.0
        pd_mult = (p.get("pd_multiplier", 1.0) * (p.get("sector_pd_multiplier") or {}).get(r["sector"], 1.0)
                   * (1 + k * (ent.get("pd_multiplier", 1.0) - 1)))
        fx_move = (p.get("fx_shocks_pct") or {}).get(r["currency"], 0.0)

        c = dict.fromkeys(COMPONENTS, 0.0)
        if ac in affected_classes:
            if ac == "Equity":
                c["equity"] = mv * eq_move
            elif ac in ("Government Bond", "Corporate Bond", "Loan"):
                c["rates"] = -r["modified_duration"] * dy * mv
                if ac == "Corporate Bond":
                    c["credit_spread"] = -r["spread_duration"] * ds * mv
                if ac == "Loan":
                    pd_s = min(1.0, r["pd_1y"] * pd_mult)
                    lgd_s = min(1.0, r["lgd"] + p.get("lgd_add", 0.0))
                    c["credit_loss"] = -mv * (pd_s * lgd_s - r["pd_1y"] * r["lgd"])
            elif ac == "Derivative":
                d = r["delta"]
                if it == "Equity Index Future":
                    c["equity"] = d * notional * p.get("equity_shock_pct", 0.0)
                elif it == "Equity Option":
                    c["equity"] = d * notional * eq_move
                elif it == "Interest Rate Swap":
                    c["rates"] = -d * r["modified_duration"] * dy * notional
                elif it == "Credit Default Swap":
                    c["credit_spread"] = -d * r["spread_duration"] * ds * notional
                elif it == "Commodity Future":
                    c["commodity"] = d * notional * (p.get("commodity_shocks_pct") or {}).get(r["underlying"], 0.0)
                elif it == "FX Forward":
                    c["fx"] = d * notional * fx_move
            if ac != "Derivative" and r["currency"] != settings()["base_currency"]:
                c["fx"] = mv * fx_move
            haircut = (p.get("liquidity_haircut_pct") or {}).get(ac, 0.0)
            if haircut and ac != "Derivative":
                c["liquidity"] = -haircut * (mv + sum(c.values()))
        total = sum(c.values())
        rows.append({
            "position_id": r["position_id"], "name": r["name"], "asset_class": ac, "instrument_type": it,
            "ticker": r["ticker"], "sector": r["sector"], "currency": r["currency"], "rating": r["rating"],
            "initial_value_usd": mv, **c, "total_pnl_usd": total, "stressed_value_usd": mv + total,
            "pnl_pct_of_position": (total / abs(mv)) if mv else 0.0,
            "affected": abs(total) > 1e-9, "entity_match": is_entity, "sector_contagion": same_sector,
            "approximated": it not in EXACT_METHODS and ac not in EXACT_METHODS, "valuation_method": _method(r),
        })

    pos = pd.DataFrame(rows)
    initial = float(pos["initial_value_usd"].sum())
    pnl = float(pos["total_pnl_usd"].sum())
    stressed = float(pos["stressed_value_usd"].sum())
    by_class = (pos.groupby("asset_class")[["initial_value_usd", "total_pnl_usd", "stressed_value_usd"]].sum()
                .reindex([a for a in ASSET_CLASSES if a in set(pos["asset_class"])]).reset_index())
    by_class["pnl_pct"] = np.where(by_class["initial_value_usd"] != 0,
                                   by_class["total_pnl_usd"] / by_class["initial_value_usd"].abs(), 0.0)
    by_class["share_of_total_pnl"] = by_class["total_pnl_usd"] / pnl if pnl else 0.0
    by_comp = pd.DataFrame({"component": COMPONENTS,
                            "label": [COMPONENT_LABELS[c] for c in COMPONENTS],
                            "pnl_usd": [float(pos[c].sum()) for c in COMPONENTS]})

    # reconciliation: components -> positions -> asset classes -> portfolio
    assert np.isclose(pos[COMPONENTS].sum(axis=1), pos["total_pnl_usd"]).all()
    assert np.isclose(by_class["total_pnl_usd"].sum(), pnl) and np.isclose(by_comp["pnl_usd"].sum(), pnl)
    assert np.isclose(initial + pnl, stressed)

    assumptions = [
        f"Severity scale {scale:.2f} applied to base shocks (impact {impact} / reference {settings()['reference_impact']})."
        if scale != 1.0 else "Base scenario shocks applied without severity scaling.",
        f"Parallel rate shock {p.get('rate_shock_bp', 0):+.0f} bp; equity market move {p.get('equity_shock_pct', 0):+.1%} x beta.",
        f"Entity shock on {entity_ticker}: equity {ent.get('equity_pct', 0) * sign:+.1%}, spread {ent.get('spread_bp', 0):+.0f} bp, "
        f"PD x{ent.get('pd_multiplier', 1):.2f}; same-sector contagion {p.get('sector_contagion', 0):.0%}."
        if entity_ticker else "No entity-specific shock (no company identified in the signal).",
        f"Shocked asset classes: {', '.join(sorted(affected_classes))}. Other positions are unchanged.",
        "Bonds use modified/spread duration (first order, convexity ignored); dy and ds are converted from bp to decimals.",
        "Loans are carried at amortised cost; stress = change in one-year expected loss (PD x LGD x EAD).",
        "Derivatives are delta/duration approximations on notional, not full revaluations.",
        "FX effect on non-USD positions is first order (MV x FX move); cross terms are ignored.",
        "Liquidity haircut is applied to post-shock value to avoid double counting.",
    ]
    name = p.get("name", key)
    return StressResult(key, name, p, scale, entity_ticker, pos, initial, stressed, pnl,
                        pnl / initial if initial else 0.0, by_class, by_comp, trigger or {}, assumptions)


def stress_from_signal(portfolio: pd.DataFrame, signal, threshold: float | None = None,
                       overrides: dict | None = None, scenario_key: str | None = None,
                       scale_with_impact: bool | None = None) -> StressResult:
    """Run the scenario mapped to a signal (or an explicitly chosen one)."""
    s = signal if isinstance(signal, dict) else signal.model_dump()
    trig = evaluate_trigger(s, threshold)
    key = scenario_key or trig["scenario_key"]
    if key is None:
        raise ValueError(trig["rationale"])
    return run_stress_test(portfolio, key, s["impact_score"], s.get("ticker"), s.get("sentiment_score"),
                           overrides, scale_with_impact, trig)
