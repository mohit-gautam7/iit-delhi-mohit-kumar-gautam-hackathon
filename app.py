"""RiskPulse AI - Streamlit dashboard. Run: streamlit run app.py"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

import pandas as pd  # noqa: E402
import plotly.express as px  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

from riskpulse import __version__  # noqa: E402
from riskpulse.config import CONFIG_DIR, DATA_DIR, NEWS_FILE, PORTFOLIO_FILE, SOCIAL_FILE  # noqa: E402
from riskpulse.evaluation.metrics import run_evaluation  # noqa: E402
from riskpulse.ingestion import fetch_rss, ingest  # noqa: E402
from riskpulse.nlp import transformer  # noqa: E402
from riskpulse.pipeline import default_engine, signals_to_csv, signals_to_json  # noqa: E402
from riskpulse.portfolio.model import load_portfolio, summary_by_asset_class  # noqa: E402
from riskpulse.portfolio.report import build_report_html  # noqa: E402
from riskpulse.portfolio.stress import (COMPONENTS, effective_scenario, evaluate_trigger, pick_demo_signal,  # noqa: E402
                                        run_stress_test, scenarios, settings)
from riskpulse.schemas import RiskSignal  # noqa: E402
from riskpulse.ui import (C, CSS, SENTIMENT_COLORS, SEQUENTIAL, SOURCE_COLORS, badge, impact_badge,  # noqa: E402
                          kpi, sentiment_badge, style_fig, usd)
from riskpulse.universe import ALL_EVENT_LABELS, SENTIMENT_LABELS  # noqa: E402

st.set_page_config(page_title="RiskPulse AI", page_icon="📈", layout="wide", initial_sidebar_state="expanded")
st.markdown(CSS, unsafe_allow_html=True)
PLOT_CFG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d"]}

ss = st.session_state
ss.setdefault("use_news", True)
ss.setdefault("use_social", True)
ss.setdefault("extra", [])          # list of (bytes, source_type | None, label)
ss.setdefault("use_tf", False)
ss.setdefault("threshold", float(settings()["trigger_threshold"]))


# ---------------------------------------------------------------- data layer
@st.cache_data(show_spinner="Running the NLP risk pipeline...")
def load_signals(use_news: bool, use_social: bool, extra: tuple, use_tf: bool):
    sources = []
    if use_news:
        sources.append((NEWS_FILE, "news", NEWS_FILE.name))
    if use_social:
        sources.append((SOCIAL_FILE, "social", SOCIAL_FILE.name))
    sources += [(data, stype, label) for data, stype, label in extra]
    records, report = ingest(sources)
    signals = default_engine(use_tf).analyze_records(records)
    return [s.model_dump(mode="json") for s in signals], report.model_dump()


@st.cache_data
def load_pf() -> pd.DataFrame:
    return load_portfolio(PORTFOLIO_FILE)


@st.cache_data(show_spinner="Computing evaluation metrics (held-out templates, CV, challenge set)...")
def cached_evaluation() -> dict:
    return run_evaluation()


def current() -> tuple[list[dict], dict, pd.DataFrame]:
    sigs, report = load_signals(ss.use_news, ss.use_social, tuple(ss.extra), ss.use_tf)
    df = pd.DataFrame(sigs)
    if not df.empty:
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        df["date"] = df["timestamp"].dt.date
        df["entity_label"] = df["ticker"].fillna("Market-wide")
    return sigs, report, df


def to_signals(rows: list[dict]) -> list[RiskSignal]:
    return [RiskSignal(**r) for r in rows]


def synthetic_banner(df: pd.DataFrame) -> None:
    n_syn = int(df["is_synthetic"].sum()) if not df.empty else 0
    st.markdown(
        badge(f"{n_syn}/{len(df)} records synthetic", "warn") + badge("Replayed dataset - not live market data", "info")
        + badge(f"Model: {'transformer mode' if ss.use_tf else 'baseline (offline)'}"), unsafe_allow_html=True)


def empty_state(msg: str = "No signals loaded. Enable a bundled source or upload a file on Data & Methodology.") -> None:
    st.info(msg)


def fig_show(fig: go.Figure) -> None:
    st.plotly_chart(fig, width="stretch", config=PLOT_CFG)


def signal_label(r: dict | pd.Series) -> str:
    who = r["ticker"] if isinstance(r["ticker"], str) and r["ticker"] else "Market-wide"
    ts = pd.Timestamp(r["timestamp"]).strftime("%Y-%m-%d %H:%M")
    return f"{ts} | {r['event_type']} | {who} | impact {r['impact_score']} | {r['source_type']}"


def signal_detail(r: dict, threshold: float) -> None:
    st.markdown(
        f"{impact_badge(int(r['impact_score']), threshold)}{sentiment_badge(r['sentiment_label'], r['sentiment_score'])}"
        f"{badge(r['event_type'], 'info')}{badge('confidence ' + format(r['confidence'], '.2f'))}"
        f"{badge(r['source_type'] + ' / ' + r['source_name'])}"
        + (badge('ambiguous: also ' + str(r['secondary_event_type']), 'warn') if r.get('is_ambiguous') else '')
        + (badge('synthetic', 'warn') if r['is_synthetic'] else badge('real source', 'pos')), unsafe_allow_html=True)
    who = f"{r['entity']} ({r['ticker']}, {r['sector']})" if r.get("ticker") else "No specific company (market-wide)"
    st.markdown(f"**Entity:** {who}  \n**Timestamp:** {pd.Timestamp(r['timestamp']).strftime('%Y-%m-%d %H:%M UTC')}  "
                f"\n**Signal ID:** `{r['signal_id']}`")
    st.markdown("**Why this signal was generated**")
    st.markdown(f"<div class='rp-card'>{r['explanation']}</div>", unsafe_allow_html=True)
    f = {k: v for k, v in (r.get("impact_factors") or {}).items()
         if k != "raw_total" and (k == "base_severity" or abs(v) >= 0.005)}
    if f:
        fig = go.Figure(go.Waterfall(
            x=[k.replace("_", " ") for k in f] + ["raw total"], y=list(f.values()) + [0],
            measure=["relative"] * len(f) + ["total"], text=[f"{v:+.2f}" for v in f.values()] + [f"{sum(f.values()):.2f}"],
            textposition="outside", increasing={"marker": {"color": C["accent"]}},
            decreasing={"marker": {"color": C["neg"]}}, totals={"marker": {"color": C["teal"]}},
            connector={"line": {"color": C["border"]}}))
        fig.update_yaxes(title="impact points")
        fig_show(style_fig(fig, 260, f"Impact score breakdown -> {r['impact_score']}/10 (rounded, clipped to 1-10)"))
    with st.expander("Source text evidence"):
        st.markdown(f"<div class='rp-evidence'>{r['text']}</div>", unsafe_allow_html=True)
    with st.expander("Structured JSON"):
        st.json({k: v for k, v in r.items() if k not in ("date", "entity_label")})


# ---------------------------------------------------------------- pages
def page_overview() -> None:
    sigs, report, df = current()
    st.title("Executive Risk Overview")
    st.caption("Statistics computed live from the currently loaded dataset. Bundled data is synthetic and replayed.")
    synthetic_banner(df)
    if df.empty:
        return empty_state()
    th = ss.threshold
    high = df[df["impact_score"] > th]
    pf = load_pf()
    demo = pick_demo_signal(to_signals(sigs), th)
    res = None
    if demo is not None:
        res = run_stress_test(pf, evaluate_trigger(demo, th)["scenario_key"], demo.impact_score, demo.ticker,
                              demo.sentiment_score, trigger=evaluate_trigger(demo, th))
    cols = st.columns(5)
    cols[0].markdown(kpi("Records processed", f"{len(df)}", f"{report['rows_read']} read · {report['duplicates']} duplicates · "
                         f"{report['rejected']} rejected"), unsafe_allow_html=True)
    cols[1].markdown(kpi("High-impact events", f"{len(high)}", f"impact > {th:g} ({len(high) / len(df):.0%} of signals)",
                         "neg" if len(high) else ""), unsafe_allow_html=True)
    avg = df["sentiment_score"].mean()
    cols[2].markdown(kpi("Average sentiment", f"{avg:+.2f}", f"{(df['sentiment_label'] == 'Negative').mean():.0%} negative",
                         "neg" if avg < -0.15 else ("pos" if avg > 0.15 else "")), unsafe_allow_html=True)
    cols[3].markdown(kpi("Entities identified", f"{df['ticker'].nunique()}",
                         f"{df['ticker'].notna().mean():.0%} of signals linked to a ticker"), unsafe_allow_html=True)
    if res is not None:
        cols[4].markdown(kpi("Top-signal stress P&L", usd(res.pnl), f"{res.pnl_pct:+.2%} · {res.scenario_name}",
                             "neg" if res.pnl < 0 else "pos"), unsafe_allow_html=True)
    else:
        cols[4].markdown(kpi("Top-signal stress P&L", "n/a", "no signal above threshold"), unsafe_allow_html=True)

    st.write("")
    c1, c2 = st.columns([1, 1.4])
    with c1:
        counts = df["sentiment_label"].value_counts().reindex(SENTIMENT_LABELS, fill_value=0)
        fig = go.Figure(go.Bar(x=counts.values, y=counts.index, orientation="h", text=counts.values, textposition="outside",
                               marker_color=[SENTIMENT_COLORS[s] for s in counts.index],
                               hovertemplate="%{y}: %{x} signals<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        fig_show(style_fig(fig, 230, "Sentiment distribution"))
        ent = df[df["ticker"].notna()]["ticker"].value_counts().head(8)
        fig = go.Figure(go.Bar(x=ent.values, y=ent.index, orientation="h", marker_color=C["accent"], text=ent.values,
                               textposition="outside", hovertemplate="%{y}: %{x} signals<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        fig_show(style_fig(fig, 300, "Most frequently affected entities"))
    with c2:
        ev = df["event_type"].value_counts().sort_values()
        fig = go.Figure(go.Bar(x=ev.values, y=ev.index, orientation="h", marker_color=C["accent"], text=ev.values,
                               textposition="outside", hovertemplate="%{y}: %{x} signals<extra></extra>"))
        fig_show(style_fig(fig, 330, "Event-category distribution"))
        daily = df.groupby("date").agg(sentiment=("sentiment_score", "mean"), n=("signal_id", "count")).reset_index()
        fig = go.Figure(go.Scatter(x=daily["date"], y=daily["sentiment"], mode="lines+markers",
                                   line=dict(color=C["accent"], width=2), marker=dict(size=8),
                                   customdata=daily["n"], hovertemplate="%{x}<br>mean sentiment %{y:+.2f}<br>%{customdata} signals<extra></extra>"))
        fig.add_hline(y=0, line_color=C["border"])
        fig.update_yaxes(range=[-1, 1], title="mean sentiment")
        fig_show(style_fig(fig, 200, "Daily sentiment trend"))

    c3, c4 = st.columns([1.6, 1])
    with c3:
        st.subheader("Recent high-impact events")
        show = high.sort_values("timestamp", ascending=False).head(10)
        st.dataframe(show[["timestamp", "event_type", "entity_label", "impact_score", "sentiment_score", "source_type", "text"]],
                     hide_index=True, width="stretch", column_config={
                         "timestamp": st.column_config.DatetimeColumn("Time (UTC)", format="YYYY-MM-DD HH:mm"),
                         "event_type": "Event", "entity_label": "Entity",
                         "impact_score": st.column_config.ProgressColumn("Impact", min_value=0, max_value=10, format="%d"),
                         "sentiment_score": st.column_config.NumberColumn("Sentiment", format="%+.2f"),
                         "source_type": "Source", "text": st.column_config.TextColumn("Text", width="large")})
    with c4:
        st.subheader("Current stress-test summary")
        if res is not None:
            st.markdown(
                f"<div class='rp-card'><p>{badge('auto-triggered', 'neg')}{badge(res.scenario_name, 'info')}</p>"
                f"<p class='rp-note'>{demo.event_type} · {demo.entity or 'market-wide'} · impact {demo.impact_score}</p>"
                f"<p>Portfolio {usd(res.initial_value)} → <b>{usd(res.stressed_value)}</b></p>"
                f"<p>P&amp;L <b style='color:{C['neg'] if res.pnl < 0 else C['pos']}'>{usd(res.pnl)} ({res.pnl_pct:+.2%})</b></p>"
                f"<p class='rp-note'>{res.trigger['rationale']}</p>"
                f"<p class='rp-note'>Open <b>Portfolio Stress Lab</b> to change the signal, scenario or assumptions.</p></div>",
                unsafe_allow_html=True)
        else:
            st.info("No signal exceeds the threshold.")
        st.subheader("Source & processing status")
        by_src = df["source_type"].value_counts()
        st.markdown(
            "<div class='rp-card'>" + "".join(f"<p>{badge(k, 'info')} {v} signals</p>" for k, v in by_src.items())
            + f"<p class='rp-note'>Files: {', '.join(report['files']) or 'none'}<br>Rejected rows: {report['rejected']} · "
              f"duplicates removed: {report['duplicates']} · file-level issues: "
              f"{sum(1 for i in report['issues'] if i['row'] is None)}</p></div>", unsafe_allow_html=True)


def page_explorer() -> None:
    sigs, _, df = current()
    st.title("Risk Signal Explorer")
    synthetic_banner(df)
    if df.empty:
        return empty_state()
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns([2, 1.3, 1.3, 1.2])
        q = f1.text_input("Search text", placeholder="e.g. downgrade, ransomware, sanctions")
        tickers = f2.multiselect("Company / ticker", sorted(df["ticker"].dropna().unique()))
        sents = f3.multiselect("Sentiment", SENTIMENT_LABELS)
        srcs = f4.multiselect("Source", sorted(df["source_type"].unique()))
        g1, g2, g3 = st.columns([2.2, 1.3, 1.5])
        evs = g1.multiselect("Event classification", [e for e in ALL_EVENT_LABELS if e in set(df["event_type"])])
        imp = g2.slider("Impact score", 1, 10, (1, 10))
        dmin, dmax = df["date"].min(), df["date"].max()
        dr = g3.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)
    m = df["impact_score"].between(*imp)
    if q:
        m &= df["text"].str.contains(q, case=False, regex=False)
    if tickers:
        m &= df["ticker"].isin(tickers)
    if sents:
        m &= df["sentiment_label"].isin(sents)
    if srcs:
        m &= df["source_type"].isin(srcs)
    if evs:
        m &= df["event_type"].isin(evs)
    if isinstance(dr, (tuple, list)) and len(dr) == 2:
        m &= df["date"].between(dr[0], dr[1])
    view = df[m].sort_values("timestamp", ascending=False).reset_index(drop=True)

    top = st.columns([3, 1, 1])
    top[0].markdown(f"**{len(view)}** of {len(df)} signals match. Select a row to see its explanation.")
    filtered = [s for s in sigs if s["signal_id"] in set(view["signal_id"])]
    top[1].download_button("Download CSV", signals_to_csv(to_signals(filtered)), "riskpulse_signals_filtered.csv",
                           "text/csv", width="stretch", disabled=not filtered)
    top[2].download_button("Download JSON", signals_to_json(to_signals(filtered)), "riskpulse_signals_filtered.json",
                           "application/json", width="stretch", disabled=not filtered)
    if view.empty:
        return st.warning("No signals match these filters. Widen the impact range or clear a filter.")
    event = st.dataframe(
        view[["timestamp", "source_type", "entity_label", "event_type", "sentiment_label", "sentiment_score",
              "impact_score", "confidence", "text"]],
        hide_index=True, width="stretch", height=380, on_select="rerun", selection_mode="single-row",
        column_config={
            "timestamp": st.column_config.DatetimeColumn("Time (UTC)", format="YYYY-MM-DD HH:mm"),
            "source_type": "Source", "entity_label": "Entity", "event_type": "Event", "sentiment_label": "Sentiment",
            "sentiment_score": st.column_config.NumberColumn("Score", format="%+.2f"),
            "impact_score": st.column_config.ProgressColumn("Impact", min_value=0, max_value=10, format="%d"),
            "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
            "text": st.column_config.TextColumn("Text", width="large")})
    rows = event.selection.rows if event and event.selection else []
    r = view.iloc[rows[0]] if rows else view.iloc[0]
    st.subheader("Signal detail" + ("" if rows else " (latest - select a row to change)"))
    signal_detail(next(s for s in sigs if s["signal_id"] == r["signal_id"]), ss.threshold)


def page_events() -> None:
    sigs, _, df = current()
    st.title("Event Intelligence")
    synthetic_banner(df)
    if df.empty:
        return empty_state()
    th = ss.threshold
    rank = (df.groupby("event_type").agg(signals=("signal_id", "count"), avg_impact=("impact_score", "mean"),
                                         max_impact=("impact_score", "max"),
                                         high_impact=("impact_score", lambda s: int((s > th).sum())),
                                         avg_sentiment=("sentiment_score", "mean"), avg_confidence=("confidence", "mean"))
            .sort_values(["high_impact", "avg_impact"], ascending=False).reset_index())
    c1, c2 = st.columns([1.1, 1])
    with c1:
        st.subheader("Event rankings")
        st.dataframe(rank, hide_index=True, width="stretch", height=35 * (len(rank) + 1) + 3, column_config={
            "event_type": "Event", "signals": "Signals",
            "avg_impact": st.column_config.ProgressColumn("Avg impact", min_value=0, max_value=10, format="%.1f"),
            "max_impact": "Max", "high_impact": f"> {th:g}",
            "avg_sentiment": st.column_config.NumberColumn("Avg sentiment", format="%+.2f"),
            "avg_confidence": st.column_config.NumberColumn("Avg conf.", format="%.2f")})
    with c2:
        jitter = (pd.util.hash_pandas_object(df["signal_id"], index=False) % 100 / 100 - 0.5) * 0.5
        fig = go.Figure()
        for src, sub in df.assign(j=df["impact_score"] + jitter.values).groupby("source_type"):
            fig.add_trace(go.Scatter(
                x=sub["sentiment_score"], y=sub["j"], mode="markers", name=src,
                marker=dict(size=9, color=SOURCE_COLORS.get(src, C["accent"]), opacity=0.8, line=dict(color=C["bg"], width=1)),
                customdata=sub[["event_type", "entity_label", "impact_score"]],
                hovertemplate="%{customdata[0]} · %{customdata[1]}<br>sentiment %{x:+.2f} · impact %{customdata[2]}<extra>%{fullData.name}</extra>"))
        fig.add_hline(y=th + 0.5, line_dash="dot", line_color=C["warn"], annotation_text=f"stress trigger (> {th:g})",
                      annotation_font_color=C["warn"])
        fig.update_xaxes(title="sentiment score", range=[-1.05, 1.05])
        fig.update_yaxes(title="impact score (jittered)", range=[0.4, 10.6])
        fig_show(style_fig(fig, 360, "Sentiment vs impact (negative tone ≠ high impact)"))

    c3, c4 = st.columns([1.3, 1])
    with c3:
        piv = df.pivot_table(index="event_type", columns="date", values="signal_id", aggfunc="count", fill_value=0)
        fig = go.Figure(go.Heatmap(z=piv.values, x=[str(d) for d in piv.columns], y=piv.index, colorscale=SEQUENTIAL,
                                   hovertemplate="%{y}<br>%{x}: %{z} signals<extra></extra>", colorbar=dict(title="signals")))
        fig_show(style_fig(fig, 360, "Event-category trend (signals per day)"))
    with c4:
        w = pd.Series(default_engine().weights, name="weight")
        ent = (df[df["ticker"].notna()].groupby("ticker").agg(signals=("signal_id", "count"),
                                                              high=("impact_score", lambda s: int((s > th).sum())))
               .join(w, how="left").fillna({"weight": 0}).reset_index().sort_values("weight"))
        fig = go.Figure()
        fig.add_trace(go.Bar(y=ent["ticker"], x=ent["weight"] * 100, orientation="h", name="portfolio weight %",
                             marker_color=C["accent"], customdata=ent[["signals", "high"]],
                             hovertemplate="%{y}: %{x:.1f}% of portfolio<br>%{customdata[0]} signals, %{customdata[1]} high-impact<extra></extra>",
                             text=[f"{h} high" for h in ent["high"]], textposition="outside"))
        fig.update_xaxes(title="share of synthetic portfolio (%)")
        fig_show(style_fig(fig, 360, "Entity portfolio weight & high-impact signals"))

    st.subheader("Recent signals - confidence & explanation")
    recent = df.sort_values("timestamp", ascending=False).head(40)
    pick = st.selectbox("Select a signal", recent.index, format_func=lambda i: signal_label(recent.loc[i]))
    r = next(s for s in sigs if s["signal_id"] == recent.loc[pick, "signal_id"])
    clf = default_engine().classifier.predict(r["text"])
    c5, c6 = st.columns([1.3, 1])
    with c5:
        signal_detail(r, th)
    with c6:
        probs = pd.Series(clf["probabilities"]).sort_values().tail(6)
        fig = go.Figure(go.Bar(x=probs.values, y=probs.index, orientation="h", marker_color=C["teal"],
                               text=[f"{v:.2f}" for v in probs.values], textposition="outside",
                               hovertemplate="%{y}: %{x:.3f}<extra></extra>"))
        fig.update_xaxes(range=[0, 1.1], title="combined probability (rules + model)")
        fig_show(style_fig(fig, 300, "Classifier probabilities (top 6)"))
        ev = clf["all_rule_evidence"]
        st.markdown("**Keyword evidence by category**")
        st.markdown("<br>".join(f"{badge(k, 'info')} " + ", ".join(f"`{x}`" for x in v) for k, v in ev.items())
                    or "<span class='rp-note'>No keyword evidence - model-only decision.</span>", unsafe_allow_html=True)


def page_stress() -> None:
    sigs, _, df = current()
    st.title("Portfolio Stress Lab")
    st.caption("Synthetic ~USD 1bn wholesale-banking book. The same engine powers the API, CLI and exported reports.")
    pf = load_pf()
    th = ss.threshold

    with st.expander("Synthetic portfolio summary", expanded=False):
        summ = summary_by_asset_class(pf)
        a, b = st.columns([1, 1.2])
        a.dataframe(summ, hide_index=True, width="stretch", column_config={
            "asset_class": "Asset class", "positions": "Positions",
            "market_value_usd": st.column_config.NumberColumn("Market value (USD)", format="dollar"),
            "notional_usd": st.column_config.NumberColumn("Notional (USD)", format="dollar"),
            "weight": st.column_config.NumberColumn("Weight", format="percent")})
        fig = go.Figure(go.Bar(x=summ["market_value_usd"] / 1e6, y=summ["asset_class"], orientation="h",
                               marker_color=C["accent"], text=[usd(v) for v in summ["market_value_usd"]],
                               textposition="outside", hovertemplate="%{y}: $%{x:,.1f}m<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title="USD m")
        with b:
            fig_show(style_fig(fig, 250, f"Composition - total {usd(pf['market_value_usd'].sum())}"))
        st.dataframe(pf, hide_index=True, width="stretch", height=260)

    # ---- 1. signal & trigger
    st.subheader("1 · Select the triggering event")
    sig_objs = to_signals(sigs)
    all_mode = st.toggle("Choose from all signals (manual override)", value=False,
                         help="Off: only signals whose impact exceeds the threshold and that map to a scenario.")
    pool = [s for s in sig_objs if all_mode or evaluate_trigger(s, th)["triggered"]]
    pool = sorted(pool, key=lambda s: (-s.impact_score, s.sentiment_score, s.timestamp))
    scn_all = scenarios()
    sig = None
    if pool:
        default_sig = pick_demo_signal(pool, th) if not all_mode else pool[0]
        idx = pool.index(default_sig) if default_sig in pool else 0
        sig = st.selectbox(f"{len(pool)} candidate signal(s)", pool, index=idx,
                           format_func=lambda s: signal_label(s.model_dump()))
    else:
        st.info(f"No signal exceeds the threshold ({th:g}). Lower it in the sidebar, enable manual override, "
                "or pick a scenario below.")
    trig = evaluate_trigger(sig, th) if sig else {"triggered": False, "scenario_key": None, "rationale": "Manual scenario."}
    if sig:
        st.markdown(f"<div class='rp-card'><p>{badge('TRIGGERED', 'neg') if trig['triggered'] else badge('not triggered', 'warn')}"
                    f"{impact_badge(sig.impact_score, th)}{sentiment_badge(sig.sentiment_label, sig.sentiment_score)}"
                    f"{badge(sig.event_type, 'info')}</p><p>{sig.text}</p><p class='rp-note'>{trig['rationale']}</p></div>",
                    unsafe_allow_html=True)

    # ---- 2. scenario & assumptions
    st.subheader("2 · Scenario and stress assumptions")
    keys = list(scn_all)
    default_key = trig["scenario_key"] or keys[0]
    s1, s2 = st.columns([1.4, 1])
    key = s1.selectbox("Scenario", keys, index=keys.index(default_key), format_func=lambda k: scn_all[k]["name"],
                       help="Auto-selected from the event type; change it to run any scenario manually.")
    scale_on = s2.toggle("Scale shocks by impact score", value=bool(settings()["scale_with_impact"]),
                         help=f"scale = impact / {settings()['reference_impact']}, clipped to "
                              f"[{settings()['scale_floor']}, {settings()['scale_cap']}]")
    base = scn_all[key]
    st.markdown(f"<span class='rp-note'>{base['description']}</span><br>"
                f"<span class='rp-note'>Shocked asset classes: {', '.join(base['affected_asset_classes'])}</span>",
                unsafe_allow_html=True)
    ov: dict = {}
    with st.expander("Edit stress assumptions (base values before impact scaling)", expanded=False):
        k = f"{key}_"
        e1, e2, e3, e4 = st.columns(4)
        ov["equity_shock_pct"] = e1.number_input("Equity market move (%)", -60.0, 60.0,
                                                 float(base.get("equity_shock_pct", 0)) * 100, 1.0, key=k + "eq") / 100
        ov["rate_shock_bp"] = e2.number_input("Parallel rate shock (bp)", -500.0, 500.0,
                                              float(base.get("rate_shock_bp", 0)), 5.0, key=k + "rt")
        ov["pd_multiplier"] = e3.number_input("PD multiplier (all loans)", 0.5, 10.0,
                                              float(base.get("pd_multiplier", 1)), 0.05, key=k + "pd")
        ov["lgd_add"] = e4.number_input("LGD add-on (pp)", 0.0, 50.0, float(base.get("lgd_add", 0)) * 100, 1.0,
                                        key=k + "lgd") / 100
        st.markdown("**Credit-spread widening by rating bucket (bp)**")
        cols = st.columns(4)
        ov["credit_spread_shock_bp"] = {b: cols[i].number_input(b.replace("_", "/"), -200.0, 2000.0,
                                                                float((base.get("credit_spread_shock_bp") or {}).get(b, 0)),
                                                                5.0, key=k + "cs" + b)
                                        for i, b in enumerate(["AAA_AA", "A", "BBB", "HY"])}
        st.markdown("**Entity-specific shock (applies to the company named in the signal)**")
        ent = base.get("entity_shock") or {}
        cols = st.columns(4)
        ov["entity_shock"] = {
            "equity_pct": cols[0].number_input("Entity equity move (%)", -100.0, 100.0, float(ent.get("equity_pct", 0)) * 100,
                                               1.0, key=k + "ee") / 100,
            "spread_bp": cols[1].number_input("Entity spread (bp)", 0.0, 3000.0, float(ent.get("spread_bp", 0)), 10.0, key=k + "es"),
            "pd_multiplier": cols[2].number_input("Entity PD multiplier", 1.0, 20.0, float(ent.get("pd_multiplier", 1)), 0.1,
                                                  key=k + "ep")}
        ov["sector_contagion"] = cols[3].number_input("Sector contagion (share)", 0.0, 1.0,
                                                      float(base.get("sector_contagion", 0)), 0.05, key=k + "sc")
        fx = dict(base.get("fx_shocks_pct") or {})
        liq = dict(base.get("liquidity_haircut_pct") or {})
        com = dict(base.get("commodity_shocks_pct") or {})
        if fx or liq or com:
            st.markdown("**FX, commodity and liquidity (%)**")
            items = [("fx", c, v) for c, v in fx.items()] + [("com", c, v) for c, v in com.items()] + \
                    [("liq", c, v) for c, v in liq.items()]
            cols = st.columns(max(1, min(4, len(items))))
            out = {"fx": {}, "com": {}, "liq": {}}
            for i, (kind, name, val) in enumerate(items):
                label = {"fx": f"{name} vs USD", "com": f"{name} price", "liq": f"{name} haircut"}[kind]
                out[kind][name] = cols[i % len(cols)].number_input(label, -100.0, 100.0, float(val) * 100, 0.5,
                                                                    key=k + kind + name) / 100
            ov["fx_shocks_pct"], ov["commodity_shocks_pct"], ov["liquidity_haircut_pct"] = out["fx"], out["com"], out["liq"]
        if st.button("Reset to scenario defaults", key=k + "reset"):
            for wk in [w for w in ss if str(w).startswith(k)]:
                del ss[wk]
            st.rerun()

    impact = sig.impact_score if sig else None
    res = run_stress_test(pf, key, impact, sig.ticker if sig else None, sig.sentiment_score if sig else None,
                          ov, scale_on, trig if sig and trig["scenario_key"] == key else
                          {"triggered": False, "scenario_key": key,
                           "rationale": f"Scenario '{base['name']}' selected manually by the analyst."})

    # ---- 3. results
    st.subheader("3 · Results")
    cols = st.columns(5)
    cols[0].markdown(kpi("Value before stress", usd(res.initial_value), f"{len(pf)} positions"), unsafe_allow_html=True)
    cols[1].markdown(kpi("Value after stress", usd(res.stressed_value), res.scenario_name), unsafe_allow_html=True)
    tone = "neg" if res.pnl < 0 else "pos"
    cols[2].markdown(kpi("P&L", usd(res.pnl), "loss" if res.pnl < 0 else "gain", tone), unsafe_allow_html=True)
    cols[3].markdown(kpi("P&L %", f"{res.pnl_pct:+.2%}", "of initial portfolio value", tone), unsafe_allow_html=True)
    cols[4].markdown(kpi("Positions affected", f"{int(res.positions['affected'].sum())}",
                         f"severity scale {res.scale:.2f}"), unsafe_allow_html=True)
    st.write("")
    r1, r2 = st.columns(2)
    with r1:
        comp = res.by_component
        fig = go.Figure(go.Waterfall(
            x=list(comp["label"]) + ["Total P&L"], y=list(comp["pnl_usd"] / 1e6) + [0],
            measure=["relative"] * len(comp) + ["total"],
            text=[usd(v) for v in comp["pnl_usd"]] + [usd(res.pnl)], textposition="outside",
            increasing={"marker": {"color": C["pos"]}}, decreasing={"marker": {"color": C["neg"]}},
            totals={"marker": {"color": C["accent"]}}, connector={"line": {"color": C["border"]}},
            hovertemplate="%{x}: %{y:,.2f}m<extra></extra>"))
        fig.update_yaxes(title="USD m")
        fig_show(style_fig(fig, 360, "P&L waterfall by risk factor"))
    with r2:
        bc = res.by_asset_class
        fig = go.Figure(go.Bar(x=bc["total_pnl_usd"] / 1e6, y=bc["asset_class"], orientation="h",
                               marker_color=[C["neg"] if v < 0 else C["pos"] for v in bc["total_pnl_usd"]],
                               text=[f"{usd(v)} ({p:+.1%})" for v, p in zip(bc["total_pnl_usd"], bc["pnl_pct"])],
                               textposition="outside", hovertemplate="%{y}: %{x:,.2f}m<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        style_fig(fig, 360, "Loss contribution by asset class")
        lo, hi = min(0, bc["total_pnl_usd"].min() / 1e6), max(0, bc["total_pnl_usd"].max() / 1e6)
        span = (hi - lo) or 1
        fig.update_xaxes(title="USD m", range=[lo - 0.55 * span * (lo < 0), hi + 0.55 * span * (hi > 0)])
        fig_show(fig)
    r3, r4 = st.columns([1, 1.2])
    with r3:
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Before", y=bc["asset_class"], x=bc["initial_value_usd"] / 1e6, orientation="h",
                             marker_color=C["accent"], hovertemplate="%{y} before: $%{x:,.1f}m<extra></extra>"))
        fig.add_trace(go.Bar(name="After", y=bc["asset_class"], x=bc["stressed_value_usd"] / 1e6, orientation="h",
                             marker_color="#B8863A", hovertemplate="%{y} after: $%{x:,.1f}m<extra></extra>"))
        fig.update_layout(barmode="group")
        fig.update_yaxes(autorange="reversed")
        fig.update_xaxes(title="USD m")
        fig_show(style_fig(fig, 330, "Before / after value by asset class"))
    with r4:
        st.markdown("**How the event triggered this scenario**")
        st.markdown(f"<div class='rp-card'><p>{res.trigger.get('rationale', '')}</p>"
                    + "".join(f"<p class='rp-note'>• {a}</p>" for a in res.assumptions) + "</div>", unsafe_allow_html=True)

    st.markdown("**Position-level results**")
    only = st.toggle("Show affected positions only", value=True)
    pos = res.positions[res.positions["affected"]] if only else res.positions
    st.dataframe(pos.sort_values("total_pnl_usd")[[
        "position_id", "name", "asset_class", "ticker", "initial_value_usd", *COMPONENTS, "total_pnl_usd",
        "stressed_value_usd", "pnl_pct_of_position", "entity_match", "approximated", "valuation_method"]],
        hide_index=True, width="stretch", height=360, column_config={
            "position_id": "ID", "name": "Position", "asset_class": "Asset class", "ticker": "Ticker",
            "initial_value_usd": st.column_config.NumberColumn("Initial", format="dollar"),
            **{c: st.column_config.NumberColumn(c.replace("_", " "), format="dollar") for c in COMPONENTS},
            "total_pnl_usd": st.column_config.NumberColumn("Total P&L", format="dollar"),
            "stressed_value_usd": st.column_config.NumberColumn("Stressed", format="dollar"),
            "pnl_pct_of_position": st.column_config.NumberColumn("P&L %", format="percent"),
            "entity_match": "Entity hit", "approximated": "Approx.", "valuation_method": "Method"})
    worst = res.positions.nsmallest(5, "total_pnl_usd")
    st.markdown("**Worst-performing exposures:** " + " · ".join(  # \$ stops Streamlit reading $...$ as LaTeX
        f"{r.position_id} {r.name} ({usd(r.total_pnl_usd)})".replace("$", r"\$")
        for r in worst.itertuples() if r.total_pnl_usd < 0))
    sigd = sig.model_dump(mode="json") if sig else None
    d1, d2, d3 = st.columns(3)
    d1.download_button("Download results (JSON)", json.dumps(res.to_dict() | ({"signal": sigd} if sigd else {}), indent=2),
                       f"riskpulse_stress_{key}.json", "application/json", width="stretch")
    d2.download_button("Download positions (CSV)", res.positions_csv(), f"riskpulse_stress_{key}_positions.csv",
                       "text/csv", width="stretch")
    d3.download_button("Download printable report (HTML)", build_report_html(res, sigd), f"riskpulse_stress_{key}.html",
                       "text/html", width="stretch")
    eff, _ = effective_scenario(key, impact, ov, scale_on)
    with st.expander("Effective (scaled) parameters used in this run"):
        st.json(eff)


def page_evaluation() -> None:
    st.title("Model Evaluation")
    st.caption("All metrics are computed by riskpulse.evaluation on synthetic, template-generated text. "
               "They show the pipeline works and how it generalises; they are not real-market performance.")
    rep = cached_evaluation()
    ec, ch, se = rep["event_classification"], rep["challenge_set"], rep["sentiment"]
    hy = ec["variants"]["hybrid"]
    cols = st.columns(5)
    cols[0].markdown(kpi("Hybrid accuracy", f"{hy['accuracy']:.1%}", "held-out templates"), unsafe_allow_html=True)
    cols[1].markdown(kpi("Hybrid macro-F1", f"{hy['macro_f1']:.3f}", "held-out templates"), unsafe_allow_html=True)
    cv = ec["grouped_cv_macro_f1"]
    cols[2].markdown(kpi("Grouped CV macro-F1", f"{cv['mean']:.3f}", f"± {cv['std']:.3f} over {len(cv['folds'])} folds"),
                     unsafe_allow_html=True)
    cols[3].markdown(kpi("Challenge-set accuracy", f"{ch['hybrid']['accuracy']:.1%}", f"{ch['rows']} hand-written paraphrases",
                         "neg"), unsafe_allow_html=True)
    cols[4].markdown(kpi("Sentiment accuracy", f"{se['finance_adapted']['accuracy']:.1%}",
                         f"naive VADER {se['naive_vader']['accuracy']:.1%}"), unsafe_allow_html=True)

    st.subheader("Event classification")
    st.markdown(f"<span class='rp-note'>Split: {ec['split']['method']} - {ec['split']['train_rows']} train rows "
                f"({ec['split']['train_templates']} templates), {ec['split']['test_rows']} test rows "
                f"({ec['split']['test_templates']} unseen templates).</span>", unsafe_allow_html=True)
    comp = pd.DataFrame([{"variant": k, "held-out accuracy": v["accuracy"], "held-out macro-F1": v["macro_f1"],
                          "challenge accuracy": ch[k]["accuracy"], "challenge macro-F1": ch[k]["macro_f1"]}
                         for k, v in ec["variants"].items()])
    tf = rep.get("transformer_upgrade", {})
    saved = DATA_DIR / "evaluation_report.json"
    if not tf.get("available") and saved.exists():
        tf = json.loads(saved.read_text(encoding="utf-8")).get("transformer_upgrade", {})
    if tf.get("available"):
        t = tf["hybrid_plus_zero_shot_challenge"]
        comp = pd.concat([comp, pd.DataFrame([{"variant": "hybrid + zero-shot fallback (optional, precomputed)",
                                               "held-out accuracy": None, "held-out macro-F1": None,
                                               "challenge accuracy": t["accuracy"], "challenge macro-F1": t["macro_f1"]}])])
    st.dataframe(comp, hide_index=True, width="stretch")
    st.markdown(
        "<span class='rp-note'><b>Reading these numbers honestly:</b> the keyword rules and the synthetic templates were "
        "written by the same author, so held-out-template scores are optimistic. The hand-written challenge set "
        "(paraphrases that avoid the rule keywords) is the fairer test and shows the baseline's main weakness: "
        "lexical coverage. The optional zero-shot fallback improves it substantially.</span>", unsafe_allow_html=True)
    c1, c2 = st.columns([1.2, 1])
    with c1:
        labels = hy["labels"]
        short = [lab.split(" ")[0].replace("/", "") for lab in labels]
        fig = go.Figure(go.Heatmap(z=hy["confusion_matrix"], x=short, y=short, colorscale=SEQUENTIAL, text=hy["confusion_matrix"],
                                   texttemplate="%{text}", hovertemplate="true %{y}<br>predicted %{x}: %{z}<extra></extra>",
                                   showscale=False))
        fig.update_yaxes(autorange="reversed", title="true")
        fig.update_xaxes(title="predicted")
        fig_show(style_fig(fig, 420, "Confusion matrix - hybrid, held-out templates"))
    with c2:
        pc = pd.DataFrame(hy["per_class"]).T.reset_index().rename(columns={"index": "class"})
        st.markdown("**Precision / recall / F1 per class (held-out)**")
        st.dataframe(pc, hide_index=True, width="stretch", height=420, column_config={
            "precision": st.column_config.NumberColumn(format="%.2f"), "recall": st.column_config.NumberColumn(format="%.2f"),
            "f1-score": st.column_config.NumberColumn(format="%.2f"), "support": st.column_config.NumberColumn(format="%d")})
    st.markdown("**Error analysis**")
    e1, e2 = st.columns(2)
    with e1:
        st.markdown("<span class='rp-note'>Held-out template errors (hybrid)</span>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(ec["errors"])[["true", "predicted", "confidence", "text"]] if ec["errors"]
                     else pd.DataFrame({"note": ["no errors"]}),
                     hide_index=True, width="stretch", height=220)
    with e2:
        st.markdown("<span class='rp-note'>Challenge-set errors (hybrid)</span>", unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(ch["hybrid_errors"])[["true", "predicted", "confidence", "text"]], hide_index=True,
                     width="stretch", height=220)

    st.subheader("Sentiment")
    s1, s2 = st.columns([1, 1.3])
    with s1:
        rows = [{"model": "naive VADER (baseline)", "labelled acc": se["naive_vader"]["accuracy"],
                 "labelled macro-F1": se["naive_vader"]["macro_f1"], "challenge acc": ch["sentiment_naive_vader"]["accuracy"]},
                {"model": "finance-adapted VADER (default)", "labelled acc": se["finance_adapted"]["accuracy"],
                 "labelled macro-F1": se["finance_adapted"]["macro_f1"],
                 "challenge acc": ch["sentiment_finance_adapted"]["accuracy"]}]
        if tf.get("available"):
            rows.append({"model": "FinBERT (optional, precomputed)", "labelled acc": tf["finbert_sentiment_labelled"]["accuracy"],
                         "labelled macro-F1": tf["finbert_sentiment_labelled"]["macro_f1"],
                         "challenge acc": tf["finbert_sentiment_challenge"]["accuracy"]})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        st.markdown(f"<span class='rp-note'>Scores observed in [{se['score_range'][0]:+.2f}, {se['score_range'][1]:+.2f}]; "
                    f"labels use ±0.15 thresholds.</span>", unsafe_allow_html=True)
    with s2:
        st.markdown("**Where the finance adaptation changes the label**")
        st.dataframe(pd.DataFrame(se["disagreement_examples"])[["true", "naive_vader", "finance_adapted", "score", "text"]],
                     hide_index=True, width="stretch", height=250)

    st.subheader("Labelled validation dataset")
    ds = rep["dataset"]
    st.markdown(f"`{ds['path']}` - {ds['rows']} synthetic rows from {ds['templates']} hand-written templates "
                f"(news and social styles, fictional companies, fixed seed 42) + `challenge_set.csv` ({ch['rows']} rows).")
    st.dataframe(pd.DataFrame({"event_type": list(ds["event_counts"]), "rows": list(ds["event_counts"].values())}),
                 hide_index=True, width=420)
    st.subheader("Impact-scoring methodology")
    st.markdown("Impact (1-10) = clip(round(base severity + intensity + breadth + portfolio exposure + sentiment strength "
                "− non-adverse tone − uncertainty − source reliability), 1, 10). All weights live in `config/scoring.yaml`. "
                "Impact measures potential downside severity; it is **not** model confidence, a probability or a price forecast. "
                "There is no ground truth for impact, so it is validated by unit tests (bounds, monotonicity) and inspection.")
    st.subheader("Known limitations")
    st.markdown("""
