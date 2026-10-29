# SC2006 Lab 3 — AI-based Project Initialisation (§3.3)

**Team 5 · GoWhere** · AI used: ChatGPT (free tier, web interface; the model name was not recorded) · Date: 29 October 2026

Both prompts were run in fresh chat sessions. The AI's full responses are reproduced word for word in Appendices A and B. The skeleton it produced is submitted as `lab3/ai_report/ai_generated_skeleton.zip`, kept apart from our own application skeleton in `gowhere/`.

---

## Part 1 — Technology stack re-prompt (§3.3.1, §3.3.2)

### 1.1 What the AI was given

We sent the **same prompt** as in Lab 2, word for word. We could not reuse the Lab 2 chat session itself, so this was a new session. What changed is the material we uploaded with the prompt:

| | Lab 2 (previous exercise) | Lab 3 (this exercise) |
|---|---|---|
| Application | *Neighbourhood Comparison App*: one feature | *GoWhere*: three features — Where to Live, Where to Lepak, Where to Eat |
| Uploaded material | The Lab 1 deliverable: FR, NFR, Data Dictionary, use case diagram and descriptions, UI mock-ups | The current requirements document (FR, NFR, Data Dictionary, use case model UC-1 to UC-13) **and the current design class diagram** (40 classes, as Mermaid source) |
| Class diagram uploaded? | No. Our Lab 2 report lists the uploaded material, and it contains no class diagram | Yes. Classes marked boundary / control / entity, one adapter per External Service, and the Strategy hierarchy for scoring |
| Scope described | Compare 2–4 Planning Areas on five factors, using government data only | Six switchable factors; events extracted from Telegram by an LLM; food places; live carpark data; Google Places ratings |

### 1.2 Prompt

> Based on the uploaded design materials, recommend a technology stack appropriate for an entry-level software engineering team

### 1.3 Response, summarised (full text: Appendix A)

| Area | Lab 2 recommendation | Lab 3 recommendation | |
|---|---|---|---|
| Language, framework | Python, Flask | Python, Flask (Django considered and rejected: no accounts needed) | Same |
| Front end | HTML, CSS, JavaScript | HTML, CSS, vanilla JavaScript, Jinja; React explicitly avoided | Same |
| Charts | Chart.js | Chart.js | Same |
| Testing | pytest | pytest, plus pytest-cov, `unittest.mock`, Playwright later | Expanded |
| Maps | Leaflet.js | "OneMap API" | Changed |
| Data processing | Pandas, GeoPandas, Shapely | pandas, NumPy — **no geospatial library** | Changed |
| Storage | "Local versioned data snapshot", JSON/CSV | SQLite in three separate stores, an in-memory session store, ratings never stored | Changed |
| External services | None named | `requests`, with **one adapter per service**: OneMap, LTA DataMall, Telegram, Google Places, LLM | New |
| Scheduling | A periodic refresh pipeline | Cron / scheduled jobs: ingestion every 6 h, maintainer-triggered rebuilds | Expanded |
| Tooling, deployment, security | Git, GitHub | Adds Ruff/Black, GitHub Actions, virtual environments, a hosting choice, a security-controls table and a list of technologies to avoid | New |

### 1.4 How similar are the recommendations? (§3.3.2)

**Mostly the same at the core, much larger around it.** The core is unchanged: the language, the web framework, the front-end approach, the chart library and the test framework. What changed is data storage, maps and geospatial processing. Everything about external services, operations and security is new.

**§3.3.2 (1) — what caused the differences.** Our prompt and our language preference were the same both times, so the differences come from the inputs. Two inputs changed, and the response lets us tell their effects apart, because ChatGPT marks which uploaded file each statement relies on.

*Caused by the class diagram* (the Lab 2 input had none, so these had nothing to anchor on before):

- **"Modular monolith"** — the response justifies this by the diagram's existing boundary / control / entity split.
- **The adapter rule** ("do not scatter direct API calls") — taken from `OneMapAdapter`, `DataMallAdapter`, `LlmAdapter` and the others. The response even sketches `OneMapAdapter`.
- **SQLite, split into three stores** — mirrors the diagram's three entity stores, `Snapshot`, `EventStore` and `PlaceStore`. Lab 2's flat "JSON/CSV snapshot" had no such structure to follow.
- **The in-memory session caveat** ("do not rely on an in-memory session store across multiple workers") — read from `SessionStore` / `SessionState`. This is the same reasoning behind our own decision to run as one process.
- **Dropping GeoPandas/Shapely, and "OneMap" for maps** (our inference; the response does not say why). The diagram shows only the classes the running app uses. Geometry arrives already computed in `Snapshot`, so no class processes geometry, which most likely explains why the geospatial library was dropped. No class draws a map either; the only map-related class is `OneMapAdapter`, which most likely explains why OneMap was named as the map technology. This tells us something about *our* diagram: it leaves out the offline data build. Part 2 shows the same gap again.

*Caused by the requirements document* (these are cited to it):

- The new External Services (Telegram, LLM, Google Places, DataMall) and the Scheduling rows. Lab 1 had none of these features.
- The privacy controls: session-only postal codes, ratings never stored, and the warning that cookie-based session storage may break the Security NFR.
- The data-freshness rules: carpark data at most two minutes old; keep the last good snapshot if a refresh fails.

**§3.3.2 (2) — not applicable.** We have not changed programming language or framework since Lab 2. Both labs use Python and Flask.

**How the advice compares with what we built.** We agree with most of it, and the shape we built matches: Flask, Jinja, vanilla JavaScript, Chart.js, SQLite, `requests`, pytest, an adapter per service, and a single process with in-memory sessions. We differ in three places:

