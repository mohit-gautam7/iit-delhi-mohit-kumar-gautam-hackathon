"""Render docs/architecture.png from the actual module layout. Run: python scripts/build_architecture.py"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BG, PANEL, PANEL2, BORDER = "#0B1220", "#18263B", "#111B2E", "#2B3A50"
ACCENT, TEAL, AMBER, TEXT, MUTED = "#4F7CFF", "#18A999", "#F4B942", "#F3F6FC", "#94A3B8"
plt.rcParams["font.family"] = ["Inter", "Segoe UI", "DejaVu Sans"]

fig = plt.figure(figsize=(16, 9), dpi=200)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, 160)
ax.set_ylim(0, 90)
ax.axis("off")
fig.patch.set_facecolor(BG)


def box(x, y, w, h, title, lines=(), edge=BORDER, fill=PANEL, title_color=TEXT, size=10.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.6", fc=fill, ec=edge, lw=1.4))
    ax.text(x + 1.4, y + h - 2.3, title, color=title_color, fontsize=size, fontweight="bold", va="top")
    for i, ln in enumerate(lines):
        ax.text(x + 1.4, y + h - 5.0 - i * 2.4, ln, color=MUTED, fontsize=7.9, va="top")


def group(x, y, w, h, label, color):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.6,rounding_size=2.2", fc=PANEL2, ec=color,
                                lw=1.2, ls=(0, (4, 3))))
    ax.text(x + 1.2, y + h + 1.4, label, color=color, fontsize=9.5, fontweight="bold")


def arrow(x1, y1, x2, y2, color=ACCENT, rad=0.0):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, color=color, lw=1.6,
                                 connectionstyle=f"arc3,rad={rad}"))


ax.text(4, 86, "RiskPulse AI - system architecture", color=TEXT, fontsize=17, fontweight="bold")
ax.text(4, 82.6, "From unstructured information to actionable financial risk intelligence  |  all modules live in "
        "src/riskpulse/", color=MUTED, fontsize=9.5)

# sources
group(3, 37, 25, 39, "1  DATA SOURCES", MUTED)
box(4.5, 64, 22, 10, "News-like articles", ["data/news_sample.csv (synthetic)", "headline, body, published_at"])
box(4.5, 52, 22, 10, "Social-media posts", ["data/social_sample.csv (synthetic)", "text, handle, likes, reposts"])
box(4.5, 40, 22, 10, "Uploads / optional RSS", ["CSV or JSON upload", "public feed, off by default"])
box(4.5, 12, 22, 14.5, "Synthetic portfolio", ["data/portfolio.csv", "37 positions, ~USD 1.02bn", "loans, bonds, equity,", "FX, derivatives"], edge=TEAL)

# ingestion
group(32, 46, 22, 30, "2  INGESTION", ACCENT)
box(33.5, 49, 19, 25, "Source adapters", ["ingestion/adapters.py", "", "schema validation", "UTC timestamps, NFKC",
                                             "duplicate detection", "UUIDv5 record IDs", "error report, never crash"],
    edge=ACCENT)

# nlp
group(58, 46, 44, 30, "3  NLP RISK ENGINE  (pipeline.py)", ACCENT)
box(59.5, 62, 20, 12, "Entity & ticker linking", ["nlp/entities.py", "alias + $TICKER dictionary"])
box(80.5, 62, 20, 12, "Sentiment  -1..+1", ["nlp/sentiment.py", "VADER + finance lexicon,", "hedging; FinBERT optional"])
box(59.5, 48, 20, 12, "Event classifier", ["nlp/classifier.py", "keyword rules + TF-IDF LR", "zero-shot BART optional"])
box(80.5, 48, 20, 12, "Impact score  1..10", ["scoring/impact.py", "severity, breadth, exposure,", "tone, uncertainty, source"])

# signal
box(106, 54, 22, 16, "RiskSignal (Pydantic)", ["schemas.py  - validated", "entity, ticker, sentiment,", "event, impact, confidence,",
                                                "explanation, source, time"], edge=AMBER, title_color=AMBER)

# outputs
group(132, 30, 25, 46, "5  CONSUMERS", TEAL)
box(133.5, 62, 22, 12, "Streamlit dashboard", ["app.py - 6 pages", "overview, explorer, events,", "stress lab, evaluation, data"],
    edge=TEAL)
box(133.5, 48, 22, 12, "FastAPI service", ["api.py  /analyze /signals", "/events/summary /portfolio", "/stress-test /health"],
    edge=TEAL)
box(133.5, 31.5, 22, 14.5, "Exports & reports", ["signals JSON / CSV", "stress JSON / CSV", "printable HTML report",
                                              "scripts/*.py CLI"], edge=TEAL)

# stress
group(32, 6, 96, 30, "4  PORTFOLIO STRESS ENGINE  (portfolio/)", TEAL)
box(33.5, 9, 26, 22, "Trigger", ["portfolio/stress.py", "", "impact > threshold (7)", "event type -> scenario",
                                    "analyst can override", "signal or scenario"], edge=TEAL)
box(63, 9, 28, 22, "Scenario library", ["config/scenarios.yaml", "", "10 event types -> 10 scenarios",
                                           "rates, spreads, equity, FX,", "oil, PD/LGD, liquidity,",
                                           "entity shock + contagion"], edge=TEAL)
box(94.5, 9, 31, 22, "Factor P&L engine", ["first-order, additive, reconciled", "", "bonds: -D x dy, -SD x ds",
                                              "loans: EAD x dPD x LGD", "equity: beta x move; FX; delta",
                                              "liquidity haircut post-shock"], edge=TEAL)

# evaluation
box(106, 73, 22, 9, "Evaluation", ["evaluation/metrics.py - held-out,", "CV, challenge set"], edge=BORDER, size=9.5)

# arrows
arrow(27, 69, 33.3, 64)
arrow(27, 57, 33.3, 60)
arrow(27, 45, 33.3, 55)
arrow(52.8, 61, 59.3, 66)
arrow(79.6, 68, 80.4, 68)
arrow(69.5, 61.8, 69.5, 60.2)
arrow(79.6, 54, 80.4, 54)
arrow(100.8, 60, 105.8, 61)
arrow(128.2, 64, 133.3, 68)
arrow(128.2, 60, 133.3, 54)
arrow(117, 53.8, 46, 31.3, TEAL, rad=-0.08)
arrow(59.7, 20, 62.8, 20, TEAL)
arrow(91.2, 20, 94.3, 20, TEAL)
arrow(125.8, 22, 133.3, 39, TEAL)
ax.plot([15.5, 15.5, 110], [11.6, 3.6, 3.6], color=TEAL, lw=1.6)  # portfolio -> P&L engine, routed under the boxes
arrow(110, 3.5, 110, 8.6, TEAL)
ax.text(88, 40.5, "high-impact signal triggers a scenario", color=TEAL, fontsize=8.5, style="italic")
ax.text(157, 1.2, "Bundled data is synthetic and fictional. Offline by default; transformer models and RSS are optional.",
        color=MUTED, fontsize=8, ha="right")

out = ROOT / "docs"
fig.savefig(out / "architecture.png", facecolor=BG)
print("wrote docs/architecture.png")
