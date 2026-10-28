# Lab 3 deliverables

Per the Lab 3 manual §4. Everything below lives in its normal place in the repo — this folder
points to it rather than duplicating it, so there's one copy of each artefact to keep current.

| Deliverable | Where |
|---|---|
| Complete Use Case model (diagram and descriptions) | [`docs/deliverable/lab4_deliverable_FR_NFR.docx`](../docs/deliverable/lab4_deliverable_FR_NFR.docx) — Use Case Diagram + UC-1 through UC-13 |
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

**Representative skeleton-shaped files**, if you want two or three concrete examples to show rather
than the whole tree — these still read as signatures-and-docstrings, the shape a skeleton has
everywhere before it's filled in:

- `gowhere/scoring/base.py` — the `ScoringStrategy` abstract interface (`@abstractmethod`s, no
  bodies) plus small option-type classes that are nothing but a signature and a docstring.
- `gowhere/adapters/overpass.py` — a short adapter: one class, two public methods, a docstring
  naming exactly which External Service it wraps and why.
- `gowhere/scoring/registry.py` — the whole file is sixteen lines: import every concrete class,
  list them. The comment at the top says what adding a new factor would change (just this file).

## How to read each diagram type (for the write-up / your supervisor)

These answer different questions, which is why they look different:

| Diagram | Question it answers | Notation |
|---|---|---|
| Class diagram | What objects exist, what do they know, what can they do? | Boxes = classes with attributes/methods inside; arrows = inheritance (`<\|--`) or uses |
| Dialog map | What screens exist, how does the user move between them? | Boxes = screens; arrows = user actions, labelled with the guard that triggers them |
| System architecture | What are the big pieces of the whole system, how does data flow between them? | Boxes = subsystems/layers (not individual classes); arrows = "calls" / "reads" / "writes"; cylinders = databases |

For the architecture diagram specifically: the coloured regions are layers (Web layer, Where to
Live, Shared services, Adapters, Data...), not classes — just groupings. Follow an arrow and read
it as a sentence: `Routes → Engine` is "the controller calls the scoring engine"; `OneMap → OneMap
API` is "the adapter calls the external service." It's deliberately zoomed out; method signatures
are the class diagram's job, not this one's.
