# docs/ — app guide · architecture · business case

Everything a reviewer needs to understand *why* this accelerator exists and *how* it is built
and operated.

## Start here

- **[APP_GUIDE.md](./APP_GUIDE.md)** — the authoritative build/run guide for this
  application (formerly the root README): feature tour, pipeline walkthrough, LLM provider
  setup, GPU acceleration, API reference.
- **[architecture/](./architecture/)** — the Cloudera deployment blueprint and diagrams.

## What goes here

| Path | Contents |
|------|----------|
| `APP_GUIDE.md` | The authoritative build/run guide for this accelerator's application. |
| `architecture/` | The Cloudera deployment blueprint, drawio diagrams, and ADRs for deviations from the standard stack. |
| `presentations/` | Deck sources — the Cloudera brand toolkit, the built value/blueprint/demo decks, their generator scripts (`build_*_deck.py`), and the deck-builder manual (`AGENTS.md`). |

## Conventions

- The **architecture** must conform to the build standard (Ingest → Lakehouse → Process →
  AI → Serve); where this accelerator deviates (e.g. the dashboard's own design system),
  the deviation is recorded as an ADR in [`architecture/`](./architecture/).
- Operational facts (metrics, thresholds, task resources) cited in these docs come from the
  repo itself (`models/metrics.json`, `.project-metadata.yaml`) — never invented.
