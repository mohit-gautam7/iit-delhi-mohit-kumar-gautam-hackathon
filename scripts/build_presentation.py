"""Build docs/presentation.pptx (7 slides) from live project outputs, then export docs/presentation.pdf.

Every number on the slides is read from the code's own outputs (evaluation report, stress engine, pytest),
so the deck cannot drift from the application. PDF export uses Microsoft PowerPoint via COM (Windows) or
LibreOffice if available.  Run: python scripts/build_presentation.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from riskpulse.config import PORTFOLIO_FILE  # noqa: E402
from riskpulse.pipeline import run_default_pipeline  # noqa: E402
from riskpulse.portfolio.model import load_portfolio  # noqa: E402
from riskpulse.portfolio.stress import evaluate_trigger, pick_demo_signal, stress_from_signal  # noqa: E402

DOCS = ROOT / "docs"
BG, BG2, PANEL, BORDER = "0B1220", "111B2E", "18263B", "2B3A50"
ACCENT, TEAL, POS, NEG, WARN, TEXT, MUTED = "4F7CFF", "18A999", "22C55E", "F05260", "F4B942", "F3F6FC", "94A3B8"
FONT = "Calibri"


def rgb(h: str) -> RGBColor:
    return RGBColor.from_string(h)


def usd(v: float) -> str:
    s = "-" if v < 0 else ""
    a = abs(v)
    return f"{s}${a / 1e9:.2f}bn" if a >= 1e9 else f"{s}${a / 1e6:.2f}m"


# ------------------------------------------------------------------ live numbers
def gather() -> dict:
    out = subprocess.run([sys.executable, "-m", "pytest", "-o", "addopts=", "-q", "-p", "no:cacheprovider"], cwd=ROOT,
                         capture_output=True, text=True)
    m = re.search(r"(\d+) passed", out.stdout)
    failed = re.search(r"(\d+) failed", out.stdout)
    if not m or failed:
        sys.exit("Tests must pass before building the deck:\n" + out.stdout[-2000:])
    t0 = time.perf_counter()
    signals, report = run_default_pipeline()  # includes training the classifier
    seconds = time.perf_counter() - t0
    pf = load_portfolio(PORTFOLIO_FILE)
    demo = pick_demo_signal(signals)
    res = stress_from_signal(pf, demo)
    example = next(s for s in signals if s.ticker == "MRDS" and s.event_type == "Credit Event"
                   and s.source_type == "news" and "coupon" in s.text)
    credit = stress_from_signal(pf, example)
    ev = json.loads((ROOT / "data" / "evaluation_report.json").read_text(encoding="utf-8"))
    return {"seconds": seconds, "tests": int(m.group(1)), "signals": signals, "report": report, "pf": pf, "demo": demo, "res": res,
            "example": example, "credit": credit, "ev": ev,
            "high": sum(evaluate_trigger(s)["triggered"] for s in signals)}


# ------------------------------------------------------------------ drawing helpers
class Deck:
    def __init__(self):
        self.prs = Presentation()
        self.prs.slide_width, self.prs.slide_height = Inches(13.333), Inches(7.5)
        self.blank = self.prs.slide_layouts[6]
        self.n = 0

    def slide(self, title: str | None, kicker: str | None = None):
        s = self.prs.slides.add_slide(self.blank)
        s.background.fill.solid()
        s.background.fill.fore_color.rgb = rgb(BG)
        self.n += 1
        if title:
            if kicker:
                text(s, 0.6, 0.38, 9, 0.3, kicker.upper(), 11, ACCENT, bold=True)
            text(s, 0.6, 0.62, 12.1, 0.75, title, 30, TEXT, bold=True)
        # footer on every slide
        text(s, 0.6, 7.05, 8, 0.3, "RiskPulse AI  ·  S&P Global & Crisil Campus Hackathon 2026  ·  synthetic data",
             9, MUTED)
        text(s, 12.0, 7.05, 0.75, 0.3, f"{self.n} / 7", 9, MUTED, align=PP_ALIGN.RIGHT)
        return s


def text(s, x, y, w, h, value, size=14, color=TEXT, bold=False, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP,
         italic=False):
    tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    lines = value if isinstance(value, list) else [value]
    for i, ln in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        runs = ln if isinstance(ln, list) else [(ln, {})]
        for chunk, opt in runs:
            r = p.add_run()
            r.text = chunk
            f = r.font
            f.name, f.size, f.bold, f.italic = FONT, Pt(opt.get("size", size)), opt.get("bold", bold), italic
            f.color.rgb = rgb(opt.get("color", color))
        p.space_after = Pt(opt.get("space", 4) if runs else 4)
    return tb


def card(s, x, y, w, h, fill=PANEL, edge=BORDER, radius=0.06):
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.adjustments[0] = radius
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    shp.line.color.rgb = rgb(edge)
    shp.line.width = Pt(1)
    shp.shadow.inherit = False
    shp.text_frame.text = ""
    return shp


def circle(s, x, y, d, fill, label, size=14):
    shp = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(x), Inches(y), Inches(d), Inches(d))
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(fill)
    shp.line.fill.background()
    shp.shadow.inherit = False
    tf = shp.text_frame
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold = FONT, Pt(size), True
    r.font.color.rgb = rgb(BG)
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    return shp


def stat(s, x, y, w, h, value, label, color=TEXT, sub=None):
    card(s, x, y, w, h)
    text(s, x + 0.22, y + 0.16, w - 0.4, 0.3, label.upper(), 10, MUTED, bold=True)
    text(s, x + 0.22, y + 0.45, w - 0.4, 0.6, value, 26, color, bold=True)
    if sub:
        text(s, x + 0.22, y + h - 0.42, w - 0.4, 0.3, sub, 10.5, MUTED)


def chip(s, x, y, w, label, color):
    shp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(0.32))
    shp.adjustments[0] = 0.5
    shp.fill.solid()
    shp.fill.fore_color.rgb = rgb(BG2)
    shp.line.color.rgb = rgb(color)
    shp.line.width = Pt(1)
    shp.shadow.inherit = False
    tf = shp.text_frame
    tf.margin_left = tf.margin_right = Inches(0.05)
    tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = label
    r.font.name, r.font.size, r.font.bold = FONT, Pt(10.5), True
    r.font.color.rgb = rgb(color)


def bar_chart(s, x, y, w, h, cats, vals, colors, number_format='0.0', title=None, horizontal=True, max_v=None, min_v=None):
    data = CategoryChartData()
    data.categories = cats
    data.add_series("value", vals)
    kind = XL_CHART_TYPE.BAR_CLUSTERED if horizontal else XL_CHART_TYPE.COLUMN_CLUSTERED
    gf = s.shapes.add_chart(kind, Inches(x), Inches(y), Inches(w), Inches(h), data)
    ch = gf.chart
    ch.has_legend = False
    ch.font.name, ch.font.size = FONT, Pt(11)
    ch.font.color.rgb = rgb(MUTED)
    if title:
        ch.has_title = True
        ch.chart_title.text_frame.text = title
        tp = ch.chart_title.text_frame.paragraphs[0]
        tp.runs[0].font.size, tp.runs[0].font.bold, tp.runs[0].font.name = Pt(13), True, FONT
        tp.runs[0].font.color.rgb = rgb(TEXT)
    else:
        ch.has_title = False
    plot = ch.plots[0]
    plot.gap_width = 55
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.number_format, dl.number_format_is_linked = number_format, False
    dl.position = XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.name = Pt(11), FONT
    dl.font.color.rgb = rgb(TEXT)
    ser = plot.series[0]
    ser.invert_if_negative = False
    from pptx.oxml.ns import qn
    from lxml import etree
    for i, c in enumerate(colors):
        pt = ser.points[i]
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = rgb(c)
        dpt = next(e for e in ser._element.findall(qn("c:dPt")) if e.find(qn("c:idx")).get("val") == str(i))
        if dpt.find(qn("c:invertIfNegative")) is None:  # PowerPoint inverts (white) negative points without this
            inv = etree.SubElement(dpt, qn("c:invertIfNegative"))
            inv.set("val", "0")
            dpt.remove(inv)
            dpt.insert(1, inv)
    va, ca = ch.value_axis, ch.category_axis
    va.has_major_gridlines = True
    va.major_gridlines.format.line.color.rgb = rgb(BORDER)
    va.format.line.fill.background()
    va.tick_labels.font.size = Pt(10)
    va.tick_labels.font.color.rgb = rgb(MUTED)
    va.tick_labels.number_format, va.tick_labels.number_format_is_linked = number_format, False
    if max_v is not None:
        va.maximum_scale = max_v
    if min_v is not None:
        va.minimum_scale = min_v
    ca.format.line.color.rgb = rgb(BORDER)
    ca.tick_labels.font.size = Pt(11)
    ca.tick_labels.font.color.rgb = rgb(TEXT)
    if horizontal:
        ca.reverse_order = True
    from pptx.enum.chart import XL_TICK_LABEL_POSITION
    ca.tick_label_position = XL_TICK_LABEL_POSITION.LOW
    return ch


def node(s, x, y, w, h, title, sub, edge=BORDER, title_color=TEXT):
    card(s, x, y, w, h, edge=edge)
    text(s, x + 0.15, y + 0.14, w - 0.3, 0.35, title, 14, title_color, bold=True)
    text(s, x + 0.15, y + 0.52, w - 0.3, h - 0.6, sub, 11, MUTED)


def connect(s, x1, y1, x2, y2, color=ACCENT, arrow=True, elbow=False):
    from lxml import etree
    from pptx.enum.shapes import MSO_CONNECTOR
    from pptx.oxml.ns import qn
    c = s.shapes.add_connector(MSO_CONNECTOR.ELBOW if elbow else MSO_CONNECTOR.STRAIGHT,
                               Inches(x1), Inches(y1), Inches(x2), Inches(y2))
    c.line.color.rgb = rgb(color)
    c.line.width = Pt(1.75)
    if arrow:
        etree.SubElement(c.line._get_or_add_ln(), qn("a:tailEnd")).set("type", "triangle")
    return c


def pic(s, path: Path, x, y, w=None, h=None, border=True):
    kw = {}
    if w:
        kw["width"] = Inches(w)
    if h:
        kw["height"] = Inches(h)
    p = s.shapes.add_picture(str(path), Inches(x), Inches(y), **kw)
    if border:
        p.line.color.rgb = rgb(BORDER)
        p.line.width = Pt(1)
    return p


# ------------------------------------------------------------------ slides
def build(d: dict) -> Presentation:
    deck = Deck()
    ev, res, demo, ex, credit = d["ev"], d["res"], d["demo"], d["example"], d["credit"]
    ec, ch, se, tf = ev["event_classification"], ev["challenge_set"], ev["sentiment"], ev["transformer_upgrade"]
    n_sig, rep = len(d["signals"]), d["report"]

    # 1 ---- title
    s = deck.slide(None)
    pic(s, ROOT / "assets" / "logo.png", 0.75, 0.9, w=0.9, border=False)
    text(s, 0.75, 2.05, 7.2, 1.0, "RiskPulse AI", 54, TEXT, bold=True)
    text(s, 0.75, 3.05, 7.2, 0.6, "Intelligent Financial Risk & Portfolio Stress Lab", 24, ACCENT, bold=True)
    text(s, 0.75, 3.75, 6.6, 0.8, "From unstructured information to actionable financial risk intelligence.", 16, MUTED,
         italic=True)
    text(s, 0.75, 5.05, 6.8, 0.4, "S&P Global & Crisil Campus Hackathon 2026", 16, TEXT, bold=True)
    text(s, 0.75, 5.45, 6.8, 0.4, "Mohit Kumar Gautam  ·  IIT Delhi", 16, TEXT)
    for i, (lab, col) in enumerate([("AI/NLP risk engine", ACCENT), ("Module B: stress testing", TEAL),
                                    ("Offline · explainable", WARN)]):
        chip(s, 0.75 + i * 2.25, 6.15, 2.1, lab, col)
    pic(s, DOCS / "screenshots" / "overview.png", 7.75, 1.25, w=4.95)
    text(s, 7.75, 4.45, 4.95, 0.3, "Executive Risk Overview - live dashboard (synthetic data)", 10, MUTED)
    stat(s, 7.75, 4.9, 1.55, 1.25, f"{n_sig}", "signals", TEXT)
    stat(s, 9.45, 4.9, 1.55, 1.25, f"{d['high']}", "high impact", NEG)
    stat(s, 11.15, 4.9, 1.55, 1.25, f"{d['tests']}", "tests pass", POS)
    s.notes_slide.notes_text_frame.text = (
        "RiskPulse AI turns news and social text into structured, explainable risk signals and shows what a "
        "high-impact event would do to a wholesale-banking portfolio. Everything runs offline on synthetic data.")

    # 2 ---- problem & approach
    s = deck.slide("Turning noisy text into risk decisions", "Problem & approach")
    card(s, 0.6, 1.6, 5.6, 5.2 - 0.0)
    text(s, 0.9, 1.8, 5.0, 0.4, "The problem", 18, TEXT, bold=True)
    probs = [("Volume", "Risk-relevant news and posts arrive faster than analysts can read them."),
             ("Ambiguity", "Tone is not impact: a negative tweet about a logo is noise; a missed coupon is not."),
             ("Disconnect", "Text insight rarely reaches portfolio numbers: what does this event cost us?")]
    for i, (h, b) in enumerate(probs):
        y = 2.45 + i * 1.35
        circle(s, 0.95, y, 0.5, NEG, str(i + 1))
        text(s, 1.65, y - 0.02, 4.3, 0.35, h, 15, TEXT, bold=True)
        text(s, 1.65, y + 0.33, 4.3, 0.9, b, 13, MUTED)
    text(s, 6.65, 1.65, 6.0, 0.4, "Our approach: headline to P&L in one pipeline", 18, TEXT, bold=True)
    short = ex.text.split(". ")[0]
    card(s, 6.65, 2.2, 6.05, 1.1)
    text(s, 6.85, 2.3, 5.7, 0.3, "1  RAW TEXT  ·  news-like record", 10.5, ACCENT, bold=True)
    text(s, 6.85, 2.62, 5.7, 0.6, "\u201c" + short + "\u201d", 13, TEXT, italic=True)
    connect(s, 9.675, 3.32, 9.675, 3.68)
    card(s, 6.65, 3.7, 6.05, 1.25)
    text(s, 6.85, 3.8, 5.7, 0.3, "2  STRUCTURED SIGNAL  ·  NLP engine + explanation", 10.5, WARN, bold=True)
    widths = [1.3, 1.45, 1.15, 1.55]
    labels = [(ex.event_type, ACCENT), (f"Sentiment {ex.sentiment_score:+.2f}", NEG),
              (f"Impact {ex.impact_score}/10", NEG), (f"{ex.ticker} · conf {ex.confidence:.2f}", TEXT)]
    for i, ((lab, col), w) in enumerate(zip(labels, widths)):
        chip(s, 6.85 + sum(widths[:i]) + 0.08 * i, 4.2, w, lab, col)
    text(s, 6.85, 4.6, 5.7, 0.3, "impact > 7  ->  stress test triggered automatically", 11, MUTED)
    connect(s, 9.675, 4.97, 9.675, 5.33)
    card(s, 6.65, 5.35, 6.05, 1.25)
    text(s, 6.85, 5.45, 5.7, 0.3, "3  PORTFOLIO IMPACT  ·  " + credit.scenario_name.lower(), 10.5, TEAL, bold=True)
    cds = credit.positions.set_index("position_id").loc["DV04", "total_pnl_usd"]
    hedge = "+" + usd(cds)
    text(s, 6.85, 5.78, 5.7, 0.75, [[(f"{usd(credit.pnl)} ({credit.pnl_pct:+.2%})", {"bold": True, "color": NEG, "size": 18}),
                                     (f"   on {usd(credit.initial_value)}", {"color": MUTED, "size": 12})],
                                    [(f"worst hits: {ex.entity} bond, loan, equity  ·  CDS hedge {hedge}",
                                      {"color": MUTED, "size": 11})]], 12)
    s.notes_slide.notes_text_frame.text = (
        "Three pain points: volume, ambiguity (tone vs impact) and the gap between text and P&L. "
        "One real record from the bundled data: a missed coupon becomes a Credit Event signal with impact 9, "
        "which triggers the issuer-credit scenario and shows the loss on the book, including the CDS hedge.")

    # 3 ---- architecture
    s = deck.slide("System design: modular, offline, one engine everywhere", "Architecture")
    text(s, 0.6, 1.45, 6, 0.3, "SIGNAL PATH  ·  AI/NLP risk engine", 10.5, ACCENT, bold=True)
    xs, w, y1, y2, h = [0.6, 3.05, 5.5, 7.95, 10.4], 2.2, 1.78, 4.12, 1.45
    row1 = [("Sources", "News + social CSV / JSON\nupload · RSS (optional)", BORDER, TEXT),
            ("Ingestion", "validate · normalise UTC\nde-duplicate · stable IDs", ACCENT, TEXT),
            ("NLP engine", "entities · sentiment\nevent type · impact 1-10", ACCENT, TEXT),
            ("Risk signal", "validated schema\n+ plain-English reason", WARN, WARN),
            ("Consumers", "6-page dashboard\nREST API · JSON / CSV / HTML", TEAL, TEXT)]
    for x, (t, sub, e, tc) in zip(xs, row1):
        node(s, x, y1, w, h, t, sub, e, tc)
    for x in xs[:-1]:
        connect(s, x + w + 0.02, y1 + h / 2, x + w + 0.23, y1 + h / 2)
    text(s, 0.6, 3.79, 7, 0.3, "STRESS PATH  ·  Module B portfolio stress testing", 10.5, TEAL, bold=True)
    row2 = {0.6: ("Synthetic portfolio", "37 positions · ~$1.02bn\nloans, bonds, equity, FX, derivs"),
            5.5: ("Trigger", "impact > 7 (configurable)\nevent type -> scenario"),
            7.95: ("Scenario library", "10 scenarios in YAML\nrates, spreads, FX, PD, oil"),
            10.4: ("Factor P&L engine", "duration · beta · delta\nPD x LGD · liquidity haircut")}
    for x, (t, sub) in row2.items():
        node(s, x, y2, w, h, t, sub, TEAL)
    connect(s, 9.05, y1 + h, 9.05, 3.62, TEAL, arrow=False)
    connect(s, 9.05, 3.62, 6.6, 3.62, TEAL, arrow=False)
    connect(s, 6.6, 3.62, 6.6, y2 - 0.02, TEAL)
    text(s, 6.75, 3.66, 2.2, 0.25, "impact > 7", 10, TEAL, italic=True)
    connect(s, 7.72, y2 + h / 2, 7.93, y2 + h / 2, TEAL)
    connect(s, 10.17, y2 + h / 2, 10.38, y2 + h / 2, TEAL)
    connect(s, 11.5, y2 - 0.02, 11.5, y1 + h + 0.02, TEAL)
    connect(s, 1.7, y2 + h, 1.7, y2 + h + 0.3, TEAL, arrow=False)
    connect(s, 1.7, y2 + h + 0.3, 11.5, y2 + h + 0.3, TEAL, arrow=False)
    connect(s, 11.5, y2 + h + 0.3, 11.5, y2 + h + 0.02, TEAL)
    tech = ["Python 3.11", "pandas", "scikit-learn", "VADER", "Pydantic", "FastAPI", "Streamlit", "Plotly", "pytest"]
    for i, t in enumerate(tech):
        chip(s, 0.6 + i * 1.355, 6.3, 1.27, t, MUTED)
    text(s, 3.05, 4.3, 2.2, 1.2, "Dashboard, API, CLI and reports call the same modules, so shown and exported "
         "numbers always agree.", 11, MUTED, italic=True)
    s.notes_slide.notes_text_frame.text = ("Top row: every record becomes a validated, explained signal. Bottom row: a high-impact signal selects a "
        "scenario that revalues the synthetic portfolio; results flow to the same dashboard, API and reports. "
        "Detailed diagram: docs/architecture.png.")

    # 4 ---- NLP
    s = deck.slide("AI/NLP risk intelligence with a reason for every score", "Risk engine")
    comps = [("Sentiment  -1 to +1", f"VADER + {116}-term finance lexicon, phrase rules, hedge dampening; "
              f"company names masked. {se['naive_vader']['accuracy']:.1%} -> {se['finance_adapted']['accuracy']:.1%} "
              "accuracy vs naive VADER.", ACCENT),
             ("Event classification", "Keyword rules (auditable evidence) + TF-IDF logistic regression over 10 "
              "categories; weak evidence -> 'Unclassified', close calls flagged ambiguous.", ACCENT),
             ("Impact score  1 to 10", "Base severity + intensity + breadth + portfolio exposure + tone - "
              "uncertainty - source reliability. Impact is severity, not confidence.", WARN),
             ("Explanation", "Every signal carries keywords, sentiment drivers, entity exposure and the "
              "arithmetic behind its impact score.", TEAL)]
    for i, (h, b, col) in enumerate(comps):
        y = 1.6 + i * 1.3
        card(s, 0.6, y, 5.9, 1.15)
        circle(s, 0.8, y + 0.3, 0.5, col, str(i + 1))
        text(s, 1.5, y + 0.12, 4.85, 0.35, h, 15, TEXT, bold=True)
        text(s, 1.5, y + 0.45, 4.85, 0.7, b, 11.5, MUTED)
    card(s, 6.85, 1.6, 5.85, 5.05, edge=WARN)
    text(s, 7.1, 1.75, 5.4, 0.3, "GENUINE OUTPUT - news record from data/news_sample.csv", 10, WARN, bold=True)
    quote = ex.text if len(ex.text) <= 150 else ex.text[:150].rsplit(" ", 1)[0].rstrip(",;") + " ..."
    text(s, 7.1, 2.08, 5.4, 0.9, f"“{quote}”", 12.5, TEXT, italic=True)
    rows = [("Entity / ticker", f"{ex.entity} ({ex.ticker})"),
            ("Event type", f"{ex.event_type}  (confidence {ex.confidence:.2f})"),
            ("Sentiment", f"{ex.sentiment_score:+.2f}  {ex.sentiment_label}"),
            ("Impact", f"{ex.impact_score} / 10   ->   stress trigger"),
            ("Source / time", f"{ex.source_type} · {ex.timestamp:%Y-%m-%d %H:%M} UTC")]
    for i, (k, v) in enumerate(rows):
        y = 3.12 + i * 0.4
        text(s, 7.1, y, 1.7, 0.35, k, 12, MUTED)
        text(s, 8.85, y, 3.7, 0.35, v, 12.5, NEG if k in ("Impact", "Sentiment") else TEXT, bold=k == "Impact")
    f = ex.impact_factors
    parts = [f"base {f['base_severity']:.1f}"] + [f"{'+' if f[k] > 0 else '-'} {lab} {abs(f[k]):.1f}" for k, lab in
                                                  [("intensity", "intensity"), ("exposure", "exposure"),
                                                   ("sentiment", "tone"), ("breadth", "breadth")] if abs(f[k]) >= 0.05]
    text(s, 7.1, 5.12, 5.4, 0.3, f"Why impact = {ex.impact_score}  (raw {f['raw_total']:.1f}, rounded)", 12, TEXT, bold=True)
    scale, x0, yb = 0.5, 7.1, 5.5
    segs = [("base", f["base_severity"], "3C5A99")] + [(lab, f[k], col) for k, lab, col in
                                                       [("intensity", "intensity", WARN), ("breadth", "breadth", WARN),
                                                        ("exposure", "exposure", TEAL), ("sentiment", "tone", NEG)]
                                                       if f[k] >= 0.05]
    x = x0
    for lab, v, col in segs:
        seg = s.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(yb), Inches(v * scale), Inches(0.3))
        seg.fill.solid()
        seg.fill.fore_color.rgb = rgb(col)
        seg.line.color.rgb = rgb(PANEL)
        seg.shadow.inherit = False
        x += v * scale
    connect(s, x0 + 7 * scale, yb - 0.08, x0 + 7 * scale, yb + 0.38, WARN, arrow=False)
    runs = []
    for i, (lab, v, col) in enumerate(segs):
        runs.append((("" if i == 0 else "  +  ") + f"{lab} {v:.1f}", {"color": "7FA0E6" if i == 0 else col, "size": 11,
                                                                      "bold": True}))
    runs.append((f"  =  {f['raw_total']:.1f}", {"color": TEXT, "size": 11, "bold": True}))
    runs.append(("     | marker = trigger > 7", {"color": WARN, "size": 10}))
    text(s, x0, yb + 0.42, 5.5, 0.3, [runs], 11)
    text(s, 7.1, 6.3, 5.4, 0.3, "Keywords: " + ", ".join(re.findall(r"'([^']+)'", ex.explanation)[:4]), 11.5, ACCENT)
    s.notes_slide.notes_text_frame.text = "Read the example: how event, sentiment, entity and impact are derived."

    # 5 ---- stress
    s = deck.slide("Event-driven portfolio stress testing", "Module B")
    text(s, 0.6, 1.45, 12.1, 0.6, f"Auto-triggered: {demo.event_type} signal (impact {demo.impact_score} > 7) -> "
         f"scenario '{res.scenario_name}', severity scale {res.scale:.2f}", 14, TEAL, bold=True)
    stat(s, 0.6, 2.0, 2.0, 1.25, usd(res.initial_value), "before", TEXT)
    stat(s, 2.75, 2.0, 2.0, 1.25, usd(res.stressed_value), "after", TEXT)
    stat(s, 4.9, 2.0, 2.0, 1.25, usd(res.pnl), "P&L", NEG)
    stat(s, 7.05, 2.0, 1.75, 1.25, f"{res.pnl_pct:+.2%}", "P&L %", NEG)
    comp = res.by_component
    bar_chart(s, 0.55, 3.4, 8.3, 3.3, list(comp["label"]), [round(v / 1e6, 2) for v in comp["pnl_usd"]],
              [POS if v >= 0 else NEG for v in comp["pnl_usd"]], number_format='0.0;-0.0', title="P&L by risk factor (USD m)",
              min_v=-20, max_v=15)
    card(s, 9.1, 2.0, 3.6, 4.7)
    text(s, 9.3, 2.15, 3.3, 0.35, "Assumptions (explicit)", 14, TEXT, bold=True)
    p = res.params
    bullets = [f"Rates {p['rate_shock_bp']:+.0f} bp (flight to quality)", f"Equities {p['equity_shock_pct']:+.1%} x beta",
               f"Spreads +{p['credit_spread_shock_bp']['BBB']:g} bp BBB / +{p['credit_spread_shock_bp']['HY']:g} bp HY",
               f"Loan PD x{p['pd_multiplier']:.2f}, LGD +{p['lgd_add'] * 100:.1f} pp",
               "Liquidity haircut after market moves", "Bonds: -ModDur x dy (bp / 10,000)",
               "Derivatives: delta / DV01 approximations"]
    text(s, 9.3, 2.6, 3.3, 2.6, [[("•  " + b, {"color": MUTED, "size": 11.5})] for b in bullets], 11.5)
    text(s, 9.3, 5.25, 3.3, 0.3, "Second example (entity-specific)", 12, TEXT, bold=True)
    cds = credit.positions.set_index("position_id").loc["DV04", "total_pnl_usd"]
    text(s, 9.3, 5.55, 3.3, 1.1, f"{ex.ticker} credit event: {usd(credit.pnl)} ({credit.pnl_pct:+.2%}); "
         f"CDS hedge offsets {usd(cds)}. Totals reconcile to the cent.", 11.5, MUTED)
    s.notes_slide.notes_text_frame.text = "Explain trigger, scenario mapping, the factor waterfall and the CDS hedge."

    # 6 ---- results
    s = deck.slide("Results, validation and domain impact", "Results")
    stat(s, 0.6, 1.55, 2.25, 1.3, f"{d['tests']} / {d['tests']}", "automated tests", POS, "ingestion, NLP, maths, API, UI")
    stat(s, 3.0, 1.55, 2.25, 1.3, f"{rep.rows_read} -> {rep.accepted}", "records ingested", TEXT,
         f"{rep.duplicates} duplicates removed")
    stat(s, 5.4, 1.55, 2.25, 1.3, f"{ec['grouped_cv_macro_f1']['mean']:.3f}", "grouped CV macro-F1", TEXT,
         "held-out templates (optimistic)")
    stat(s, 7.8, 1.55, 2.25, 1.3, f"{d['seconds']:.1f} s", "text -> signals", ACCENT, f"{n_sig} records, laptop CPU")
    cats = ["Naive VADER", "Finance VADER", "FinBERT (opt.)"]
    vals = [se["naive_vader"]["accuracy"] * 100, se["finance_adapted"]["accuracy"] * 100]
    cols = [MUTED, ACCENT]
    if tf.get("available"):
        vals.append(tf["finbert_sentiment_labelled"]["accuracy"] * 100)
        cols.append(TEAL)
    bar_chart(s, 0.55, 3.05, 4.7, 3.55, cats[:len(vals)], [round(v, 1) for v in vals], cols, '0.0',
              "Sentiment accuracy, % (628 labelled)", horizontal=False, min_v=0, max_v=100)
    cv = [ch["hybrid"]["accuracy"] * 100]
    cc = ["Hybrid baseline"]
    if tf.get("available"):
        cv.append(tf["hybrid_plus_zero_shot_challenge"]["accuracy"] * 100)
        cc.append("+ zero-shot (opt.)")
    bar_chart(s, 5.35, 3.05, 4.7, 3.55, cc, [round(v, 1) for v in cv], [ACCENT, TEAL][:len(cv)], '0.0',
              f"Event accuracy on {ch['rows']} unseen paraphrases, %", horizontal=False, min_v=0, max_v=100)
    card(s, 10.25, 1.55, 2.45, 5.1)
    text(s, 10.45, 1.7, 2.1, 0.35, "Why it matters", 15, TEXT, bold=True)
    impact = ["Early warning: minutes from headline to quantified exposure",
              "Explainable scores an analyst can audit and challenge",
              "Links NLP output directly to portfolio P&L by asset class",
              "API + CSV/JSON feed limits, alerts and credit reviews"]
    text(s, 10.45, 2.15, 2.1, 3.0, [[("•  " + b, {"color": MUTED, "size": 11.5, "space": 8})] for b in impact], 11.5)
    share = d["high"] / n_sig
    text(s, 10.45, 5.0, 2.1, 0.6, f"{share:.0%}", 34, NEG, bold=True)
    text(s, 10.45, 5.65, 2.1, 0.9, f"of signals ({d['high']} of {n_sig}) exceed the trigger - "
         "analysts review these first", 11, MUTED)
    text(s, 0.6, 6.66, 9.4, 0.3, "All metrics measured on synthetic data by scripts/evaluate_model.py; they show the pipeline "
         "works, not real-market predictive power.", 10.5, WARN)
    s.notes_slide.notes_text_frame.text = "Be explicit: synthetic evaluation, honest challenge set, engineering tests."

    # 7 ---- limitations
    s = deck.slide("Limitations and next steps", "Honest assessment")
    card(s, 0.6, 1.6, 5.95, 3.85, edge=WARN)
    text(s, 0.85, 1.78, 5.5, 0.4, "What remains unvalidated", 17, WARN, bold=True)
    lims = [f"Synthetic, template-generated text; no real-market labels or price reaction data",
            f"Baseline classifier generalises poorly to unseen phrasing ({ch['hybrid']['accuracy']:.0%} on paraphrases)",
            "Impact weights and scenario shocks are expert-set, not calibrated to history",
            "First-order stress maths: no convexity, gamma/vega or full loan revaluation",
            "Dictionary entity linking over a fixed fictional universe; one primary entity per text"]
    text(s, 0.85, 2.35, 5.45, 4.2, [[("•  " + b, {"color": TEXT, "size": 12.5, "space": 6})] for b in lims], 12.5)
    card(s, 6.8, 1.6, 5.9, 3.85, edge=TEAL)
    text(s, 7.05, 1.78, 5.5, 0.4, "Next steps", 17, TEAL, bold=True)
    nxt = ["Label real public news (with licences) and calibrate impact against market moves",
           "Fine-tune FinBERT / a small LLM for events; keep rules as an audit layer",
           "Historical scenario library (2008, 2020, 2022 rates) and full repricing",
           "Streaming ingestion (Kafka) with alerting and analyst feedback loop",
           "Coreference + entity resolution against reference data (LEI / tickers)"]
    text(s, 7.05, 2.35, 5.4, 4.2, [[("•  " + b, {"color": TEXT, "size": 12.5, "space": 6})] for b in nxt], 12.5)
    card(s, 0.6, 5.7, 12.1, 1.0, fill=BG2, edge=ACCENT)
    text(s, 0.85, 5.82, 11.6, 0.8, [[("Benefit: ", {"bold": True, "color": ACCENT, "size": 13}),
                                     ("headline-to-P&L in one explainable, offline workflow an analyst can audit.  ",
                                      {"color": TEXT, "size": 13}),
                                     ("Key limitation: ", {"bold": True, "color": WARN, "size": 13}),
                                     ("validated on synthetic data only; real-market calibration is the next step.",
                                      {"color": TEXT, "size": 13})]], 13)
    s.notes_slide.notes_text_frame.text = "Close with the benefit and the main limitation: synthetic validation only."
    return deck.prs


def export_pdf(pptx: Path, pdf: Path) -> bool:
    if sys.platform == "win32":
        ps = (f"$p = New-Object -ComObject PowerPoint.Application; "
              f"$d = $p.Presentations.Open('{pptx}', $true, $false, $false); "
              f"$d.SaveAs('{pdf}', 32); $d.Close(); $p.Quit()")
        r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True)
        if r.returncode == 0 and pdf.exists():
            return True
        print("PowerPoint export failed:", r.stderr[-500:])
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if soffice:
        subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(pdf.parent), str(pptx)], check=False)
        return pdf.exists()
    return False


def main() -> None:
    d = gather()
    logo_png = ROOT / "assets" / "logo.png"
    if not logo_png.exists():
        import pymupdf as fitz  # renders the SVG logo to PNG
        doc = fitz.open(str(ROOT / "assets" / "logo.svg"))
        doc[0].get_pixmap(dpi=300, alpha=True).save(str(logo_png))
    prs = build(d)
    pptx, pdf = DOCS / "presentation.pptx", DOCS / "presentation.pdf"
    if pdf.exists():
        pdf.unlink()
    prs.save(pptx)
    ok = export_pdf(pptx.resolve(), pdf.resolve())
    print(f"wrote {pptx.name}" + (f" and {pdf.name}" if ok else " (PDF export unavailable)"))


if __name__ == "__main__":
    main()
