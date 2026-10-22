"""Where to Eat search (DECISIONS.md sections 25 and 25a): results are sorted, not scored.
There is no quality or popularity signal: hygiene grades have no current bulk source, and
Michelin's terms forbid copying its guide (docs/eat-measurements.md).

1. Places of the chosen price tiers. If cuisines are chosen, the places in them, plus the
   places whose cuisine is not listed. Those are labelled and can be hidden with a chip,
   but are kept by default (§25: shown and labelled, never hidden).
2. Straight-line pre-filter, as for Lepak: a place that could not be reached within the
   maximum time even at the mode's top speed is dropped without routing.
3. Unlike events, there are thousands of places within reach of a city-centre starting
   point, so only the ROUTE_BUDGET nearest by straight line are routed. The results say
   how many places were within reach and how many were timed. Two reservations within
   that budget:
   - up to DESTINATION_SLOTS go to food destinations (hawker centres, food courts), so
     "Most variety" has something to sort;
   - when cuisines are chosen, at most NOT_LISTED_SLOTS go to places whose cuisine is not
     listed. Otherwise they crowd out what was asked for: near Orchard, half the nearest
     restaurants have no cuisine tag.
4. Routed places within the maximum are kept. Unroutable ones are kept as straight-line
   estimates and listed last, as for Lepak (§13).

Departure time is the chosen mealtime, and "open" is judged at that time from OSM
opening_hours. About one place in five has hours we understand; the rest are "Opening
hours unknown".
"""
from datetime import datetime, time, timedelta

from gowhere.eat import hours as hours_mod
from gowhere.eat.cuisines import CUISINES, NOT_LISTED
from gowhere.etl.geo import haversine_m
from gowhere.lepak.routing import MODES
from gowhere.lepak.search import TOP_SPEED_M_PER_MIN

# "Now", or the next breakfast, lunch, dinner or supper: today if it is still ahead,
# otherwise tomorrow.
WHEN_OPTIONS = {"now": ("Now", None), "breakfast": ("Breakfast", time(8, 30)),
                "lunch": ("Lunch", time(12, 30)), "dinner": ("Dinner", time(19, 0)),
                "supper": ("Supper", time(22, 30))}
TIERS = {"budget": "Hawker centres, food courts & kopitiams",
         "casual": "Cafés & fast food",
         "restaurant": "Restaurants"}
MAX_MINUTES_CHOICES = (10, 15, 20, 30, 45)
MIN_MINUTES, MAX_MINUTES = 5, 90
# 25, not 40 (DECISIONS.md section 30): measured 19 Oct, 25 places gave a better median
# (4.47 s against 5.29 s), a better 90th percentile and about half the OneMap rate-limit
# retries. Halving the workers instead pushed the 90th percentile to 7.97 s.
ROUTE_BUDGET = 25
DESTINATION_SLOTS = 6
NOT_LISTED_SLOTS = 6
SORTS = {"nearest": "Nearest", "open": "Open first", "variety": "Most variety",
         "rated": "Highest rated"}
PAGE_SIZE = 10


class InvalidSearch(ValueError):
    pass


def validate(cuisines, tiers, when, mode, max_minutes):
    if any(c not in CUISINES for c in cuisines):
        raise InvalidSearch("Choose cuisines from the list.")
    if not tiers or any(t not in TIERS for t in tiers):
        raise InvalidSearch("Choose at least one kind of place.")
    if when not in WHEN_OPTIONS:
        raise InvalidSearch("Choose when you want to eat.")
    if mode not in MODES:
        raise InvalidSearch("Choose a travel mode.")
    if not isinstance(max_minutes, int) or not MIN_MINUTES <= max_minutes <= MAX_MINUTES:
        raise InvalidSearch(f"Maximum travel time must be {MIN_MINUTES} to {MAX_MINUTES} minutes.")


def meal_time(when, now):
    """The datetime the user means: now, or the next such mealtime."""
    at = WHEN_OPTIONS[when][1]
    if at is None:
        return now
    slot = datetime.combine(now.date(), at)
    return slot if slot >= now else slot + timedelta(days=1)


