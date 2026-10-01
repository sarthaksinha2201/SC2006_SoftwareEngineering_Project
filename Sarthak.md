# Work Assignment — Sarthak

GoWhere (SC2006 Team 5). Four tasks, in priority order. Each one is self-contained: you can finish and verify it without waiting for the other half of the project.

**Read `DECISIONS.md` first** — it has every design decision and the reasoning behind it.

**Stack (already decided):** Python 3.13, Flask, SQLite, Jinja templates, Leaflet (maps), Chart.js (charts). Your `transport test/app.py` prototype confirmed Flask works for this, so we're continuing with it.

**Ground rules**
- Each task lists an **acceptance check** — a command you run that proves it works. Don't hand over a task until its check passes.
- Don't change files outside your task's listed outputs. We're working in the same repo.
- Commit to a branch per task (`feat/s1-data-acquisition`, etc.), not to `main`.
- If a contract below seems wrong, say so before building — changing it later breaks the other half.

---

## S1 — Raw data acquisition (do this first)

**Goal:** one module that downloads every source dataset we need and caches it locally, so nothing downstream ever hits the network.

**Why it's yours:** completely self-contained, and correctness is easy to prove — record counts either match or they don't.

**Datasets to fetch** (all from data.gov.sg unless noted):

| Dataset | ID / source | Notes |
|---|---|---|
| HDB Property Information | `d_17f5382f26140b1fdae0ba2ef6239d2f` | 13,357 records, paginated. Verified working. |
| LTA MRT Station Exit (GEOJSON) | `d_b39d3a0871985372d7e1637193335da5` | Verified working. |
| HDB resale transactions | `d_8b84c4ee58e3cfc0ece0d773c8ca6abc` | **Verified.** Filter to the 12 complete calendar months before the fetch date — the current month is partial and must be excluded. Record the window in the manifest. Check each month's record count against the API's own total, so a page lost to rate limiting can't pass as a quiet month. |
| URA Master Plan 2019 Planning Area Boundary (No Sea) | find the dataset ID | GeoJSON; downloaded as a file, not via datastore_search |
| Parks & park connectors | NParks datasets on data.gov.sg | |
| CHAS clinics, polyclinics, hospitals | MOH / data.gov.sg | Three separate files is fine |
| Hawker centres (NEA) | `d_4a086da0a5553be1d89383cd90d07ecd` | **Verified.** 123 open; 6 under construction are excluded |
| Supermarkets (SFA) | `d_11edd0117280c5776651d7891114c88c` | **Verified.** Addresses only, no coordinates — the ETL geocodes them |
| Libraries (NLB) | OneMap theme `libraries` | **Use the OneMap theme, not data.gov.sg's Libraries GeoJSON** — that one last changed in April 2019 and predates Punggol Regional Library |
| Bus stops + services | LTA DataMall (static datasets) | Needs a DataMall account key — do the others first |
| OSM amenities (malls, gyms, cafés) | Overpass API, bbox over Singapore | No key needed, but it **requires a User-Agent header** or returns 406. Tags are in `config.OSM_AMENITY_TAGS` |

**Two API shapes on data.gov.sg** (both verified against the live API today):
- **Tabular data** → `https://data.gov.sg/api/action/datastore_search?resource_id=<id>&limit=<n>&offset=<n>`. Response has `result.total` and `result.records`. Page until you've collected `total`.
- **Geospatial/file data** → the newer poll-based download API: initiate a download, poll until ready, then fetch the returned URL.

**Output contract** — these names and shapes are **fixed**; the ETL already reads them, so changing one breaks the build.
```
data/raw/hdb_property_information.json    # paginated: a JSON LIST of page responses, unmodified
data/raw/lta_mrt_station_exits.json       # single response
data/raw/ura_mp2019_planning_areas.json   # single response
data/raw/<other_dataset>.json             # same convention
data/raw/_manifest.json                   # per dataset: source id/url, fetch timestamp, record count
```
For a paginated `datastore_search` dataset, store the **list of page responses exactly as returned** — do not merge or flatten them.

