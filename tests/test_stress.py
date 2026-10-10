"""Stress-engine tests against hand-computed expected values (independent of the implementation)."""
import io

import numpy as np
import pytest

from riskpulse.config import PORTFOLIO_FILE
from riskpulse.portfolio.model import entity_weights, load_portfolio
from riskpulse.portfolio.stress import (COMPONENTS, effective_scenario, evaluate_trigger, run_stress_test, scenarios,
                                        stress_from_signal)

COLS = ("position_id,name,asset_class,instrument_type,issuer,ticker,sector,region,currency,rating,notional_usd,"
        "market_value_usd,modified_duration,spread_duration,pd_1y,lgd,beta,delta,underlying\n")
MINI = COLS + "\n".join([
    "EQ,Equity A,Equity,Common Stock,A,AAA1,Technology,US,USD,,0,10000000,0,0,0,0,1.2,0,",
    "GB,Gov bond,Government Bond,Sovereign Bond,UST,,,US,USD,AA+,100000000,100000000,5,0,0,0,0,0,",
    "CB,Corp bond,Corporate Bond,Senior Bond,B,BBB1,Energy,US,USD,BBB,50000000,50000000,4,4,0,0,0,0,",
    "LN,Loan,Loan,Term Loan,C,LN1,Industrials,US,USD,BB,100000000,100000000,0,0,0.02,0.40,0,0,",
    "FX,EUR cash,FX,Currency Balance,,,,EU,EUR,,10000000,10000000,0,0,0,0,0,0,",
    "SW,Pay-fixed swap,Derivative,Interest Rate Swap,,,,US,USD,,100000000,0,4,0,0,0,0,-1,USD_RATES",
    "CD,CDS protection,Derivative,Credit Default Swap,B,BBB1,Energy,US,USD,HY,10000000,0,0,4,0,0,0,-1,BBB1",
    "OP,Call option,Derivative,Equity Option,A,AAA1,Technology,US,USD,,10000000,1000000,0,0,0,0,1.0,0.5,AAA1",
    "OF,Oil future,Derivative,Commodity Future,,,,US,USD,,10000000,0,0,0,0,0,0,1,oil",
    "FW,Short EUR forward,Derivative,FX Forward,,,,EU,EUR,,10000000,0,0,0,0,0,0,-1,EURUSD",
    "ZZ,Zero position,Equity,Common Stock,Z,ZZZ,Technology,US,USD,,0,0,0,0,0,0,1,0,",
])
BLANK = {"event_types": [], "affected_asset_classes": ["Equity", "Government Bond", "Corporate Bond", "Loan", "FX",
                                                       "Derivative"], "equity_shock_pct": 0.0, "rate_shock_bp": 0.0,
         "credit_spread_shock_bp": {}, "fx_shocks_pct": {}, "commodity_shocks_pct": {}, "pd_multiplier": 1.0,
         "lgd_add": 0.0, "liquidity_haircut_pct": {}, "entity_shock": {}, "sector_contagion": 0.0}


@pytest.fixture
def mini():
    return load_portfolio(io.StringIO(MINI))


def pnl(res, pid, comp="total_pnl_usd"):
    return float(res.positions.set_index("position_id").loc[pid, comp])


def run(pf, **shocks):
    return run_stress_test(pf, {**BLANK, **shocks}, scale_with_impact=False)


def test_valuation(mini):
    res = run(mini)
    assert res.initial_value == pytest.approx(10e6 + 100e6 + 50e6 + 100e6 + 10e6 + 1e6)
    assert res.pnl == 0 and res.stressed_value == res.initial_value


def test_equity_shock_uses_beta(mini):
    res = run(mini, equity_shock_pct=-0.10)
    assert pnl(res, "EQ") == pytest.approx(-1_200_000)       # 10m x 1.2 x -10%
    assert pnl(res, "OP") == pytest.approx(-500_000)         # 0.5 delta x 10m x (1.0 x -10%)
    assert pnl(res, "GB") == 0                                # equity shock never touches bonds


