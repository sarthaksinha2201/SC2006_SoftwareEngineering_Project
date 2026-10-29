I've created the **GoWhere Flask project skeleton** based on your Mermaid design class diagram. The structure follows the diagram's three main architectural layers: Boundary, Control, and Entity. class_diagram_mermaid

## 1. Download the ZIP file

**gowhere_flask_skeleton.zip[📦 Download the GoWhere Flask Skeleton](sandbox:/mnt/data/gowhere_flask_skeleton.zip)**

The ZIP contains 74 files, organized into a Python 3 and Flask project structure.

### What I've included

- **Boundary layer:** Web routes and adapters for OneMap, DataMall, Google Places, Telegram, LLMs, data.gov.sg, and Overpass.
- **Control layer:** Search services, scoring engine and strategies, routing, location services, parking, and event ingestion.
- **Entity layer:** Events, places, neighbourhood snapshots, stores, opening hours, and session state.
- **Templates:** Placeholder pages for Live, Lepak, and Eat workflows, plus error pages.
- **Tests:** Placeholder test files for routes, search, scoring, adapters, routing, and stores.
- **Configuration:** Placeholder files for project dependencies, settings, environment variables, and the application entry point.

**Your constraints are preserved:** every file contains only TODO comments. There are no imports, class or function definitions, method signatures, variables, configuration values, or HTML tags.

---

## 2. Folder tree

```text
gowhere_flask_skeleton/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── run.py
│
├── config/
│   ├── __init__.py
│   └── settings.py
│
├── app/
│   ├── __init__.py
│   │
│   ├── boundary/
│   │   ├── __init__.py
│   │   ├── web_routes.py
│   │   ├── onemap_adapter.py
│   │   ├── token_source.py
│   │   ├── datamall_adapter.py
│   │   ├── llm_adapter.py
│   │   ├── telegram_post_source.py
│   │   ├── google_places_adapter.py
│   │   ├── daily_cap.py
│   │   ├── data_gov_adapter.py
│   │   └── overpass_adapter.py
│   │
│   ├── control/
│   │   ├── __init__.py
│   │   ├── lepak_search.py
│   │   ├── eat_search.py
│   │   ├── eat_ratings.py
│   │   ├── eat_hours.py
│   │   ├── scoring_engine.py
│   │   ├── scoring_strategy.py
│   │   ├── public_transport_scorer.py
│   │   ├── housing_affordability_scorer.py
│   │   ├── amenities_scorer.py
│   │   ├── greenery_scorer.py
│   │   ├── healthcare_scorer.py
│   │   ├── commute_scorer.py
│   │   ├── commute_router.py
│   │   ├── location_service.py
│   │   ├── event_router.py
│   │   ├── parking_service.py
│   │   └── ingestor.py
│   │
│   └── entity/
│       ├── __init__.py
│       ├── snapshot.py
│       ├── neighbourhood.py
│       ├── event_store.py
│       ├── event.py
│       ├── place_store.py
│       ├── place.py
│       ├── hours.py
│       ├── factor_choice.py
│       ├── session_store.py
│       └── session_state.py
│
├── templates/
│   ├── base.html
│   ├── live/
│   │   ├── submit.html
│   │   └── results.html
│   ├── lepak/
│   │   ├── submit.html
│   │   ├── results.html
│   │   └── event.html
│   ├── eat/
│   │   ├── submit.html
│   │   ├── results.html
│   │   ├── area.html
│   │   └── place.html
│   └── errors/
│       ├── 404.html
│       └── 500.html
│
├── static/
│   ├── css/
│   │   └── TODO.md
│   ├── js/
│   │   └── TODO.md
│   └── images/
│       └── TODO.md
│
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_web_routes.py
    ├── test_lepak_search.py
    ├── test_eat_search.py
    ├── test_eat_hours.py
    ├── test_scoring_engine.py
    ├── test_routing_services.py
    ├── test_stores.py
    └── test_adapters.py
```

---

## 3. Why each folder exists

| Folder | Purpose |
|---|---|
| `config/` | Holds application configuration documentation and the planned settings structure, keeping configuration concerns separate from business logic. |
| `app/` | Contains the main application package and the components that implement the web application's architecture. |
| `app/boundary/` | Isolates the web interface and external-system integrations so the rest of the application does not need to handle API communication directly. |
| `app/control/` | Contains the application's workflows, business logic, search operations, scoring strategies, and routing services. |
| `app/entity/` | Organizes domain records, data-access components, stores, and session-state representations. |
| `templates/` | Holds the HTML template files that Flask will eventually render for the application's pages. |
| `templates/live/` | Groups the pages associated with the Live workflow. |
| `templates/lepak/` | Groups the event-search, event-results, and event-detail pages. |
| `templates/eat/` | Groups the food-search, browsing, results, and place-detail pages. |
| `templates/errors/` | Reserves templates for common HTTP error pages, such as 404 and 500. |
| `static/` | Reserves space for frontend assets served directly by Flask. |
| `static/css/` | Will hold the application's stylesheets. |
| `static/js/` | Will hold browser-side JavaScript. |
| `static/images/` | Will hold image assets used by the interface. |
| `tests/` | Separates automated tests from application code so individual components and their interactions can be verified. |

### Root-level files

These files are not folders, but they have distinct responsibilities:

| File | Purpose |
|---|---|
| `README.md` | Documents the project's purpose, architecture, setup, and development workflow. |
| `pyproject.toml` | Reserves space for Python project metadata and development-tool configuration. |
| `requirements.txt` | Documents where runtime dependencies, including Flask, will eventually be listed. |
| `.env.example` | Documents the environment variables the application will eventually require without storing real secrets. |
| `.gitignore` | Documents which local files and generated artifacts should be excluded from version control. |
| `run.py` | Reserves the entry point for starting the application during development. |
| `app/__init__.py` | Documents the intended Flask application setup and application-factory responsibilities. |
| `tests/conftest.py` | Reserves space for shared pytest fixtures and test setup. |

---

## 4. Architectural notes

I made three deliberate decisions when translating your diagram into a project structure.

**1. Preserve the three-layer architecture.**

The Boundary, Control, and Entity packages reflect the diagram's organization rather than placing all classes into a single application module. This should make the project easier to navigate as it grows.

**2. Give the scoring strategies separate files.**

The six scoring strategies each have their own placeholder file, alongside the shared strategy and scoring-engine files. This mirrors the Strategy pattern shown in the diagram and keeps individual scoring concerns separate.

**3. Keep external integrations at the boundary.**

Adapters for OneMap, DataMall, Google Places, LLMs, and other external services live under `app/boundary/`. Their consumers and business workflows are organized separately under `app/control/`.

**One important limitation:** this is a structural skeleton, not an executable Flask application yet. Since you requested comment-only files, Flask cannot run until the relevant TODOs are implemented.

**Recommended next step:** implement the application factory and basic routing first, then add the Entity layer, Control services, and external adapters incrementally. This will let you establish a working Flask application before implementing the more complex business logic.
