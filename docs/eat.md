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
| Price tier | Venue type | Every place | Hawker centre, food court, market or kopitiam · café or fast food · restaurant |
| Variety | NEA stall count | 125 of 129 hawker centres | "Hawker centre · 83 stalls" |

**Groups:**

- The eight groups are Local, Chinese, Malay & Indonesian, Indian, Japanese &
  Korean, Thai & Vietnamese, Western, and Cafés & Desserts.
- `coffee_shop` maps to Cafés & Desserts. It marks Starbucks and Toast Box far more
  often than kopitiams.
- Kopitiams are recognised by name instead ("Kopitiam", "Eating House", "Coffee Shop").
- A place tagged only `seafood` counts as not listed, because seafood here is as often
  Chinese as Western.

**Opening hours:** the parser understands day ranges, split shifts, hours past midnight,
`24/7` and `off`, which covers 98.4% of tagged values. Anything else counts as unknown
and is never guessed.

**Quality signals (DECISIONS.md §29):**

- **Google ratings** ("★ 4.3 · 1,234 reviews", with "Google Maps" attribution and a link
  to the place on Google Maps). The flow:
  - `gowhere.eat.google_ids` resolves a place ID offline with the free "Text Search
    Essentials (IDs Only)" SKU. The ID is the only Google content stored.
  - At search time, `gowhere.eat.ratings` fetches rating, review count, name and Maps
    link for each timed place. This is the "Place Details Enterprise" SKU: 1,000 free a
    month, then US$20 per 1,000, i.e. US$0.02 a lookup.
  - A rating is shown only if Google's name for the place matches ours.
  - Ratings live only in that user's session memory.
  - A hard daily cap, `config.GOOGLE_DAILY_CAP`, defaults to 32 (992 in a 31-day month)
    and is counted before every call. Once it is spent, places show without ratings, and
    "Highest rated" disappears rather than sorting nothing.
  - A place with no rating shows none, which never reads as a low rating.
  - **Needs `GOOGLE_MAPS_API_KEY` in `.env`, plus one run of `gowhere.eat.google_ids`.**
    Until then, no place has an ID and no rating is fetched.
- **"On Wikipedia" badge** on 24 places with their own Wikipedia article
  (`gowhere.eat.notable`). The badge claims notability, not good food, and says so.
  An article counts only if every word of the place's own name appears in its title.
  Without that rule, shops picked up their mall's article and road-named markets their
  road's.

**Not built, and why:**

- **Hygiene grades:** the only bulk data is from 2015–16, and SFA has since replaced
  that grading scheme.
- **Michelin badge:** the guide's terms forbid copying its content.
- **Halal filter:** MUIS's terms of use (updated 24 Feb 2025) say its content "shall not
  be reproduced, republished, uploaded, posted, transmitted or otherwise distributed in
  any way, without the prior permission of MUIS". Even with permission, the content must
  not be "copied or posted on any network computer". The halal search
  (halal.muis.gov.sg) has a JSON endpoint, but the terms attach to the content, and the
  community mirrors republish the same content. It needs written permission from MUIS
  Corporate Communications. OSM's own `diet:halal` tags (3.7% coverage) are no
  substitute for a religious requirement.

## Search

`gowhere/eat/search.py`:

1. Filter by the chosen price tiers. If cuisines are chosen, keep the places in them,
   plus the places whose cuisine is not listed. Those can be hidden with a chip, but are
   shown by default.
2. Straight-line pre-filter at the mode's top speed, as for Lepak.
3. Route the 25 nearest by straight line. Up to 6 slots go to food destinations, and,
   when cuisines are chosen, at most 6 go to unlisted places. The page says how many
   were within reach and how many were timed.
4. Departure is the chosen mealtime, either now or the next breakfast, lunch, dinner or
   supper. Open or closed is judged at that time.

The sorts are Nearest, Open first, Most variety (destinations by stall count) and Highest
rated (when ratings are available). With a cuisine chosen, places whose cuisine is not
listed come after every match, whatever the sort (§28). Sort, chips and paging reorder
the saved results, and call nothing.

**Measured live (19 Oct, from 238801):** a search takes 4.0–6.5 s, inside the 8 s target.
With the first budget of 40 places, OneMap answered some of the parallel routing calls
with HTTP 429. The retry recovered most of them, and the times include those retries.

