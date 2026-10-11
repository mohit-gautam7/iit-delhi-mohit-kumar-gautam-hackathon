# Test report

**Result: 93 passed, 0 failed** - `python -m pytest -v` on Python 3.11.9, pytest 9.1.1, Windows 11
(2026-10-10). Runtime about 12-17 s. The same suite also passed in a fresh virtual environment created from
a clean `git clone` with only `pip install -r requirements.txt` (fresh clone, new virtual environment).

```
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
collected 93 items
...
============================= 93 passed in 16.43s =============================
```

## Inventory

| File | Tests | What is verified |
|---|---|---|
| `tests/test_ingestion.py` | 12 | both bundled sources ingest; social adapter fields; empty file; missing text / invalid / missing timestamps rejected with reasons; malformed JSON; JSON list and `{"records": [...]}`; duplicates across files and `RT @handle` reposts (earliest kept); IDs unique, deterministic and provenance-aware; UTC normalisation; source-type detection and `is_synthetic` default; text cleaning and truncation; RSS refuses non-http and degrades gracefully when unreachable |
| `tests/test_nlp.py` | 24 | positive / negative / neutral sentiment; bounds on all 628 labelled texts; negation and hedging; company names carry no tone; entity + ticker linking (and "summit" is not a company); one canonical sentence per each of the 10 event categories; unknown text -> Unclassified; every signal's ranges, categories, IDs, ambiguity fields; schema rejects out-of-range or invalid values; impact factor sum and monotonicity (social <= news, hedged <= plain, milder <= stronger, exposure >= none, positive < negative), Unclassified <= 2, cap at 10; negative sentiment does not imply high impact; JSON / CSV serialisation round trip; free-text analysis |
| `tests/test_stress.py` | 49 | portfolio valuation; equity shock x beta (-1.2m on 10m, beta 1.2, -10%); rate sign convention (+100 bp on D=5, 100m -> -5.0m; -100 bp -> +5.0m; pay-fixed swap +4.0m; floating loan 0); spread and CDS (-1.0m, +0.4m); loan expected loss (-1.0m) and PD cap at 1; FX and short-EUR forward hedge (-0.5m / +0.5m); commodity future (+2.0m); liquidity haircut on post-shock value; entity shock and contagion; unaffected asset classes unchanged; zero / missing exposures; portfolio validation errors; impact scaling floor / reference / cap; reconciliation for **every scenario x impact {3, 8, 10}** on the bundled book (30 cases); adverse scenarios lose money; trigger threshold is strictly > 7 and every event type maps; stress from signal hits the named issuer and Unclassified raises; product-launch sign follows sentiment; entity weights |
| `tests/test_api.py` | 7 | `/health`; `/signals` filters, invalid enum 422, out-of-range 422, unknown ID 404; `/analyze` valid, empty list, too-short text, bad source type and malformed JSON -> 422; `store` adds a signal; `/events/summary`; `/portfolio` total equals the CSV; `/stress-test` equals a direct engine call and reconciles; overrides change P&L; unknown scenario / ticker / missing body / out-of-range impact -> 422; unknown signal 404; Unclassified signal -> 422 |
| `tests/test_dashboard.py` | 1 | Streamlit `AppTest` runs `app.py` headless; the Executive Overview renders with no exception |

Expected values in `test_stress.py` were computed by hand from the documented formulas
(`docs/methodology.md` section 8), independently of the implementation.

## Additional verification performed

| Check | How | Outcome |
|---|---|---|
| All six dashboard pages | `scripts/capture_screenshots.py` drives Microsoft Edge (Playwright) through every page and fails on any Streamlit exception | all 6 pages `ok`; screenshots in `docs/screenshots/` |
| Live API | `uvicorn api:app --port 8000`, real `curl` calls | `/health` 200, `/analyze` 200, empty payload 422, `/docs` 200; responses saved in `docs/api_examples/` |
| CLI scripts | `generate_demo_data.py`, `run_pipeline.py`, `evaluate_model.py`, `run_stress_test.py` | run successfully; outputs in `data/` and `docs/stress_report.html` |
| Optional transformer mode | `run_pipeline.py --transformers` and `evaluate_model.py` with local FinBERT / BART-MNLI weights | completed (about 80 s on CPU for 254 records) |
| Presentation | built by `scripts/build_presentation.py` (fails if any test fails), exported to PDF by PowerPoint, every slide rendered to PNG and inspected; OOXML schema validation | 7 slides, validation passed |

## How to reproduce

```bash
pip install -r requirements.txt
python -m pytest -v
```
