# SC2006 Lab 3 — AI-based Project Initialisation

**Team 5 · GoWhere** · ChatGPT (free tier) · 29 October 2026

## Part 1 — Technology stack re-prompt (3.3.1)

**Uploaded:** our current requirements document and the current class diagram. In Lab 2 we uploaded only the Lab 1 deliverable: the one-feature Neighbourhood Comparison App, with no class diagram.

**Prompt** (same as Lab 2, in a fresh chat):

> Based on the uploaded design materials, recommend a technology stack appropriate for an entry-level software engineering team

**AI response:**

{{RESPONSE_A}}

### Answers to 3.3.2

**How similar are the recommendations?** Mostly the same. The core is unchanged: Python, Flask, HTML/CSS/JavaScript, Chart.js, pytest and Git. Four things changed:

- storage moved from a JSON/CSV snapshot to SQLite
- GeoPandas was dropped
- maps moved from Leaflet to OneMap
- new advice was added: one adapter per external service, scheduled jobs, CI and security controls

**(1) What caused the differences?** Our prompt and preferences were the same, so the change comes from the inputs:

- **From the class diagram,** which Lab 2 did not have:
  - its adapter classes led to the "one adapter per service" rule
  - its three stores (`Snapshot`, `EventStore`, `PlaceStore`) led to SQLite in three stores
  - its in-memory `SessionStore` led to the single-process caveat
- **From the requirements:** the new features (Telegram, LLM, Google Places) added those services to the stack.

**(2)** Not applicable. We have not changed language or framework since Lab 2.

**What we adopt, and what we don't:**

- **Adopted:** Python, Flask, Jinja, vanilla JavaScript, Chart.js, SQLite, `requests`, pytest, one adapter per external service, and a single process with in-memory sessions.
- **Not adopted:**
  - *pandas/NumPy:* our scoring is medians and percentiles over about 10,800 HDB blocks, which plain Python handles, so it is one less dependency.
  - *OneMap for maps:* OneMap supplies location and routing data, but drawing a map needs a JavaScript library, so we use Leaflet and MapLibre.
  - *Serving with Flask itself:* Flask's built-in server is for development only, so we use Waitress.
  - *Ruff and GitHub Actions:* not adopted yet.

## Part 2 — AI-generated minimal skeleton (3.3.3)

**Uploaded:** the class diagram only. Fresh chat.

**Prompt:**

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

**AI response:**

{{RESPONSE_B}}

The output is submitted as `lab3/ai_report/ai_generated_skeleton.zip`, separate from our application skeleton in `gowhere/`.

### Answers to 3.3.4

**To what extent do we agree with its choices?**

- **We agree with the content.** The folders follow the diagram's boundary / control / entity layers, each scoring strategy gets its own file, and external services sit in the boundary layer.
- **We do not adopt its folder layout.** Our `gowhere/` groups code by feature instead (`scoring/`, `lepak/`, `eat/`, `adapters/`, …), so that each feature's changes stay in one folder.

**Has it missed anything obvious?**

- **No home page template.**
- **Nothing builds the data snapshot or the place list.** The data.gov.sg and Overpass adapters exist, but nothing calls them. Our class diagram does not show those build classes either, so the AI could not have known about them.
- **No `data/` folder.**
- **Only a development `run.py`.** There is no production server and no ingestion schedule.
- **Each TODO is a single line,** so the operations listed in the class diagram are lost.

**Did it add anything beyond what was requested?** No code: we checked that all 74 files contain only a comment. Small extras:

- placeholder `TODO.md` files in the `static/` folders
- a `pyproject.toml` that duplicates `requirements.txt`
- an unrequested "Architectural notes" section in its reply
