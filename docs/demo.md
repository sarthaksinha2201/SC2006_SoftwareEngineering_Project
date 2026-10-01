# Demo runbook

Everything below was rehearsed on 30 Sep 2026 against the real snapshot, from a clean
clone of `feat/etl-transport`. It was run once online, and once offline with every
outbound connection failing. The rehearsal driver is kept at the end of this file.

## 1. Bring the app up from a clean checkout

```bash
git clone <repo> gowhere && cd gowhere && git checkout feat/etl-transport
python3.13 -m venv .venv
.venv/bin/pip install -r requirements.txt           # needs network; ~10 s

# .env in the repo root. See section 2 for what each key is for.
cat > .env <<'EOF'
ONEMAP_TOKEN=...
ANTHROPIC_API_KEY=...
LTA_DATAMALL_KEY=...
EOF

# Events: a live ingestion run (needs the key and the S2 scraper). See section 4.
.venv/bin/python -m gowhere.ingest.run

GOWHERE_SECRET_KEY=$(openssl rand -hex 32) .venv/bin/flask --app "gowhere.web:create_app()" run
# open http://127.0.0.1:5000
```

- **Checks:** `.venv/bin/python -m pytest -q` should report 323 passed. It needs no
  network and no keys.
- **The snapshot** (`data/snapshot.db`, 11 MB, built 30 Sep 2026) is committed, so a
  clean clone runs as it is (DECISIONS §14).
- **Regenerating the snapshot:** `python -m gowhere.etl.build_snapshot`, after the raw
  data has been fetched and geocoded. It needs the network and takes about an hour,
  mostly geocoding 10,796 blocks. Don't do this on demo day.
- **Run one server process.** Sessions live in memory.
- **The Flask tip** "Install python-dotenv" is harmless. `.env` is read by GoWhere
  itself.

## 2. What goes in `.env`, and what works without each key

| Key | Used for | Without it |
|---|---|---|
| `ONEMAP_TOKEN` | Routing: Commute, Lepak travel times, route lines | Postal lookups still work, at 1 per second. Commute is left out and named as such. Every Lepak event shows its straight-line distance as an estimate. |
| `ANTHROPIC_API_KEY` | Event extraction at ingestion | Ingestion stores nothing and keeps each channel's place. The app serves whatever `data/events.db` already holds. |
| `LTA_DATAMALL_KEY` | Live carpark availability (drive mode) | Each drive-mode result says "Parking information unavailable"; everything else shows. |
| `GOWHERE_SECRET_KEY` (environment) | Signing the session cookie | A random key is used, so sessions reset when the server restarts. |

Today only `ONEMAP_TOKEN` is set.

## 3. The five-minute script

The inputs are exact. The results quoted are from the rehearsal against the 30 Sep
snapshot.

### Where to Live (about 3 minutes)

1. **Home → Where to Live.**
2. **Select Queenstown, Tampines, Punggol and Changi.** Include every factor except
   Commute:
   - Housing Affordability: weight 8; 4-room; $400,000 to $700,000; at least 60 years
     of lease left.
   - Public Transport: weight 6.
   - Amenities: weight 5; supermarket and hawker centre.
   - Greenery: weight 4.
   - Healthcare: weight 5; polyclinic.

   **Before submitting**, the page warns: *"Housing Affordability was left out because
   Changi had fewer than 10 matching resales."* This is the dropped-factor case. Say:
   the app would rather drop a factor for everyone than score Changi on a handful of
   sales, and it tells you before you submit, not after.
3. **Swap Changi for Bedok.** The warning disappears.
4. **Include Commute:** weight 7, destination **119077** (NUS), public transport.
   **Submit.**
5. **Results:** *"Queenstown ranks first with 5.3 out of 10. Queenstown ranks ahead of
   Punggol mainly because of Commute and Amenities."*

   | Rank | Area | Score |
   |---|---|---|
   | 1st | Queenstown | 5.3 |
   | 2nd | Punggol | 4.3 |
   | 3rd | Bedok | 3.9 |
   | 4th | Tampines | 3.2 |

   Commute is 21.6 minutes from Queenstown, against 65–67 from the other three.
