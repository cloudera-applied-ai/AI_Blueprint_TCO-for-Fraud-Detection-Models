# docs/architecture/ — reference architecture & ADRs

## Architecture

This accelerator realizes the **build standard** (§5 of the operating model):

```
Ingest (synthetic transaction generation) → Lakehouse (data/ parquet + SQLite estate) →
Process (preprocess → features → train, as CML AMP tasks) → AI layer (XGBoost + SHAP
serving, ReAct agent on Cloudera AI Inference) → Serve (fraud dashboard Application)
```

- **[cloudera_deployment_blueprint.md](./cloudera_deployment_blueprint.md)** — the full
  Cloudera deployment blueprint: the repeatable CDP pattern, the fraud-detection → Cloudera
  service mapping, and the Dev/Test/Prod deployment topology.
- Companion diagrams (open in [draw.io](https://app.diagrams.net/)):
  - [`cloudera_blueprint_pattern.drawio`](./cloudera_blueprint_pattern.drawio) — the layered CDP pattern
  - [`cloudera_fraud_mapping.drawio`](./cloudera_fraud_mapping.drawio) — demo → Cloudera service mapping
  - [`cloudera_deployment_topology.drawio`](./cloudera_deployment_topology.drawio) — Dev / Test / Prod topology
  - [`fraud_detection_architecture.drawio`](./fraud_detection_architecture.drawio) · [`fraud_detection_blueprint.drawio`](./fraud_detection_blueprint.drawio) · [`fraud_detection_simplified.drawio`](./fraud_detection_simplified.drawio) — application-level views (rendered: [`Fraud detection blueprint.jpg`](<./Fraud detection blueprint.jpg>))
- ADRs record any deviation from the standard stack:
  - **[ADR-001](./ADR-001-dashboard-design-system.md)** — the dashboard keeps its own design
    system rather than adopting the Forge design template; root-level `models/`, `config/`,
    and `data/` stay at the repo root (CWD-relative contract).

## Design system (the `app/` / Serve layer)

The canonical Forge design-system docs (`DESIGN_TEMPLATE.md`, `USING_THE_TEMPLATE.md`,
`STORYBOOK.html`) live in the template repository, `demo-design-template/docs/architecture/`,
and are not copied here. This app's frontend predates the template's adoption and keeps its
own Tailwind-based dark theme — the rationale and consequences are in
[ADR-001](./ADR-001-dashboard-design-system.md).
