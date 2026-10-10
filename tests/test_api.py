import pytest
from fastapi.testclient import TestClient

from api import app
from riskpulse.config import PORTFOLIO_FILE
from riskpulse.portfolio.model import load_portfolio
from riskpulse.portfolio.stress import stress_from_signal


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["status"] == "ok" and r.json()["signals_loaded"] > 200


def test_signals_filters(client):
    r = client.get("/signals", params={"event_type": "Credit Event", "min_impact": 8, "limit": 5})
    assert r.status_code == 200
    rows = r.json()
    assert 0 < len(rows) <= 5 and all(s["event_type"] == "Credit Event" and s["impact_score"] >= 8 for s in rows)
    assert client.get("/signals", params={"event_type": "Weather"}).status_code == 422
    assert client.get("/signals", params={"min_impact": 11}).status_code == 422
    assert client.get("/signals/sig-does-not-exist").status_code == 404


def test_analyze_valid_and_invalid(client):
    r = client.post("/analyze", json={"items": [
        {"text": "Ransomware attack forces Quantum Payments to halt card processing", "source_type": "news"},
        {"text": "$NWBK earnings beat estimates!!", "source_type": "social"}]})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2 and body["signals"][0]["event_type"] == "Cybersecurity"
    assert body["signals"][0]["ticker"] == "QPAY" and "stress_trigger" in body["signals"][0]
    assert client.post("/analyze", json={"items": []}).status_code == 422
    assert client.post("/analyze", json={"items": [{"text": "x"}]}).status_code == 422
    assert client.post("/analyze", json={"items": [{"text": "valid text", "source_type": "fax"}]}).status_code == 422
    assert client.post("/analyze", content="not json", headers={"content-type": "application/json"}).status_code == 422


def test_analyze_store_adds_signal(client):
    n = client.get("/health").json()["signals_loaded"]
    client.post("/analyze", json={"items": [{"text": "Fire halts production at Summit Steel plant"}], "store": True})
    assert client.get("/health").json()["signals_loaded"] == n + 1


def test_events_summary_and_portfolio(client):
    s = client.get("/events/summary").json()
    assert s["total_signals"] > 200 and "Credit Event" in s["by_event_type"] and s["high_impact_count"] > 0
    p = client.get("/portfolio").json()
    assert p["total_market_value_usd"] == pytest.approx(load_portfolio(PORTFOLIO_FILE)["market_value_usd"].sum())
    assert len(p["holdings"]) == p["positions"] and p["is_synthetic"]


def test_stress_test_matches_engine(client):
    top = client.get("/signals", params={"event_type": "Credit Event", "min_impact": 9, "limit": 1}).json()[0]
    r = client.post("/stress-test", json={"signal_id": top["signal_id"]})
    assert r.status_code == 200
    body = r.json()
    direct = stress_from_signal(load_portfolio(PORTFOLIO_FILE), top)
    assert body["trigger"]["triggered"] and body["pnl_usd"] == pytest.approx(round(direct.pnl, 2))
    assert body["initial_value_usd"] + body["pnl_usd"] == pytest.approx(body["stressed_value_usd"], abs=0.05)


def test_stress_test_scenario_overrides_and_errors(client):
    base = client.post("/stress-test", json={"scenario_key": "macro_rates_shock", "impact_score": 8,
                                             "include_positions": False}).json()
    more = client.post("/stress-test", json={"scenario_key": "macro_rates_shock", "impact_score": 8,
                                             "overrides": {"rate_shock_bp": 400}, "include_positions": False}).json()
    assert "positions" not in base and more["pnl_usd"] < base["pnl_usd"]
    assert client.post("/stress-test", json={"scenario_key": "alien_invasion"}).status_code == 422
    assert client.post("/stress-test", json={}).status_code == 422
    assert client.post("/stress-test", json={"signal_id": "sig-missing"}).status_code == 404
    assert client.post("/stress-test", json={"scenario_key": "credit_event", "ticker": "NOPE"}).status_code == 422
    assert client.post("/stress-test", json={"scenario_key": "credit_event", "impact_score": 42}).status_code == 422
    unclassified = client.get("/signals", params={"event_type": "Unclassified", "limit": 1}).json()[0]
    assert client.post("/stress-test", json={"signal_id": unclassified["signal_id"]}).status_code == 422
