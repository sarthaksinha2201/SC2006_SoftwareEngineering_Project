# Class diagram (design model)

Built from the real code in `gowhere/` (class and method names verified against source, not the
Lab 2 placeholder diagram, which predates most of the implementation and all of Where to Eat).
Raw source also lives on its own at [`class-diagram.mmd`](class-diagram.mmd).

```mermaid
classDiagram
    %% GoWhere design class model, built from the real code (gowhere/), not the Lab 2
    %% placeholder names. Every class carries its Fox/Bruegge stereotype and sits in a
    %% Boundary, Control or Entity group. A module of plain functions (web routes,
    %% lepak.search, eat.search, eat.ratings, eat.hours) also carries <<utility>>, UML's
    %% notation for free functions grouped in one place. An <<entity, table>> class is a
    %% database table whose rows the code carries as dicts. The view-model builders are
    %% left out: they only reshape results for the templates.

    namespace Boundary {
        class WebRoutes {
            <<boundary, utility>>
            +live_submit()
            +live_results()
            +lepak_submit()
            +lepak_event(event_id)
            +eat_submit()
            +eat_area(area)
            +eat_place(place_id)
        }
        class OneMapAdapter {
            <<boundary>>
            +tokens TokenSource
            +token bool
            +search(query, page, redact) dict
            +route(start, end, route_type) dict
            +transit_route(start, end, departure) dict
            +drive_route(start, end) dict
        }
        class TokenSource {
            <<boundary>>
            +configured bool
            +get(force_renew) str
        }
        class DataMallAdapter {
            <<boundary>>
            +carpark_availability() list
            +pages(endpoint, max_pages) list
        }
        class LlmAdapter {
            <<boundary>>
            +call_tool(system, user, tool) dict
        }
        class TelegramPostSource {
            <<boundary>>
            +posts(channel, since_post_id) list
        }
        class GooglePlacesAdapter {
            <<boundary>>
            +cap DailyCap
            +find_place_id(name, lat, lon, radius_m) str
            +details(place_id) dict
        }
        class DailyCap {
            <<boundary>>
            +limit int
            +used int
            +take() bool
        }
        class DataGovAdapter {
            <<boundary>>
            +datastore_pages(resource_id, page_size, filters) list
            +download_file(dataset_id, max_polls) dict
        }
        class OverpassAdapter {
            <<boundary>>
            +query(overpass_ql) dict
            +amenities(selectors, bbox) dict
        }
    }

    namespace Control {
        class LepakSearch {
            <<control, utility>>
            +search(events, origin, categories, date_option, mode, max_minutes, router, now, parking) dict
            +sort_and_filter(results, sort, hidden, page) tuple
        }
        class EatSearch {
            <<control, utility>>
            +search(places, origin, cuisines, tiers, when, mode, max_minutes, router, now, parking) dict
            +browse(places, area, cuisines, tiers, now) list
            +sort_and_filter(results, sort, hidden, page, cuisine_filter) tuple
        }
        class EatRatings {
            <<control, utility>>
            +attach(results, adapter)
        }
        class EatHours {
            <<control, utility>>
            +parse(text) Hours
            +status(text, when) dict
        }
        class ScoringEngine {
            <<control>>
            +strategies Dict~str, ScoringStrategy~
            +snapshot Snapshot
            +factors() list
            +compare(areas, choices) dict
        }
        class ScoringStrategy {
            <<control, abstract>>
            +key str
            +label str
            +missing_reason str
            +option_labels dict
            +schema()*
            +precompute(blocks, sources)*
            +meta(sources) dict
            +options(snapshot) dict
            +validate_options(options)
            +category_scores(snapshot, areas, options)* dict
            +raw_values(snapshot, areas, options) dict
            +notes(snapshot, areas, options) dict
            +factor_notes(snapshot, options) list
        }
        class PublicTransportScorer {
            <<control>>
        }
        class HousingAffordabilityScorer {
            <<control>>
        }
        class AmenitiesScorer {
            <<control>>
        }
        class GreeneryScorer {
            <<control>>
        }
        class HealthcareScorer {
            <<control>>
        }
        class CommuteScorer {
            <<control>>
            +router CommuteRouter
        }
        class CommuteRouter {
            <<control>>
            +adapter OneMapAdapter
            +locations LocationService
            +locate(postal) tuple
            +minutes(origins, postal, mode) dict
        }
        class LocationService {
            <<control>>
            +adapter OneMapAdapter
            +offline_postal
            +postal(postal) tuple
            +place(venue, address) dict
            +for_session(offline_postal)$ LocationService
        }
        class EventRouter {
            <<control>>
            +adapter OneMapAdapter
            +route(origin, destination, mode, departure) dict
            +route_many(origin, items, mode, now, departure) dict
        }
        class ParkingService {
            <<control>>
            +adapter DataMallAdapter
            +near(lat, lon) dict
        }
        class Ingestor {
            <<control>>
            +store EventStore
            +llm LlmAdapter
            +locations LocationService
            +run(source, channels, now) dict
        }
    }

    namespace Entity {
        class Snapshot {
            <<entity>>
            +query(sql, params) list
            +meta() dict
            +areas(names) dict
            +postal_location(postal) tuple
        }
        class Neighbourhood {
            <<entity, table>>
            +name str
            +region str
            +in_scope bool
            +n_blocks int
            +n_flats int
            +small_sample bool
        }
        class EventStore {
            <<entity>>
            +events(now) list
            +event(event_id) dict
            +commit_batch(events, channel, last_post_id, now) tuple
            +purge_ended(now) int
            +last_post_id(channel) int
        }
        class Event {
            <<entity, table>>
            +id int
            +title str
            +category str
            +start_at str
            +ends_at str
            +all_day bool
            +venue str
            +place_name str
            +lat float
            +lon float
            +summary str
        }
        class PlaceStore {
            <<entity>>
            +places list
            +meta dict
            +get(place_id) dict
            +load(path)$ PlaceStore
        }
        class Place {
            <<entity, table>>
            +id int
            +name str
            +kind str
            +stalls int
            +price_tier str
            +cuisines list
            +opening_hours str
            +lat float
            +lon float
            +planning_area str
            +wikipedia_title str
            +google_place_id str
        }
        class Hours {
            <<entity>>
            +week dict
            +is_open(when) bool
            +span_at(when) tuple
            +next_opening(when, within_days) datetime
        }
        class FactorChoice {
            <<entity, dataclass>>
            +weight int
            +options dict
        }
        class SessionStore {
            <<entity>>
            +new_id() str
            +get(sid) SessionState
        }
        class SessionState {
            <<entity>>
            +router CommuteRouter
            +locations LocationService
            +event_router EventRouter
            +last_request
            +lepak
            +eat
            +eat_anchor
        }
    }

    %% ==== Web layer: who calls what ====
    WebRoutes --> SessionStore : looks up this browser's state
    WebRoutes --> ScoringEngine : Where to Live
    WebRoutes --> LepakSearch : Where to Lepak
    WebRoutes --> EatSearch : Where to Eat
    WebRoutes --> EatRatings : after each Eat search
    WebRoutes --> EventStore : reads events
    WebRoutes --> PlaceStore : reads places
    WebRoutes --> ParkingService : refreshes on a detail screen

    %% ==== Where to Lepak and Where to Eat ====
    LepakSearch --> EventRouter : route_many
    LepakSearch --> ParkingService : drive mode
    EatSearch --> EventRouter : route_many
    EatSearch --> ParkingService : drive mode
    EatSearch ..> EatHours : opening status
    EatHours ..> Hours : creates
    EatRatings --> GooglePlacesAdapter : details

    %% ==== Where to Live: Strategy pattern ====
    ScoringStrategy <|-- PublicTransportScorer
    ScoringStrategy <|-- HousingAffordabilityScorer
    ScoringStrategy <|-- AmenitiesScorer
    ScoringStrategy <|-- GreeneryScorer
    ScoringStrategy <|-- HealthcareScorer
    ScoringStrategy <|-- CommuteScorer
    ScoringEngine "1" --> "6" ScoringStrategy : dispatches to (interface only)
    ScoringEngine --> Snapshot : reads
    ScoringEngine ..> FactorChoice : takes as input

    %% ==== Shared routing and location services ====
    CommuteScorer --> CommuteRouter : uses
    CommuteRouter --> OneMapAdapter : uses
    CommuteRouter --> LocationService : uses
    LocationService --> OneMapAdapter : uses
    LocationService ..> Snapshot : HDB postal codes when OneMap is down
    EventRouter --> OneMapAdapter : uses
    ParkingService --> DataMallAdapter : uses

    %% ==== Event ingestion (background, off by default) ====
    Ingestor ..> TelegramPostSource : reads posts from
    Ingestor --> LlmAdapter : uses
    Ingestor --> LocationService : uses
    Ingestor --> EventStore : writes

    %% ==== Adapters' helpers ====
    OneMapAdapter --> TokenSource : renews from
    GooglePlacesAdapter --> DailyCap : checks before each call

    %% ==== Stores and their rows ====
    Snapshot "1" --> "*" Neighbourhood : planning_area rows
    EventStore "1" --> "*" Event : event rows
    PlaceStore "1" --> "*" Place : place rows
    Place ..> Hours : opening_hours parsed into

    %% ==== Per-browser-tab session state, in memory only ====
    SessionStore "1" --> "*" SessionState : holds, one per session id
    SessionState "1" --> "1" CommuteRouter : owns (Commute route cache)
    SessionState "1" --> "0..1" LocationService : owns, created on first search
    SessionState "1" --> "0..1" EventRouter : owns, created on first search
```

