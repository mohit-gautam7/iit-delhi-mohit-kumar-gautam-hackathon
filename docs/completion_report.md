# Completion report - RiskPulse AI

Date: 2026-10-10 · Candidate: Mohit Kumar Gautam (IIT Delhi) · Built from scratch: the working directory
initially contained only the official submission-guidelines PDF.

## 1. Requirement checklist

| Requirement (brief / guidelines PDF) | Status | Where |
|---|---|---|
| >= 2 source types (news-like, social-media-like), CSV + JSON | Done | `src/riskpulse/ingestion/adapters.py`, `data/news_sample.csv`, `data/social_sample.csv` |
| Validation, normalisation, missing / malformed handling, unique IDs, dedupe, provenance | Done | adapters + `tests/test_ingestion.py` |
| Upload extra records, replay mode, optional online source with graceful failure | Done | Data & Methodology page; `ingestion/rss.py` (off by default) |
| Sentiment -1..+1 + label; negation, finance terms, uncertainty, mixed tone | Done | `nlp/sentiment.py` |
| 10 event categories + explicit Unclassified + ambiguity | Done | `nlp/classifier.py` |
| Impact 1-10 with configurable factors and explanation; distinct from confidence | Done | `scoring/impact.py`, `config/scoring.yaml` |
| Entity / ticker, source, timestamp, text, confidence, explanation per signal | Done | `schemas.py` (`RiskSignal`) |
| Outputs via API and JSON / CSV | Done | `api.py`, `pipeline.py`, `data/sample_signals.*` |
| Module B: synthetic portfolio (loans, bonds, equities, FX, derivatives) | Done | `data/portfolio.csv` (37 positions, ~USD 1.02bn) |
| Event + impact trigger (impact > 7), scenario mapping, manual override | Done | `portfolio/stress.py`, `config/scenarios.yaml` |
| Explicit maths (duration with bp -> decimal, spreads, PD x LGD, FX, delta), reconciliation, approximation flags | Done | `portfolio/stress.py`, `docs/methodology.md` |
| Before / after, P&L abs + %, asset-class and position contributions, assumptions, trigger explanation, exports | Done | Portfolio Stress Lab page, `portfolio/report.py` |
| Same engine for dashboard, API, exports | Done | all call `riskpulse.portfolio.stress` / `riskpulse.pipeline` (API test asserts equality) |
| 6 dashboard pages with working controls | Done | `app.py`; verified in Edge (see section 3) |
| Model evaluation: accuracy, macro-F1, precision / recall, confusion matrix, error analysis | Done | `evaluation/metrics.py`, Model Evaluation page |
| Pytest suite covering ingestion, NLP, stress, API | Done | 93 tests pass |
| Scripts: data generation, pipeline, evaluation, stress test | Done | `scripts/` |
| README following the official template | Done | `README.md` |
| Architecture diagram (PNG + Mermaid) | Done | `docs/architecture.png`, `docs/architecture.svg`, `docs/architecture.mmd` |
| 5-7 slide deck, PDF + PPTX | Done (7 slides) | `docs/presentation.pdf`, `docs/presentation.pptx` |
| Demo script (5 min) with contingency | Done | `docs/demo_script.md` |
| Methodology, model card, test report | Done | `docs/` |
| MIT licence, `.gitignore`, `.env.example`, no secrets | Done | repo root |
| Public GitHub repo `<college>-<candidate-name>-hackathon` | See section 5 | |
| Demo video (YouTube unlisted) | **Pending - requires the candidate** | README placeholder |
| College email ID | **Pending - requires the candidate** | README placeholder |

## 2. Key numbers (all reproducible)

| Item | Value | Source |
|---|---|---|
| Rows read / signals / duplicates / rejected | 266 / 254 / 12 / 0 | `data/ingestion_report.json` |
| High-impact signals (> 7) | 56 | dashboard, `/events/summary` |
| Top auto-triggered stress | Market / liquidity stress, $1,019,100,000 -> $990,412,531, P&L -$28,687,469 (-2.81%) | `data/stress_result.json` |
| Meridian credit-event stress | -$12,469,067 (-1.22%); CDS hedge +$3.26m | `docs/methodology.md` section 9 |
| Event classifier, held-out templates (hybrid) | accuracy 0.994, macro-F1 0.993; grouped CV macro-F1 0.976 +/- 0.018 | `data/evaluation_report.json` |
| Event classifier, 44-sentence challenge set | 22.7% baseline; 68.2% with optional zero-shot fallback | same |
| Sentiment accuracy (628 rows) | naive VADER 57.5%, finance-adapted 70.4%, FinBERT (optional) 82.3% | same |
| Tests | 93 passed | `docs/test_report.md` |

