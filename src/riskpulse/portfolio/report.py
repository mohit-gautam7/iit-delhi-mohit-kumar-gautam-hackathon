"""Printable, self-contained HTML stress-test report built from the same StressResult as the dashboard."""
from __future__ import annotations

import html
from datetime import datetime, timezone

from .stress import StressResult

CSS = """
body{font-family:Inter,Segoe UI,Arial,sans-serif;background:#F5F7FB;color:#0B1220;margin:32px;}
h1{font-size:22px;margin:0 0 4px} h2{font-size:15px;margin:24px 0 8px;color:#18263B}
.muted{color:#5b6b82;font-size:12px} .kpis{display:flex;gap:12px;margin:16px 0}
.kpi{background:#fff;border:1px solid #d6dde8;border-radius:8px;padding:10px 14px;min-width:150px}
.kpi b{display:block;font-size:18px} .neg{color:#C2283A} .pos{color:#15803D}
table{border-collapse:collapse;width:100%;font-size:12px;background:#fff}
th,td{border:1px solid #d6dde8;padding:5px 7px;text-align:right} th{background:#18263B;color:#F3F6FC}
td:first-child,th:first-child,td.l{text-align:left} .badge{background:#F4B942;color:#0B1220;padding:2px 6px;border-radius:4px;font-size:11px}
@media print{body{margin:12mm}}
"""


def _usd(v: float) -> str:
    return f"{'-' if v < 0 else ''}${abs(v):,.0f}"


def _cls(v: float) -> str:
    return "neg" if v < 0 else ("pos" if v > 0 else "")


def build_report_html(res: StressResult, signal: dict | None = None) -> str:
    e = html.escape
    sig = ""
    if signal:
        sig = (f"<h2>Triggering signal</h2><p><b>{e(signal.get('event_type', ''))}</b> | impact "
               f"{signal.get('impact_score')} | sentiment {signal.get('sentiment_score', 0):+.2f} | "
               f"{e(str(signal.get('entity') or 'market-wide'))} | {e(str(signal.get('timestamp', '')))}</p>"
               f"<p class='muted'>{e(signal.get('text', ''))}</p>"
               f"<p class='muted'>{e(signal.get('explanation', ''))}</p>")
    trig = f"<p>{e(res.trigger.get('rationale', 'Manually selected scenario.'))}</p>" if res.trigger else ""
    classes = "".join(
        f"<tr><td>{e(r.asset_class)}</td><td>{_usd(r.initial_value_usd)}</td><td class='{_cls(r.total_pnl_usd)}'>"
        f"{_usd(r.total_pnl_usd)}</td><td>{r.pnl_pct:+.2%}</td><td>{_usd(r.stressed_value_usd)}</td></tr>"
        for r in res.by_asset_class.itertuples())
    comps = "".join(f"<tr><td>{e(r.label)}</td><td class='{_cls(r.pnl_usd)}'>{_usd(r.pnl_usd)}</td></tr>"
                    for r in res.by_component.itertuples())
    worst = res.positions.sort_values("total_pnl_usd").head(12)
    pos = "".join(
        f"<tr><td>{e(r.position_id)}</td><td class='l'>{e(r.name)}</td><td class='l'>{e(r.asset_class)}</td>"
        f"<td>{_usd(r.initial_value_usd)}</td><td class='{_cls(r.total_pnl_usd)}'>{_usd(r.total_pnl_usd)}</td>"
        f"<td class='l'>{e(r.valuation_method)}{' <span class=badge>approx</span>' if r.approximated else ''}</td></tr>"
        for r in worst.itertuples())
    assumptions = "".join(f"<li>{e(a)}</li>" for a in res.assumptions)
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>RiskPulse AI stress report</title>
<style>{CSS}</style></head><body>
<h1>RiskPulse AI - Portfolio Stress Report</h1>
<div class="muted">Scenario: <b>{e(res.scenario_name)}</b> ({e(res.scenario_key)}) | severity scale {res.scale:.2f} |
generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} | SYNTHETIC PORTFOLIO - illustrative only, not investment advice</div>
<div class="kpis"><div class="kpi">Initial value<b>{_usd(res.initial_value)}</b></div>
<div class="kpi">Stressed value<b>{_usd(res.stressed_value)}</b></div>
<div class="kpi">P&amp;L<b class="{_cls(res.pnl)}">{_usd(res.pnl)}</b></div>
<div class="kpi">P&amp;L %<b class="{_cls(res.pnl)}">{res.pnl_pct:+.2%}</b></div></div>
{sig}<h2>Trigger rationale</h2>{trig or '<p>Manually selected scenario.</p>'}
<h2>P&amp;L by asset class</h2><table><tr><th>Asset class</th><th>Initial</th><th>P&amp;L</th><th>P&amp;L %</th><th>Stressed</th></tr>{classes}</table>
<h2>P&amp;L by risk factor</h2><table><tr><th>Component</th><th>P&amp;L</th></tr>{comps}</table>
<h2>Worst-affected positions</h2><table><tr><th>ID</th><th>Position</th><th>Class</th><th>Initial</th><th>P&amp;L</th><th>Method</th></tr>{pos}</table>
<h2>Assumptions</h2><ul>{assumptions}</ul>
</body></html>"""
