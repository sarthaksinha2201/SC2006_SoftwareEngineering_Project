# System architecture

Built from the architectural decisions already recorded in prose in `DECISIONS.md` §4 — this is
that section as a diagram, not a new decision. Raw source also lives on its own at
[`architecture.mmd`](architecture.mmd).

```mermaid
flowchart TB
    Browser["Browser<br/>(desktop or phone, 390px+)"]

    subgraph Process["One always-on process: python -m gowhere.serve (Waitress)"]
        direction TB

        subgraph WebLayer["Web layer (Flask) -- Boundary"]
            Routes["routes.py<br/>(controllers: live_*, lepak_*, eat_*)"]
            Views["view-model builders<br/>view_models.py / lepak_views.py / eat_views.py"]
            Templates["Jinja templates + static assets<br/>Leaflet, MapLibre, Chart.js -- vendored, never a CDN"]
            Session["SessionStore / SessionState<br/>in-memory, one per browser tab"]
        end

        subgraph LiveFeature["Where to Live"]
            Engine["ScoringEngine"]
            Strategies["6x ScoringStrategy<br/>(Strategy pattern)"]
        end

        subgraph LepakFeature["Where to Lepak"]
            LepakSearch["lepak/search.py: search()"]
        end

        subgraph EatFeature["Where to Eat"]
            EatSearch["eat/search.py: search()"]
        end

        subgraph Shared["Shared services -- Facade"]
            Location["LocationService"]
            CommRouter["CommuteRouter"]
            EvRouter["EventRouter<br/>(shared by Lepak and Eat)"]
            Parking["ParkingService"]
        end

        subgraph AdapterLayer["Adapters -- one per External Service"]
            OneMap["OneMapAdapter"]
            DataMall["DataMallAdapter"]
            LLM["LlmAdapter"]
            Places["GooglePlacesAdapter"]
        end

        Ingestor["Ingestor<br/>(background thread, optional, off by default)"]

        subgraph Stores["Data -- read every request"]
            Snap[("snapshot.db<br/>read-only")]
            Events[("events.db<br/>read-write")]
            PlaceDb[("eat.db<br/>read-only")]
        end
    end

    subgraph Offline["Offline builds -- Maintainer only, never reachable by users"]
        Refresh["build_snapshot.py"]
        EatBuild["eat/build.py"]
    end

    subgraph Sources["Data Sources -- bulk, read offline only"]
        GovData["data.gov.sg, URA, HDB,<br/>LTA static, NParks, MOH, NEA, SFA, NLB"]
        OSM["OpenStreetMap"]
        Wiki["Wikipedia"]
    end

    subgraph External["External Services -- called at request time"]
        OneMapAPI["OneMap API"]
        DataMallAPI["LTA DataMall"]
        LLMAPI["LLM Service"]
        PlacesAPI["Google Places"]
        TelegramAPI["Telegram"]
    end

    Browser --> Routes
    Routes --> Views --> Templates --> Browser
    Routes --> Session

    Routes --> Engine
    Routes --> LepakSearch
    Routes --> EatSearch

    Engine --> Strategies
    Strategies --> CommRouter
    Strategies --> Snap

    LepakSearch --> EvRouter
    LepakSearch --> Parking
    LepakSearch --> Events

    EatSearch --> EvRouter
    EatSearch --> Parking
    EatSearch --> PlaceDb
    EatSearch --> Places

    CommRouter --> Location
    CommRouter --> OneMap
    EvRouter --> OneMap
    Location --> OneMap
    Parking --> DataMall

    Ingestor --> LLM
    Ingestor --> Location
    Ingestor --> Events
    Ingestor --> TelegramAPI

    OneMap --> OneMapAPI
    DataMall --> DataMallAPI
    LLM --> LLMAPI
    Places --> PlacesAPI

    Refresh --> GovData
    Refresh --> Snap
    EatBuild --> OSM
    EatBuild --> Wiki
    EatBuild --> GovData
    EatBuild --> PlaceDb
```

## Notes

- **One process, not a microservice-per-feature split.** `DECISIONS.md` §4: "Two deployments is
  twice the operations work for a 5-week project." Session state in `SessionStore` lives in that
  one process's memory, which is why the deploy guidance in the README insists on a single instance
  with no autoscaling.
- **Two-tier data**: `snapshot.db` and `eat.db` are built offline and read-only at request time;
  `events.db` is the one store written at request time, by `Ingestor` on its own background thread.
  Splitting read-only from read-write data this way is what makes the Performance NFR achievable —
  a request never waits on a bulk Data Source, only (at most) on an External Service.
- **`EventRouter` crosses the Lepak/Eat boundary** deliberately — it's the one piece of this diagram
  that was written for one feature and reused unchanged by a feature that didn't exist yet when it
  was built, which is the Supportability NFR's reuse claim made visible as a diagram edge.
- **Every External Service sits behind its own Adapter.** `DECISIONS.md` §4: "Makes them mockable,
  which the test plan depends on." Swapping the LLM Service provider (Anthropic → OpenAI, partway
  through the project) only ever touched `LlmAdapter`.
