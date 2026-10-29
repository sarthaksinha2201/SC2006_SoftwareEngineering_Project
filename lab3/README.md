# Lab 3 deliverables

Per the Lab 3 manual §4. Every deliverable is in this folder except the application itself
(`gowhere/`). The three diagrams in `diagrams/` are copies of `docs/`, taken on 29 Oct 2026 for
submission; `docs/` stays the working copy.

| Deliverable | Where |
|---|---|
| Complete Use Case model (diagram and descriptions) | [`lab3_FR_NFR.docx`](lab3_FR_NFR.docx) — Use Case Diagram + UC-1 through UC-13 |
| Design Model — class diagram | [`diagrams/class-diagram.md`](diagrams/class-diagram.md) |
| Design Model — dialog map | [`diagrams/dialog-map.md`](diagrams/dialog-map.md) |
| System architecture | [`diagrams/architecture.md`](diagrams/architecture.md) |
| Application skeleton | [`gowhere/`](../gowhere/) — see note below |
| Design issues, patterns, architectural style (§3.1.3, §3.2.1, §3.2.2) | [`design-issues.md`](design-issues.md) |
| PDF report (§3.3.5: AI tech-stack re-prompt + AI-generated minimal skeleton + critique) | [`ai_report/report.pdf`](ai_report/report.pdf); the AI's skeleton, kept apart from `gowhere/`: [`ai_report/ai_generated_skeleton.zip`](ai_report/ai_generated_skeleton.zip) |

## On "application skeleton"

§4 allows "an in-progress prototype... so long as the skeleton structure of the overall project is
clear." `gowhere/` is past that bar: a complete, tested, working application (441 tests, three
features). It is organised **by feature and layer**, not by stereotype: the boundary, control and
entity stereotypes are marked on each class in the class diagram rather than used as folder names.
A change to one feature stays in one folder.

| Folder or file | What it holds |
|---|---|
| `gowhere/serve.py` | The start-up class: starts the web server (Waitress) and, optionally, the event-ingestion schedule |
| `gowhere/config.py` | Settings: file paths, channel list, caps and limits |
| `gowhere/snapshot.py` | `Snapshot`, read-only access to the neighbourhood data |
| `gowhere/web/` | Flask routes, the per-browser session store, form parsing, view-model builders, templates, static assets |
| `gowhere/scoring/` | Where to Live: `ScoringEngine`, the `ScoringStrategy` interface, its six concrete strategies and the registry that lists them |
| `gowhere/lepak/` | Where to Lepak: event search, routing, parking, the event store, categories, venue photos |
| `gowhere/eat/` | Where to Eat: search, the place store, ratings, opening hours, cuisines, and the offline place-list build (`build.py`, `google_ids.py`, `notable.py`) |
| `gowhere/services/` | `LocationService`, the shared Facade for "where is this?" |
| `gowhere/adapters/` | One Adapter class per External Service: OneMap, LTA DataMall, Google Places and the LLM are called by the running app; data.gov.sg and Overpass only by the offline build. `http.py` is the shared request helper. Telegram's adapter, `TelegramPostSource`, sits with the ingestion pipeline in `ingest/run.py` |
| `gowhere/ingest/` | Event ingestion: Telegram scraper, date pre-filter, LLM extraction, the `Ingestor` pipeline |
| `gowhere/etl/` | The offline neighbourhood-data build: raw download (`_temp_fetch_raw.py`, the class diagram's `RawFetch`), geocoding, `build_snapshot.py` |

See [`diagrams/class-diagram.md`](diagrams/class-diagram.md) for exactly which class lives where.
Every class there carries its boundary, control or entity stereotype, and its notes explain where
the drawing differs from plain classes: Flask's route and search modules are drawn as `«utility»`
classes, each screen (a template) as a `«boundary, page»` class, the offline build as
`«control, offline»` classes, and `Neighbourhood`, `HDBBlock`, `Event` and `Place` as
`«entity, table»` because the code carries their rows as plain dicts.

**Representative skeleton-shaped files**, if you want two or three concrete examples rather than
the whole tree:

- `gowhere/scoring/base.py`: the `ScoringStrategy` abstract interface. Its three abstract methods
  have no bodies, only docstrings; the other methods are documented defaults.
- `gowhere/adapters/overpass.py`: a short adapter: one class, two public methods, and a docstring
  naming exactly which External Service it wraps and why.
- `gowhere/scoring/registry.py`: the whole file is sixteen lines: import every concrete class, list
  them. The comment at the top says adding a new factor changes only this file.

## How to read each diagram type (for the write-up / your supervisor)

These answer different questions, which is why they look different:

| Diagram | Question it answers | Notation |
|---|---|---|
| Class diagram | What objects exist, what do they know, what can they do? | Boxes = classes with attributes/methods inside, each marked «boundary», «control» or «entity» and grouped by it; arrows = generalization, composition, aggregation, association or dependency (the diagram's own legend says which is which) |
| Dialog map | What screens exist, how does the user move between them? | Boxes = screens; arrows = user actions, labelled with the guard that triggers them |
| System architecture | What are the big pieces of the whole system, how does data flow between them? | Boxes = subsystems/layers (not individual classes); arrows = "calls" / "reads" / "writes"; cylinders = databases |

For the architecture diagram specifically: the coloured regions are layers (Web layer, Where to
Live, Shared services, Adapters, Data...), not classes — just groupings. Follow an arrow and read
it as a sentence: `Routes → Engine` is "the controller calls the scoring engine"; `OneMap → OneMap
API` is "the adapter calls the external service." It's deliberately zoomed out; method signatures
are the class diagram's job, not this one's.