## Notes

- **Boundary, Control, Entity.** Every class carries its Fox/Bruegge stereotype and sits in the
  matching group:
  - **Boundary**: the actors' side of the system. `WebRoutes` takes the User's requests; each
    Adapter is the system's interface to one External Service actor (OneMap, LTA DataMall, the
    LLM Service, Telegram, Google Places, data.gov.sg, Overpass). `TokenSource` and `DailyCap` are
    parts of their adapters.
  - **Control**: the use cases' logic: the scoring engine and its strategies, the Lepak and Eat
    searches, ratings, opening hours, the routers, `LocationService`, `ParkingService` and
    `Ingestor`.
  - **Entity**: the information the system keeps, in its stores (`Snapshot`, `EventStore`,
    `PlaceStore`), the rows they hold, and per-session state.
- **No `WhereToLiveUI` or `EventSearchController` wrapper classes** (the Lab 2 placeholder names):
  the real web layer is Flask route functions (`gowhere/web/routes.py`) and view-model builder
  functions (`view_models.py`, `lepak_views.py`, `eat_views.py`), not classes. Wrapping them in
  classes would add indirection with no behaviour to justify it — `DECISIONS.md` §4 makes the same
  call explicitly ("Flask stays out of the way... where Django's conventions would fight it").
  The function modules are drawn as `«utility»` classes instead (`WebRoutes` = `web/routes.py`,
  `LepakSearch` = `lepak/search.py`, `EatSearch` = `eat/search.py`, `EatRatings` = `eat/ratings.py`,
  `EatHours` = `eat/hours.py`). `«utility»` is UML's own notation for a module of free functions,
  so the diagram keeps its Boundary and Control roles without inventing classes the code doesn't
  have.
