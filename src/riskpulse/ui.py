"""RiskPulse AI design system for the Streamlit dashboard: tokens, CSS, Plotly template, small components."""
from __future__ import annotations

import html

import plotly.graph_objects as go
import plotly.io as pio

# ---- design tokens (single source of truth; mirrored in docs/slides) ----
C = {
    "bg": "#0B1220", "bg2": "#111B2E", "panel": "#18263B", "accent": "#4F7CFF", "teal": "#18A999",
    "pos": "#22C55E", "neg": "#F05260", "warn": "#F4B942", "text": "#F3F6FC", "muted": "#94A3B8",
    "border": "#2B3A50", "light": "#F5F7FB",
}
# Categorical order checked for colour-blind separation and contrast on the dark surface.
CATEGORICAL = ["#4F7CFF", "#B8863A", "#18A999", "#8F6FE8"]
SENTIMENT_COLORS = {"Positive": C["pos"], "Neutral": C["muted"], "Negative": C["neg"]}
SOURCE_COLORS = {"news": C["accent"], "social": C["teal"], "rss": "#B8863A"}
SEQUENTIAL = [[0, "#18263B"], [0.5, "#4F7CFF"], [1, "#C7D5FF"]]

LOGO_SVG = """<svg width="34" height="34" viewBox="0 0 34 34" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="RiskPulse AI logo">
<rect x="1" y="1" width="32" height="32" rx="8" fill="#18263B" stroke="#2B3A50"/>
<polyline points="5,19 11,19 14,11 18,25 21,15 23,19 29,19" fill="none" stroke="#4F7CFF" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
<circle cx="29" cy="19" r="2.2" fill="#18A999"/></svg>"""

CSS = f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {{ --rp-bg:{C['bg']}; --rp-bg2:{C['bg2']}; --rp-panel:{C['panel']}; --rp-accent:{C['accent']};
  --rp-teal:{C['teal']}; --rp-pos:{C['pos']}; --rp-neg:{C['neg']}; --rp-warn:{C['warn']};
  --rp-text:{C['text']}; --rp-muted:{C['muted']}; --rp-border:{C['border']}; }}
html, body, [class*="css"], .stMarkdown, .stDataFrame, button, input, textarea, select {{
  font-family: Inter, "Segoe UI", system-ui, -apple-system, Roboto, Arial, sans-serif; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 3rem; max-width: 1380px; }}
h1, h2, h3 {{ letter-spacing: -0.01em; }}
h1 {{ font-size: 1.65rem !important; font-weight: 700 !important; }}
h3 {{ font-size: 1.05rem !important; font-weight: 600 !important; color: var(--rp-text); }}
[data-testid="stSidebar"] {{ background: var(--rp-bg2); border-right: 1px solid var(--rp-border); }}
.rp-brand {{ display:flex; align-items:center; gap:10px; margin: 0 0 6px 0; }}
.rp-brand b {{ font-size: 1.05rem; color: var(--rp-text); }}
.rp-brand span {{ display:block; font-size: .72rem; color: var(--rp-muted); }}
.rp-kpi {{ background: var(--rp-panel); border: 1px solid var(--rp-border); border-radius: 10px; padding: 12px 14px; min-height: 92px; }}
.rp-kpi .l {{ font-size: .74rem; text-transform: uppercase; letter-spacing: .05em; color: var(--rp-muted); }}
.rp-kpi .v {{ font-size: 1.45rem; font-weight: 700; color: var(--rp-text); margin-top: 4px; font-variant-numeric: tabular-nums; }}
.rp-kpi .s {{ font-size: .78rem; color: var(--rp-muted); margin-top: 2px; }}
.rp-kpi .v.neg {{ color: var(--rp-neg); }} .rp-kpi .v.pos {{ color: var(--rp-pos); }}
.rp-badge {{ display:inline-block; padding: 2px 8px; border-radius: 999px; font-size: .72rem; font-weight: 600;
  border: 1px solid var(--rp-border); background: var(--rp-bg2); color: var(--rp-text); margin-right: 4px; }}
