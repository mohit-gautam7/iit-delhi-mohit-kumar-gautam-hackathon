# RiskPulse AI - 5-minute demo script

> **Duration note.** The case-study brief asks for a live demo of at most **5 minutes**; the submission
> guidelines PDF describes a **10-minute** recorded walkthrough (Section 2.2: intro ~30 s, setup ~30 s,
> walkthrough ~2-3 min, results ~30-60 s). This script is the 5-minute core. For the recording, use the
> extended segments marked *(+10-min)*. Confirm the final limit on the official submission portal.

## Before you start (once)

```bash
cd iit-delhi-mohit-kumar-gautam-hackathon
pip install -r requirements.txt
python -m pytest            # expect: 93 passed
```

Open two terminals:

```bash
streamlit run app.py                 # terminal 1 -> http://localhost:8501
uvicorn api:app --port 8000          # terminal 2 -> http://localhost:8000/docs
```

Keep the browser at 1440 x 900 or larger, sidebar expanded, threshold at 7, transformer toggle **off**.

## Timeline

### 0:00-0:30 - Problem and product
- "Risk teams drown in headlines and posts. Negative tone is not the same as financial impact, and text
  insight rarely reaches portfolio numbers."
- "RiskPulse AI turns unstructured text into explainable risk signals and shows what a high-impact event
  would cost a wholesale-banking portfolio. Everything you will see runs offline on synthetic data."

### 0:30-1:00 - Launch
- Show terminal 1 running `streamlit run app.py`; open **Executive Overview**.
- Point at the badges: *254/254 records synthetic*, *Replayed dataset - not live market data*.
- KPIs: **254 signals** from 266 rows (12 duplicates removed), **56 high-impact**, top-signal stress
  **-$28.69m (-2.81%)**.

### 1:00-2:00 - Two source types
- Go to **Data & Methodology**: both bundled sources (news-like, social-media-like) are ticked.
- Click **+ Malformed CSV example**: Rejected = 3 with reasons (missing text, invalid timestamp, missing
  timestamp) and one more duplicate removed - nothing crashes.
- Click **Start replay** (normal speed) for ~10 s: records arrive in timestamp order with live badges.
  Say "this is a replay of stored data, not a live feed".
- *(+10-min)* Upload `data/upload_example.json` with **Process upload** and show it appear in the Explorer.

### 2:00-3:00 - Sentiment, event, impact
- **Risk Signal Explorer**: search `coupon`, select the Meridian Shipping news row.
- Read the explanation: Credit Event, keywords *missed a coupon, downgrades, default, restructuring*;
  sentiment **-1.00**; entity MRDS (10.0% of the portfolio); impact **9/10** =
  base 6.5 + intensity 0.5 + exposure 0.8 + tone 1.5 = 9.3.
- Show the impact waterfall and the structured JSON. "Impact is severity; confidence is separate."
- **Event Intelligence**: the sentiment-vs-impact scatter - many negative signals sit well below the
  trigger line. "Negative tone alone never triggers a stress test."
- *(+10-min)* Model Evaluation page: held-out macro-F1 0.993 vs challenge-set accuracy 22.7%; explain the
  honest reading and the optional zero-shot fallback (68.2%).

### 3:00-4:15 - Stress test
- **Portfolio Stress Lab**: the default candidate is the top auto-triggered signal - *Bond market sell-off
  deepens...* (Market / Liquidity, impact 10 > 7) -> scenario **Market / liquidity stress**, scale 1.25.
- Results: **$1.02bn -> $990.41m, P&L -$28.69m (-2.81%)**. Walk the waterfall: rates +$9.02m
  (flight to quality), equity -$14.12m, spreads -$9.66m, liquidity haircut -$7.87m.
- Switch the candidate to the **Meridian Shipping** credit signal (2026-10-01 13:40, impact 9):
  scenario becomes *Issuer credit event*; the worst positions are Meridian's bond, loan and equity, and the
  CDS hedge gains. P&L about **-$12.47m (-1.22%)**.
- Open **Edit stress assumptions**, change *Entity equity move* from -35 to -50: numbers update instantly.
  Click **Reset to scenario defaults**.

### 4:15-4:45 - Results and exports
- Click **Download printable report (HTML)** and **Download positions (CSV)**.
- Terminal 2 / browser: open `http://localhost:8000/docs`, run `POST /analyze` with
  `{"items":[{"text":"Ransomware attack forces Quantum Payments to halt card processing"}]}`
  -> Cybersecurity, QPAY, stress trigger included. "Other systems consume the same engine."

### 4:45-5:00 - Benefit and limitation
- "Benefit: minutes from headline to a quantified, explainable portfolio impact."
- "Key limitation: validated on synthetic data only; impact weights and shocks are not yet calibrated
  to real market reactions - that is the next step."

## Expected numbers (bundled data, threshold 7, baseline models)

| Item | Value |
|---|---|
| Rows read / signals / duplicates / rejected | 266 / 254 / 12 / 0 |
| High-impact signals (> 7) | 56 |
| Top auto-triggered stress | Market / liquidity stress, -$28,687,469 (-2.81%) |
| Meridian credit-event stress | Issuer credit event, -$12,469,067 (-1.22%) |
| Tests | 93 passed |

## Contingency plan

| Problem | Fallback |
|---|---|
| No internet | Nothing changes: the demo is fully offline (fonts fall back to system fonts). Do not use the RSS box. |
| Streamlit port busy | `streamlit run app.py --server.port 8502` |
| API not reachable | Skip the API segment; show `docs/api_examples/*.json` (real responses) and the CLI: `python scripts/run_stress_test.py` |
| Dashboard fails to start | `python scripts/run_pipeline.py` and `python scripts/run_stress_test.py` print the same numbers; open `docs/stress_report.html` |
| Transformer toggle slow | Leave it off (default). It is optional and takes ~1-3 min on CPU. |
| Screen too small | Collapse the sidebar; all pages are responsive down to laptop width. |
