"""Run an event-driven stress test from the processed signals.

Usage:
  python scripts/run_stress_test.py                      # highest-impact triggered signal
  python scripts/run_stress_test.py --signal-id sig-...  # a specific signal
  python scripts/run_stress_test.py --scenario macro_rates_shock --impact 9
Writes data/stress_result.json, data/stress_positions.csv and docs/stress_report.html.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from riskpulse.config import DATA_DIR, DOCS_DIR, PORTFOLIO_FILE  # noqa: E402
from riskpulse.pipeline import run_default_pipeline  # noqa: E402
from riskpulse.portfolio.model import load_portfolio  # noqa: E402
from riskpulse.portfolio.report import build_report_html  # noqa: E402
from riskpulse.portfolio.stress import pick_demo_signal, run_stress_test, stress_from_signal  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--signal-id")
    ap.add_argument("--scenario", help="run a scenario directly instead of from a signal")
    ap.add_argument("--impact", type=float, default=None)
    ap.add_argument("--ticker", default=None)
    ap.add_argument("--threshold", type=float, default=None)
    args = ap.parse_args()

    portfolio = load_portfolio(PORTFOLIO_FILE)
    signal = None
    if args.scenario:
        res = run_stress_test(portfolio, args.scenario, args.impact, args.ticker)
    else:
        signals, _ = run_default_pipeline()
        if args.signal_id:
            signal = next((s for s in signals if s.signal_id == args.signal_id), None)
        else:
            signal = pick_demo_signal(signals, args.threshold)
        if signal is None:
            sys.exit("No matching / triggered signal found.")
        res = stress_from_signal(portfolio, signal, args.threshold)

    sig = signal.model_dump(mode="json") if signal else None
    out = res.to_dict() | ({"signal": sig} if sig else {})
    (DATA_DIR / "stress_result.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    (DATA_DIR / "stress_positions.csv").write_text(res.positions_csv(), encoding="utf-8")
    (DOCS_DIR / "stress_report.html").write_text(build_report_html(res, sig), encoding="utf-8")

    if sig:
        print(f"Signal: {sig['event_type']} | impact {sig['impact_score']} | {sig['entity']} | {sig['text'][:110]}")
    print(f"Trigger: {res.trigger.get('rationale', 'manual scenario')}")
    print(f"Scenario: {res.scenario_name} (scale {res.scale:.2f})")
    print(f"Initial ${res.initial_value:,.0f} -> stressed ${res.stressed_value:,.0f} | "
          f"P&L ${res.pnl:,.0f} ({res.pnl_pct:+.2%})")
    print(res.by_asset_class.round(0).to_string(index=False))
    print(res.by_component[["label", "pnl_usd"]].round(0).to_string(index=False))
    print("Worst positions:")
    print(res.positions.nsmallest(5, "total_pnl_usd")[["position_id", "name", "total_pnl_usd"]].round(0).to_string(index=False))


if __name__ == "__main__":
    main()
