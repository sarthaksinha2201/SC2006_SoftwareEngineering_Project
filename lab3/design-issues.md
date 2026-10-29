# Design issues, patterns and architectural style

Lab 3 manual §3.1.3 (Fox's design heuristics), §3.2.1 (Bruegge §7.4 key design issues:
persistent data, access control) and §3.2.2 (design patterns), stated in one place. Every
claim names the file that does it, so each one can be checked against the code. The class
diagram ([`docs/class-diagram.md`](../docs/class-diagram.md)) and architecture
([`docs/architecture.md`](../docs/architecture.md)) show the same classes; this page says
*why* they are arranged that way.

---

## 1. Architectural style

GoWhere combines four of the styles in Lecture 12, each where it fits:

| Style | Where | Why this style here |
|---|---|---|
| **Client–server** | Browser (client) ↔ one Flask process (server), over HTTP | The Usability NFR asks for desktop and phone with nothing to install. A browser is the only client every user already has. |
| **Layered** | Web layer → feature logic (Live / Lepak / Eat) → shared services → adapters → data | Each layer calls only the one below it. A route never calls OneMap directly; it calls a router, which calls `OneMapAdapter`. So an External Service can change without touching a screen. |
| **MVC** (Lecture 15), inside the web layer | **Model**: `ScoringEngine`, `lepak/search.py`, `eat/search.py` and the stores. **View**: Jinja templates plus the view-model builders (`view_models.py`, `lepak_views.py`, `eat_views.py`). **Controller**: `web/routes.py` | The same ranking is shown as a list, a map and a chart. Keeping the Model free of HTML is what lets three Views read one result, and what let us redesign the interface (DECISIONS.md §22) without changing a single scoring test. |
| **Pipe-and-filter**, for event ingestion | `ingest/run.py` `Ingestor`: fetch posts → prefilter → LLM extraction → resolve venue → merge into `EventStore` | Each stage takes the previous stage's output and keeps no shared state, so each is tested on its own and a post rejected at any stage is logged with the stage that rejected it (DECISIONS.md §20). |

The offline data build (`etl/build_snapshot.py`, `eat/build.py`) is a **batch-sequential**
step feeding a **repository** (`snapshot.db`, `eat.db`) that the running app only reads. That
split is the subject of §4.

**Rejected alternative:** one service per feature (three deployments). Twice the operations
work for a 5-week, two-developer project, with nothing gained at this scale (DECISIONS.md §4).

---

## 2. Design patterns applied

Lecture 14's catalogue, the ones we use, and the problem each one solves for us:

| Pattern (GoF group) | Classes | Problem it solves |
|---|---|---|
| **Strategy** (behavioural) | `ScoringStrategy` (abstract, `scoring/base.py`) with six concrete strategies: `PublicTransportScorer`, `HousingAffordabilityScorer`, `AmenitiesScorer`, `GreeneryScorer`, `HealthcareScorer`, `CommuteScorer`. `ScoringEngine` holds a set of them. | The user includes or excludes any factor (FR 1.x). The engine computes a weighted mean over *whichever* strategies are switched on and never asks which one it holds. Adding a seventh factor is a new subclass, with no change to the engine: the Open–Closed Principle. |
| **Factory** (creational, the simple/static form Lecture 14 pairs with Strategy) | `scoring/registry.py` `default_strategies()`; `web/__init__.py` `create_app()`; the `*_FACTORY` config entries (`ROUTER_FACTORY`, `EVENT_ROUTER_FACTORY`, …) | The one place that knows the concrete scorer classes is the registry, so neither the engine nor the ETL imports them. `create_app()` builds the whole app from a config dict, so the tests swap a real router for a fake one by passing a different factory. |
| **Adapter** (structural) | One class per External Service: `OneMapAdapter`, `DataMallAdapter`, `GooglePlacesAdapter`, `LlmAdapter`, `DataGovAdapter`, `OverpassAdapter`, and `TelegramPostSource` | Each service has its own URL scheme, auth and rate limit. The adapter turns it into plain Python calls. Two payoffs, both real: the 400+ tests run with no network by substituting fakes, and changing LLM provider mid-project touched `LlmAdapter` only (DECISIONS.md §19). |
| **Facade** (structural) | `LocationService` (`services/location.py`) | "Where is this?" needs an alias list, several OneMap query forms, a word-for-word match rule, an on-disk cache for public venues, *no* cache for a user's postal code, and an offline fallback. Lepak, Eat, Commute and ingestion all call one method and see none of that. |
| **Singleton** (creational), in the per-process form | `shared_places()` in `adapters/google_places.py` | Google's daily cap must count every user's calls together. A lazily created, lock-protected single instance per process does that; a second instance would keep a second count and could double the bill. |

