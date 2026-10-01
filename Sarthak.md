# Work Assignment — Sarthak

GoWhere (SC2006 Team 5). **Updated 1 Oct** — the backend is now built and merged to `main`, so this brief has changed. S1 is mostly done; your highest-value task is now **S2**.

**Read `DECISIONS.md` first** — every design decision with its reasoning. **`docs/`** has the technical write-ups (`demo.md` is the runbook, `web.md` describes the routes and page contracts, `frontend-notes.md` is written for you).

**Stack:** Python 3.13, Flask, SQLite, Jinja, Leaflet, Chart.js. 323 tests pass offline — run `.venv/bin/python -m pytest -q` before and after your changes.

## Status at a glance

| Task | State | Priority |
|---|---|---|
| **S1** Data acquisition | **Mostly done** — 12 datasets already fetched. Only bus stops remain, blocked on a key | Low |
| **S2** Telegram scraper | **Not started — nothing else can produce live events** | **1st** |
| **S3** Templates | **Not started** — the contract and placeholders are ready for you | **2nd** |
| **S4** Diagrams + test tables | **Not started** — must match the refactored code, not the Lab 1 design | **3rd** |

## Ground rules

- Each task has an **acceptance check**. Don't hand it over until that passes.
- Branch per task (`feat/s2-telegram`, ...), then merge to `main`.
- If a contract below looks wrong, say so *before* building — changing it afterwards breaks the other half.

---

## S2 — Telegram scraper <- start here

**Goal:** fetch posts from public Telegram channels. Scraping only; the LLM extraction is already built and waiting for you.

Everything downstream exists already — extraction, validation, venue resolution, deduplication, storage, search, routing. The pipeline currently runs on 31 saved fixture posts. **Without this, GoWhere has no live events at all.**

**The exact function the pipeline calls** (`TelegramPostSource` is the only caller):

```python
gowhere.ingest.telegram.fetch_posts(channel: str, since_post_id: str | None = None) -> list[dict]
# fetch_posts("sgweekend", since_post_id="sgweekend/1234") -> records oldest first
```

**Record shape:**

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

**How:** public channels serve plain HTML at `https://t.me/s/<channel>` — no login, no API key, no Telegram account. `requests` + BeautifulSoup. **Don't** use the Telegram API or a headless browser; both were considered and rejected (see `DECISIONS.md`).

**Channels:** `sgweekend` and `sgwhereto` are confirmed. Not `sgnightlife` — it's a group, not a broadcast channel, with no post feed. The test for any new one: can you open `t.me/s/<name>` in a browser and see posts?

**Traps, each of which will cost you an afternoon:**

- **The page shows only ~20 recent posts.** Older ones need pagination (a `before=` parameter). Check this on day one — without it, `since_post_id` can't really be tested.
- **Timestamps in the HTML are UTC.** Singapore is UTC+8, so a 23:00 SGT post silently lands on the previous day, and events then show on the wrong date.
- **Some posts are media-only** with no text, and long posts may be truncated in the web view. Skip empty ones; check truncation before assuming you have the full text.
- **Posts get edited and deleted.** Take `post_id` from the post's own link, never from its position on the page.

**Also required:** save the raw HTML of at least 20 posts to `tests/fixtures/telegram/*.html` and write tests that parse those files. **They must pass with the wifi off.**

**Acceptance check**

```bash
python -m gowhere.ingest.telegram --channel sgweekend --limit 20
.venv/bin/python -m pytest tests/test_telegram_scraper.py     # wifi off
python -m gowhere.ingest.run --once                           # end to end, needs ANTHROPIC_API_KEY
```

Passes when 20 records come back with correct SGT timestamps, `since_post_id` returns only newer posts, the fixture tests pass offline, and a full ingestion run stores events.

**Out of scope:** extracting title/date/venue from post text — already built, in `gowhere/ingest/extract.py`.

---

## S3 — Templates

**Goal:** replace the placeholder templates in `gowhere/web/templates/` with real, responsive pages. No backend logic — the view models hand you everything pre-formatted.

**Read `docs/frontend-notes.md`** — written for this task.

**Your contract, already committed:**

- `tests/fixtures/mock_results.json` — a real Where to Live result (Changi / Tampines / Pasir Ris / Tengah) with a dropped factor, a small-area note and far-from-rail notes
- `tests/fixtures/mock_results_all_scored.json` — all six factors scored
- `tests/fixtures/mock_lepak_results.json` and `mock_lepak_event.json` — the Lepak pages
- The placeholder templates themselves, which already render the right fields