.rp-badge.neg {{ color: var(--rp-neg); border-color: rgba(240,82,96,.45); }}
.rp-badge.pos {{ color: var(--rp-pos); border-color: rgba(34,197,94,.45); }}
.rp-badge.warn {{ color: var(--rp-warn); border-color: rgba(244,185,66,.5); }}
.rp-badge.info {{ color: var(--rp-accent); border-color: rgba(79,124,255,.5); }}
.rp-note {{ font-size: .8rem; color: var(--rp-muted); }}
.rp-card {{ background: var(--rp-panel); border: 1px solid var(--rp-border); border-radius: 10px; padding: 14px 16px; }}
.rp-card p {{ margin: .25rem 0; }}
.rp-evidence {{ background: var(--rp-bg); border: 1px solid var(--rp-border); border-radius: 8px; padding: 10px 12px;
  font-size: .9rem; color: var(--rp-text); }}
div[data-testid="stMetric"] {{ background: var(--rp-panel); border: 1px solid var(--rp-border); border-radius: 10px; padding: 10px 14px; }}
</style>
"""

# ---- Plotly template ----
pio.templates["riskpulse"] = go.layout.Template(layout=go.Layout(
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, Segoe UI, Arial, sans-serif", color=C["text"], size=12),
    colorway=CATEGORICAL, margin=dict(l=10, r=10, t=36, b=10),
    title=dict(font=dict(size=14, color=C["text"]), x=0, xanchor="left"),
    xaxis=dict(gridcolor="rgba(43,58,80,.55)", zerolinecolor=C["border"], linecolor=C["border"],
               tickfont=dict(color=C["muted"]), title=dict(font=dict(color=C["muted"]))),
    yaxis=dict(gridcolor="rgba(43,58,80,.55)", zerolinecolor=C["border"], linecolor=C["border"],
               tickfont=dict(color=C["muted"]), title=dict(font=dict(color=C["muted"]))),
    legend=dict(font=dict(color=C["muted"]), orientation="h", y=1.08, x=0),
    hoverlabel=dict(bgcolor=C["panel"], bordercolor=C["border"], font=dict(color=C["text"])),
    bargap=0.25,
))
pio.templates.default = "riskpulse"


def usd(v: float, compact: bool = True) -> str:
    sign = "-" if v < 0 else ""
    a = abs(v)
    if compact and a >= 1e9:
        return f"{sign}${a / 1e9:,.2f}bn"
    if compact and a >= 1e6:
        return f"{sign}${a / 1e6:,.2f}m"
    return f"{sign}${a:,.0f}"


def kpi(label: str, value: str, sub: str = "", tone: str = "") -> str:
    return (f"<div class='rp-kpi'><div class='l'>{html.escape(label)}</div>"
            f"<div class='v {tone}'>{html.escape(value)}</div><div class='s'>{html.escape(sub)}</div></div>")


def badge(text: str, tone: str = "") -> str:
    return f"<span class='rp-badge {tone}'>{html.escape(str(text))}</span>"


def sentiment_badge(label: str, score: float) -> str:
    tone = {"Positive": "pos", "Negative": "neg"}.get(label, "")
    arrow = {"Positive": "▲", "Negative": "▼"}.get(label, "■")
    return badge(f"{arrow} {label} {score:+.2f}", tone)


def impact_badge(impact: int, threshold: float = 7) -> str:
    tone = "neg" if impact > threshold else ("warn" if impact >= 5 else "")
    return badge(f"Impact {impact}/10", tone)


def style_fig(fig: go.Figure, height: int = 320, title: str | None = None) -> go.Figure:
    fig.update_layout(height=height, template="riskpulse")
    fig.update_traces(cliponaxis=False, selector=dict(type="bar"))  # outside labels never clip
    fig.update_traces(cliponaxis=False, selector=dict(type="waterfall"))
    bars = [t for t in fig.data if t.type == "bar" and t.textposition == "outside"]
    if bars:  # headroom so outside labels fit inside the plot area
        horiz = bars[0].orientation == "h"
        vals = [float(v) for t in bars if (t.x if horiz else t.y) is not None for v in (t.x if horiz else t.y) if v is not None]
        lo, hi = min(0, min(vals)), max(0, max(vals))
        pad = (hi - lo) * 0.18 or 1
        fig.update_layout({"xaxis" if horiz else "yaxis": dict(range=[lo - (pad if lo < 0 else 0), hi + (pad if hi > 0 else 0)])})
    if title:
        fig.update_layout(title=title)
    return fig
