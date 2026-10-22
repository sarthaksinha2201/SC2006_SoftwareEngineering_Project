"""Where to Eat: form parsing and view models (DECISIONS.md sections 25 and 25a).

Same contract as the other screens: templates only loop and print, and every sentence
is written here. The starting point is personal data and is handled exactly as for
Where to Lepak: parsed here, kept in session memory, never put in a URL, the cookie or a
message. URLs built here carry only the sort, the hidden cuisines and the page.
"""
from datetime import datetime

from flask import url_for

from gowhere.eat.cuisines import CUISINES, NOT_LISTED
from gowhere.eat.hours import clock
from gowhere.eat.search import (MAX_MINUTES_CHOICES, SORTS, TIERS,
                                WHEN_OPTIONS, InvalidSearch, label_of, sort_and_filter)
from gowhere.lepak.images import slugify
from gowhere.lepak.routing import MODES
from gowhere.scoring.stats import round0
from gowhere.web.lepak_views import parse_max_minutes, parse_origin, travel_text

DEFAULTS = {"cuisines": [], "tiers": list(TIERS), "when": "now", "mode": "pt",
            "max_minutes": 15, "origin": "postal"}
KIND_LABELS = {"hawker_centre": "Hawker centre", "food_court": "Food court",
               "marketplace": "Market", "restaurant": "Restaurant", "cafe": "Café",
               "fast_food": "Fast food", "ice_cream": "Ice cream & desserts"}


def parse_eat_form(form):
    """{cuisines, tiers, when, mode, max_minutes, origin}. Raises InvalidSearch."""
    max_minutes = parse_max_minutes(form, InvalidSearch)
    origin = parse_origin(form, InvalidSearch)
    return {"cuisines": [c for c in form.getlist("cuisines") if c],
            "tiers": [t for t in form.getlist("tiers") if t],
            "when": form.get("when", ""), "mode": form.get("mode", ""),
            "max_minutes": max_minutes, "origin": origin}


# ---- wording -------------------------------------------------------------------

def when_text(when, at, now):
    """'now', or 'lunch today (12:30 pm)' / 'supper tomorrow (10:30 pm)'."""
    if WHEN_OPTIONS[when][1] is None:
        return "now"
    day = "today" if at.date() == now.date() else "tomorrow"
    return f"{WHEN_OPTIONS[when][0].lower()} {day} ({clock(at)})"


def kind_text(p):
    label = KIND_LABELS.get(p["kind"], "Eatery")
    if p.get("stalls"):
        return f"{label} · {p['stalls']} stalls"
    return label


def cuisine_text(p):
    return ", ".join(p["cuisines"]) if p["cuisines"] else NOT_LISTED


def card(r, mode):
    route = r.get("route")
    parking = r.get("parking")
    return {
        "id": r["id"], "name": r["name"], "kind": kind_text(r),
        "tier_label": TIERS[r["price_tier"]],
        "cuisine": cuisine_text(r), "cuisine_listed": bool(r["cuisines"]),
        "cuisine_slug": slugify(r["cuisines"][0]) if r["cuisines"] else "not-listed",
        "open_text": r["open"]["text"],
        # open / closed / unknown: the CSS colours the status line from this.
        "open_state": {True: "open", False: "closed", None: "unknown"}[r["open"]["open"]],
        "address": r["address"],
        "travel": travel_text(r, mode),
        "travel_estimated": route is None,
        "route_summary": route["summary"] if route else None,
        "parking": parking["text"] if parking else None,
        "detail_url": url_for("web.eat_place", place_id=r["id"]),
        "rating": rating_view(r.get("rating")),
        # DECISIONS.md section 29: notability, not quality; the wording says which.
        "notable": ({"label": "On Wikipedia",
                     "title": "This place has its own Wikipedia article. That says it is "
                              "notable, not that the food is good.",
                     "url": "https://en.wikipedia.org/wiki/" + r["wikipedia_title"].replace(" ", "_")}
                    if r.get("wikipedia_title") else None),
    }


def rating_view(rating):
    """'4.3' with '1,234 reviews' and the Google Maps link, or None. No rating shows
    nothing at all, so it can't be read as a bad one."""
    if not rating:
        return None
    count = rating["count"]
    return {"value": f"{rating['value']:.1f}",
            "count": f"{count:,} review{'s' if count != 1 else ''}",
            "maps_url": rating["maps_url"]}


def coverage_note(meta):
    return (f"Cuisine is listed for {round0(float(meta['cuisine_listed_pct']))}% of places "
            f"in OpenStreetMap, and opening hours are known for "
            f"{round0(float(meta['hours_known_pct']))}%. Places without them are still shown, "
            f"marked \"{NOT_LISTED}\" or \"Opening hours unknown\".")


def data_note(meta):
    return (f"Places from OpenStreetMap (data of {meta['osm_data_as_of']}) and NEA hawker "
            f"centres (fetched {meta['hawker_data_as_of']}). No ratings: there is no free, "
            f"current source of food quality or hygiene grades we can use.")


# ---- screens -------------------------------------------------------------------