- **pandas/NumPy** — we don't use either. Scoring is medians and percentiles over about 10,800 HDB blocks, which plain Python handles. That is one fewer dependency for teammates to install.
- **Maps** — OneMap supplies data (search, routing), but drawing a map in a browser needs a JavaScript map library. We use Leaflet (Lab 2's answer) and MapLibre. On this point the Lab 2 answer was the better one.
- **Serving** — "a Flask application process" is incomplete. Flask's built-in server is meant for development only, so we serve the app with Waitress.

Ruff and GitHub Actions are sensible suggestions that we have not adopted yet.

---

## Part 2 — AI-generated minimal skeleton (§3.3.3, §3.3.4)

### 2.1 Prompt

New chat session. We uploaded **only** the class diagram, as the manual specifies ("using your class diagram as input"):

> The attached file is the design class diagram of a web application, written in Mermaid.
>
> Generate a minimal skeleton template for this project in Python 3, using Flask.
>
> Rules for the files:
> 1. Create a folder hierarchy containing all the files you think the project needs (source, templates, tests, configuration).
> 2. Every file must be empty except for TODO comments describing what will go in it.
> 3. Do not write any code at all. No imports, no class or function definitions, no method signatures, no variables, no configuration values, no HTML tags. Only comments.
>
> Package the whole folder hierarchy as a single .zip file I can download.
>
> After the zip, show the folder tree, and give one sentence per folder explaining why it exists.

No follow-up prompt was needed: the zip came with the first response.

### 2.2 What it produced (full text: Appendix B)

- 74 files under `app/boundary/`, `app/control/` and `app/entity/` (one folder per stereotype), plus `templates/` grouped by feature, `static/`, `tests/` and `config/`.
- **Every file is exactly one line: a single TODO comment.** We checked this with a script over the extracted zip: 74 files, 74 lines in total.

### 2.3 Critical evaluation (§3.3.4)

**To what extent do we agree with its choices?**

- **Packages follow the diagram's stereotypes** (boundary / control / entity). This is exactly what manual §3.4.2 suggests, and it is a faithful reading of our diagram.
  - Our own `gowhere/` is organised differently, **by feature**: `scoring/`, `lepak/`, `eat/`, `adapters/`, `services/`, `ingest/`, `etl/`, `web/`. The stereotypes are shown on the class diagram, not as folders. We chose this so that a change to Where to Eat stays in one folder (high cohesion) and two developers working on different features rarely edit the same folder.
  - Both arrangements are defensible. The AI's matches the diagram more closely; ours matches how the work was divided.
- **One file per scoring strategy**, next to `scoring_strategy.py` and `scoring_engine.py`, makes the Strategy pattern visible in the folder tree. We agree.
- **External integrations kept at the boundary**, `.env.example` for secrets, and the application factory named in `app/__init__.py`: all agree with our design. We have a `create_app()` factory.
- **The TODOs say too little.** The diagram gives `ScoringStrategy` nine operations, including `category_scores`, `precompute` and `validate_options`. The skeleton's whole file is "*TODO: Document the shared scoring-strategy contract…*".
  - Our rules banned signatures, but not a comment *listing* the operations still to write. The AI chose to say less than it was allowed to, and most of the diagram's detail did not reach the skeleton.
  - Every TODO also begins "*Document …*", which reads as writing documentation rather than implementing anything.

**Has it missed something obvious, or failed to produce anything reasonable?**

1. **No home page.** There are templates for each feature's pages, but none for the screen the dialog map starts from: the page that leads to the three features.
2. **No offline data build.** `data_gov_adapter.py` and `overpass_adapter.py` exist, but nothing in the skeleton calls them, and nothing builds the neighbourhood snapshot or the place list (UC-9, UC-13).
   - The cause is ours: our class diagram shows these two adapters but none of the build classes that use them. It is the same gap seen in §1.4.
   - **Action:** add the offline build to the class diagram.
3. **No `data/` folder** for the databases and the hand-kept reference lists. The Part 1 response, given the requirements, did include one.
4. **Only a development entry point.** `run.py` is described as being for development. Nothing serves the app in production or runs ingestion on its background schedule. Our `serve.py` does both.
5. **Uneven test files.** Six scorer files but a single scoring test file, and one test file for all seven adapters.
6. **No place for the map and chart libraries** in `static/`. We serve Leaflet, MapLibre and Chart.js from our own server, never from a CDN, so the app still works offline. That is an architecture decision the class diagram doesn't show, so this one is fair to the AI.

Overall, it did produce something reasonable: a complete, consistently named tree that mirrors the diagram one-to-one.

**Did it add anything beyond what was requested?**

- **No code.** All 74 files are comment-only. The HTML templates use HTML comment syntax (`<!-- TODO … -->`), which is a comment rather than a tag, so they also follow the "no HTML tags" rule.
- **Small extra files:**
  - Placeholder `TODO.md` files inside `static/css`, `static/js` and `static/images`. These are sensible, because a zip cannot hold empty folders.
  - A `pyproject.toml` alongside `requirements.txt`, which duplicates where dependencies would be declared.
- **Unrequested text in the response**: an "Architectural notes" section and a "Recommended next step". Both are harmless.
- **Separate modules for the `Event`, `Place` and `Neighbourhood` entities.** Our diagram marks these «entity, table» because our code carries their rows as plain dictionaries. Giving each its own module is a reasonable reading of a class diagram that doesn't know that.

**Conclusion.** The skeleton reproduces the class diagram faithfully and adds almost nothing to it. That made it a useful check on our design: everything missing from the skeleton — the offline data build, the start-up and serving code, the home page — is something our class diagram does not show either.