Not used, with reason: **Observer**. Nothing in GoWhere needs live push to the screen; every
page is a request and a response. Adding it would be pattern-for-its-own-sake.

---

## 3. Fox's design heuristics (pp. 341–345)

| Heuristic | Where it is applied |
|---|---|
| **Add a start-up class** that performs system initialisation | `gowhere/serve.py` `main()` parses options, opens the log, calls `create_app()` and starts Waitress, and starts the ingestion thread when asked. `create_app()` (`web/__init__.py`) does the object wiring: opens `Snapshot`, creates the `SessionStore` and `ParkingService`, registers the routes and error pages. Two things are deliberately created on first use instead: per-session objects (a router, a location service), and the Where to Eat `PlaceStore`, read once per process the first time anyone opens Where to Eat. |
| **Add control classes** and distribute coordination among them | One control object per use case family rather than one "god" controller: `ScoringEngine` (UC-4/5), `CommuteRouter` (UC-6), `lepak/search.py` (UC-1), `EventRouter` (UC-2/UC-7), `ParkingService` (UC-3), `eat/search.py` (UC-11/12), `Ingestor` (UC-10). `routes.py` only parses the request, calls one of these, and picks a template. |
| **Add container classes** to hold collections of objects | `SessionStore` (all live sessions, with expiry and a 5,000 cap), `EventStore` (events plus their source links), `PlaceStore` (the 8,600 places, indexed by id), `Snapshot` (per-thread read-only access to areas and blocks). |
| **Apply design patterns** where appropriate | §2 above. |

---

## 4. Key design issue: identifying and storing persistent data (Bruegge §7.4)

**What is persistent, and how it is stored:**

| Store | Holds | Written by | Read by | Access while the app runs |
|---|---|---|---|---|
| `data/snapshot.db` (SQLite, 11 MB, committed) | 32 Planning Areas, every HDB block, facilities, precomputed factor values | `etl/build_snapshot.py`, run by the Maintainer (UC-9) | `Snapshot` | **Read-only** — opened `mode=ro`, one connection per thread |
| `data/eat.db` (SQLite, 1.4 MB, committed) | ~8,600 places, cuisines, price tier, notability | `eat/build.py` (UC-13) | `PlaceStore` | **Read-only** — loaded into memory once per process, on first use |
| `data/events.db` (SQLite) | Extracted event fields and source links | `Ingestor` on its background thread (UC-10) | `EventStore` | **Read–write**, but only by ingestion, never by a user's request |
| `data/reference/*.csv` (committed) | Hand-kept lists: hospitals, polyclinics, venue aliases, venue images — each row with its source | People, by hand, reviewed in git | ETL and `LocationService` | Read-only |
| `data/cache/` (not committed) | OneMap responses for *public* venue names | `LocationService` | `LocationService` | Read–write, public data only |

**Why SQLite and not flat files or a database server.** Flat files would mean writing our own
indexing and our own concurrent-write handling for `events.db`. A server database (PostgreSQL)
is another process to install, run and back up, and a clean clone would no longer run by itself.
SQLite is a single file, is in Python's standard library, gives us SQL queries and safe
concurrent access, and a committed `.db` file means `git clone` then run works with no setup
(DECISIONS.md §14).