- Synthetic, template-generated data; no real-market labels, so no claim of predictive power.
- Keyword rules + TF-IDF generalise poorly to unseen phrasing (challenge set); transformer fallback is optional and slower.
- Lexicon sentiment misses sarcasm and context ("record losses" vs "record revenue" is handled only by explicit phrase rules).
- Entity linking is dictionary-based over a fixed fictional universe; no coreference ("the lender") or unknown companies.
- One primary entity per record; multi-company stories are attributed to the first mention.
- Impact weights are expert-set, not calibrated to market moves.
""")


def page_data() -> None:
    sigs, report, df = current()
    st.title("Data & Methodology")
    synthetic_banner(df)
    st.subheader("Datasets")
    c1, c2 = st.columns([1, 1.3])
    with c1:
        with st.container(border=True):
            st.markdown("**Bundled synthetic sources**")
            news_on = st.checkbox(f"News-like articles · `{NEWS_FILE.name}`", value=ss.use_news)
            soc_on = st.checkbox(f"Social-media-like posts · `{SOCIAL_FILE.name}`", value=ss.use_social)
            if (news_on, soc_on) != (ss.use_news, ss.use_social):
                ss.use_news, ss.use_social = news_on, soc_on
                st.rerun()
            st.markdown("**Example files**")
            b1, b2 = st.columns(2)
            if b1.button("+ JSON upload example", width="stretch"):
                ss.extra = ss.extra + [((DATA_DIR / "upload_example.json").read_bytes(), "news", "upload_example.json")]
                st.rerun()
            if b2.button("+ Malformed CSV example", width="stretch", help="Shows validation errors and duplicates"):
                ss.extra = ss.extra + [((DATA_DIR / "malformed_example.csv").read_bytes(), "news", "malformed_example.csv")]
                st.rerun()
    with c2:
        with st.container(border=True):
            st.markdown("**Upload additional records (CSV or JSON)**")
            up = st.file_uploader("News columns: published_at, headline, body, source_name · Social columns: created_at, "
                                  "text, platform, handle", type=["csv", "json"], accept_multiple_files=False)
            stype = st.radio("Source type", ["auto-detect", "news", "social"], horizontal=True)
            u1, u2 = st.columns(2)
            if u1.button("Process upload", type="primary", disabled=up is None, width="stretch"):
                ss.extra = ss.extra + [(up.getvalue(), None if stype == "auto-detect" else stype, up.name)]
                st.success(f"Added {up.name}; the pipeline re-ran.")
                st.rerun()
            if u2.button("Reset to bundled data", width="stretch"):
                ss.extra, ss.use_news, ss.use_social = [], True, True
                load_signals.clear()
                st.rerun()
            if ss.extra:
                st.markdown("Extra files loaded: " + ", ".join(f"`{x[2]}`" for x in ss.extra))

    st.subheader("Ingestion status")
    k = st.columns(4)
    k[0].markdown(kpi("Rows read", str(report["rows_read"]), ", ".join(report["files"])), unsafe_allow_html=True)
    k[1].markdown(kpi("Accepted", str(report["accepted"]), "validated & normalised", "pos"), unsafe_allow_html=True)
    k[2].markdown(kpi("Rejected", str(report["rejected"]), "missing / invalid fields", "neg" if report["rejected"] else ""),
                  unsafe_allow_html=True)
    k[3].markdown(kpi("Duplicates removed", str(report["duplicates"]), "normalised-text match across sources"),
                  unsafe_allow_html=True)
    if report["issues"]:
        st.dataframe(pd.DataFrame(report["issues"]), hide_index=True, width="stretch")
    else:
        st.success("All rows passed validation.")

    st.subheader("Event replay")
    st.markdown("<span class='rp-note'>Replays the loaded records in timestamp order to simulate arrival. "
                "This is a replay of stored synthetic data, not a live feed.</span>", unsafe_allow_html=True)
    r1, r2 = st.columns([1, 3])
    n = r1.slider("Records to replay", 5, min(60, max(5, len(df))), min(20, max(5, len(df)))) if len(df) else 0
    speed = r1.select_slider("Speed", ["slow", "normal", "fast"], value="normal")
    if r1.button("▶ Start replay", disabled=df.empty):
        ph, prog = r2.empty(), r2.progress(0.0)
        rows = df.sort_values("timestamp").head(n)
        delay = {"slow": 0.6, "normal": 0.25, "fast": 0.05}[speed]
        for i in range(1, len(rows) + 1):
            cur = rows.iloc[:i]
            last = cur.iloc[-1]
            ph.markdown(f"<div class='rp-card'><p>{badge('REPLAY', 'info')} {badge(str(last['timestamp'])[:16])}"
                        f"{badge(last['source_type'], 'info')}{impact_badge(int(last['impact_score']), ss.threshold)}"
                        f"{sentiment_badge(last['sentiment_label'], last['sentiment_score'])}{badge(last['event_type'])}</p>"
                        f"<p>{last['text'][:220]}</p><p class='rp-note'>{i}/{len(rows)} replayed · "
                        f"{int((cur['impact_score'] > ss.threshold).sum())} high-impact so far</p></div>",
                        unsafe_allow_html=True)
            prog.progress(i / len(rows))
            time.sleep(delay)

    st.subheader("Optional public RSS source")
    st.markdown("<span class='rp-note'>Off by default; the demo needs no network. Use only feeds whose terms allow "
                "programmatic reading. Fetched items are labelled as real (not synthetic).</span>", unsafe_allow_html=True)
    f1, f2 = st.columns([3, 1])
    url = f1.text_input("Feed URL", placeholder="https://example.org/feed.xml", label_visibility="collapsed")
    if f2.button("Fetch feed", disabled=not url, width="stretch"):
        rows, err = fetch_rss(url)
        if err:
            st.warning(err)
        else:
            ss.extra = ss.extra + [(json.dumps(rows).encode(), "rss", f"rss:{url[:40]}")]
            st.success(f"Fetched {len(rows)} items.")
            st.rerun()

    st.subheader("Exports")
    x1, x2, x3 = st.columns(3)
    x1.download_button("All signals (JSON)", signals_to_json(to_signals(sigs)), "riskpulse_signals.json", "application/json",
                       width="stretch", disabled=not sigs)
    x2.download_button("All signals (CSV)", signals_to_csv(to_signals(sigs)), "riskpulse_signals.csv", "text/csv",
                       width="stretch", disabled=not sigs)
    x3.download_button("Ingestion report (JSON)", json.dumps(report, indent=2, default=str), "ingestion_report.json",
                       "application/json", width="stretch")

    st.subheader("Methodology")
    st.markdown("""
