# Where to Eat

Hawker centres, kopitiams, cafés and restaurants near a starting point, with whether
they are open at the chosen time. Scope and decisions: DECISIONS.md §25 and §25a. The
numbers behind them: [eat-measurements.md](eat-measurements.md).

Where to Eat lists permanent places. Lepak lists time-bound events: a pasar malam this
weekend is a Lepak event, while a hawker centre is a Where to Eat place.

## Data (offline)

```bash
python -m gowhere.etl._temp_fetch_raw     # includes osm_food (Overpass)
python -m gowhere.eat.build               # writes data/eat.db (committed, ~1.5 MB)
```

`data/eat.db` holds 8,604 places (19 Oct 2026). They combine:

- OpenStreetMap restaurants, cafés, fast food, food courts, ice cream and markets;
- the 123 operating NEA hawker centres, each one entry with its cooked-food stall count.

The build drops:

- 511 OSM venues outside Singapore (the download box reaches into Johor);
- 379 unnamed ones;
- 165 OSM copies of a hawker centre. These are food courts or markets within 60 m of an
  NEA centre, or within 200 m and sharing a distinctive word of its name.

## Signals

| Signal | Source | Coverage | Shown as |
|---|---|---|---|
| Cuisine | OSM `cuisine`, mapped to 8 groups (`gowhere/eat/cuisines.py`) | 53% of OSM places | A tag; otherwise "Cuisine not listed" |
| Open at the chosen time | OSM `opening_hours` (`gowhere/eat/hours.py`) | 22% of places | "Open until 10 pm" / "Closed, opens 6 pm" / "Opening hours unknown" |
| Travel time | OneMap, through the same `EventRouter` as Lepak | Every routed place | As for Lepak, with straight-line estimates when unroutable |
| Price tier | Venue type | Every place | $ hawker centre, food court, market or kopitiam · $$ café or fast food · $$$ restaurant |
| Variety | NEA stall count | 125 of 129 hawker centres | "Hawker centre · 83 stalls" |

**Groups:**

- The eight groups are Local & Hawker, Chinese, Malay & Indonesian, Indian, Japanese &
  Korean, Thai & Vietnamese, Western, and Cafés & Desserts.
- `coffee_shop` maps to Cafés & Desserts. It marks Starbucks and Toast Box far more
  often than kopitiams.
- Kopitiams are recognised by name instead ("Kopitiam", "Eating House", "Coffee Shop").
- A place tagged only `seafood` counts as not listed, because seafood here is as often
  Chinese as Western.

**Opening hours:** the parser understands day ranges, split shifts, hours past midnight,
`24/7` and `off`, which covers 98.4% of tagged values. Anything else counts as unknown
and is never guessed.

**Not built, and why:**

- **Hygiene grades:** the only bulk data is from 2015–16, and SFA has since replaced
  that grading scheme.
- **Michelin badge:** the guide's terms forbid copying its content.
- **Star ratings:** Google Places costs money per request and forbids caching.
- **Halal and vegetarian filters:** OSM tags cover under 4% of places. MUIS's
  certification register is the authoritative halal source, and we don't hold it.

## Search

`gowhere/eat/search.py`:

1. Filter by the chosen price tiers. If cuisines are chosen, keep the places in them,
   plus the places whose cuisine is not listed. Those can be hidden with a chip, but are
   shown by default.
2. Straight-line pre-filter at the mode's top speed, as for Lepak.
3. Route the 40 nearest by straight line. Up to 10 slots go to food destinations, and,
   when cuisines are chosen, at most 10 go to unlisted places. The page says how many
   were within reach and how many were timed.
4. Departure is the chosen mealtime, either now or the next breakfast, lunch, dinner or
   supper. Open or closed is judged at that time.

The sorts are Nearest, Open first and Most variety (destinations by stall count). Sort,
chips and paging reorder the saved results, and call nothing.

**Measured live (19 Oct, from 238801):** a search takes 4.0–6.5 s, inside the 8 s target.
OneMap answers some of the 40 parallel routing calls with HTTP 429. The retry recovers
each one, and the times include those retries.

## Screens

| Route | What it does |
|---|---|
| `GET /eat`, `POST /eat` | The search form. Its starting point is handled exactly as for Lepak: session memory only. |
| `GET /eat/results?sort=&hide=&page=` | The results. |
| `GET /eat/places/<id>` | A place: hours as tagged, cuisine as tagged, travel time, map with start and route, directions, parking in drive mode, source link. |