def test_interest_rate_sign_convention(mini):
    up, down = run(mini, rate_shock_bp=100), run(mini, rate_shock_bp=-100)
    assert pnl(up, "GB") == pytest.approx(-5_000_000)        # -5 x 0.01 x 100m
    assert pnl(down, "GB") == pytest.approx(5_000_000)
    assert pnl(up, "CB") == pytest.approx(-2_000_000)        # -4 x 0.01 x 50m
    assert pnl(up, "SW") == pytest.approx(4_000_000)         # pay-fixed gains when rates rise
    assert pnl(up, "LN") == 0                                 # floating-rate loan: no duration


def test_credit_spread_and_cds(mini):
    res = run(mini, credit_spread_shock_bp={"BBB": 50, "HY": 100})
    assert pnl(res, "CB", "credit_spread") == pytest.approx(-1_000_000)  # -4 x 0.005 x 50m
    assert pnl(res, "CD") == pytest.approx(400_000)                       # protection: +4 x 0.01 x 10m


def test_loan_expected_loss(mini):
    res = run(mini, pd_multiplier=2.0, lgd_add=0.05)
    # -(0.04 x 0.45 - 0.02 x 0.40) x 100m = -1.0m
    assert pnl(res, "LN", "credit_loss") == pytest.approx(-1_000_000)


def test_pd_capped_at_one(mini):
    res = run(mini, pd_multiplier=1000.0)
    assert pnl(res, "LN") == pytest.approx(-(1.0 * 0.40 - 0.008) * 100e6)


def test_fx_and_forward_hedge(mini):
    res = run(mini, fx_shocks_pct={"EUR": -0.05})
    assert pnl(res, "FX") == pytest.approx(-500_000)
    assert pnl(res, "FW") == pytest.approx(500_000)          # short EUR forward offsets the cash loss


def test_commodity_future(mini):
    assert pnl(run(mini, commodity_shocks_pct={"oil": 0.20}), "OF") == pytest.approx(2_000_000)


def test_liquidity_haircut_on_post_shock_value(mini):
    res = run(mini, rate_shock_bp=100, liquidity_haircut_pct={"Corporate Bond": 0.01})
    assert pnl(res, "CB", "liquidity") == pytest.approx(-0.01 * (50e6 - 2e6))


def test_entity_shock_and_contagion(mini):
    res = run_stress_test(mini, {**BLANK, "entity_shock": {"equity_pct": -0.20, "spread_bp": 100, "pd_multiplier": 1},
                                 "sector_contagion": 0.5}, entity_ticker="AAA1", scale_with_impact=False)
    assert pnl(res, "EQ") == pytest.approx(-2_000_000)       # named entity: full -20%
    assert pnl(res, "ZZ") == 0                                # same sector but zero exposure
    assert pnl(res, "CB") == 0                                # other sector untouched


def test_unaffected_asset_classes_unchanged(mini):
    res = run_stress_test(mini, {**BLANK, "affected_asset_classes": ["Equity"], "rate_shock_bp": 300,
                                 "equity_shock_pct": -0.1}, scale_with_impact=False)
    assert pnl(res, "GB") == 0 and pnl(res, "EQ") != 0


def test_zero_and_missing_exposures():
    csv = COLS + "Z1,Empty,Equity,Common Stock,,,,US,USD,,,,,,,,,,\n"
    pf = load_portfolio(io.StringIO(csv))
    res = run(pf, equity_shock_pct=-0.5, rate_shock_bp=100)
    assert res.pnl == 0 and res.pnl_pct == 0 and pf.loc[0, "beta"] == 0