**Pipeline:** source adapters (news, social, optional RSS) → validation & normalisation (UTC timestamps, NFKC text,
size limits) → duplicate detection (normalised text; ignores `RT @handle:`, URLs, case) → deterministic UUIDv5 IDs →
entity & ticker linking → sentiment → event classification → impact scoring → validated `RiskSignal` (Pydantic) →
API / CSV / JSON → stress engine.

**Sentiment:** VADER + 116-term finance lexicon, 20 neutralised words, 9 multi-word finance phrase rules + hedge dampening (×0.85 per hedge word,
floor 0.6); company names are masked first so "Helix *Energy*" or "Granite *Trust*" carry no tone. Optional FinBERT.

**Event classification:** weighted keyword rules (auditable evidence) blended 45/55 with TF-IDF + logistic regression;
"Unclassified" when evidence is weak; "ambiguous" when the runner-up is within 75% of the winner. Optional zero-shot
BART-MNLI fallback for texts the baseline cannot classify.

**Stress engine:** first-order, additive factor P&L (duration, spread duration, beta, FX, delta, PD×LGD, liquidity
haircut) so every total reconciles exactly; see `docs/methodology.md`.
""")
    with st.expander("Source & scoring configuration (config/scoring.yaml)"):
        st.code((CONFIG_DIR / "scoring.yaml").read_text(encoding="utf-8"), language="yaml")
    with st.expander("Scenario assumptions (config/scenarios.yaml)"):
        st.code((CONFIG_DIR / "scenarios.yaml").read_text(encoding="utf-8"), language="yaml")


# ---------------------------------------------------------------- shell
ASSETS = Path(__file__).resolve().parent / "assets"
st.logo(str(ASSETS / "logo_wordmark.svg"), icon_image=str(ASSETS / "logo.svg"), size="large")

pages = [
    st.Page(page_overview, title="Executive Overview", icon=":material/dashboard:", url_path="overview", default=True),
    st.Page(page_explorer, title="Risk Signal Explorer", icon=":material/manage_search:", url_path="signals"),
    st.Page(page_events, title="Event Intelligence", icon=":material/insights:", url_path="events"),
    st.Page(page_stress, title="Portfolio Stress Lab", icon=":material/science:", url_path="stress-lab"),
    st.Page(page_evaluation, title="Model Evaluation", icon=":material/fact_check:", url_path="evaluation"),
    st.Page(page_data, title="Data & Methodology", icon=":material/database:", url_path="data"),
]
nav = st.navigation(pages)

with st.sidebar:
    ss.threshold = st.slider("High-impact threshold (impact >)", 1.0, 9.0, ss.threshold, 0.5,
                             help="Signals above this impact can auto-trigger a stress test.")
    tf_ok = transformer.available()
    ss.use_tf = st.toggle("Transformer models (FinBERT + zero-shot)", value=ss.use_tf and tf_ok, disabled=not tf_ok,
                          help="Optional local open models; slower (~1-3 min on CPU). "
                               + ("" if tf_ok else "Not installed: pip install -r requirements-transformers.txt"))
    st.markdown(f"<span class='rp-note'>RiskPulse AI v{__version__} · From unstructured information to actionable "
                "financial risk intelligence.<br>All bundled data is synthetic and fictional. Not investment advice.</span>",
                unsafe_allow_html=True)

nav.run()
