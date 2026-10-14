# Sequence diagrams (S4)

Three diagrams, built against the code as it stands today (`gowhere/`), not the Lab 1
design — class and method names below are copy-checked against the source files named
in each section. UC IDs refer to the Use Case diagram in the Lab 2 deliverable
(`SC2006 Lab2 deliverables.pdf`).

---

## 1. Compare Neighbourhoods with Commute

**UC-4 Compare Neighbourhoods**, extended by **UC-6 Estimate Commute Time** (guard:
Commute factor included), which includes **UC-7 Plan Route**, which includes
**UC-8 Resolve Location**. Sources: `gowhere/web/routes.py` (`live_submit`),
`gowhere/scoring/engine.py` (`ScoringEngine`), `gowhere/scoring/commute.py`
(`CommuteScorer`, `CommuteRouter`), `gowhere/adapters/onemap.py` (`OneMapAdapter`).

```mermaid
sequenceDiagram
    actor User
    participant Routes as routes.live_submit
    participant Engine as ScoringEngine
    participant Strategy as ScoringStrategy
    participant Comm as CommuteScorer
    participant Router as CommuteRouter
    participant OneMap as OneMapAdapter
    participant API as OneMap API

    User->>Routes: POST /live (areas, factor choices)
    Routes->>Engine: compare(areas, choices)

    Note over Engine,Strategy: Strategy stands for whichever concrete class is included:<br/>PublicTransportScorer, HousingAffordabilityScorer,<br/>AmenitiesScorer, GreeneryScorer, HealthcareScorer.<br/>ScoringEngine calls only the ScoringStrategy interface.
    loop for each included factor except Commute
        Engine->>Strategy: category_scores(snapshot, areas, options)
        Strategy-->>Engine: {area: score}
    end

    opt Commute included
        Note over Engine,Comm: «extend» UC-6 Estimate Commute Time<br/>guard: [Commute factor included]
        Engine->>Comm: category_scores(snapshot, areas, options)

        Comm->>Router: locate(destination_postal)
        Note over Router,API: «include» UC-8 Resolve Location
        Router->>OneMap: search(postal)
        OneMap->>API: GET /search
        API-->>OneMap: coordinates
        OneMap-->>Router: (lat, lon)

        Comm->>Router: minutes(origins, postal, mode)
        Note over Router,API: «include» UC-7 Plan Route
        par for each selected area (at most 4), in parallel
            Router->>OneMap: transit_route(origin, destination, departure)
            OneMap->>API: GET /routing
            API-->>OneMap: itineraries
            OneMap-->>Router: duration
        end
        Router-->>Comm: {area: minutes or None}
        Comm-->>Engine: {area: score or None}
    end

    Engine->>Engine: rank areas, compute marginal-contribution explanation
    Engine-->>Routes: result
    Routes-->>User: 303 redirect to /live/results

    Note over User,Routes: GET /live/results calls compare() again to render the page.<br/>CommuteRouter caches by (area, postal, mode) per session,<br/>so this second call does not re-call OneMap (docs/demo.md: 0.0 s reload).
```

**Notes**

