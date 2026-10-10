# RiskPulse AI - Methodology

This document explains every transformation from raw text to portfolio P&L. All code paths referenced
here are the ones used by the dashboard, the API, the CLI scripts and the exported reports.

## 1. Data and assumptions

- The organisers supplied no dataset, so all inputs are **synthetic and fictional** and generated with a
  fixed seed by `scripts/generate_demo_data.py` (see `data/README.md`).
- The bundled workflow is fully offline. "Replay" mode re-plays stored records in timestamp order; it is
  never presented as a live feed.

## 2. Ingestion (`src/riskpulse/ingestion/`)

| Step | Rule |
|---|---|
| Read | CSV (header required) or JSON (list of objects, or `{"records": [...]}`); 5 MB limit per file |
| Adapter | `news`: `headline` + `body` (+ `published_at`, `source_name`); `social`: `text`, `handle`, `platform`, `created_at`, engagement = likes + reposts. Column aliases accepted. Source type auto-detected from columns if not given. |
| Validate | Missing text or timestamp, unparseable timestamp, timestamp outside 2000-2100 -> row rejected with a reason; a bad file never stops the run |
| Normalise | NFKC unicode, control characters removed, whitespace collapsed, 5,000-character cap; timestamps converted to UTC (naive = UTC) |
| De-duplicate | Key = lower-case text without URLs, `@handles`, a leading `RT`, punctuation; checked globally across all files; earliest copy kept |
| Identify | `record_id = rec-` + UUIDv5(source type, source name, UTC time, dedupe key) - deterministic and unique; `signal_id` reuses the same UUID |
| Provenance | `source_type`, `source_name`, `author`, `is_synthetic` retained on every signal |

The optional RSS adapter (`rss.py`) accepts only http(s) URLs, times out after 5 s, caps the response at
2 MB and returns an error message instead of raising.

## 3. Entity and ticker linking (`nlp/entities.py`)

Case-sensitive, word-boundary dictionary matching over company aliases (longest alias first) plus
`TICKER` / `$TICKER`. The first mention is the primary entity; others are listed in the explanation.
Before sentiment and classification, names are masked to `company` so that words such as "Energy"
(Helix Energy) or "Trust" (Granite Real Estate Trust) do not carry tone and the classifier learns events,
not names.

## 4. Sentiment (`nlp/sentiment.py`)

1. **VADER** (Hutto & Gilbert, 2014) compound score - handles negation ("did not default"), intensifiers,
   capitalisation and contrastive "but".
2. **Finance lexicon**: 116 domain terms added or re-weighted (e.g. *default -3.0, downgrade -2.5,
   ransomware -3.0, beat +1.8, upgrade +2.2*); 20 words VADER scores but which are neutral in finance
   (*credit, security, interest, trust, bank, liquidity ...*) are removed from the lexicon.
3. **Phrase rules** (9) for multi-word expressions: "beat/missed estimates", "raised/cut guidance",
   "record losses", "missed a coupon payment", "rate hike", "spreads widen", "no material impact".
4. **Hedging**: each hedge word (*may, could, reportedly, rumour, unconfirmed, potential ...*) multiplies
   the score by 0.85, floor 0.6.
