"""Where to Lepak search (DECISIONS.md section 3): results are sorted, not scored.

1. Stored events in the chosen categories (1 to 8) that overlap the chosen dates.
2. Straight-line pre-filter: an event whose straight-line distance could not be covered
   within the maximum travel time even at a generous top speed for the mode is dropped
   without routing. The speeds are deliberately loose upper bounds, so the filter never
   drops an event a real route would have kept.
3. More than ROUTE_CAP survivors: only the ROUTE_CAP nearest by straight line are
   routed, and the results say how many were within reach (DECISIONS.md section 33).
   Refusing the search was reasonable while 4 categories kept searches narrow. With all 8
   allowed, "everything this weekend" is the expected first search, and it gets the
   nearest events, honestly labelled, not an error.
4. Each routed event within the maximum is kept.
   Events OneMap could not route are kept too, marked "travel time unavailable" and
   sorted last: they passed the straight-line check, and hiding them would hide the
   failure.

The result is computed once per search and kept in the user's session; sorting, hiding
categories and paging only reorder it (sort_and_filter), so they call nothing.
"""
from datetime import datetime, time, timedelta

from gowhere.etl.geo import haversine_m
from gowhere.lepak.categories import CATEGORIES, MAX_SELECTED, MIN_SELECTED
from gowhere.lepak.routing import MODES

DATE_OPTIONS = {"today": "Today", "tomorrow": "Tomorrow", "weekend": "This weekend",
                "week": "Next 7 days", "month": "Next 30 days"}
MAX_MINUTES_CHOICES = (15, 30, 45, 60, 90)
MIN_MINUTES, MAX_MINUTES = 5, 180
# Straight-line metres per minute no real trip beats: brisk walk 6 km/h; MRT at 60 km/h
# with no walking or waiting; driving at 90 km/h door to door.
TOP_SPEED_M_PER_MIN = {"walk": 100.0, "pt": 1000.0, "drive": 1500.0}
# 25, not 50 (DECISIONS.md section 33, measured 22 Oct 2026): 50 routes took a median of
# 9.2 s, past the 8 s target, while 25 took 6.4 s. The same as Where to Eat.
ROUTE_CAP = 25
SORTS = {"travel": "Shortest travel time", "soonest": "Soonest", "recent": "Recently added"}
PAGE_SIZE = 10


class InvalidSearch(ValueError):
    pass


def validate(categories, date_option, mode, max_minutes):
    if not MIN_SELECTED <= len(set(categories)) <= MAX_SELECTED:
        raise InvalidSearch(f"Choose {MIN_SELECTED} to {MAX_SELECTED} categories.")
    if any(c not in CATEGORIES for c in categories):
        raise InvalidSearch("Choose categories from the list.")
    if date_option not in DATE_OPTIONS:
        raise InvalidSearch("Choose when you want to go.")
    if mode not in MODES:
        raise InvalidSearch("Choose a travel mode.")
    if not isinstance(max_minutes, int) or not MIN_MINUTES <= max_minutes <= MAX_MINUTES:
        raise InvalidSearch(f"Maximum travel time must be {MIN_MINUTES} to {MAX_MINUTES} minutes.")


def date_window(option, now):
    """(from, to) naive Singapore datetimes for a date option."""
    today = datetime.combine(now.date(), time(0, 0))
    end_of = lambda d: datetime.combine(d.date(), time(23, 59))
    if option == "today":
        return now, end_of(now)
    if option == "tomorrow":
        return today + timedelta(days=1), end_of(today + timedelta(days=1))
    if option == "weekend":
        if now.weekday() >= 5:                       # already Saturday or Sunday
            return now, end_of(today + timedelta(days=6 - now.weekday()))
        saturday = today + timedelta(days=5 - now.weekday())
        return saturday, end_of(saturday + timedelta(days=1))
    days = {"week": 7, "month": 30}[option]
    return now, end_of(today + timedelta(days=days))


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def candidates(events, categories, date_option, now):
    start, end = date_window(date_option, now)
    return [e for e in events if e["category"] in categories
            and e["start_at"] <= _fmt(end) and e["ends_at"] >= _fmt(start)]


def within_straight_line(events, origin, mode, max_minutes):
    reach = TOP_SPEED_M_PER_MIN[mode] * max_minutes
    out = []
    for e in events:
        d = haversine_m(origin[0], origin[1], e["lat"], e["lon"])
        if d <= reach:
            out.append({**e, "distance_m": d})
    return out


def search(events, origin, categories, date_option, mode, max_minutes, router, now,
           parking=None):
    """{results, counts}. `events` are the store's current events. Raises InvalidSearch.
    `parking` (drive mode only) adds each result's parking."""
    validate(categories, date_option, mode, max_minutes)
    pool = candidates(events, set(categories), date_option, now)
    near = within_straight_line(pool, origin, mode, max_minutes)
    timed = sorted(near, key=lambda e: (e["distance_m"], e["id"]))[:ROUTE_CAP]
    routes = router.route_many(origin, timed, mode, now) if timed else {}
    results = []
    for e in timed:
        route = routes.get(e["id"])
        if route is not None and route["minutes"] > max_minutes:
            continue
        results.append({**e, "route": route,
                        "minutes": None if route is None else route["minutes"]})
    if mode == "drive" and parking is not None:
        for r in results:
            r["parking"] = parking.near(r["lat"], r["lon"])
    return {"results": results,
            "counts": {"in_categories_and_dates": len(pool), "within_straight_line": len(near),
                       "timed": len(timed),
                       "routed": sum(r is not None for r in routes.values()),
                       "shown": len(results)}}


def sort_and_filter(results, sort="travel", hidden=(), page=1):
    """(page of results, total matching, number of pages), with the categories in
    `hidden` left out (FR 2.4.2). Pure: no external calls."""
    hidden = set(hidden)
    if hidden:
        results = [r for r in results if r["category"] not in hidden]
    if sort == "soonest":
        key = lambda r: (r["start_at"], r["title"])
    elif sort == "recent":
        key = lambda r: (-datetime.strptime(r["added_at"], "%Y-%m-%d %H:%M").timestamp(), r["title"])
    else:
        key = lambda r: (r["minutes"] is None, r["minutes"] or 0, r["start_at"], r["title"])
    ordered = sorted(results, key=key)
    pages = max(1, -(-len(ordered) // PAGE_SIZE))
    page = min(max(1, page), pages)
    return ordered[(page - 1) * PAGE_SIZE: page * PAGE_SIZE], len(ordered), pages