6. **The Queenstown housing 0.0 case.** Point at Queenstown's Housing Affordability
   **0.0**: *"0% of 4-room resales with at least 60 years of lease left in the last 12
   months (0 of 270) were within your budget."* Say: this is not missing data. There
   were 270 matching sales, and none fit the budget. Compare Changi, where there were too
   few sales to judge, so Housing was left out instead. These are two different answers
   to two different situations.
7. **Change the comparison, untick Commute, and resubmit.** Punggol now wins with 4.8,
   *"mainly because of Housing Affordability and Public Transport."* The weights decide
   the ranking, and the explanation follows them.

### Where to Lepak (about 2 minutes)

1. **Where to Lepak.** Choose:
   - Categories: Arts & Culture, Music & Performances, Family & Kids.
   - When: Next 7 days.
   - Starting point: postal code **238801** (ION Orchard).
   - Travel: public transport, at most 45 min.

   **Find events.**
2. **Results:** *"6 events within 45 min by public transport."* They are sorted by
   travel time: Seoul Anthem at 13 min, the Yukata experience at 18, Anime Earth at 20,
   and so on. Each card has the route ("Walk 1 min → North South Line → …") and its
   Telegram source link.
3. **Sort by Soonest, then tap the Family & Kids chip.** Say: this is instant because
   nothing is re-fetched. The results were routed once and are only reordered.
4. **Open an event.** The detail page shows the route.
5. **Search again with Car.** Every card says *"Parking information unavailable"* and
   the results still show. That is the designed fallback until there is a DataMall key.
6. **Optional, on a phone:** "Use my location" in place of the postal code.

## 4. Events for the demo

The web app shows whatever `data/events.db` holds. Getting real events needs:

- the S2 scraper (`gowhere/ingest/telegram.py`, Sarthak's), which is **not written
  yet**;
- `ANTHROPIC_API_KEY`, which is **not set yet**.

Without both, `python -m gowhere.ingest.run` stores nothing.

For rehearsal only, the fixture posts can be replayed through the real pipeline with
hand-written stand-in replies. This calls no model and still places venues on OneMap:

```bash
.venv/bin/python -m gowhere.ingest.run --posts-file tests/fixtures/lepak/posts.json \
    --replay-replies tests/fixtures/lepak/extractions.json    # 13 events, ~20 s
```

Those events were posted in September. Most end by 1 to 2 Nov, and ended events are
purged. **A demo after early November needs a live ingestion run.** Do it the day
before the demo and keep a copy of `data/events.db`, so the demo doesn't depend on
Telegram, the LLM or the network. Events are local data once ingested.

## 5. What degrades when a service is unavailable

This is the Reliability NFR. A grader may test it by unplugging the wifi.

| Service down | What still works | What the user sees |
|---|---|---|
| **OneMap** (network off) | All of Where to Live except Commute, from the local snapshot. Lepak from any **HDB** postal code: the 10,786 in the snapshot resolve offline. Lepak with "Use my location". Sorting, chips, paging and event details. | Where to Live: *"Commute was left out because Queenstown, Tampines, Punggol and Bedok could not be routed to your destination"*, and the other five factors ranked. Lepak: every event with *"About 2.4 km away (straight-line estimate, no route available)"*. A postal code that isn't an HDB block's: *"OneMap can't be reached right now. Without it we can only look up HDB block postal codes, and this one isn't one, so it couldn't be checked."* It is never reported as an invalid code. |
| **LTA DataMall** | Everything | Drive mode: *"Parking information unavailable"* on each result. |
| **LLM** (Anthropic) | Everything in the web app | Nothing. Ingestion stores no events that run and keeps each channel's marker, so no post is lost; the next run catches up. The app serves the events it already has. |
| **Telegram** | Everything in the web app | Nothing; as for the LLM. |
| **CDN / map tiles** | Nothing today | The placeholder templates load no external files. **Sarthak's templates will:** Leaflet, Chart.js and basemap tiles. Serve Leaflet and Chart.js from `gowhere/web/static/`, not a CDN, or the charts and maps vanish offline. Basemap tiles can't be bundled. Offline, the area outlines will draw on a blank background. |

**Rehearsal timings** (clean clone, real snapshot, real server). The last run on 1 Oct
was from a fresh clone with nothing copied in except `.env`:

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