def candidates(places, cuisines, tiers):
    """Places of the chosen tiers in the chosen cuisines, plus those not listed.
    No cuisines chosen means any."""
    tiers, chosen = set(tiers), set(cuisines)
    out = []
    for p in places:
        if p["price_tier"] not in tiers:
            continue
        if chosen and p["cuisines"] and not chosen & set(p["cuisines"]):
            continue
        out.append(p)
    return out


def nearest_within_reach(places, origin, mode, max_minutes, cuisines_chosen=False):
    """(the places to route, how many were within straight-line reach)."""
    reach = TOP_SPEED_M_PER_MIN[mode] * max_minutes
    near = []
    for p in places:
        d = haversine_m(origin[0], origin[1], p["lat"], p["lon"])
        if d <= reach:
            near.append({**p, "distance_m": d})
    near.sort(key=lambda p: (p["distance_m"], p["id"]))
    chosen = [p for p in near if p["destination"]][:DESTINATION_SLOTS]
    not_listed = 0
    for p in near:
        if len(chosen) >= ROUTE_BUDGET:
            break
        if p["destination"]:
            continue                     # every destination worth routing is in already
        if cuisines_chosen and not p["cuisines"]:
            if not_listed >= NOT_LISTED_SLOTS:
                continue
            not_listed += 1
        chosen.append(p)
    return sorted(chosen, key=lambda p: (p["distance_m"], p["id"])), len(near)


def search(places, origin, cuisines, tiers, when, mode, max_minutes, router, now,
           parking=None):
    """{results, at, counts}. Raises InvalidSearch."""
    validate(cuisines, tiers, when, mode, max_minutes)
    at = meal_time(when, now)
    pool = candidates(places, cuisines, tiers)
    chosen, within_reach = nearest_within_reach(pool, origin, mode, max_minutes,
                                                cuisines_chosen=bool(cuisines))
    routes = router.route_many(origin, chosen, mode, now, departure=at) if chosen else {}
    results = []
    for p in chosen:
        route = routes.get(p["id"])
        if route is not None and route["minutes"] > max_minutes:
            continue
        results.append({**p, "route": route,
                        "minutes": None if route is None else route["minutes"],
                        "open": hours_mod.status(p["opening_hours"], at)})
    if mode == "drive" and parking is not None:
        for r in results:
            r["parking"] = parking.near(r["lat"], r["lon"])
    return {"results": results, "at": at,
            "counts": {"matching": len(pool), "within_reach": within_reach,
                       "routed": len(chosen), "shown": len(results)}}


def label_of(place):
    """The cuisine labels a result is filtered by: its groups, or 'not listed'."""
    return place["cuisines"] or [NOT_LISTED]


_OPEN_ORDER = {True: 0, None: 1, False: 2}


def sort_and_filter(results, sort="nearest", hidden=(), page=1, cuisine_filter=False):
    """(page of results, total matching, number of pages). A result is hidden only when
    every one of its cuisine labels is hidden. With a cuisine filter active, places whose
    cuisine is not listed come after every match, whatever the sort (DECISIONS.md
    section 28): still shown and labelled, but no longer above what was asked for.
    Pure: no external calls."""
    hidden = set(hidden)
    if hidden:
        results = [r for r in results if not set(label_of(r)) <= hidden]
    travel = lambda r: (r["minutes"] is None, r["minutes"] or 0, r["distance_m"])
    if sort == "open":
        key = lambda r: (_OPEN_ORDER[r["open"]["open"]], *travel(r), r["name"])
    elif sort == "variety":
        key = lambda r: (not r["destination"], -(r["stalls"] or 0), *travel(r), r["name"])
    elif sort == "rated":
        # Rated places first, best first; places with no rating follow in travel order,
        # because no rating is not a low rating (DECISIONS.md section 29).
        rating = lambda r: r.get("rating") or {}
        key = lambda r: (not rating(r), -rating(r).get("value", 0), -rating(r).get("count", 0),
                         *travel(r), r["name"])
    else:
        key = lambda r: (*travel(r), r["name"])
    ordered = sorted(results, key=(lambda r: (not r["cuisines"], key(r))) if cuisine_filter else key)
    pages = max(1, -(-len(ordered) // PAGE_SIZE))
    page = min(max(1, page), pages)
    return ordered[(page - 1) * PAGE_SIZE: page * PAGE_SIZE], len(ordered), pages
