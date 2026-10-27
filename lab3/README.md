# Lab 3 deliverables

Per the Lab 3 manual §4. Everything below lives in its normal place in the repo — this folder
points to it rather than duplicating it, so there's one copy of each artefact to keep current.

| Deliverable | Where |
|---|---|
| Complete Use Case model (diagram and descriptions) | [`lab3_FR_NFR.docx`](lab3_FR_NFR.docx) — Use Case Diagram + UC-1 through UC-13 |
| Design Model — class diagram | [`docs/class-diagram.md`](../docs/class-diagram.md) |
| Design Model — dialog map | [`docs/dialog-map.md`](../docs/dialog-map.md) |
| System architecture | [`docs/architecture.md`](../docs/architecture.md) |
| Application skeleton | [`gowhere/`](../gowhere/) — see note below |
| PDF report (§3.3.5: AI tech-stack re-prompt + AI-generated minimal skeleton + critique) | **Not yet done** — tracked separately |

## On "application skeleton"

§4 allows "an in-progress prototype... so long as the skeleton structure of the overall project is
clear." `gowhere/` is past that bar — it's a complete, tested, working application (439 tests,
three features), organized into packages matching the design model's stereotypes:

- `gowhere/scoring/` — the Strategy hierarchy and `ScoringEngine` (Where to Live)
- `gowhere/lepak/` — Where to Lepak's search, routing, parking, event store
- `gowhere/eat/` — Where to Eat's search, place store, ratings, notability
- `gowhere/adapters/` — one Adapter class per External Service
- `gowhere/services/` — `LocationService`, the shared Facade
- `gowhere/ingest/` — the Telegram scraper and LLM extraction pipeline
- `gowhere/etl/` — the offline data-snapshot build
- `gowhere/web/` — Flask routes, view models, templates, static assets

See [`docs/class-diagram.md`](../docs/class-diagram.md) for exactly which class lives where, and
its notes for the two places this package structure deliberately diverges from the Lab 2 class
names (no boundary/control wrapper classes around Flask's route functions; no entity classes for
what are plain SQLite-row dicts throughout).
