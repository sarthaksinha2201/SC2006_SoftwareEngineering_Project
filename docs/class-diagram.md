# Class diagram (design model)

Built from the real code in `gowhere/` (class and method names verified against source, not the
Lab 2 placeholder diagram, which predates most of the implementation and all of Where to Eat).
Raw source also lives on its own at [`class-diagram.mmd`](class-diagram.mmd).

```mermaid
classDiagram
    %% GoWhere design class model, built from the real code (gowhere/), not the Lab 2
    %% placeholder names. Grouped by Fox/Bruegge stereotype. A plain function (web
    %% routes, lepak.search.search(), eat.search.search(), the view-model builders) is
    %% not shown here -- see docs/architecture.mmd for where those sit as components.

    %% ==== Strategy: Where to Live scoring ====
    class ScoringStrategy {
        <<abstract>>
        +key str
        +label str
        +missing_reason str
        +schema()*
        +precompute(blocks, sources)*
        +options(snapshot) dict
        +validate_options(options)
        +category_scores(snapshot, areas, options)* dict
        +raw_values(snapshot, areas, options) dict
        +notes(snapshot, areas, options) dict
    }
    class PublicTransportScorer
    class HousingAffordabilityScorer
    class AmenitiesScorer
    class GreeneryScorer
    class HealthcareScorer
    class CommuteScorer {
        +router CommuteRouter
    }
    ScoringStrategy <|-- PublicTransportScorer
    ScoringStrategy <|-- HousingAffordabilityScorer
    ScoringStrategy <|-- AmenitiesScorer
    ScoringStrategy <|-- GreeneryScorer
    ScoringStrategy <|-- HealthcareScorer
    ScoringStrategy <|-- CommuteScorer

    class ScoringEngine {
        +strategies Dict~str, ScoringStrategy~
        +snapshot Snapshot
        +factors() list
        +compare(areas, choices) dict
    }
    ScoringEngine "1" --> "*" ScoringStrategy : dispatches to (interface only)
    ScoringEngine --> Snapshot : reads
    ScoringEngine ..> FactorChoice : takes as input

    class FactorChoice {
        <<dataclass>>
        +weight int
        +options dict
    }

    %% ==== Control: shared routing and location services ====
    class CommuteRouter {
        +adapter OneMapAdapter
        +locations LocationService
        +locate(postal) tuple
        +minutes(origins, postal, mode) dict
    }
    CommuteScorer --> CommuteRouter : uses
    CommuteRouter --> OneMapAdapter : uses
    CommuteRouter --> LocationService : uses

    class LocationService {
        +postal(postal) tuple
        +place(venue, address) dict
        +for_session(offline_postal)$ LocationService
    }
    LocationService --> OneMapAdapter : uses

    class EventRouter {
        +adapter OneMapAdapter
        +route(origin, destination, mode, departure) dict
        +route_many(origin, items, mode, now) dict
    }
    EventRouter --> OneMapAdapter : uses

    class ParkingService {
        +adapter DataMallAdapter
        +near(lat, lon) dict
    }
    ParkingService --> DataMallAdapter : uses

    %% ==== Control: event ingestion ====
    class Ingestor {
        +store EventStore
        +llm LlmAdapter
        +locations LocationService
        +run(source, channels, now) dict
    }
    Ingestor --> LlmAdapter : uses
    Ingestor --> LocationService : uses
    Ingestor --> EventStore : writes

    %% ==== Adapter: external services, one per service ====
    class OneMapAdapter {
        +token TokenSource
        +search(query, page, redact) dict
        +route(start, end, route_type) dict
        +transit_route(start, end, departure) dict
        +drive_route(start, end) dict
    }
    class TokenSource {
        +configured bool
        +get(force_renew) str
    }
    OneMapAdapter --> TokenSource : renews from

    class DataMallAdapter {
        +carpark_availability() list
    }

    class LlmAdapter {
        +call_tool(system, user, tool) dict
    }

    class GooglePlacesAdapter {
        +cap DailyCap
        +find_place_id(name, lat, lon, radius_m) str
        +details(place_id) dict
    }
    class DailyCap {
        +limit int
        +used int
        +take() bool
    }
    GooglePlacesAdapter --> DailyCap : checks before each call

    %% ==== Container / store: persistent data, read each request ====
    class Snapshot {
        +query(sql, params) list
        +meta() dict
        +areas(names) dict
        +postal_location(postal) tuple
    }
    class EventStore {
        +events(now) list
        +event(event_id) dict
        +commit_batch(events, channel, last_post_id, now) tuple
        +purge_ended(now) int
        +last_post_id(channel) int
    }
    class PlaceStore {
        +places list
        +meta dict
        +get(place_id) dict
        +load(path)$ PlaceStore
    }
    PlaceStore ..> Hours : parsed at display time

    class Hours {
        +week dict
        +is_open(when) bool
        +span_at(when) tuple
        +next_opening(when, within_days) datetime
    }

    %% ==== Boundary: per-browser-tab session state ====
    class SessionStore {
        +new_id() str
        +get(sid) SessionState
    }
    class SessionState {
        +last_request
        +lepak
        +eat
        +router
    }
    SessionStore "1" --> "*" SessionState : holds, one per session id
```

## Notes

- **Why no `WhereToLiveUI`, `EventSearchController` etc.** (the Lab 2 placeholder boundary/control
  classes): the real web layer is Flask route functions (`gowhere/web/routes.py`) and view-model
  builder functions (`view_models.py`, `lepak_views.py`, `eat_views.py`), not classes. Wrapping them
  in classes would add indirection with no behaviour to justify it — `DECISIONS.md` §4 makes the same
  call explicitly ("Flask stays out of the way... where Django's conventions would fight it").
  These are shown as components in the architecture diagram instead.
- **Why no `Neighbourhood`, `Event`, `Place`, `Route`, `Carpark` entity classes**: these are rows
  from SQLite, carried as plain `dict`s all the way to the templates. A class with no behaviour
  beyond field access buys nothing a dict doesn't already give for free — the real entity-like
  classes that *do* exist (`FactorChoice`, `Hours`, `TokenSource`, `DailyCap`) all earn their keep
  with actual logic (`Hours.is_open`, `TokenSource.get`'s renewal, `DailyCap.take`'s daily reset).
- **`EventRouter` is shared** by both Where to Lepak and Where to Eat (`gowhere/lepak/search.py`
  and `gowhere/eat/search.py` each call `route_many` through their own instance) — the Supportability
  NFR's "added with only small additive changes at the shared seams" claim, in class form.
- **`ScoringEngine → ScoringStrategy` is "dispatches to (interface only)"**: the engine never
  imports a concrete scorer; `gowhere/scoring/registry.py` is what lists the six concrete classes.
  Adding a seventh factor touches that registry and nothing else.
