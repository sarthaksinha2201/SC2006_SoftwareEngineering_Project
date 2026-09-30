"""Where to Lepak: form parsing and view models.

Same contract as the Where to Live screens: templates only loop and print. Every
sentence is written here. tests/fixtures/mock_lepak_results.json and
mock_lepak_event.json are examples of what the templates receive.

The starting point (a postal code or the device's location) is personal data. It is
parsed here, handed to the session's in-memory state, and never put in a URL, the
cookie or an error message. URLs built here carry only the sort, the category chip and
the page.
"""
from datetime import datetime

from flask import url_for

from gowhere.lepak.categories import CATEGORIES, MAX_SELECTED, MIN_SELECTED
from gowhere.lepak.routing import MODES
from gowhere.lepak.search import (DATE_OPTIONS, MAX_MINUTES_CHOICES, ROUTE_CAP, SORTS,
                                  InvalidSearch, sort_and_filter)
from gowhere.scoring.stats import round0

DEFAULTS = {"categories": [], "date_option": "weekend", "mode": "pt", "max_minutes": 45,
            "origin": "postal"}
SG_BOUNDS = (1.15, 1.48, 103.59, 104.10)     # lat min, lat max, lon min, lon max


def parse_lepak_form(form):
    """{categories, date_option, mode, max_minutes, origin: ("postal", code) or
    ("here", (lat, lon))}. Raises InvalidSearch; messages never echo the input."""
    try:
        max_minutes = int((form.get("max_minutes") or "").strip())
    except ValueError:
        raise InvalidSearch("Maximum travel time must be a whole number of minutes.")
    if form.get("origin") == "here":
        try:
            lat, lon = float(form.get("lat", "")), float(form.get("lon", ""))
        except ValueError:
            raise InvalidSearch("Your location isn't available. Allow location access, "
                                "or enter a postal code instead.")
        if not (SG_BOUNDS[0] <= lat <= SG_BOUNDS[1] and SG_BOUNDS[2] <= lon <= SG_BOUNDS[3]):
            raise InvalidSearch("Your location appears to be outside Singapore. "
                                "Enter a postal code instead.")
        origin = ("here", (lat, lon))
    else:
        postal = (form.get("postal") or "").strip()
        if not (len(postal) == 6 and postal.isdigit()):
            raise InvalidSearch("Enter a 6-digit Singapore postal code.")
        origin = ("postal", postal)
    return {"categories": [c for c in form.getlist("categories") if c],
            "date_option": form.get("date_option", ""), "mode": form.get("mode", ""),
            "max_minutes": max_minutes, "origin": origin}


# ---- wording -------------------------------------------------------------------