def test_portfolio_validation_errors():
    with pytest.raises(ValueError):
        load_portfolio(io.StringIO(COLS + "A,a,Crypto,x,,,,US,USD,,1,1,0,0,0,0,0,0,\n"))
    with pytest.raises(ValueError):
        load_portfolio(io.StringIO(COLS + "A,a,Loan,x,,,,US,USD,,1,1,0,0,1.5,0.4,0,0,\n"))
    with pytest.raises(ValueError):
        load_portfolio(io.StringIO("position_id,name\nA,a\n"))


def test_impact_scaling():
    _, s_low = effective_scenario("credit_event", impact=2)
    _, s_ref = effective_scenario("credit_event", impact=8)
    p_hi, s_hi = effective_scenario("credit_event", impact=10)
    assert (s_low, s_ref, s_hi) == (0.5, 1.0, 1.25)
    assert p_hi["entity_shock"]["equity_pct"] == pytest.approx(-0.35 * 1.25)
    assert p_hi["entity_shock"]["pd_multiplier"] == pytest.approx(1 + 3.0 * 1.25)


@pytest.mark.parametrize("key", list(scenarios()))
@pytest.mark.parametrize("impact", [3, 8, 10])
def test_bundled_portfolio_reconciles_for_every_scenario(key, impact):
    pf = load_portfolio(PORTFOLIO_FILE)
    res = run_stress_test(pf, key, impact, "MRDS", -0.5)
    pos = res.positions
    assert np.allclose(pos[COMPONENTS].sum(axis=1), pos["total_pnl_usd"])
    assert res.by_asset_class["total_pnl_usd"].sum() == pytest.approx(res.pnl)
    assert res.by_component["pnl_usd"].sum() == pytest.approx(res.pnl)
    assert res.initial_value + res.pnl == pytest.approx(res.stressed_value)
    assert res.initial_value == pytest.approx(pf["market_value_usd"].sum())


def test_scenarios_produce_losses_on_bundled_book():
    pf = load_portfolio(PORTFOLIO_FILE)
    for key in ["geopolitical_shock", "macro_rates_shock", "credit_event", "liquidity_stress"]:
        assert run_stress_test(pf, key, 9, "MRDS", -0.8).pnl < 0


def sig(event, impact, ticker="MRDS", sentiment=-0.7):
    return {"event_type": event, "impact_score": impact, "ticker": ticker, "entity": "Meridian Shipping",
            "sentiment_score": sentiment}


def test_trigger_threshold_and_mapping():
    t = evaluate_trigger(sig("Geopolitical", 8))
    assert t["triggered"] and t["scenario_key"] == "geopolitical_shock"
    assert not evaluate_trigger(sig("Geopolitical", 7))["triggered"]           # strictly greater than 7
    assert evaluate_trigger(sig("Geopolitical", 6), threshold=5)["triggered"]
    assert evaluate_trigger(sig("Unclassified", 10))["scenario_key"] is None
    for ev in ["Macroeconomic", "Credit Event", "Cybersecurity", "Market / Liquidity", "Regulatory / Legal",
               "Operational Disruption", "Merger & Acquisition"]:
        assert evaluate_trigger(sig(ev, 9))["scenario_key"] is not None


def test_stress_from_signal():
    pf = load_portfolio(PORTFOLIO_FILE)
    res = stress_from_signal(pf, sig("Credit Event", 10))
    worst = res.positions.nsmallest(3, "total_pnl_usd")
    assert res.trigger["triggered"] and set(worst["ticker"]) == {"MRDS"}
    with pytest.raises(ValueError):
        stress_from_signal(pf, sig("Unclassified", 10))


def test_product_launch_sign_follows_sentiment():
    pf = load_portfolio(PORTFOLIO_FILE)
    up = run_stress_test(pf, "product_launch", 8, "AURS", sentiment_score=0.8)
    down = run_stress_test(pf, "product_launch", 8, "AURS", sentiment_score=-0.8)
    assert up.pnl > 0 > down.pnl


def test_entity_weights_sum_below_one():
    w = entity_weights(load_portfolio(PORTFOLIO_FILE))
    assert 0 < sum(w.values()) < 1 and w["MRDS"] > 0.05
