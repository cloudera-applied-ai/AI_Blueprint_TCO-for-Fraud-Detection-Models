# SE Workshop: Explainable Fraud Detection with Agentic AI on Cloudera

A 2-hour enablement workshop for technical Sales Engineers, built directly on this
repository's fraud-detection accelerator. The narrative: **Cloudera AI is the unified
platform** (AMP deployment, in-app retraining, governed promotion, LLM serving via
Cloudera AI Inference) and **NVIDIA GPUs are the compute engine where they pay**
(optional RAPIDS pipeline acceleration, GPU-served LLM inference, and a live GPU TCO
calculator with NVIDIA hardware presets).

This is the *classical, fully-reproducible* FSI accelerator: it generates its own
synthetic 200K-transaction estate, trains XGBoost in minutes on CPU (RAPIDS-accelerated
when a GPU is present), explains every score with SHAP, and puts a ReAct LLM agent with
fraud tools in front of the analyst. Its sibling, `demo-foundational-model`, tells the
GPU foundation-model story; this one tells the explainability + agentic-AI story.

## Session structure

| Segment | Duration | Materials |
| --- | --- | --- |
| **Part 1 — Presentation & Technical Deep-Dive** | 50 min | [`part1-presentation/`](part1-presentation/) |
| Break | 10 min | — |
| **Part 2 — Hands-On Implementation Lab** | 60 min | [`part2-lab/`](part2-lab/) |

## Part 1 modules (50 min)

| Module | Time | File |
| --- | --- | --- |
| 1. From Black Box to Analyst Copilot | 10 min | [`module-1-analyst-copilot.md`](part1-presentation/module-1-analyst-copilot.md) |
| 2. Core Terminology & Architecture | 15 min | [`module-2-terminology-architecture.md`](part1-presentation/module-2-terminology-architecture.md) |
| 3. Model Lifecycle & Governance on Cloudera AI | 15 min | [`module-3-lifecycle-governance.md`](part1-presentation/module-3-lifecycle-governance.md) |
| 4. Platform Architecture & Lab Preview | 10 min | [`module-4-platform-lab-preview.md`](part1-presentation/module-4-platform-lab-preview.md) |

Each module file is a slide-by-slide outline with speaker notes, the exact numbers to
quote, and pointers into the codebase so presenters can answer "show me" questions.

## Part 2 lab (60 min)

| File | Purpose |
| --- | --- |
| [`00-instructor-setup.md`](part2-lab/00-instructor-setup.md) | Environment prep — do this **before** the session |
| [`lab-guide.md`](part2-lab/lab-guide.md) | The attendee-facing lab: scoring + SHAP, agent investigation, retrain-and-promote, threshold & drift |

## Support materials

| File | Purpose |
| --- | --- |
| [`facilitator-guide.md`](facilitator-guide.md) | Run-of-show, timing checkpoints, anticipated Q&A / objection handling |
| [`glossary.md`](glossary.md) | One-page terminology reference (handout) |

## Source-of-truth pointers

- App build/run guide: [`../docs/APP_GUIDE.md`](../docs/APP_GUIDE.md)
- 3-minute customer demo script: [`../docs/presentations/demo_script.md`](../docs/presentations/demo_script.md)
- Cloudera deployment blueprint (six-layer mapping): [`../docs/architecture/cloudera_deployment_blueprint.md`](../docs/architecture/cloudera_deployment_blueprint.md)
- AMP manifest (the six one-click tasks): [`../.project-metadata.yaml`](../.project-metadata.yaml)
- Agent + tools: [`../ai/agents/`](../ai/agents/) (ReAct loop, tool registry, PII masking, cost estimator)
- Experiment lab / retrain loop: [`../pipelines/model_training/experiment_runner.py`](../pipelines/model_training/experiment_runner.py)
- Model card: [`../governance/model-cards/xgboost_fraud.md`](../governance/model-cards/xgboost_fraud.md)