- **`Neighbourhood`, `Event` and `Place` are `«entity, table»`**: each is a database table
  (`planning_area` in `snapshot.db`, `event` in `events.db`, `place` in `eat.db`), with the columns
  the app uses. The code carries each row as a plain `dict` all the way to the templates rather than
  wrapping it in a class: a class with no behaviour beyond field access buys nothing a dict doesn't
  already give. The entity classes that *do* exist in code (`FactorChoice`, `Hours`) earn their keep
  with actual logic (`Hours.is_open`). `Route` and `Carpark` aren't stored at all: they are built per
  request from OneMap and DataMall replies.
- **`EventRouter` is shared** by both Where to Lepak and Where to Eat: `gowhere/lepak/search.py`
  and `gowhere/eat/search.py` both call `route_many` on the same per-session instance
  (`SessionState.event_router`) — the Supportability NFR's "added with only small additive changes
  at the shared seams" claim, in class form.
- **Each session owns its routers.** `SessionState` holds that browser's `CommuteRouter` (with its
  route cache), `LocationService` (its postal-code lookups) and `EventRouter`, in memory only
  (`DECISIONS.md` §17). That is why the app must run as one process.
- **Offline-only adapters.** `DataGovAdapter` and `OverpassAdapter` are used only by the offline data
  builds, never by the running app; `GooglePlacesAdapter.find_place_id` likewise runs only offline
  (`eat/google_ids.py`), while `details` runs at request time through `EatRatings`.
- **`TelegramPostSource`** (`ingest/run.py`) is the Telegram adapter: it wraps the scraper functions
  in `ingest/telegram.py`. `Ingestor.run` takes any object with `posts()`, so tests pass a
  `FilePostSource` instead.
- **`ScoringEngine → ScoringStrategy` is "dispatches to (interface only)"**: the engine never
  imports a concrete scorer; `gowhere/scoring/registry.py` is what lists the six concrete classes.
  Adding a seventh factor touches that registry and nothing else.