**Screens:** home, Where to Live setup, Where to Live results (plus the breakdown modal), Lepak search, Lepak results, event detail, and shared error/empty states.

**Factor labels, exactly:** Public Transport, Housing Affordability, Amenities, Greenery, Healthcare, Commute. **"Public Transport", never "Transport"** — and `public_transport` in code, CSS and JSON.

**Requirements:**

- **Responsive.** We demo Lepak on a phone.
- **One note component, reused.** There are a lot of notes — small-area, far-from-rail, dropped-factor (naming the area and the reason), plus per-factor notes for commute timing, the hospital rule, the CHAS date and the housing window. Styled ad hoc they will swamp the page.
- **A factor can be missing entirely.** Every results template must treat a dropped factor as a normal state, not an error.
- **Download Leaflet and Chart.js into `gowhere/web/static/`. Never a CDN.** The demo may run with the network off, and CDN-loaded libraries would take every map and chart with them. (Basemap tiles can't be bundled — offline, the area outlines draw on a blank background. That's expected.)
- **Never put a postal code in a URL or Flask's cookie session.** Security NFR: it lives in server-side memory only. A query string lands in browser history and server access logs.
- **Escape all event text.** Event titles come from public Telegram posts — untrusted input.
- Attribution footer on every page: *Map and location data from OneMap (SLA) · Amenity data © OpenStreetMap contributors · Government data from data.gov.sg*

**Acceptance check:** `flask run`, then click through all six screens against both mock fixtures, in a desktop browser and a phone-sized viewport, **with the wifi off**. No console errors; maps and charts still render.

---

## S4 — Diagrams and test tables

**Sequence diagrams** — three, and they must match the code that exists, not the Lab 1 design. Check the class names in `gowhere/` first: a diagram that contradicts the code is worse than none.

- **Compare Neighbourhoods with commute** — controller to `ScoringEngine` to the `ScoringStrategy` implementations to `RouteService` to `OneMapAdapter`. Shows the extend, the include chain and an external call.
- **Find Events in drive mode** — two external services plus the parking extend.
- **Ingest Events** — the scheduled trigger, the LLM, and the validate-or-discard branch.

**What changed since Lab 1:** one `ScoringStrategy` interface with a class per factor; a `ScoringEngine` that knows only that interface; an adapter per external service (OneMap, LTA DataMall, Telegram, LLM); `LocationService` and the route cache as shared services.

**Black-box test table** — equivalence partitioning and boundary values from the *current* FR, not the Lab 1 numbers: neighbourhoods **2–4** (test 1/2/4/5), weights **1–10** (0/1/10/11), categories **1–4** (0/1/4/5), postal codes of 5/6/7 digits, budget minimum above maximum. One row per case: input, expected result, FR reference.

---

## S1 — Data acquisition (mostly done)

12 datasets are already fetched and cached in `data/raw/` by `gowhere/etl/_temp_fetch_raw.py`: HDB property information (13,357), MRT/LRT exits (613), planning areas (55), parks (462), park connectors (878), CHAS clinics (1,193), hospitals (31), resale transactions (24,590), hawker centres (129), libraries (28), supermarkets (478), OSM amenities (2,533).

**What's left:**

1. **Bus stops and services — blocked on an LTA DataMall account key.** This matters more than it sounds: the Public Transport factor is currently **rail-only**. The FR promises an MRT/LRT, Bus, or Either choice, and the Bus option cannot be built without this data. Registering for a key unblocks a whole requirement.
2. **Optionally**, turn `_temp_fetch_raw.py` into a proper `fetch_raw.py` with a `--force` flag and per-dataset source dates in the manifest. Cosmetic — the current module works. If you do it, run `pytest` immediately after: if the ETL tests fail, your output shape differs.

**If you touch `data/raw/`:** write raw responses **unmodified**. Don't filter or clean — hawker centres include 6 under construction and the supermarket list includes minimarts, and the ETL decides what to exclude. Filter here and a number goes wrong later with no way to trace it.

**Still true and worth knowing:** `initiate-download` returns **HTTP 201**, not 200. A rate-limited page can look like a quiet month, so check collected records against the API's own `total`.