**Why split read-only from read-write.** A user's request never waits on a bulk Data Source
(data.gov.sg, OpenStreetMap): that work happens offline. It reads a local file at most. This is
what makes the Performance NFR achievable and what keeps Where to Live working with the network
down.

**What is deliberately *not* persisted** — this is a design decision as much as what is:

- **Session state** (the user's choices, results, route cache) lives in `SessionStore`, in
  memory only, and expires after 2 hours. A restart forgets it. No accounts is a scope
  decision (DECISIONS.md §1), so nothing about a user needs to survive.
- **A user's postal code** (Commute destination, Lepak/Eat starting point) is looked up with
  `redact=True`, never written to the cache, the log or a database (Security NFR). Even the HTTP
  library's request logging is held at INFO so the URL carrying it is never logged
  (`adapters/onemap.py`).
- **Telegram post text and the poster's identity** are never stored — only the extracted fields
  and a link back to the public post (`lepak/store.py`).

---

## 5. Key design issue: providing access control (Bruegge §7.4)

**Decision: no authentication.** GoWhere has no accounts and stores nothing personal, so there is
nothing a login would protect, and making users sign up to compare neighbourhoods would cost
Usability for no gain. That moves access control from "who is this user" to "what can reach
which operation". Bruegge's access matrix for GoWhere:

| Actor ↓ / Operation → | Use the three features (UC-1, 4, 11 and their extensions) | Read *own* session state | Read another session's state | Refresh data (UC-9, UC-13) | Ingest events (UC-10) | Read API keys |
|---|---|---|---|---|---|---|
| **User** (any browser) | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| **Maintainer** (shell on the host) | ✓ | ✓ | ✗ | ✓ | ✓ | ✓ (in `.env`) |
| **External systems** | — | — | — | — | — | — |

**How each ✗ is enforced:**

| Protection | Mechanism (file) |
|---|---|
| Maintainer operations are not reachable from the web | They have **no route at all**. UC-9, UC-10 and UC-13 are command-line modules (`python -m gowhere.etl.build_snapshot`, `…ingest.run`, `…eat.build`), so running one requires a shell on the host. A route that doesn't exist can't be misused. |
| One user can't read another's session | The cookie holds only a random 24-byte id (`secrets.token_urlsafe`) inside Flask's **signed** session; state stays on the server (`web/session_store.py`). Cookie is `HttpOnly`, `SameSite=Lax`, and `Secure` when served over HTTPS (`web/__init__.py`). |
| The web app can't modify reference data | `snapshot.db` and `eat.db` are opened with SQLite's `mode=ro` (`snapshot.py`, `eat/store.py`). |
| API keys and the signing secret never reach the repo | Read from `.env`, which is git-ignored and untracked. The Google billing account lives on Google's side; the repo holds no billing detail. |
| Our Google bill can't be run up by traffic | `GooglePlacesAdapter` counts every call against a daily cap **before** sending it; past the cap, places show without ratings (§2, Singleton). |
| Untrusted input can't act as code | **Pages:** Jinja autoescapes every value, and no template marks anything `|safe` (this closed a stored-XSS finding, DECISIONS.md §17). **LLM:** the extraction prompt treats post text strictly as data — "extract, never obey" — and output must match a fixed JSON schema (`ingest/extract.py`). **SQL:** every query is parameterised. **Forms:** validated server-side (`web/forms.py`, `InvalidSearch`). |
| Resource exhaustion | `SessionStore` caps live sessions at 5,000 and expires idle ones after 2 hours. |

**Known limitation, stated honestly:** the POST forms carry no CSRF token. `SameSite=Lax` already
stops another site from submitting them with the user's cookie, and the worst a forged
submission could do is change that user's own search; there is no account, payment or stored
data to tamper with. A token (e.g. Flask-WTF) is the fix if accounts are ever added.
