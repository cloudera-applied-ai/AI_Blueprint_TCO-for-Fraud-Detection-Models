# Module 4 — Platform Architecture & Lab Preview (10 min)

**Goal:** attendees can map every demo layer to its production Cloudera service, explain
where NVIDIA GPUs plug in, and know exactly what they'll click in the lab.

---

## Slide 4.1 — Demo layer → production Cloudera service (3 min)

**On the slide**

From `docs/architecture/cloudera_deployment_blueprint.md` (six-layer pattern):

| Demo (this repo) | Production on Cloudera |
| --- | --- |
| Synthetic generator → CSV | NiFi / Kafka ingest from card networks |
| SQLite `transactions.db` (47.5 MB) | Iceberg lakehouse + Impala on CDW |
| pandas / cuDF pipelines | Spark or GPU-accelerated pipelines on CDE |
| In-process XGBoost + `.bak` promote | CML Models + **Model Registry** promotion |
| Settings-panel LLM endpoint | **Cloudera AI Inference (CAII)** — NVIDIA-GPU-served LLMs |
| React SPA on `CDSW_APP_PORT` | CML Application behind workspace auth |

**Speaker notes**

- This mapping table is the presentation backbone for architects: nothing in the demo is
  a dead end — each layer names its production replacement, and the Dev/Test/Prod
  topology + promotion flow are drawn in the same doc (`docs/architecture/*.drawio`).
- Emphasize the two NVIDIA insertion points: RAPIDS on the data/ML pipeline, and
  GPU-served LLM inference behind CAII.

---

## Slide 4.2 — NVIDIA GPU strategy: acceleration where it pays (3 min)

**On the slide**

- **Pipeline**: one import point (`pipelines/gpu_utils.py`) flips the whole pipeline to
  cuDF / cuML / CuPy when an NVIDIA GPU is present; identical outputs on CPU. Install is
  three packages from `pypi.nvidia.com`; `deploy/install.py` auto-detects via
  `nvidia-smi`.
- **Training**: XGBoost hist trees on GPU via the same utility.
- **LLM inference**: the agent's model runs on NVIDIA GPUs behind CAII or vLLM.
- **TCO, live**: the in-app calculator prices agent conversations against cloud APIs
  and against amortized NVIDIA hardware — presets from H100 SXM (700 W / $30K) through
  A100, L40S, down to an RTX 4090 fallback.

**Speaker notes**

- The honest framing sells better than hype: a 200K-row XGBoost problem trains in
  minutes on CPU — the GPU story here is *pipeline scale* (RAPIDS pattern carries to
  billions of rows unchanged) and *LLM serving economics* (where GPUs are mandatory).
- The TCO calculator turns "GPUs are expensive" into an interactive, defensible
  comparison: energy × PUE + amortization + maintenance vs. per-token cloud pricing
  (live-refreshed price list).

---

## Slide 4.3 — Generalizing the pattern (2 min)

**On the slide**

The reusable recipe — *explainable classical model + agent with governed tools + in-app
retraining, on Cloudera AI*:

| Use case | Same skeleton, different tools |
| --- | --- |
| **AML / sanctions** | Entity-flow queries, network tracing, SAR drafting |
| **Credit risk** | Score + SHAP adverse-action reasons, portfolio drift |
| **Claims fraud (insurance)** | Claim scoring, provider network investigation |
| **Payments disputes** | Case triage, evidence assembly, chargeback analytics |

**Speaker notes**

- The agent's tool registry is the extension point: every new use case is "same loop,
  new tools." The PII mask, cost counter, and trace view come along for free.
- Also generalize the *process*: scorecard → gates → standard repo layout is the
  Cloudera Forge operating model (`docs/OPERATING_MODEL.md`) — the answer to "how would
  you build this for us?"

---

## Slide 4.4 — Lab preview: what you will do in 60 minutes (2 min)

**On the slide**

1. **Score & explain** — pull up transactions, read the SHAP panel, find the injected
   fraud patterns in the top features.
2. **Investigate with the agent** — trace a fraud ring in one sentence; inspect the
   tool-call trace, PII masking, and the live cost counter.
3. **Retrain & promote** — correct labels in the Experiment Lab, train a candidate,
   compare confusion matrices, promote it to production.
4. **Pick the operating point & check drift** — threshold sweep + PSI drift between
   2018 and a later year.

**Speaker notes**

- Logistics before the break: instance URLs (or `docker compose up` on their laptops —
  this accelerator runs anywhere), lab guide location
  (`workshop/part2-lab/lab-guide.md`), and which LLM endpoint the agent is pointed at.
- Set the timing expectation: a retrain experiment on this estate takes ~a minute — the
  lab loop is tight by design.
