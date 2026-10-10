# Model card - RiskPulse AI risk engine v0.1

## Overview

| | |
|---|---|
| Purpose | Turn short financial news / social text into structured risk signals: entity, ticker, sentiment (-1..+1), event type (10 + Unclassified), impact (1-10), confidence, explanation |
| Default models | Finance-adapted VADER sentiment; hybrid keyword-rules + TF-IDF logistic-regression event classifier; configurable impact formula |
| Optional models | ProsusAI/finbert (sentiment), facebook/bart-large-mnli (zero-shot event fallback) - open weights, run locally |
| Training data | `data/labelled_events.csv`: 628 synthetic sentences from 157 hand-written templates, fictional companies |
| Intended use | Hackathon prototype; demonstration of an explainable text-to-risk pipeline feeding a stress test |
| Not intended for | Trading, investment advice, regulatory capital, or any decision on real portfolios |
| Author | Mohit Kumar Gautam (IIT Delhi), with AI coding assistance (disclosed in README) |

## Evaluation protocol

All numbers below are produced by `python scripts/evaluate_model.py` and stored in
`data/evaluation_report.json`; the dashboard's Model Evaluation page recomputes the baseline numbers live.

1. **Template-grouped hold-out**: `StratifiedGroupKFold(n_splits=4, groups=template_id, seed=42)`,
   fold 0 held out: 468 training rows (117 templates) vs 160 test rows (40 templates never seen in
   training). Plus 4-fold grouped cross-validation.
2. **Challenge set**: 44 hand-written paraphrases (4 per class) written to avoid the rule keywords,
   never used for training or rule design. This is the fairer generalisation test.
3. **Sentiment**: labels intended by each template (628 rows) and the challenge set; naive VADER is the
   baseline.

## Results (synthetic data)

### Event classification

| Variant | Held-out accuracy | Held-out macro-F1 | Challenge accuracy | Challenge macro-F1 |
|---|---|---|---|---|
| Hybrid (default) | 0.994 | 0.993 | 0.227 | 0.231 |
| TF-IDF + LR only | 0.581 | 0.607 | 0.204 | 0.194 |
| Rules only | 1.000 | 1.000 | 0.159 | 0.126 |
| Hybrid + zero-shot fallback (optional) | - | - | 0.682 | 0.666 |

Hybrid grouped 4-fold CV macro-F1: **0.976 +/- 0.018**.

**Interpretation.** The keyword rules and the synthetic templates were written by the same person, so
held-out-template scores are optimistic: they show the pipeline is internally consistent, not that it
understands finance. The challenge set exposes the real weakness of the lightweight baseline - lexical
coverage (e.g. "skipped an interest instalment" is not recognised as a credit event). The optional
zero-shot fallback raises challenge accuracy from 22.7% to 68.2% at roughly 2 s per fallback text on CPU.
When the baseline is unsure it abstains (Unclassified) rather than guessing; on the challenge set most
baseline errors are abstentions, which is the safer failure mode for a risk system.

### Sentiment

| Model | Labelled accuracy (628) | Labelled macro-F1 | Challenge accuracy (44) |
|---|---|---|---|
| Naive VADER (baseline) | 0.575 | 0.541 | 0.477 |
| Finance-adapted VADER (default) | 0.704 | 0.646 | 0.591 |
| FinBERT (optional) | 0.823 | 0.773 | 0.705 |

### Impact score

There is no ground truth for impact, so it is validated by construction and tests:
bounds (1-10), monotonicity (more negative tone, more exposure, fewer hedges, more reliable source ->
impact never decreases), Unclassified <= 2, and inspection of the factor breakdown attached to every
signal. Weights are expert-set in `config/scoring.yaml`.

## Known limitations and risks

- Synthetic, template-based text is far cleaner than real news; real-world accuracy will be lower.
- Dictionary entity linking over 12 fictional companies; no coreference ("the lender"), no unknown entities.
- One primary entity per text; multi-company stories are attributed to the first mention.
- Lexicon sentiment misses sarcasm and context ("oil surges" is scored as positive tone).
- Impact weights and stress shocks are not calibrated to historical market reactions.
- Social posts are treated as less reliable, but there is no bot / manipulation detection.
- Confidence values are model scores, not calibrated probabilities.

## Ethical and data considerations

- No real, confidential or client data; every record is labelled `is_synthetic`.
- Uploaded or RSS records are labelled as non-synthetic and keep their provenance.
- Outputs are explanations for analysts, not automated decisions.