- A per-area routing failure returns `None` for that area; the engine then drops
  Commute for every selected area (`ScoringEngine.compare`'s `missing` check) rather
  than only for the one that failed — this is why the factor is "has no data for any
  selected area → dropped for all" in `DECISIONS.md` section 2.
- Routing is parallel (`ThreadPoolExecutor`, `CommuteRouter.minutes`), at most 4 calls
  per comparison (`CommuteRouter.max_workers=4`), far under OneMap's rate limit.

---

## 2. Find Events in Drive Mode

**UC-1 Find Events**, extended by **UC-3 Check Parking Availability** (guard: travel
mode = Drive). Two external services: OneMap API (routing, and resolving the postal
starting point) and LTA DataMall (parking). Sources: `gowhere/web/routes.py`
(`lepak_submit`), `gowhere/lepak/search.py` (`search`), `gowhere/lepak/routing.py`
(`EventRouter`), `gowhere/lepak/parking.py` (`ParkingService`),
`gowhere/adapters/datamall.py` (`DataMallAdapter`).

```mermaid
sequenceDiagram
    actor User
    participant Routes as routes.lepak_submit
    participant Loc as LocationService
    participant OneMap as OneMapAdapter
    participant OMAPI as OneMap API
    participant Search as search()
    participant EvStore as EventStore
    participant Router as EventRouter
    participant Parking as ParkingService
    participant DataMall as DataMallAdapter
    participant LTAAPI as LTA DataMall

    User->>Routes: POST /lepak (categories, date, postal, mode=drive, max_minutes)
    Routes->>Loc: postal(value)
    Loc->>OneMap: search(postal)
    OneMap->>OMAPI: GET /search
    OMAPI-->>OneMap: coordinates
    OneMap-->>Loc: (lat, lon)
    Loc-->>Routes: origin

    Routes->>EvStore: events(now)
    EvStore-->>Routes: stored events
    Routes->>Search: search(events, origin, categories, date_option, "drive", max_minutes, router, now, parking)

    Search->>Search: candidates() — category + date filter
    Search->>Search: within_straight_line() — drops events no mode could reach in time

    Search->>Router: route_many(origin, near, "drive", now)
    par for each surviving event, in parallel
        Router->>OneMap: route(origin, destination, "drive")
        OneMap->>OMAPI: GET /routing
        OMAPI-->>OneMap: route summary
        OneMap-->>Router: minutes, distance, geometry
    end
    Router-->>Search: {event id: route or None}

    opt travel mode = Drive
        Note over Search,LTAAPI: «extend» UC-3 Check Parking Availability<br/>guard: [travel mode = Drive]
        loop for each result
            Search->>Parking: near(lat, lon)
            Parking->>DataMall: carpark_availability()
            Note over Parking,LTAAPI: Whole dataset cached 120 s, shared across all users<br/>(gowhere/lepak/parking.py) — one DataMall call per<br/>results page, not one per event.
            DataMall->>LTAAPI: GET CarParkAvailabilityv2
            LTAAPI-->>DataMall: carpark records
            DataMall-->>Parking: records
            Parking-->>Search: {available, text, carparks}
        end
    end

    Search-->>Routes: {results, counts}
    Routes-->>User: 303 redirect to /lepak/results
```

**Notes**

- Events OneMap could not route (`route is None`) are still kept, marked with their
  straight-line distance as an estimate, and sorted last — never hidden
  (`gowhere/lepak/search.py` docstring, `travel_text` in `lepak_views.py`).
- A DataMall failure (no key, outage, bad reply) returns the same
  `"Parking information unavailable"` for every event and never blocks the results
  from showing (`ParkingService._all`, `UNAVAILABLE`).

---

## 3. Ingest Events

**UC-10 Ingest Events** — initiating actor **NULL** (system-triggered hourly; per
`DECISIONS.md` section 6, no Scheduler actor is drawn, since a scheduler is internal
to the system). Includes **UC-8 Resolve Location** when placing a venue. Sources:
`gowhere/ingest/run.py` (`Ingestor`, `TelegramPostSource`), `gowhere/ingest/telegram.py`
(`fetch_posts`), `gowhere/ingest/extract.py` (`extract_batch`, `validate`, `Discard`),
`gowhere/adapters/llm.py` (`LlmAdapter`).

```mermaid
sequenceDiagram
    participant Run as Ingestor
    participant Source as TelegramPostSource
    participant TG as gowhere.ingest.telegram
    participant TGHost as t.me (Telegram)
    participant Extract as extract_batch()
    participant LLM as LlmAdapter
    participant LLMAPI as LLM Service
    participant Loc as LocationService
    participant OneMap as OneMapAdapter
    participant OMAPI as OneMap API
    participant Store as EventStore

    Note over Run: Triggered hourly by the system's own schedule.<br/>Initiating actor: NULL — no Scheduler actor (DECISIONS.md section 6).

    loop for each channel in the Telegram Channel List
        Run->>Source: posts(channel, since_post_id)
        Source->>TG: fetch_posts(channel, since_post_id)
        TG->>TGHost: GET https://t.me/s/channel[?before=id]
        TGHost-->>TG: post HTML
        TG-->>Source: post records (oldest first)
        Source-->>Run: posts

        Run->>Run: pre-filter (has_date_like_text), batch ~10 posts

        loop for each batch
            Run->>Extract: extract_batch(batch, llm)
            Extract->>LLM: call_tool(system, user, record_events tool)
            LLM->>LLMAPI: POST /messages
            LLMAPI-->>LLM: tool call: events[]
            LLM-->>Extract: extracted items
            Extract-->>Run: [(post, item), ...]

            loop for each extracted item
                alt item passes validate
                    Run->>Run: validate(item, post, now)
                    Run->>Loc: place(venue, address)
                    Note over Loc,OMAPI: «include» UC-8 Resolve Location
                    Loc->>OneMap: search(venue / address)
                    OneMap->>OMAPI: GET /search
                    OMAPI-->>OneMap: coordinates
                    OneMap-->>Loc: place or None
                    alt place found
                        Loc-->>Run: place with lat, lon, name
                        Run->>Run: keep.append(event)
                    else place not found
                        Run->>Run: discard - venue could not be placed on the map
                    end
                else item fails validate
                    Note over Run: Discard reasons - no title, date or location,<br/>undefined category, impossible date, or already ended.
                    Run->>Run: discard(reason), count it, log it
                end
            end

            Run->>Store: commit_batch(keep, channel, last_post_number, now)
            Note over Store: Duplicate events (same date, similar title,<br/>within 200 m) are merged, keeping every source link.
            Store-->>Run: added, merged counts
        end
    end

    Run->>Store: purge_ended(now)
    Run->>Store: record_run(started, finished, counts)
```

**Notes**

- If the LLM call fails (`LlmError`) or OneMap fails while placing a venue
  (`HttpError`), the whole batch is dropped and the channel's marker is **not**
  advanced — those posts are retried on the next run, never skipped
  (`Ingestor._batch`'s `return False` paths).
- Raw post text and the identity of the poster are never stored; only the extracted
  event fields and the source link are (`EventStore.commit_batch`, FR 3.2.6).
