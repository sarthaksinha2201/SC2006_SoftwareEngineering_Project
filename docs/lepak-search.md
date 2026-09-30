# Where to Lepak: search, travel time and parking

Results are sorted, not scored (DECISIONS §3). The code is in `gowhere/lepak/search.py`,
`routing.py` and `parking.py`, and the screens are in `gowhere/web/lepak_views.py`.

## Search

1. **Candidates.** Stored events in the chosen 1–4 categories that overlap the chosen
   dates. The date options are today, tomorrow, this weekend, the next 7 days and the next
   30 days. "This weekend" means Saturday and Sunday, or the rest of the weekend if it
   has already started.
2. **Straight-line pre-filter.** An event is dropped, without routing, if its
   straight-line distance could not be covered within the maximum time even at a top
   speed:

   | Mode | Top speed |
   |---|---|
   | Walk | 100 m/min |
   | Public transport | 1,000 m/min |
   | Drive | 1,500 m/min |

   These are loose on purpose, so the filter never drops an event a real route would
   keep. On the recorded Junction 8 to City Square Mall routes, the real straight-line
   speeds were 66, 180 and 335 m/min.
3. **The cap.** If more than 50 events survive, nothing is routed and the search page
   asks the user to narrow the search.
4. **Routing.** Each survivor is routed with OneMap, 16 in parallel. Events beyond the
   maximum are dropped. The departure time is:
   - now, for an event already under way;
   - the event's start time, if it has one;
   - 10:00 on its first day, for an all-day event.

   A short trip that gets no public transport itinerary is routed as a walk instead.
5. **Unroutable events are kept.** If OneMap can't route an event, it is listed last,
   marked "Travel time unavailable". It passed the straight-line check, and hiding it
   would hide the failure.

The results are computed once per search and stored in the session. Sorting (shortest
travel time, the default; soonest; recently added), the category chips and paging all
reorder that stored list. A test checks that none of them calls OneMap, DataMall or the
location lookup. Pages hold 10 results.

**Speed.** Measured on 30 Sep 2026: one public transport route takes about 1 s, and 40
of them take 3.1 s with 16 workers (7.4 s with 8), with no failures. So 50 routes fit
inside the 8-second target. A live end-to-end search took 6.0 s for public transport,
including one 2-second backoff after OneMap returned HTTP 429, and 1.1 s for driving.

## Parking (UC-3, drive mode only)

`DataMallAdapter` fetches LTA DataMall's `CarParkAvailabilityv2`, all pages, with the
`AccountKey` header. `ParkingService` then works out, for each venue, the car lots free
within 500 m, listing up to 3 carparks. It keeps one dataset for all users, cached for 2
minutes, so a results page costs at most one DataMall call.

Any failure gives "Parking information unavailable", and the results still show. A
failure is cached like a success, so a DataMall outage doesn't cause a retry storm. The
possible failures are:

- no key;
- an HTTP error;
- a reply that isn't a list of records.

Nobody has registered for a DataMall key yet, so that failure path is what every drive
search shows today, and it is the tested one.
`tests/fixtures/lepak/datamall_carparks.json` is constructed in DataMall's documented
shape, not recorded. The first live call with a key should be checked against it.

Parking is computed at search time and stored with the results. The detail page
refreshes it through the same 2-minute cache. Sorting never refreshes it.

## Privacy (Security NFR)

The starting point is a postal code or the device's coordinates:

- It is posted with the form and never appears in a URL. Only `sort`, `category` and
  `page` do.
- It is resolved by the session's own `LocationService`, in memory only and never
  written to the search cache.
- It is routed with `redact=True`. OneMap echoes coordinates in `requestParameters`, and
  only the duration, legs and geometry are kept.
- The route line shown on the detail page starts at the user's location. That page is
  rendered only for that user's own session.

Tests check that neither the postal code nor the coordinates appear in:

- the redirect;
- the cookie, which holds only `sid`;
- any link on the results pages;
- the log.

A live smoke run against OneMap logged the postal code 0 times.
