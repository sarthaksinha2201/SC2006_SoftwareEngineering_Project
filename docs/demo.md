# Demo runbook

Everything below was rehearsed on 30 Sep 2026 against the real snapshot, from a clean
clone of `feat/etl-transport`. It was run once online, and once offline with every
outbound connection failing. The rehearsal driver is kept at the end of this file.

## 1. Bring the app up from a clean checkout

```bash
git clone <repo> gowhere && cd gowhere          # main
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt       # needs network; ~10 s

# .env in the repo root: section 2 says what each key is for and what fails without it.
# Fill it in yourself; never paste these into a chat.
cat > .env <<'END'
ONEMAP_EMAIL=...
ONEMAP_PASSWORD=...
ANTHROPIC_API_KEY=...
LTA_DATAMALL_KEY=...
END

# Fetch events by hand (Telegram -> LLM -> events.db), whenever you want fresh ones:
.venv/bin/python -m gowhere.ingest.run
.venv/bin/python -m gowhere.ingest.run --report      # the yield of recent runs

# Run the app: one process, Waitress, http://127.0.0.1:8000
GOWHERE_SECRET_KEY=$(openssl rand -hex 32) .venv/bin/python -m gowhere.serve
```

- **Showing it to the team before demo day:** run the app as above (web only, the
  default). Fetch events with the manual command, which works while the server runs.
- **Demo day:** add `--ingest-every-hours 6`. The server then fetches events at start
  and every 6 hours on a background thread, in the same single process.
  `--host 0.0.0.0` lets a phone on the same Wi-Fi open it.
- **Checks:** `.venv/bin/python -m pytest -q` should report 370 passed. It needs no
  network and no keys.
- **The snapshot** (`data/snapshot.db`, rebuilt 14 Oct 2026 with bus data) is
  committed, so a clean clone runs as it is (DECISIONS §14).
- **Regenerating the snapshot:** first fetch the raw data
  (`python -m gowhere.etl._temp_fetch_raw`, which needs `LTA_DATAMALL_KEY` for bus
  stops and routes), then run `python -m gowhere.etl.build_snapshot`. With the
  geocode cache in place the build takes about 20 s. From nothing, geocoding 10,796
  blocks takes about an hour.
- **Run one server process.** Sessions live in memory; `gowhere.serve` uses threads
  only.

## 2. What goes in `.env`, and what works without each key

| Key | Used for | Without it |
|---|---|---|
| `ONEMAP_EMAIL` + `ONEMAP_PASSWORD` | OneMap routing: Commute, Lepak travel times, route lines and directions. The app fetches a token and renews it before its 3-day expiry. | Postal lookups still work. Commute is left out and named as such, and every Lepak event shows its straight-line distance as an estimate. |
| `ONEMAP_TOKEN` (fallback) | The same, until it expires after 3 days. The 30 Sep token expired on 3 Oct, so routing was down until renewal was added. | As above, and the log warns once that the token has expired. |
| `ANTHROPIC_API_KEY` | Event extraction at ingestion | Ingestion stores nothing and keeps each channel's place. The app serves whatever `data/events.db` already holds. |
| `LTA_DATAMALL_KEY` | Live carpark availability (drive mode), and bus stops and routes when the snapshot is rebuilt | Drive-mode results say "Parking information unavailable"; everything else shows. A rebuilt snapshot would be rail-only. |
| `GOWHERE_SECRET_KEY` (environment) | Signing the session cookie | A random key is used, so sessions reset when the server restarts. |

As of 14 Oct, `.env` holds `ONEMAP_TOKEN` (expired) and `LTA_DATAMALL_KEY`.
`ONEMAP_EMAIL`, `ONEMAP_PASSWORD` and `ANTHROPIC_API_KEY` are still to add.

## 3. The five-minute script

The inputs are exact. The Where to Live results are from the 14 Oct snapshot with the
14 Oct defaults: five factors on, Public Transport set to Either, all amenity types,
GP clinics. The Commute minutes are the ones OneMap returned on 1 Oct. Routing is
down until `ONEMAP_EMAIL` and `ONEMAP_PASSWORD` are added, so re-check steps 4 and 5
once it works.

### Where to Live (about 3 minutes)

1. **Home → Where to Live.** Five factors are already on. Commute is off and greyed.
2. **Select Queenstown, Tampines, Punggol and Changi.** Set Housing Affordability to
   weight 8, 4-room, $400,000 to $700,000, at least 60 years of lease left. Set
   Public Transport to weight 6 and Greenery to weight 4, and leave the rest as they
   are.

   **Before submitting**, the page warns: *"Housing Affordability was left out because
   Changi had fewer than 10 matching resales."* This is the dropped-factor case. Say:
   the app would rather drop a factor for everyone than score Changi on a handful of
   sales, and it tells you before you submit, not after.