def setup_view(form=None, error=None):
    get = (lambda k, d=None: form.get(k, d)) if form else (lambda k, d=None: d)
    cuisines = set(form.getlist("cuisines")) if form else set(DEFAULTS["cuisines"])
    tiers = set(form.getlist("tiers")) if form else set(DEFAULTS["tiers"])
    when = get("when", DEFAULTS["when"])
    mode = get("mode", DEFAULTS["mode"])
    max_minutes = str(get("max_minutes", DEFAULTS["max_minutes"]))
    return {
        "cuisines": [{"value": c, "label": c, "slug": slugify(c), "checked": c in cuisines}
                     for c in CUISINES],
        "tiers": [{"value": k, "label": v, "checked": k in tiers}
                  for k, v in TIERS.items()],
        "whens": [{"value": k, "label": v[0] if v[1] is None else f"{v[0]} ({clock_of(v[1])})",
                   "selected": k == when} for k, v in WHEN_OPTIONS.items()],
        "modes": [{"value": k, "label": v[0].upper() + v[1:], "selected": k == mode}
                  for k, v in MODES.items()],
        "max_minutes": [{"value": str(m), "label": f"{m} min", "selected": str(m) == max_minutes}
                        for m in MAX_MINUTES_CHOICES],
        "origin": get("origin", DEFAULTS["origin"]),
        "postal": get("postal", "") if get("origin", "postal") == "postal" else "",
        "error": error,
    }


def clock_of(t):
    return clock(datetime.combine(datetime(2000, 1, 1).date(), t))


def results_view(saved, sort, hidden, page, now, meta):
    """`saved` is the session's search: {request, search}. Reordering only."""
    req, found = saved["request"], saved["search"]
    rated = sum(bool(r.get("rating")) for r in found["results"])
    sorts = [k for k in SORTS if k != "rated" or rated]   # no ratings: no rating sort
    sort = sort if sort in sorts else "nearest"
    labels = req["cuisines"] + [NOT_LISTED] if req["cuisines"] else []
    hidden = [c for c in labels if c in set(hidden or ())]
    rows, total, pages = sort_and_filter(found["results"], sort, hidden, page,
                                         cuisine_filter=bool(req["cuisines"]))
    page = min(max(1, page), pages)
    link = lambda **kw: url_for("web.eat_results", **{"sort": sort, "hide": hidden,
                                                      "page": 1, **kw})
    toggled = lambda c: [x for x in labels if (x in hidden) != (x == c)]
    results = found["results"]
    counts = found["counts"]
    n = len(results)
    by_label = {c: sum(c in label_of(r) for r in results) for c in labels}
    sort_labels = {**SORTS, "open": "Open now" if req["when"] == "now" else
                   f"Open at {WHEN_OPTIONS[req['when']][0].lower()}"}
    return {
        "heading": (f"{n} {'place' if n == 1 else 'places'} within {req['max_minutes']} min "
                    f"by {MODES[req['mode']]}"
                    + ("" if req["when"] == "now" else
                       f", for {when_text(req['when'], found['at'], now)}")),
        "timed_note": (f"Travel times were worked out for the {counts['routed']} nearest of "
                       f"{counts['within_reach']:,} places within reach."
                       if counts["within_reach"] > counts["routed"] else ""),
        "coverage_note": coverage_note(meta),
        "data_note": data_note(meta),
        "empty_text": ("" if total else
                       "No places match. Try more kinds of place, more cuisines or a longer "
                       "travel time." if not hidden else
                       "Every matching place is in a hidden cuisine. Show one again to see "
                       "its places."),
        "unroutable_note": ("No route could be found for some places, so their straight-line "
                            "distance is shown as an estimate and they are listed last."
                            if any(r["minutes"] is None for r in rows) else ""),
        "sorts": [{"value": k, "label": sort_labels[k], "selected": k == sort,
                   "url": link(sort=k)} for k in sorts],
        "ratings_note": (f"Ratings from Google Maps for {rated} of these places. A place "
                         f"with no rating shown has none we could fetch, not a low one."
                         if rated else ""),
        "chips": ([{"label": "All", "count": n, "selected": not hidden, "url": link(hide=[])}]
                  + [{"label": c, "count": by_label[c], "selected": c not in hidden,
                      "url": link(hide=toggled(c))} for c in labels]) if labels else [],
        "cards": [card(r, req["mode"]) for r in rows],
        "page": page, "pages": pages, "total": total,
        "prev_url": link(page=page - 1) if page > 1 else None,
        "next_url": link(page=page + 1) if page < pages else None,
        "search_url": url_for("web.eat_setup"),
        "view_state": {"sort": sort, "hide": hidden, "page": page},
    }


def _source(p):
    if p["source"] == "nea":
        return {"url": p["source_url"], "label": "NEA hawker centres (data.gov.sg)"}
    return {"url": p["source_url"], "label": "OpenStreetMap"}


def place_view(p, mode, back=None, origin=None, meta=None):
    """The place detail screen. With a session search (`mode`), the travel time, route,
    directions and starting point; without one, the place alone."""
    c = card(p, mode or "pt")
    if not mode:
        c["travel"], c["travel_estimated"] = None, False
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [p["lon"], p["lat"]]},
                 "properties": {"kind": "venue", "name": p["name"]}}]
    if p.get("route"):
        features.insert(0, {"type": "Feature", "geometry": p["route"]["geometry"],
                            "properties": {"kind": "route"}})
    if origin:          # the user's own starting point, on their own page only
        features.append({"type": "Feature",
                         "geometry": {"type": "Point", "coordinates": [origin[1], origin[0]]},
                         "properties": {"kind": "start", "name": "Your starting point"}})
    parking = p.get("parking")
    return {**c,
            "hours_tag": p["opening_hours"],
            "cuisine_tag": p["cuisine_tag"],
            "map": {"type": "FeatureCollection", "features": features},
            "steps": (p.get("route") or {}).get("steps", []),
            "carparks": [{"name": cp["name"], "lots": cp["lots"],
                          "distance": f"{round0(cp['distance_m'] / 10) * 10} m"}
                         for cp in (parking or {}).get("carparks", [])],
            "source": _source(p),
            "data_note": data_note(meta) if meta else "",
            "back_url": url_for("web.eat_results", **(back or {})) if back is not None else None,
            "search_url": url_for("web.eat_setup")}