5. score = clip((VADER + phrase adjustment) x hedge factor, -1, 1); label Positive >= 0.15,
   Negative <= -0.15, otherwise Neutral (wider band than VADER's +/-0.05 because headlines are terse).
   Mixed tone (both positive and negative mass >= 0.12) is flagged in the explanation.

Optional: **FinBERT** (`ProsusAI/finbert`), score = P(positive) - P(negative), same hedging and thresholds.

## 5. Event classification (`nlp/classifier.py`)

Ten categories (Geopolitical, Macroeconomic, Credit Event, Merger & Acquisition, Product Launch,
Earnings / Financial Results, Regulatory / Legal, Cybersecurity, Operational Disruption, Market / Liquidity)
plus **Unclassified**.

- **Rules**: weighted regex keywords per category; matched words are kept as evidence.
  p_rule = rule weights normalised to sum to 1.
- **Model**: TF-IDF (word 1-2 grams, sublinear tf, English stop words) + logistic regression
  (C = 20, class-balanced, seed 42) trained on `labelled_events.csv` (entity-masked).
- **Blend**: p = 0.55 p_ml + 0.45 p_rule when rules fire, otherwise p = p_ml.
- **Abstain**: "Unclassified" when there is no evidence, when the model alone is below 0.40, or when
  the combined probability is below 0.30.
- **Ambiguity**: flagged when the runner-up is within 75% of the winner; it is reported as the
  secondary category and confidence is discounted by 15%.
- Optional **zero-shot fallback** (`facebook/bart-large-mnli`) is applied *only* to texts the baseline
  leaves Unclassified; it must reach 0.35 to override.

**Signal confidence** = classifier confidence x 0.9^(hedges, max 3) x 0.85 for social posts.
Confidence measures how sure the model is about the label; it is reported separately from impact.

## 6. Impact score (`scoring/impact.py`, weights in `config/scoring.yaml`)

```
raw    = base_severity[event]                    Geopolitical 6.5, Credit 6.5, Market/Liquidity 6.0,
                                                 Macro 5.5, Cyber 5.5, Regulatory 4.5, Operational 4.5,
                                                 M&A 4.0, Earnings 3.5, Product 2.5, Unclassified 1.5
       + intensity     0.5 per severe keyword (default, war, sanction, ransomware, bank run ...), cap 2.0
       + breadth       +1.0 market-wide language; +0.5 for Geopolitical / Macro / Market-Liquidity
       + exposure      1.0 x min(1, portfolio weight of the entity / 12%)
       + sentiment     |score| x 1.5 if negative, x 0.5 if positive
       - direction     1.5 if tone is positive, 0.75 if neutral (we score DOWNSIDE risk)
       - uncertainty   0.4 per hedge word, cap 1.2
       - evidence      (1 - source reliability) x 1.5; reliability news 1.0, rss 0.9, social 0.6
                       (+0.2 for social posts with >= 500 engagements)
impact = clip(round_half_up(raw), 1, 10)
```

Unclassified signals keep only the base severity. The impact score is an expert-weighted severity
index for prioritisation. It is **not** a probability, a calibrated loss estimate or a price forecast, and
negative tone alone cannot make an event high-impact (a negative product review stays low).

## 7. Stress trigger (`portfolio/stress.py`)

A signal triggers when `impact > threshold` (default 7, editable in the sidebar, the API and
`config/scenarios.yaml`) **and** its event type maps to a scenario. Each of the 10 event types maps to one
scenario. Unclassified signals never trigger. The analyst can always pick a signal or scenario manually;
the rationale is shown and exported.

## 8. Stress engine

All P&L is first-order and additive per position, so components, positions, asset classes and the
portfolio total reconcile exactly (asserted in code and in tests). Units: shocks in bp are divided by
10,000 before use; percentages are decimals.

| Component | Formula | Applies to |
|---|---|---|
| Rates | -ModDur x dy x MV | government & corporate bonds, fixed-rate loans |
| Credit spread | -SpreadDur x ds x MV, ds = bucket shock x sector multiplier + k x entity spread | corporate bonds |
| Equity | MV x (beta x market move + sector move + k x entity move) | equities |
| FX | MV x FX move (foreign value vs USD; cross-terms ignored) | non-USD positions, FX balances |
| Credit loss | -EAD x (min(1, PD x m) x min(1, LGD + add) - PD x LGD) | loans (amortised cost) |
| Liquidity | -haircut x (MV + market P&L) - applied last to avoid double counting | asset classes listed in the scenario |
| Derivatives | index future: delta x N x market move; option: delta x N x underlying move; swap: -delta x D x dy x N; CDS: -delta x SD x ds x N; commodity future: delta x N x move; FX forward: delta x N x FX move | flagged *approximated* |

`k` = 1 for positions of the named entity, `sector_contagion` (e.g. 0.3) for same-sector names, 0 otherwise.
PD multiplier = scenario x sector x (1 + k (entity multiplier - 1)).

**Severity scaling**: additive shocks (and each multiplier's excess over 1) are multiplied by
`impact / 8`, clipped to [0.5, 1.25]. It can be switched off in the dashboard or API.

**Relevance**: each scenario lists `affected_asset_classes`; nothing else is shocked (a cyber incident
does not move government-bond yields).

### Scenario library (`config/scenarios.yaml`, base values at impact 8)

| Scenario | Event type | Key shocks |
|---|---|---|
| Geopolitical escalation | Geopolitical | equity -10%, rates -25 bp, spreads +15/30/60/150 bp, oil +20%, EUR -4%, JPY +3%, PD x1.3 |
| Macroeconomic rates shock | Macroeconomic | rates +200 bp, equity -8%, spreads +10/20/40/100 bp, PD x1.25 |
| Issuer credit event | Credit Event | entity equity -35%, spread +400 bp, PD x4; sector contagion 30% |
| Regulatory / legal action | Regulatory / Legal | entity equity -12%, spread +80 bp, PD x1.5 |
| Cybersecurity incident | Cybersecurity | entity equity -18%, spread +120 bp; Financials/Tech -2% |
| Operational disruption | Operational Disruption | entity equity -12%, spread +90 bp; Industrials -2%, oil +3% |
| Market / liquidity stress | Market / Liquidity | equity -15%, rates -40 bp, spreads +25/50/100/250 bp, haircuts 1-1.5% |
| M&A event risk | Merger & Acquisition | acquirer equity -6%, spread +60 bp |
| Earnings shock | Earnings / Financial Results | entity equity -10%, spread +40 bp |
| Product launch | Product Launch | entity equity +/-5% following sentiment sign |

## 9. Worked example (reproducible: `python scripts/run_stress_test.py`)

The highest-impact auto-triggered signal in the bundled data is the news item *"Bond market sell-off
deepens as funding stress spreads across the sector..."*: Market / Liquidity, sentiment -1.00, impact 10.
Impact 10 > 7, so **Market / liquidity stress** runs with severity scale 10 / 8 = 1.25:

| | USD |
|---|---|
| Portfolio before stress | 1,019,100,000 |
| Portfolio after stress | 990,412,531 |
| P&L | -28,687,469 (-2.81%) |

By factor: rates +9.02m (flight to quality: rates -50 bp), credit spreads -9.66m, equity -14.12m,
FX -3.32m, commodities -1.50m, expected credit loss -1.24m, liquidity haircut -7.87m.

Entity-specific example: *"Meridian Shipping missed a coupon payment ... downgrades ... to CCC"* (impact 9)
-> Issuer credit event at scale 1.125: P&L -12.47m (-1.22%); the three worst positions are Meridian's
bond, loan and equity, and the CDS protection on Meridian gains +3.26m.

## 10. Evaluation

See `docs/model_card.md` and `data/evaluation_report.json`. Event-classifier metrics use a
template-grouped hold-out (no template appears in both train and test) plus a 44-sentence hand-written
challenge set that avoids the rule keywords.
