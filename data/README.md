# Data used by RiskPulse AI

**Every record in this folder is synthetic and fictional.** The hackathon pack contained only the
submission-guidelines PDF - no transaction file or sample dataset - so all text and the portfolio were
generated for this project by `scripts/generate_demo_data.py` (fixed seed `42`). The companies
(Northwind Bank, Helix Energy Corp, Meridian Shipping, ...) and tickers (NWBK, HLXE, MRDS, ...) are invented.
Nothing here comes from S&P Global, Crisil, any client, or any real news provider, and no record
describes a real event. Every row carries `is_synthetic = true`.

Regenerate everything with:

```bash
python scripts/generate_demo_data.py   # inputs: news, social, labelled set, portfolio, examples
python scripts/run_pipeline.py         # outputs: sample_signals.*, ingestion_report.json
python scripts/evaluate_model.py       # outputs: evaluation_report.json
python scripts/run_stress_test.py      # outputs: stress_result.json, stress_positions.csv
```

## Inputs

| File | Rows | What it is |
|---|---|---|
| `news_sample.csv` | 126 | News-like articles: `article_id, published_at, source_name, headline, body, author, is_synthetic`. Six hand-written showcase headlines (`N-H00`..`N-H05`) plus 120 template-generated items, 21 Sep - 4 Oct 2026 (UTC). |
| `social_sample.csv` | 140 | Social-media-like posts: `post_id, created_at, platform, handle, text, likes, reposts, is_synthetic`. Includes 10 `RT @handle:` reposts that exercise duplicate detection. |
| `portfolio.csv` | 37 | Illustrative ~USD 1.02bn wholesale-banking book: 8 loans, 8 corporate bonds, 4 government bonds, 8 equities, 3 FX balances, 6 derivatives. Columns are documented below. |
| `labelled_events.csv` | 628 | Labelled validation set from 157 hand-written templates (news and social styles), with `event_type`, `sentiment_label`, `style`, `template_id`. Used to train the TF-IDF model and to evaluate with template-grouped hold-out. |
| `challenge_set.csv` | 44 | Hand-written paraphrases (4 per class) that deliberately avoid the keyword rules - an out-of-template stress test. Never used for training. |
| `upload_example.json` | 3 | Example JSON upload for the dashboard / `--extra` flag. |
| `malformed_example.csv` | 5 | Deliberately broken rows (empty text, invalid / missing timestamps, a near-duplicate) to demonstrate validation errors. |

### Portfolio columns

| Column | Unit / meaning |
|---|---|
| `notional_usd` | Contract notional in USD (drives derivative sensitivities) |
| `market_value_usd` | Current value in USD; loans = carrying value = EAD; derivatives = current mark |
| `modified_duration` | Years; price change ~ -D x dy (fixed-rate loans have D > 0, floating = 0) |
| `spread_duration` | Years; price change ~ -SD x ds for credit-spread moves (bonds, CDS) |
| `pd_1y`, `lgd` | One-year probability of default and loss-given-default, decimals in [0, 1] |
| `beta` | Equity beta to the market move (index future and options use the underlying's beta) |
| `delta` | Derivative direction/sensitivity: +1 long, -1 short; option delta 0.55; pay-fixed swap -1; CDS protection bought -1 |
| `rating` | Maps to spread buckets AAA_AA / A / BBB / HY |
| `currency` | Non-USD positions receive the scenario FX move |

Amounts, ratings, PDs and durations are plausible illustrations chosen by the author, not market data.

## Generated outputs (reproducible)

| File | Produced by |
|---|---|
| `sample_signals.json`, `sample_signals.csv` | `scripts/run_pipeline.py` - 254 structured `RiskSignal`s |
| `ingestion_report.json` | rows read / accepted / rejected / duplicates and every issue |
| `evaluation_report.json` | `scripts/evaluate_model.py` - all model metrics shown in the dashboard and slides |
| `stress_result.json`, `stress_positions.csv` | `scripts/run_stress_test.py` - stress run for the top auto-triggered signal |

## Assumptions

- Timestamps without a timezone are treated as UTC.
- Duplicate = same text after lower-casing and removing URLs, `@handles`, a leading `RT`, and punctuation; the earliest copy is kept.
- Uploaded files without an `is_synthetic` column are labelled `is_synthetic = false` (unknown provenance is never called synthetic).
- The optional RSS adapter fetches real public items only when the user supplies a feed URL; it is off by default.