3. **Swap Changi for Bedok.** The warning disappears.
4. **Switch Commute on.** The destination field appears only now. Enter **119077**
   (NUS) with weight 7 and public transport, then **Compare**.
5. **Results:** *"Queenstown ranks first with 5.6 out of 10. Queenstown ranks ahead of
   Punggol mainly because of Commute and Healthcare."*

   | Rank | Area | Score |
   |---|---|---|
   | 1st | Queenstown | 5.6 |
   | 2nd | Punggol | 3.8 |
   | 3rd | Tampines | 3.5 |
   | 4th | Bedok | 2.9 |

   The bar chart shows one group per factor. **See how this was calculated** opens the
   full breakdown:
   - each factor's weight;
   - both top areas' scores and raw values;
   - each factor's marginal contribution, largest first;
   - the formula with your weights filled in;
   - every factor left out, and why.
6. **The Queenstown housing 0.0 case.** Point at Queenstown's Housing Affordability
   **0.0**: *"0% of 4-room resales with at least 60 years of lease left in the last 12
   months (0 of 270) were within your budget."* Say: this is not missing data. There
   were 270 matching sales, and none fit the budget. Compare Changi, where there were too
   few sales to judge, so Housing was left out instead. These are two different answers
   to two different situations.
7. **Change the comparison:** switch Commute off and raise Housing Affordability to
   **10**. Punggol now ranks first with **4.4**, ahead of Queenstown with 4.2, and the
   page says they are nearly tied. One weight moved the ranking, and the app says how
   close the call is.
8. **Optional:** set Public Transport's "Walk to" to **Bus**. The runner-up changes
   from Punggol to Tampines. Someone who travels by bus gets a different answer.

### Where to Lepak (about 2 minutes)

The events depend on the last ingestion run, so choose the inputs on the day. Use a
central postal code such as **238801** (ION Orchard), public transport, at most 45
minutes, and the three or four categories with the most events.

1. **Find events.** Under the heading is *"Events last updated … ago"*, with a warning
   if the last update was more than 24 hours ago. Results are sorted by travel time.
   Each card has the route summary and its Telegram source link.
2. **Sort by Soonest, then hide one category chip.** The other categories stay. Say:
   this is instant because nothing is re-fetched; the results were routed once and are
   only reordered.
3. **Open an event.** The map shows your starting point, the venue and the route, with
   step-by-step directions below. **Back to results** returns to the same sort,
   hidden categories and page.
4. **Search again with Car.** Each card shows the car lots free within 500 m (live
   LTA DataMall, at most 2 minutes old). If DataMall can't be reached, the cards say
   *"Parking information unavailable"* and the results still show.
5. **Optional, on a phone:** "Use my location" in place of the postal code.

## 4. Events for the demo

The web app shows whatever `data/events.db` holds. `python -m gowhere.ingest.run`
fetches every channel in `config.LEPAK_CHANNELS` using Sarthak's scraper, extracts
events with the LLM and stores them. It needs `ANTHROPIC_API_KEY`; without it the run
stores nothing and keeps each channel's place.

**Measured 14 Oct, before the LLM step:** the scraper read the 40 newest posts from
each of the 8 channels.

| Channel | Posts | Pass the date pre-filter | Newest post |
|---|---|---|---|
| sgweekend | 40 | 37 | 14 Oct |
| sgwhereto | 40 | 37 | 14 Oct |
| SGArtsChannel | 40 | 39 | 14 Oct |
| sgconcerts | 40 | 40 | 13 Oct |
| dateideas | 40 | 25 | 14 Oct |
| sgfitnesshealth | 40 | 31 | 12 Oct |
| TimeOutSG | 40 | 8 | **19 Jun** |
| sgbestnightlife | 40 | 17 | 9 Oct |

TimeOutSG hasn't posted since June, so it looks dormant. Extraction, storage and the
true yield need the API key.

For rehearsal only, the fixture posts can be replayed through the real pipeline with
hand-written stand-in replies. This calls no model and still places venues on OneMap:

```bash
.venv/bin/python -m gowhere.ingest.run --posts-file tests/fixtures/lepak/posts.json \
    --replay-replies tests/fixtures/lepak/extractions.json
```

Those events were posted in September, and most end by early November.

## 5. What degrades when a service is unavailable