def _dt(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M")


def _day(d):
    return f"{d:%a} {d.day} {d:%b}"


def _clock(d):
    return f"{d.hour % 12 or 12}{f':{d:%M}' if d.minute else ''} {'am' if d.hour < 12 else 'pm'}"


def when_text(event, now):
    start = _dt(event["start_at"])
    end = _dt(event["end_at"]) if event["end_at"] else None
    if end and start < now and start.date() != end.date():
        return f"On now until {_day(end)}"
    if end is None or end.date() == start.date() or (not event["all_day"] and end.hour < 6
                                                      and (end.date() - start.date()).days == 1):
        if event["all_day"]:
            return _day(start)
        return f"{_day(start)}, {_clock(start)}" + (f" – {_clock(end)}" if end else "")
    return f"{_day(start)} – {_day(end)}" + ("" if event["all_day"] else f", from {_clock(start)}")


def distance_text(metres):
    if metres < 1000:
        return f"{round0(metres / 10) * 10} m"
    return f"{round0(metres / 100) / 10:.1f} km"


def travel_text(r, mode):
    """The travel line on a card. Three cases, each labelled for what it is:
    a route in the chosen mode; a walking route used because public transport had no
    itinerary for a short trip; or no route at all, where only the straight-line
    distance is known (FR 2.2.6: shown as an estimate)."""
    route = r.get("route")
    if route is None:
        if r.get("distance_m") is None:
            return None
        return (f"About {distance_text(r['distance_m'])} away "
                f"(straight-line estimate, no route available)")
    minutes = max(1, round0(route["minutes"]))
    if route.get("mode", mode) != mode:
        return (f"{minutes} min on foot (walking route: no {MODES[mode]} route was found "
                f"for this short trip)")
    return f"{minutes} min by {MODES[mode]}"


def _source(url):
    return {"url": url, "label": url.replace("https://", "")}


def card(r, mode, now):
    route = r.get("route")
    parking = r.get("parking")
    return {
        "id": r["id"], "title": r["title"], "category": r["category"],
        "when": when_text(r, now), "venue": r["venue"] or r["address"],
        "address": r["address"] if r["venue"] else None,
        "summary": r["summary"],
        "travel": travel_text(r, mode),
        "travel_estimated": route is None,
        "route_summary": route["summary"] if route else None,
        "parking": parking["text"] if parking else None,
        "sources": [_source(u) for u in r["sources"]],
        "detail_url": url_for("web.lepak_event", event_id=r["id"]),
    }


# ---- screens -------------------------------------------------------------------

def setup_view(form=None, error=None):
    get = (lambda k, d=None: form.get(k, d)) if form else (lambda k, d=None: d)
    chosen = set(form.getlist("categories")) if form else set(DEFAULTS["categories"])
    date_option = get("date_option", DEFAULTS["date_option"])
    mode = get("mode", DEFAULTS["mode"])
    max_minutes = str(get("max_minutes", DEFAULTS["max_minutes"]))
    return {
        "min_categories": MIN_SELECTED, "max_categories": MAX_SELECTED,
        "categories": [{"value": c, "label": c, "checked": c in chosen} for c in CATEGORIES],
        "date_options": [{"value": k, "label": v, "selected": k == date_option}
                         for k, v in DATE_OPTIONS.items()],
        "modes": [{"value": k, "label": v[0].upper() + v[1:], "selected": k == mode}
                  for k, v in MODES.items()],
        "max_minutes": [{"value": str(m), "label": f"{m} min", "selected": str(m) == max_minutes}
                        for m in MAX_MINUTES_CHOICES],
        "origin": get("origin", DEFAULTS["origin"]),
        # Refilled only from this session's own server-side state, never a URL.
        "postal": get("postal", "") if get("origin", "postal") == "postal" else "",
        "error": error,
    }


def too_many_message(count):
    return (f"{count} events match, more than the {ROUTE_CAP} we can work out travel times for "
            f"at once. Choose fewer categories, a shorter date range or a shorter travel time.")


def results_view(saved, sort, category, page, now):
    """`saved` is the session's search: {request, search}. Reordering only."""
    req, found = saved["request"], saved["search"]
    sort = sort if sort in SORTS else "travel"
    category = category if category in req["categories"] else None
    rows, total, pages = sort_and_filter(found["results"], sort, category, page)
    page = min(max(1, page), pages)
    link = lambda **kw: url_for("web.lepak_results", **{"sort": sort, "category": category,
                                                        "page": 1, **kw})
    all_count = len(found["results"])
    by_cat = {c: sum(r["category"] == c for r in found["results"]) for c in req["categories"]}
    return {
        "heading": (f"{all_count} {'event' if all_count == 1 else 'events'} within "
                    f"{req['max_minutes']} min by {MODES[req['mode']]}, "
                    f"{DATE_OPTIONS[req['date_option']].lower()}"),
        "empty_text": ("" if total else
                       "No events match. Try more categories, a longer date range or a longer "
                       "travel time."),
        "unroutable_note": ("No route could be found for some events, so their straight-line "
                            "distance is shown as an estimate and they are listed last."
                            if any(r["minutes"] is None for r in rows) else ""),
        "sorts": [{"value": k, "label": v, "selected": k == sort, "url": link(sort=k)}
                  for k, v in SORTS.items()],
        "chips": ([{"label": "All", "count": all_count, "selected": category is None,
                    "url": link(category=None)}]
                  + [{"label": c, "count": by_cat[c], "selected": c == category,
                      "url": link(category=c)} for c in req["categories"]]),
        "cards": [card(r, req["mode"], now) for r in rows],
        "page": page, "pages": pages, "total": total,
        "prev_url": link(page=page - 1) if page > 1 else None,
        "next_url": link(page=page + 1) if page < pages else None,
        "search_url": url_for("web.lepak_setup"),
    }


def event_view(r, mode, now):
    """The event detail screen: its card plus a map of the venue and, when the event
    came from this session's search, the route to it."""
    c = card(r, mode, now) if mode else card({**r, "route": None, "distance_m": None}, "pt", now)
    if not mode:
        c["travel"], c["travel_estimated"] = None, False
    features = [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [r["lon"], r["lat"]]},
                 "properties": {"kind": "venue", "name": c["venue"]}}]
    if r.get("route"):
        features.insert(0, {"type": "Feature", "geometry": r["route"]["geometry"],
                            "properties": {"kind": "route"}})
    parking = r.get("parking")
    return {**c, "map": {"type": "FeatureCollection", "features": features},
            "carparks": [{"name": p["name"], "lots": p["lots"],
                          "distance": f"{round0(p['distance_m'] / 10) * 10} m"}
                         for p in (parking or {}).get("carparks", [])],
            "back_url": url_for("web.lepak_results"), "search_url": url_for("web.lepak_setup")}