**Verified dataset IDs** (confirmed against the live metadata API — don't re-derive these):
- HDB Property Information: `d_17f5382f26140b1fdae0ba2ef6239d2f` (13,357 records, of which 10,796 are residential)
- LTA MRT Station Exit (GEOJSON): `d_b39d3a0871985372d7e1637193335da5` (613 exits, 190 stations, includes LRT)
- URA Master Plan 2019 Planning Area Boundary (No Sea): `d_4765db0e87b9c86336792efe8a1f7a66` (55 features, area name in property `PLN_AREA_N`)
- HDB resale transactions: `d_8b84c4ee58e3cfc0ece0d773c8ca6abc` (raw name `hdb_resale_prices`; 24,590 records in the current 12-month window)

**Poll-download API** (for geospatial/file datasets): `https://api-open.data.gov.sg/v1/public/api/datasets/<id>/initiate-download`, then poll `/poll-download`. **`initiate-download` returns HTTP 201, not 200** — don't treat that as a failure.

**Note:** `gowhere/etl/_temp_fetch_raw.py` is a temporary stand-in fetching the datasets listed above. Delete it when your `fetch_raw.py` lands. It's deliberately named differently so you won't collide with it.
Write raw responses **unmodified**. No cleaning, no renaming fields, no filtering (except the resale 12-month window). Cleaning happens in the ETL, which is my half — if you clean here, we can't debug where a wrong number came from.

**Acceptance check**
```bash
python -m gowhere.etl.fetch_raw --all
python -c "import json;m=json.load(open('data/raw/_manifest.json'));[print(k, v['record_count']) for k,v in m.items()]"
```
Passes when every dataset appears in the manifest with a non-zero count, HDB shows **13357**, and re-running the command does not re-download datasets already cached (unless `--force`).

**Out of scope:** geocoding, distance calculations, anything spatial. Don't touch `data/snapshot.db`.

---

## S2 — Telegram channel scraper

**Goal:** turn public Telegram channels into structured post records. Scraping only — **no LLM work**, that's my half.

**Why it's yours:** clean input/output boundary, and it's fully testable offline once you've saved fixtures.

**How:** public channels expose a readable web view at `https://t.me/s/<channel>` — plain server-rendered HTML, no login, no API key, no Telegram account. Use `requests` + BeautifulSoup. **Do not** use the Telegram API or a headless browser; both were considered and rejected (see `DECISIONS.md`).

**Channels** (verified usable):
- `sgweekend` — ~4–5 posts/week
- `sgwhereto` — ~3–5 posts/week

Not `sgnightlife` — it's a group, not a broadcast channel, and has no post feed. When more channels arrive, the test is: can you open `t.me/s/<name>` in a browser and see posts?

**Output contract** — one record per post:
```json
{
  "channel": "sgweekend",
  "post_id": "sgweekend/1234",
  "posted_at": "2026-09-28T14:03:00+08:00",
  "text": "full post text with emoji preserved",
  "links": ["https://..."],
  "source_url": "https://t.me/sgweekend/1234"
}
```
Sorted oldest first. The scraper takes a `since_post_id` per channel and returns only newer posts — we run this every 6 hours and must not reprocess old posts.

**Exact function the ingestion pipeline already calls:**
```python
gowhere.ingest.telegram.fetch_posts(channel: str, since_post_id: str | None = None) -> list[dict]
# e.g. fetch_posts("sgweekend", since_post_id="sgweekend/1234")  → records oldest first
```
Match that name and signature. If you have a good reason to change it, say so first — `TelegramPostSource` is the only place that would need updating, but it's still a coordination cost.

**Also required: fixtures.** Save the raw HTML of at least 20 posts to `tests/fixtures/telegram/*.html` and write tests that parse those files. Your tests must pass with the network off — that's the whole point.

**Acceptance check**
```bash
python -m gowhere.ingest.telegram --channel sgweekend --limit 20
pytest tests/test_telegram_scraper.py     # must pass with wifi off
```
Passes when: 20 records come back with correct timestamps and non-empty text; passing `since_post_id` returns only newer posts; and the fixture tests pass offline.

**Out of scope:** extracting events (title, date, venue) from post text — that's the LLM step, mine. You hand me post text; I hand back events.

---

## S3 — Front-end templates

**Goal:** the six screens as Jinja templates + CSS, built against mock JSON. No backend logic.

**Why it's yours:** visual work is checked by looking at it, and it's the most decoupled piece in the project.

**Screens**
1. **Home** — choose Where to Live or Where to Lepak
2. **Where to Live — setup** — neighbourhood picker (2–4, enforced), six factor cards each with include/exclude toggle + weight slider 1–10 (default 5) + that factor's options

   **Factor labels — use exactly these:** Public Transport · Housing Affordability · Amenities · Greenery · Healthcare · Commute. The first one is **"Public Transport"**, never "Transport" — "Transport" reads as though it includes driving, when the factor measures walking access to MRT/LRT and buses. Same name in code identifiers, CSS classes, and JSON keys (`public_transport`).
3. **Where to Live — results** — ranked list (overall + category scores + raw values), grouped bar chart (Chart.js), map with shaded boundaries (Leaflet), recommendation banner, "see how this was calculated" modal. Areas with very few HDB blocks must show a small-area note, e.g. *"Changi — 412 flats across 4 blocks. Scores are based on a small number of blocks."* The block and flat counts come from the results JSON; don't hard-code which areas get the note.
4. **Lepak — search** — categories (1–4), date option, starting point (postal code or "use my location"), travel mode, max travel time
5. **Lepak — results** — cards with title/category/date/venue/travel time/route summary/source link; sort dropdown; category chips; 10 per page
6. **Event detail** — map with route line + step-by-step directions

Plus shared error and empty states.

**Requirements**
- **Responsive** — must work on a phone browser. We demo Lepak on a phone.
- Every page carries the attribution footer: *Map and location data from OneMap (SLA) · Amenity data © OpenStreetMap contributors · Government data from data.gov.sg*
- Escape all event text on output. Event titles come from public Telegram posts and are untrusted input.
- **Leaflet and Chart.js must be downloaded into `gowhere/web/static/`, never loaded from a CDN.** The demo may be run with the network off — a grader unplugging the wifi is a realistic test of our Reliability NFR — and CDN-loaded libraries would make every map and chart vanish. (Basemap tiles can't be bundled, so offline the area outlines draw on a blank background. That's expected; the shapes still render.)
- **Never put a postal code in a URL query string or in Flask's cookie session.** The Security NFR says the user's postal code and device location are held for the session only and never stored or logged — a query string lands in browser history and server access logs, and Flask's default session is a cookie sent to the browser. Keep it in server-side memory. (The ETL side has already been hardened for this: OneMap echoes request coordinates back in its responses and in connection-error text, so those are redacted before logging.)

**Mock data:** I'll commit `tests/fixtures/mock_results.json` matching the real response shape. Build against that; the swap to live data should be a one-line change in the view.

**Acceptance check:** `flask run`, then click through all six screens with mock data, in a desktop browser and a phone-sized viewport. No console errors.

**Out of scope:** scoring, routing, database queries.

---

## S4 — Design documents

**Goal:** the diagrams and test tables for the next deliverable.

- **Sequence diagrams** (you've started). Three: (a) Compare Neighbourhoods with commute included — shows the `«extend»` to UC-6, the `«include»` chain into UC-7/UC-8, and an external call; (b) Find Events in drive mode — two external services plus the parking `«extend»`; (c) Ingest Events — the scheduled trigger, the LLM, and the validate-or-discard branch. Between them, every relationship in the use case diagram appears at least once. Send them to me when drafted and I'll review before submission.
- **Black-box test case table.** Equivalence partitioning + boundary values, taken from the FR document, which already states every boundary: neighbourhoods selected (1/2/4/5), weights (0/1/10/11), categories selected (0/1/4/5), postal code (5/6/7 digits), budget min > max. One row per case: input, expected result, FR reference.

---

## What I'm handling (don't start these)

ETL geospatial pipeline (geocoding, point-in-polygon, distance calculations, flat-weighting) · scoring engine and the Strategy classes · LLM event extraction and schema validation · OneMap routing and LTA parking adapters · integration and the golden test.

---

## Suggested order

**Week 1:** S1, then start S3.
**Week 2:** S2, finish S3.
**Week 3:** S4, plus fixing whatever integration turns up.

Message me before starting anything not on this list.

---

## Known traps — read before starting each task

These are problems we've already hit or can see coming. Each one cost us time somewhere else in the project.

### S1 — data acquisition
- **`data/raw/` is already populated** by the temporary fetcher, and the ETL reads it right now. Don't overwrite it until your output is byte-compatible. Check by running `pytest` after your first fetch — if the ETL tests fail, your file shape is different, not theirs.
- **Bus stops need an LTA DataMall account key**, which nobody has registered for yet. Do every other dataset first and flag this rather than being blocked by it.
- **Record each dataset's own last-updated date in the manifest**, not just your fetch time. They are often years apart — the CHAS clinic data's listing page says June 2024 while the records themselves say September 2021, and we need the real one to show users.
- **Don't filter or clean anything** except the resale 12-month window. Hawker centres include 6 under construction, and the supermarket list includes minimarts — the ETL decides what to exclude, not you. If you filter here, a number gets wrong later and nobody can tell where.
- **A rate-limited page can look like a quiet month.** For any paginated dataset, check the records you collected against the API's own `total`, and fail loudly if they differ.

### S2 — Telegram scraper
- **`t.me/s/<channel>` shows only about 20 recent posts.** Older ones need pagination (a `before=` parameter). Check this on day one — if you only ever get one page, `since_post_id` is untestable.
- **Timestamps in the HTML are UTC.** Singapore is UTC+8, so a post at 23:00 SGT reads as the previous day if you don't convert. This will silently put events on the wrong date.
- **Some posts are media-only with no text**, and some may be truncated in the web view. Skip empty ones; verify whether long posts are cut off before assuming you have the full text.
- **Posts get edited and deleted.** `post_id` must come from the post's own link, never from its position on the page.
- Only **2 channels are confirmed usable** (`sgweekend`, `sgwhereto`). Don't build assumptions that need 10.

### S3 — templates
- **Wait for `tests/fixtures/mock_results.json`** — it's being written now and is the contract. Building against invented JSON means rework.
- **There are a lot of notes to display**, and they'll swamp the page if each is styled differently. Design *one* note component and reuse it. Expect: a small-area note, a far-from-rail note, a dropped-factor message naming the area and reason, and per-factor notes for commute (timing assumptions), healthcare (hospital rule, CHAS date) and housing (the transaction window).
- **A factor can be missing entirely.** Every results template must handle a factor that was dropped for all areas — not as an error state, as normal.
- **Never put a postal code in a URL or the cookie session** (see the S3 requirements above). This is a Security NFR commitment.

### S4 — diagrams and test tables
- **The design changed after the use case diagram.** Sequence diagrams must match what exists: a `ScoringStrategy` interface with one class per factor, a `ScoringEngine` that knows only that interface, and an adapter per external service (OneMap, LTA DataMall, Telegram, LLM). Check the class names in `gowhere/` before drawing — a diagram that doesn't match the code is worse than no diagram.
- **Boundaries changed too.** Weights are **1–10**, not 0–10 (exclude is a separate control). Neighbourhoods are **2–4**. Event categories are **1–4**. Use the current numbers from the FR document, not the Lab 1 version.
