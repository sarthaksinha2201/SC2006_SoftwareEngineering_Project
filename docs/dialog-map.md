# Dialog map

A state machine of UI screens (Fox, Dialog Maps), built from `docs/deliverable/lab4_deliverable_FR_NFR.docx`
(use case descriptions UC-1 through UC-13, revised 26 Oct 2026) and cross-checked against the
routes in `gowhere/web/routes.py`. Supersedes the two-feature dialog map in the Lab 2 deliverable.

**Scope:** User-facing screens only. UC-9 Refresh Static Data, UC-10 Ingest Events and UC-13 Build
Place List are Maintainer-initiated or system-scheduled background procedures with no screen of
their own — they produce the data the screens below read, but neither a User nor this map ever
sees them run. UC-3 Check Parking, UC-6 Estimate Commute, UC-7 Plan Route and UC-8 Resolve Location
are internal `«include»`s with no screen either; their effect (a parking line, a commute score, a
route) shows up inline on the screens that invoke them, noted where relevant below.

```mermaid
stateDiagram-v2
    [*] --> Home

    Home --> LiveSetup : Where to Live
    Home --> LepakSetup : Where to Lepak
    Home --> EatSetup : Where to Eat

    state "Where to Live (UC-4)" as Live {
        [*] --> LiveSetup
        LiveSetup : Pick 2-4 neighbourhoods (map picker or list) then weight what matters
        LiveSetup --> LiveSetup : choose or change areas, factors, weights, options
        LiveSetup --> LiveSetup : invalid submit - wrong area count, no factor included, budget min over max, or an unresolvable postal code (UC-4 E1-E3)
        LiveSetup --> LiveResults : submit [2-4 areas, at least 1 factor, valid inputs]
        LiveResults : Ranked list, bar chart, map, recommendation and explanation
        LiveResults --> LiveSetup : change the comparison (UC-4 A7)
        LiveResults --> LiveBreakdown : request score breakdown (UC-5)
        LiveBreakdown : Per-factor weight, scores, raw values, marginal contribution, excluded factors
        LiveBreakdown --> LiveResults : close
    }

    state "Where to Lepak (UC-1)" as Lepak {
        [*] --> LepakSetup
        LepakSetup : Category wheel (1-8 of 8), remaining criteria reveal once a category is chosen (FR 2.1.1.1)
        LepakSetup --> LepakSetup : choose categories, date, starting point, mode, max time
        LepakSetup --> LepakSetup : invalid submit - unresolvable postal code (UC-1 E1)
        LepakSetup --> LepakSearching : submit [valid]
        LepakSearching : Waiting indicator, shown only past 320 ms (FR 2.2.7)
        LepakSearching --> LepakResults : results ready (or "no events match", UC-1 A3)
        LepakResults : Paginated list, freshness line, photo or category artwork per card
        LepakResults --> LepakResults : sort, show/hide a category, page (no new request, FR 2.4.3)
        LepakResults --> LepakEventRoute : select an event (UC-2)
        LepakEventRoute : Map with start, venue, route, step-by-step directions, parking line inline if travel mode is drive (UC-3)
        LepakEventRoute --> LepakResults : back [restores sort, hidden categories, page]
    }

    state "Where to Eat (UC-11)" as Eat {
        [*] --> EatSetup
        EatSetup : Cuisine/kind filters, mealtime, starting point (manual, or pre-filled from an event, UC-11 A1)
        EatSetup --> EatSetup : edit filters or starting point
        EatSetup --> EatSetup : clear a pre-filled starting point [start=own]
        EatSetup --> EatSetup : invalid submit - unresolvable postal code (UC-11 E1)
        EatSetup --> EatSearching : submit [valid]
        EatSearching : Waiting indicator (shared with Lepak's search path)
        EatSearching --> EatResults : results ready (or "no place matches", UC-11 E3)
        EatResults : Paginated list, rating + review count where available, "not listed" cuisines shown last
        EatResults --> EatResults : sort, show/hide a cuisine group, page (no new request, FR 3.4.3)
        EatResults --> EatPlaceDetails : select a place (UC-12)
        EatPlaceDetails --> EatResults : back [restores sort, hidden cuisines, page]

        EatBrowse : Every place in one neighbourhood, no starting point or routing at all (UC-11 A2) - sort by variety or A-Z only
        EatBrowse --> EatBrowse : filter by cuisine or kind, sort, page (no external call, no routing)
        EatBrowse --> EatPlaceDetails : select a place [no route shown, UC-12 A1]
        EatPlaceDetails --> EatBrowse : back [restores filters, sort, page]

        EatPlaceDetails : Name, hours, rating, notability badge, map with route if one was calculated, parking line inline if travel mode is drive (UC-3)
    }

    LiveResults --> EatBrowse : find places to eat in this neighbourhood (FR 1.6, every joint-ranked neighbourhood)
    LepakEventRoute --> EatSetup : find places to eat near this event (FR 2.7.1, sets the event's location as the starting point)
```

## Notes

- **The map picker and the category wheel are not separate states.** Both are presentation over
  the same form state as the equivalent checkbox list — `LiveSetup` and `LepakSetup` work
  identically with JavaScript disabled, just rendered as a list instead of a map or a wheel. A
  dialog map models screens, not widgets, so this is one state either way.
- **The persistent header** (`GoWhere` · `Where to Live` · `Where to Lepak` · `Where to Eat`) is on
  every page and jumps straight to `Home`, `LiveSetup`, `LepakSetup` or `EatSetup` from anywhere in
  the diagram. Drawing that from all eleven states would make the diagram unreadable, so it's noted
  once here instead of as fourty-some edges.
- **`EatPlaceDetails` is one state reached two ways**, matching UC-12 exactly: from `EatResults`
  with a calculated route, or from `EatBrowse` with no route at all (UC-12 A1) — same screen,
  conditionally missing the map's route layer and the travel-time line.
- **Two cross-feature edges are new since the two-feature dialog map**: `LiveResults -> EatBrowse`
  (FR 1.6) and `LepakEventRoute -> EatSetup` (FR 2.7.1). Both exist because Where to Eat was added
  after Where to Live and Where to Lepak already worked — UC-11's two alternative entries (A1, A2)
  are what make them possible without Where to Eat needing to know anything about the other two
  features beyond a location and a name.
- **`LepakSearching` and `EatSearching`** are genuinely transient — UC-1 and UC-11 share the same
  routing path (`«include» UC-7 Plan Route`) and the same 8-second 90th-percentile target, so the
  waiting indicator is one shared piece of UI, not two.
