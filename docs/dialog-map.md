# Dialog map

A state machine of UI screens (Fox, Dialog Maps), extending the Lab 2 dialog map to all three
features. Built from the use case descriptions in `lab3/lab3_FR_NFR.docx`
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
        ConfigureComparison --> ConfigureComparison : edit [warns if a factor would drop]
        ConfigureComparison --> Scoring : Compare
        Scoring : Scoring...
        Scoring --> ConfigureComparison : [invalid input]
        Scoring --> AllExcluded : [all excluded]
        AllExcluded : All Factors Excluded
        AllExcluded --> ConfigureComparison : Change factors
        Scoring --> Ranking : [valid] results ready
        Ranking : Ranking + Recommendation
        Ranking --> ConfigureComparison : Change comparison
        Ranking --> Breakdown : View breakdown (UC-5)
        Breakdown : Score Breakdown (UC-5)
        Breakdown --> Ranking : Close
    }

    state "Where to Lepak (UC-1, UC-2, UC-3)" as Lepak {
        SearchCriteria : Event Search Criteria
        SearchCriteria --> LepakSearching : Search
        LepakSearching : Searching...
        LepakSearching --> SearchCriteria : [invalid input]
        LepakSearching --> EventResults : [valid] results found
        LepakSearching --> NoEvents : [valid] no matches
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
        EatCriteria --> EatSearching : Search
        EatSearching : Searching...
        EatSearching --> EatCriteria : [invalid input]
        EatSearching --> PlaceResults : [valid] results found
        EatSearching --> NoPlaces : [valid] no matches
        NoPlaces : No Places Found
        NoPlaces --> EatCriteria : widen search
        PlaceResults : Place Results
        PlaceResults --> PlaceResults : sort / filter / page
        PlaceResults --> PlaceDetails : select a place
        Browse : Browse Neighbourhood
        Browse --> Browse : filter / sort / page
        Browse --> PlaceDetails : select a place
        Browse --> EatCriteria : Search from a starting point
        PlaceDetails : Place Details (UC-12)
        PlaceDetails --> PlaceResults : Back to results (restores view)
        PlaceDetails --> Browse : Back to the neighbourhood (restores view)
    }

    Ranking --> Browse : Find eats here (FR 1.6)
    Browse --> Ranking : Back to the comparison
    EventRoute --> EatCriteria : Find eats nearby (FR 2.7.1)

    classDef highlight fill:#ddd,stroke:#333,stroke-width:2px
    class Ranking highlight
```

## Notes

- **The persistent header** (`GoWhere` · `Where to Live` · `Where to Lepak` · `Where to Eat`) is on
  every screen in this diagram and jumps straight to `Home` or any feature's entry state from
  anywhere. Not drawn as edges from all 17 states — that's the one thing this map leaves to the
  header rather than to an arrow.
- **`Configure Comparison` is one screen**, not two: the built `/live` page is a single form —
  the neighbourhood picker, all six factor panels and Compare together — so there's no separate
  "select neighbourhoods" step to transition out of.
- **Map picker / category wheel are not states.** Both drive the same form as the equivalent
  checkbox list — one state either way.
- **`Scoring...` / `Searching...` are where validation happens.** Each is the loading overlay on the
  form, shown while the server checks the request. Errors (a bad area count, a postal code OneMap
  doesn't know, OneMap being unreachable) are only found there, so they are drawn as edges out of
  the loading state back to the form, with the error shown on it. `[invalid input]` covers:
  - Live: area count, a factor with no options chosen, a bad budget, a Commute postal code that
    isn't recognised.
  - Lepak: categories, date, travel mode, travel time, a postal code that isn't recognised, OneMap
    unreachable.
  - Eat: cuisines, kinds of place, mealtime, travel mode, travel time, a postal code that isn't
    recognised, OneMap unreachable.

  The one check made before Compare is the live "this factor would be dropped" warning on
  `Configure Comparison` (the `edit` self-loop: selecting areas, weighting factors, setting
  options).
- **`No Events Found` / `No Places Found` are the results screen with nothing on it** — the same
  page as `Event Results` / `Place Results`, showing a note instead of cards. They are drawn as
  states because what the user can do next is different. They replace Lab 2's `Too Many Events`:
  the current system no longer refuses above a cap, it routes the 25 nearest and says how many were
  in reach, so there's no longer a dead-end screen for that case.
- **`Place Details` is one screen, reached two ways** (UC-12): with a route, from `Place Results`;
  without one, from `Browse`. Its Back link returns to whichever screen opened it, with that
  screen's sort, filters and page kept.
- **Not-found pages are not drawn.** `Event not found`, `Place not found` and `Neighbourhood not
  found` are only reached from a stale or hand-typed link (an event purged after it ended, for
  example), not from any arrow on this map. Each one leads back to its own feature's entry state.
- **FR 1.4.3** ("nearly tied") is a wording detail on the `Ranking` screen, not a state of its own,
  so it isn't drawn separately.
- **Three edges cross between features**, all new since Lab 2 and all added for the third
  feature: `Ranking -> Browse`, its way back `Browse -> Ranking`, and `Event Route -> Eat Criteria`.