**Routing concurrency (19 Oct 2026, §28).** 8 searches per configuration, interleaved,
from 238801. Public transport, 15 min, any cuisine, routing only (ratings not yet live):

| Configuration | Median | 90th percentile | Max | 429 retries per search (median / total) | Routes lost after retry |
|---|---|---|---|---|---|
| 40 places, 16 workers (first build) | 5.29 s | 6.45 s | 6.45 s | 14 / 108 | 3 |
| **25 places, 16 workers (now built, §30)** | **4.47 s** | **6.30 s** | 6.30 s | **8.5 / 74** | 2 |
| 40 places, 8 workers | 5.68 s | 7.97 s | 7.97 s | 10.5 / 73 | 4 |

Routing fewer places is better on every measure. Fewer workers cuts retries about as
much, but pushes the 90th percentile to the 8 s limit, so the budget is now 25.

**Rate limiting costs accuracy, not only time.** A route that OneMap refuses twice is
dropped, and that place falls back to a straight-line estimate. The "routes lost" column
counts these: the user sees "About 600 m away (straight-line estimate)" instead of a
real travel time. Fewer places per search means fewer refusals, so fewer places lose
their real time.

## Entering from the other two features (DECISIONS.md §27)

**From a Lepak event: a search from a point.** The event page links to "Where to eat
near this event" (`/eat/from-event/<event id>`). The event's name and coordinates go
into the session, never the URL. The search form then shows "Near *event*" in place of
the starting-point fields, and the user still chooses mealtime, travel mode, maximum
time and filters. Everything after that is the normal search path with a different
origin. The results page says "Starting from *event*". "Start somewhere else" clears
the event and brings back the postal code and location fields.

**From the Where to Live recommendation: a browse, not a search.** The recommendation
links to "Where to eat in *Queenstown*" (`/eat/in/QUEENSTOWN`; both areas when joint
first). There is no starting point, no travel mode and no travel time, because someone
choosing where to live is not planning a journey yet. So browse mode:

- **Filters:** every place whose `planning_area` is that neighbourhood. The cuisine and
  kind-of-place filters still apply, as does the rule that unlisted places come after
  every match.
- **Routes nothing:** no OneMap call, no straight-line estimate, no rate-limit exposure
  and no waiting overlay. The page states how many places it lists ("458 places to eat
  in Queenstown").
- **Sorts:** **Most variety** (the default: food destinations first, most stalls
  first, then by name) and **A to Z**. Nearest and Open first are left out, because
  both assume a journey. "Most variety" is the default because it puts the hawker
  centres, the places that best answer "what is there to eat around here", at the top.
  A to Z gives a predictable order for scanning.
- **No rating sort, and no ratings:** a neighbourhood holds between 20 places (Marina
  South) and 1,020 (Downtown Core), with a median of about 200. Rating them all would
  spend many days of the 32-a-day Google cap on a single page view. Rating only the page
  shown would make "Highest rated" a sort of ten places pretending to be a ranking. A
  search rates its 25 timed places, so ratings stay there.
- **Works with JavaScript off:** the filters are a GET form on the same page. The URL
  holds only the neighbourhood name, the filters, the sort and the page.

**The seam:** the search sort assumes a travel time and a distance on every result, so
browse needed its own sort (`search.browse_sort`) and view (`eat_views.area_view`). The
card builder needed no change, because it already handles a place with no route. The
browse is a filter and a sort over the same place list, not a variant of the search.

## Screens

| Route | What it does |
|---|---|
| `GET /eat`, `POST /eat` | The search form. Its starting point is handled exactly as for Lepak: session memory only. |
| `GET /eat/results?sort=&hide=&page=` | The results. |
| `GET /eat/from-event/<event id>` | Sets a Lepak event as the starting point (in the session), then opens the search form. |
| `GET /eat/in/<area>?cuisines=&tiers=&sort=&hide=&page=` | Browse one neighbourhood, with no journey. Linked from the Where to Live recommendation. |
| `GET /eat/places/<id>` | A place: hours as tagged, cuisine as tagged, travel time, map with start and route, directions, parking in drive mode, source link. |
