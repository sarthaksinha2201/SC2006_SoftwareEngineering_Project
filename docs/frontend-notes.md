# Notes for whoever builds the web front end

## Warn before submit when a factor will be dropped

A factor is dropped for every selected area when any one of them lacks data for it (DECISIONS.md section 2). The commonest case is Housing Affordability with a small area: Tanglin, Downtown Core and Changi have fewer than 10 resales of most flat types. Users should learn this while they are choosing, not after they submit.

`ScoringEngine.compare()` takes milliseconds for every factor except Commute, which calls OneMap. So on each change to the setup screen:

1. Call `engine.compare(areas, choices)` with the `"commute"` entry removed from `choices`.
2. Read `result["dropped"]`: a list of `{"key", "label", "missing_for": [area, ...]}`.
3. If every included factor is dropped, `compare` raises `NoFactorsLeft`. Its `.dropped` attribute has the same list.

Name the area and the reason, never a generic message. For example: "Housing Affordability will be left out because Tanglin had fewer than 10 matching resales." The results page must use `missing_for` the same way.

## Where the other things you need live in a result

- **Notes about one area:** `area["notes"]` (small-area note, rail-data note). Wording is in `gowhere/scoring/notes.py`.
- **Notes about a factor as a whole:** `result["factors"][i]["notes"]` (hospital scope, GP data age, resale window, supermarket list and OpenStreetMap sources, commute method).
- **Display values:** `area["overall_display"]` and `area["category_display"]`, already rounded half-up to 1 d.p. Never round the raw values yourself with Python's `round()`.
- **Options for the setup screen:** `engine.factors()` lists every factor's options. Each is one of: a list of choices, `{"min", "max"}`, `{"pattern", "description"}` or `{"any_of": [...]}`.

## Commute and the destination postal code (Security NFR)

- Create one `CommuteRouter` per user session and pass it to `default_strategies(commute_router)`. Keep it in server memory only.
- **Never** put the postal code in a URL query string, in Flask's cookie session, or in a log line.
- Post it in a form body, and hold it with the router in a server-side, in-memory session.