## 3. Verification actually performed

- `python -m pytest`: **93 passed** (repeated after every change; final run recorded in `docs/test_report.md`).
- **Clean install**: fresh `git clone` of this repository into a temporary folder, new virtual environment,
  `pip install -r requirements.txt` only, then `pytest`, `run_pipeline.py` and `run_stress_test.py`:
  **93 passed** (1 third-party deprecation warning from FastAPI's test client), pipeline 266 -> 254 signals,
  stress P&L -$28,687,469 (-2.81%) - identical to the development machine. The resolver installed newer
  versions than development (e.g. Streamlit 1.65.0, FastAPI 0.143.0, pandas 3.0.6), so the bounded
  ranges in `requirements.txt` were exercised.
- **Dashboard in a real browser** (Microsoft Edge via Playwright): all six pages load with no Streamlit
  exception (`scripts/capture_screenshots.py`); controls exercised: adding the malformed CSV (3 rows
  rejected with reasons), replay, reset to bundled data, text search (2 of 254 match "coupon"), editing a
  stress assumption (P&L -2.81% -> -3.97%) and resetting it, downloading the HTML report. No page errors.
- **API**: started with `uvicorn api:app --port 8000`; `/health`, `/signals`, `/analyze`, `/events/summary`,
  `/stress-test` and `/docs` called with `curl`; invalid payload returned 422. Responses saved in
  `docs/api_examples/`.
- **Optional transformer mode**: FinBERT + BART-MNLI (locally cached open weights) ran end-to-end
  (`run_pipeline.py --transformers`, ~80 s on CPU) and in `evaluate_model.py`.
- **Presentation**: generated by `scripts/build_presentation.py` from live outputs (it refuses to build if
  any test fails), exported to PDF with Microsoft PowerPoint, each of the 7 slides rendered to PNG and
  inspected; overlaps, a truncated quote, white negative bars and a logo border were found and fixed.
  `validate.py` from the pptx skill: passed.
- **Design**: chart categorical palette checked with the dataviz skill's `validate_palette.js`
  (lightness, chroma, colour-vision-deficiency separation, contrast) on the dark surface: all checks pass.

## 4. Tools and skills used

- Claude Code skills actually loaded: `skill-leader` (router), `anthropic-skills:pptx` (deck creation and
  validation), `dataviz` (chart method + palette validator). The pptx skill recommends pptxgenjs; the deck
  was built with python-pptx instead to keep the repository Python-only, with the skill's validator used for QA.
- Claude Design, Canva and Figma integrations were not authorised in this environment and were **not** used;
  the design system, diagram and deck were produced with code (CSS tokens, matplotlib, python-pptx).
- Local tools: Python 3.11.9, Microsoft PowerPoint (PDF export), Microsoft Edge + Playwright (browser
  tests and screenshots), git, GitHub CLI.

## 5. Publication

- Public repository created with the GitHub CLI at the candidate's request:
  **https://github.com/mohit-gautam7/iit-delhi-mohit-kumar-gautam-hackathon** (branch `main`, incremental
  commit history as recommended in guidelines section 14).
- Verified: `gh repo view` reports visibility `PUBLIC`; unauthenticated requests to the raw README and to
  `docs/presentation.pdf` return HTTP 200.
- Submission archive `RiskPulse_AI_Hackathon_Submission.zip` (created with `git archive`, so it contains only
  tracked files - no virtual environments, caches or secrets) is stored next to the project folder.
- Not done (needs the candidate): demo video upload, college email, submission form. No app hosting
  (Streamlit Cloud etc.) was configured; the guidelines require a public repo and a live local demo.

## 6. Remaining steps for the candidate

1. Add the **college email ID** to `README.md`.
2. Record the walkthrough (follow `docs/demo_script.md`; the guidelines PDF suggests up to 10 minutes, the
   brief a 5-minute live demo - confirm on the submission portal), upload to **YouTube as Unlisted**, check
   it plays in a private window, and paste the link into `README.md`.
3. Confirm the GitHub repository is **public** and opens in a private browser window.
4. Submit the repository link, video link and deck through the official form before the deadline.

## 7. Known limitations

Synthetic validation only; baseline classifier generalises poorly to unseen phrasing (optional zero-shot
fallback mitigates); impact weights and shocks are expert-set, not calibrated; first-order stress maths;
dictionary entity linking over a fixed fictional universe; Streamlit Community Cloud or other hosting was not
set up (the guidelines require only a public repository and a live local demo).