This is the Reliability NFR. A grader may test it by unplugging the wifi.

| Service down | What still works | What the user sees |
|---|---|---|
| **OneMap** (network off) | All of Where to Live except Commute, from the local snapshot. Lepak from any **HDB** postal code: the 10,786 in the snapshot resolve offline. Lepak with "Use my location". Sorting, chips, paging and event details. | Where to Live: *"Commute was left out because Queenstown, Tampines, Punggol and Bedok could not be routed to your destination"*, and the other five factors ranked. Lepak: every event with *"About 2.4 km away (straight-line estimate, no route available)"*. A postal code that isn't an HDB block's: *"OneMap can't be reached right now. Without it we can only look up HDB block postal codes, and this one isn't one, so it couldn't be checked."* It is never reported as an invalid code. |
| **LTA DataMall** | Everything | Drive mode: *"Parking information unavailable"* on each result. |
| **LLM** (Anthropic) | Everything in the web app | Nothing. Ingestion stores no events that run and keeps each channel's marker, so no post is lost; the next run catches up. The app serves the events it already has. |
| **Telegram** | Everything in the web app | Nothing; as for the LLM. |
| **CDN / map tiles** | Nothing today | The placeholder templates load no external files. **Sarthak's templates will:** Leaflet, Chart.js and basemap tiles. Serve Leaflet and Chart.js from `gowhere/web/static/`, not a CDN, or the charts and maps vanish offline. Basemap tiles can't be bundled. Offline, the area outlines will draw on a blank background. |

**Rehearsal timings** (clean clone, real snapshot, real server). The last full run was
on 1 Oct, from a fresh clone with nothing copied in except `.env`. It predates the
14 Oct changes (bus data, Waitress, new defaults), and OneMap routing has been down
since the token expired on 3 Oct. Repeat it once `ONEMAP_EMAIL` and `ONEMAP_PASSWORD`
are in `.env`.

| Step | Online | Offline |
|---|---|---|
| Selection-time warning (Changi) | instant, warning shown | instant, warning shown |
| Where to Live results with Commute | 0.5–3.7 s. Queenstown first. | 2.5 s. Commute left out, Punggol first. |
| Reload results | 0.0 s | 0.0 s |
| Lepak search by postal code 238801 (not HDB) | 2.2–5.8 s, 6 events | 1.2 s, "only HDB block postal codes can be looked up" message |
| Lepak search by HDB postal code 140051 | 2.8 s, 5 events routed | 5.1 s, 6 events as straight-line estimates (offline fallback) |
| Sort, chip, detail | 0.0 s | 0.0 s |
| Lepak drive mode | 0.2–1.0 s, parking unavailable | 0.0 s, same message (238801 is not HDB) |
| Lepak by device location | 2.0–2.4 s, 6 events routed | 2.7 s, 6 events as straight-line estimates |
| Postal codes or coordinates in the server log | 0 | 0 |

**Fixed during the rehearsal:** the first offline run took **63 s** to show Where to
Live results with Commute. A reload took 32 s, and a Lepak postal lookup took 33 s.
Request-time OneMap calls were inheriting the ETL's 4 retries with long backoff. They
now use 1 retry and an 8 s timeout. A failed postal lookup is also remembered for 60 s,
so a reload or slider change doesn't wait on a dead network again. The numbers above are
after the fix.

**Also added after the rehearsal: an offline postal-code fallback.** A Lepak search
by postal code used to be the last complete failure offline. "Use my location" isn't a
reliable fallback on a demo machine, where geolocation may be denied. Now, when OneMap
can't be reached, a postal code is looked up among the snapshot's HDB blocks. That
covers HDB postal codes only (10,786 of them). Any other code gets a message saying it
couldn't be checked offline, never that it doesn't exist.

**Still imperfect offline:**

1. **Non-HDB starting points** (condos, landed homes, offices) can't be looked up
   without OneMap. The user is told so, and "Use my location" still works.
2. **The Commute wording** says the areas "could not be routed to your destination"
   even when OneMap itself was unreachable. It's true, but not the most useful reason.

## Rehearsal driver

`scripts/rehearse.py`, run as `python scripts/rehearse.py <checkout> online|offline`, starts the real
server and walks section 3 over HTTP. Offline mode sets `HTTP(S)_PROXY` to a dead local
port, so every outbound call fails as it would with the wifi off. That is a simulation.
Before the demo, repeat the offline half once with the wifi actually off. A captive
portal or a very slow network fails differently: it times out rather than failing at
once. The 8-second timeout bounds that at about 16 s for one lookup.
