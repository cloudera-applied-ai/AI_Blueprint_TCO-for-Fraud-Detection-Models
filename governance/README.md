# governance/ — model cards

**Governance packaged** — model documentation travels with the repo, so intended use,
provenance, evaluation, and limitations ship alongside the solution rather than being bolted
on later.

## What goes here

| Path | Contents | Automated by |
|------|----------|--------------|
| `model-cards/` | One card per served model — intended use, training data, eval results, limitations. [`xgboost_fraud.md`](./model-cards/xgboost_fraud.md) is this accelerator's card; [`example_model_card.md`](./model-cards/example_model_card.md) is the blank template. | (authored; kept in step with `models/metrics.json`) |
| `policies/` *(add as needed)* | SDX/Ranger-style access policies. Not yet packaged here — access is governed by CML project permissions; the LLM endpoint credential lives in the gitignored `config/config.yaml`. | Cloudera SDX policy APIs |

## Conventions

- Every scoring path (the in-process `app/backend/model_serving/` and any standalone CML
  endpoint deployed from `model_serving/predict.py`) **must** be covered by a card in
  [`model-cards/`](./model-cards/).
- Evaluation numbers on a card come from the pipeline's own outputs (`models/metrics.json`,
  `models/experiments/`) — update the card when retraining meaningfully shifts them.
- Secrets never live here (or anywhere in the repo): LLM credentials are in the gitignored
  `config/config.yaml` / `.env`.

A promoted experiment (experiment lab → promote) is the trigger to re-check the card
against reality.
