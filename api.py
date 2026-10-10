"""RiskPulse AI REST API (FastAPI). Run: uvicorn api:app --port 8000   Docs: http://localhost:8000/docs

Uses the same engine as the dashboard: signals are produced from the bundled synthetic data at
startup and from any text posted to /analyze; stress tests call the same calculation module.
"""
from __future__ import annotations

import sys
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from riskpulse import __version__  # noqa: E402
from riskpulse.config import PORTFOLIO_FILE  # noqa: E402
from riskpulse.pipeline import HIGH_IMPACT_THRESHOLD, default_engine, run_default_pipeline  # noqa: E402
from riskpulse.portfolio.model import load_portfolio, summary_by_asset_class  # noqa: E402
from riskpulse.portfolio.stress import evaluate_trigger, run_stress_test, scenarios, stress_from_signal  # noqa: E402
from riskpulse.schemas import RiskSignal  # noqa: E402
from riskpulse.universe import ALL_EVENT_LABELS, BY_TICKER  # noqa: E402

STATE: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    signals, report = run_default_pipeline()
    STATE.update(signals={s.signal_id: s for s in signals}, report=report, portfolio=load_portfolio(PORTFOLIO_FILE))
    yield
    STATE.clear()


app = FastAPI(title="RiskPulse AI API", version=__version__, lifespan=lifespan,
              description="Explainable risk signals from unstructured text + event-driven portfolio stress testing. "
                          "All bundled data is synthetic.")


class AnalyzeItem(BaseModel):
    text: str = Field(min_length=3, max_length=5000)
    source_type: Literal["news", "social"] = "news"
    source_name: str = Field(default="api", max_length=80)
    timestamp: Optional[datetime] = None


class AnalyzeRequest(BaseModel):
    items: list[AnalyzeItem] = Field(min_length=1, max_length=100)
    store: bool = Field(default=False, description="add the resulting signals to the in-memory signal store")


class StressRequest(BaseModel):
    signal_id: Optional[str] = Field(default=None, description="run the scenario mapped to this stored signal")
    scenario_key: Optional[str] = Field(default=None, description="explicit scenario (overrides the mapping)")
    impact_score: Optional[int] = Field(default=None, ge=1, le=10)
    ticker: Optional[str] = None
    threshold: Optional[float] = Field(default=None, ge=0, le=10)
    scale_with_impact: Optional[bool] = None
    overrides: dict = Field(default_factory=dict, description="partial scenario parameters, e.g. {'rate_shock_bp': 150}")
    include_positions: bool = True


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "signals_loaded": len(STATE.get("signals", {})),
            "positions_loaded": len(STATE["portfolio"]) if "portfolio" in STATE else 0, "data": "synthetic"}


@app.get("/signals", response_model=list[RiskSignal])
def get_signals(event_type: Optional[str] = None, ticker: Optional[str] = None,
                sentiment_label: Optional[Literal["Positive", "Neutral", "Negative"]] = None,
                source_type: Optional[Literal["news", "social", "rss"]] = None,
                min_impact: int = Query(1, ge=1, le=10), limit: int = Query(100, ge=1, le=1000)):
    if event_type and event_type not in ALL_EVENT_LABELS:
        raise HTTPException(422, f"event_type must be one of {ALL_EVENT_LABELS}")
    out = [s for s in STATE["signals"].values()
           if (not event_type or s.event_type == event_type) and (not ticker or s.ticker == ticker.upper())
           and (not sentiment_label or s.sentiment_label == sentiment_label)
           and (not source_type or s.source_type == source_type) and s.impact_score >= min_impact]
    return sorted(out, key=lambda s: s.timestamp, reverse=True)[:limit]


@app.get("/signals/{signal_id}", response_model=RiskSignal)
def get_signal(signal_id: str):
    if signal_id not in STATE["signals"]:
        raise HTTPException(404, "signal not found")
    return STATE["signals"][signal_id]


@app.post("/analyze")
def analyze(req: AnalyzeRequest) -> dict:
    engine = default_engine()
    signals = [engine.analyze_text(i.text, i.source_type, i.source_name, i.timestamp) for i in req.items]
    if req.store:
        STATE["signals"].update({s.signal_id: s for s in signals})
    return {"count": len(signals), "signals": [s.model_dump(mode="json") | {"stress_trigger": evaluate_trigger(s)}
                                               for s in signals]}


@app.get("/events/summary")
def events_summary() -> dict:
    sigs = list(STATE["signals"].values())
    high = sorted([s for s in sigs if s.impact_score > HIGH_IMPACT_THRESHOLD], key=lambda s: s.timestamp, reverse=True)
    by_event = {}
    for ev in ALL_EVENT_LABELS:
        sub = [s for s in sigs if s.event_type == ev]
        if sub:
            by_event[ev] = {"count": len(sub), "avg_impact": round(sum(s.impact_score for s in sub) / len(sub), 2),
                            "avg_sentiment": round(sum(s.sentiment_score for s in sub) / len(sub), 3),
                            "high_impact": sum(s.impact_score > HIGH_IMPACT_THRESHOLD for s in sub)}
    rep = STATE["report"]
    return {"total_signals": len(sigs), "high_impact_threshold": HIGH_IMPACT_THRESHOLD, "high_impact_count": len(high),
            "by_event_type": by_event, "by_sentiment": dict(Counter(s.sentiment_label for s in sigs)),
            "by_source": dict(Counter(s.source_type for s in sigs)),
            "top_entities": Counter(s.ticker for s in sigs if s.ticker).most_common(5),
            "recent_high_impact": [{"signal_id": s.signal_id, "timestamp": s.timestamp, "event_type": s.event_type,
                                    "ticker": s.ticker, "impact_score": s.impact_score} for s in high[:10]],
            "ingestion": {"rows_read": rep.rows_read, "accepted": rep.accepted, "rejected": rep.rejected,
                          "duplicates": rep.duplicates}}


@app.get("/portfolio")
def portfolio() -> dict:
    df = STATE["portfolio"]
    return {"total_market_value_usd": float(df["market_value_usd"].sum()), "positions": len(df),
            "by_asset_class": summary_by_asset_class(df).to_dict(orient="records"),
            "scenarios": {k: {"name": v["name"], "event_types": v["event_types"]} for k, v in scenarios().items()},
            "holdings": df.to_dict(orient="records"), "is_synthetic": True}


@app.post("/stress-test")
def stress_test(req: StressRequest) -> dict:
    pf = STATE["portfolio"]
    if req.scenario_key and req.scenario_key not in scenarios():
        raise HTTPException(422, f"unknown scenario_key; choose from {list(scenarios())}")
    if req.ticker and req.ticker.upper() not in BY_TICKER:
        raise HTTPException(422, "unknown ticker")
    try:
        if req.signal_id:
            sig = STATE["signals"].get(req.signal_id)
            if sig is None:
                raise HTTPException(404, "signal not found")
            res = stress_from_signal(pf, sig, req.threshold, req.overrides, req.scenario_key, req.scale_with_impact)
        elif req.scenario_key:
            res = run_stress_test(pf, req.scenario_key, req.impact_score, req.ticker.upper() if req.ticker else None,
                                  None, req.overrides, req.scale_with_impact)
        else:
            raise HTTPException(422, "provide signal_id or scenario_key")
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(422, f"invalid stress request: {exc}") from exc
    out = res.to_dict()
    if not req.include_positions:
        out.pop("positions")
    return out
