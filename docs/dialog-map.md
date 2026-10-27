# Dialog map

A state machine of UI screens (Fox, Dialog Maps), extending the Lab 2 dialog map to all three
features. Built from the use case descriptions in `docs/deliverable/lab4_deliverable_FR_NFR.docx`
(UC-1 through UC-13) and cross-checked against `gowhere/web/routes.py` and the templates. Screens
only — the detail behind each box and arrow (exact FRs, exceptions, wording) lives in the use case
descriptions, not duplicated here.

The raw Mermaid source below also lives on its own at [`dialog-map.mmd`](dialog-map.mmd) — paste it
into the [Mermaid Live Editor](https://mermaid.live) to re-render or export it (PNG, SVG, PDF)
without needing this repo checked out.

Not shown: UC-9, UC-10 and UC-13 (Maintainer-only or scheduled background work, no screen of their
own), and UC-3 Check Parking, UC-6 Estimate Commute, UC-7 Plan Route, UC-8 Resolve Location
(internal `«include»`s with no screen of their own either — UC-3 is extra content on a results
screen when the travel mode is drive, UC-6 is backend scoring, UC-7/UC-8 are routing plumbing).

```mermaid
stateDiagram-v2
    [*] --> Home
    Home --> ConfigureComparison : Choose "Where to Live"
    Home --> SearchCriteria : Choose "Where to Lepak"
    Home --> EatCriteria : Choose "Where to Eat"

    state "Where to Live (UC-4, UC-5, UC-6)" as Live {
        ConfigureComparison : Configure Comparison
        ConfigureComparison --> ConfigureComparison : select areas / weight factors / set options [warns live if a factor would drop]
        ConfigureComparison --> ConfigureComparison : Compare [invalid - area count, missing factor, bad budget]
        ConfigureComparison --> ConfigureComparison : Compare [postal not recognised]
        AllExcluded : All Factors Excluded
        ConfigureComparison --> AllExcluded : Compare [all excluded]
        AllExcluded --> ConfigureComparison : Change factors
        ConfigureComparison --> Scoring : Compare [valid]
        Scoring : Scoring...
        Scoring --> Ranking : results ready
        Ranking : Ranking + Recommendation
        Ranking --> ConfigureComparison : Change comparison
        Ranking --> Breakdown : View breakdown (UC-5)
        Breakdown : Score Breakdown (UC-5)
        Breakdown --> Ranking : Close
    }

    state "Where to Lepak (UC-1, UC-2, UC-3)" as Lepak {
        SearchCriteria : Event Search Criteria
        SearchCriteria --> SearchCriteria : postal not recognised
        SearchCriteria --> LepakSearching : Search [valid]
        LepakSearching : Searching...
        LepakSearching --> EventResults : results found
        LepakSearching --> NoEvents : no matches
        NoEvents : No Events Found
        NoEvents --> SearchCriteria : widen search
        EventResults : Event Results
        EventResults --> EventResults : sort / filter / page
        EventResults --> EventRoute : select an event
        EventRoute : Event Route Map (UC-2)
        EventRoute --> EventResults : Back (restores view)
    }

    state "Where to Eat (UC-11, UC-12, UC-3)" as Eat {
        EatCriteria : Eat Search Criteria
        EatCriteria --> EatCriteria : postal not recognised
        EatCriteria --> EatSearching : Search [valid]
        EatSearching : Searching...
        EatSearching --> PlaceResults : results found
        EatSearching --> NoPlaces : no matches
        NoPlaces : No Places Found
        NoPlaces --> EatCriteria : widen search
        PlaceResults : Place Results
        PlaceResults --> PlaceResults : sort / filter / page
        PlaceResults --> PlaceDetails : select a place
        Browse : Browse Neighbourhood
        Browse --> Browse : filter / sort / page
        Browse --> PlaceDetails : select a place
        PlaceDetails : Place Details (UC-12)
        PlaceDetails --> PlaceResults : Back (restores view)
        PlaceDetails --> Browse : Back (restores view)
    }

    Ranking --> Browse : Find eats here (FR 1.6)
    EventRoute --> EatCriteria : Find eats nearby (FR 2.7.1)

    classDef highlight fill:#ddd,stroke:#333,stroke-width:2px
    class Ranking highlight
```

## Notes

- **The persistent header** (`GoWhere` · `Where to Live` · `Where to Lepak` · `Where to Eat`) is on
  every screen in this diagram and jumps straight to `Home` or any feature's entry state from
  anywhere. Not drawn as edges from all eleven states — that's the one thing this map leaves to the
  header rather than to an arrow.
- **`Configure Comparison` is one screen**, not two: the built `/live` page is a single form —
  the neighbourhood picker, all six factor panels and Compare together — so there's no separate
  "select neighbourhoods" step to transition out of.
- **Map picker / category wheel are not states.** Both drive the same form as the equivalent
  checkbox list — one state either way.
- **`No Events Found` / `No Places Found`** replace Lab 2's `Too Many Events`: the current system no
  longer refuses above a cap, it routes the 25 nearest and says how many were in reach, so there's
  no longer a dead-end screen for that case.
- **`Place Details` is one screen, reached two ways** (UC-12): with a route, from `Place Results`;
  without one, from `Browse`.
- **FR 1.4.3** ("nearly tied") is a wording detail on the `Ranking` screen, not a state of its own,
  so it isn't drawn separately.
- **Two edges are new since Lab 2**: `Ranking -> Browse` and `Event Route -> Eat Criteria`, both
  added for the third feature.
