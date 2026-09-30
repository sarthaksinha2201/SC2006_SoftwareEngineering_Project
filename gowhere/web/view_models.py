"""Turn engine output into exactly what a template needs.

Templates do no computation beyond looping and printing: every number here is already
formatted (scores rounded half up to 1 d.p. by the engine), every sentence already
written. tests/fixtures/mock_results.json is an example of results_view()'s output and
is the contract the front-end templates are built against.
"""
import json
from datetime import datetime

from shapely.geometry import mapping, shape

from gowhere.scoring.amenities import AMENITY_TYPES
from gowhere.scoring.commute import MODES
from gowhere.scoring.healthcare import FACILITY_LABELS
from gowhere.scoring.housing import FLAT_TYPES, MIN_LEASE_YEARS
from gowhere.web.forms import FACTOR_ORDER

CLOSE_CALL_POINTS = "0.2"
MAP_TOLERANCE_DEG = 0.0001   # ~11 m: boundaries stay accurate at street zoom, page stays light
DEFAULTS = {
    "weight": 5,
    "excluded": {"commute"},           # needs a destination, so opt-in
    "flat_type": "4 ROOM", "budget_min": 400_000, "budget_max": 700_000,
    "min_remaining_lease_years": None,
    "amenity_types": ["supermarket", "hawker_centre"],
    "facility_type": "polyclinic",
    "mode": "pt",
}


def area_name(key):
    return key.title()


def _ordinal(n):
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _join(names):
    return names[0] if len(names) == 1 else f"{', '.join(names[:-1])} and {names[-1]}"


def _fmt(score):
    return f"{score:.1f}"


def snapshot_date(meta):
    d = datetime.fromisoformat(meta["generated_at"])
    return f"{d.day} {d:%b %Y}"


# ---- results ------------------------------------------------------------------

def dropped_messages(dropped):
    return [f"{d['label']} was left out because {_join([area_name(a) for a in d['missing_for']])} "
            f"{d['reason']}." for d in dropped]


def recommendation(result):
    ex, areas = result["explanation"], result["areas"]
    winner, runner = area_name(ex["winner"]), area_name(ex["runner_up"])
    top = areas[0]
    joint = areas[1]["rank"] == top["rank"]
    reasons = [{"label": f["label"], "contribution": _fmt(abs(f["contribution"])),
                "favours": winner if f["contribution"] >= 0 else runner}
               for f in ex["factors"]]
    helping = [f["label"] for f in ex["factors"] if f["contribution"] > 0][:2]
    if joint:
        headline = f"{winner} and {runner} are joint first with {_fmt(top['overall_display'])} out of 10."
    else:
        headline = f"{winner} ranks first with {_fmt(top['overall_display'])} out of 10."
    because = (f"{winner} ranks ahead of {runner} mainly because of {_join(helping)}."
               if helping and not joint else "")
    return {
        "headline": headline, "because": because, "winner": winner, "runner_up": runner,
        "close_call": result["close_call"],
        "close_call_text": (f"{winner} and {runner} are within {CLOSE_CALL_POINTS} points of each "
                            f"other, so changing a single weight could swap them."
                            if result["close_call"] else ""),
        "reasons": reasons,
    }


def results_view(result, snapshot):
    factors = result["factors"]
    rank_counts = {}
    for a in result["areas"]:
        rank_counts[a["rank"]] = rank_counts.get(a["rank"], 0) + 1
    rows = []
    for a in result["areas"]:
        rows.append({
            "key": a["name"], "name": area_name(a["name"]), "rank": a["rank"],
            "rank_label": ("Joint " if rank_counts[a["rank"]] > 1 else "") + _ordinal(a["rank"]),
            "overall": _fmt(a["overall_display"]),
            "flats_text": f"{a['n_flats']:,} flats in {a['n_blocks']} "
                          f"{'block' if a['n_blocks'] == 1 else 'blocks'}",
            "small_sample": bool(a["small_sample"]),
            "notes": a["notes"],
            "categories": [{"key": f["key"], "label": f["label"],
                            "score": _fmt(a["category_display"][f["key"]]),
                            "summary": a["raw"].get(f["key"], {}).get("summary", "")}
                           for f in factors],
        })
    geometry = {r["name"]: _simplified(r["geometry_geojson"]) for r in snapshot.query(
        f"SELECT name, geometry_geojson FROM planning_area WHERE name IN "
        f"({', '.join('?' for _ in rows)})", tuple(r["key"] for r in rows))}
    return {
        "snapshot_date": snapshot_date(result["snapshot"]),
        "factors": [{"key": f["key"], "label": f["label"], "weight": f["weight"],
                     "notes": f["notes"]} for f in factors],
        "areas": rows,
        "dropped": dropped_messages(result["dropped"]),
        "recommendation": recommendation(result),
        "chart": {"labels": [f["label"] for f in factors],
                  "datasets": [{"label": r["name"],
                                "data": [float(c["score"]) for c in r["categories"]]}
                               for r in rows]},
        "map": {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": geometry[r["key"]],
             "properties": {"name": r["name"], "rank": r["rank"], "overall": r["overall"]}}
            for r in rows]},
    }


def _simplified(geojson_text):
    geom = shape(json.loads(geojson_text)).simplify(MAP_TOLERANCE_DEG, preserve_topology=True)
    return json.loads(json.dumps(mapping(geom)))   # tuples -> lists, as JSON has them


# ---- setup --------------------------------------------------------------------

def setup_view(engine, snapshot, form=None, error=None):
    """The setup screen. `form` is the last submitted form (to refill it), or None."""
    get = (lambda k, d=None: form.get(k, d)) if form else (lambda k, d=None: d)
    getlist = (lambda k, d: form.getlist(k)) if form else (lambda k, d: d)
    labels = {f["key"]: f["label"] for f in engine.factors()}
    areas = snapshot.areas()
    selected = set(getlist("areas", []))
    factors = []
    for key in FACTOR_ORDER:
        if key not in labels:
            continue
        included = bool(get(f"include_{key}")) if form else key not in DEFAULTS["excluded"]
        factors.append({"key": key, "label": labels[key], "included": included,
                        "weight": int(get(f"weight_{key}", DEFAULTS["weight"]) or DEFAULTS["weight"]),
                        "controls": _controls(key, get, getlist)})
    return {
        "snapshot_date": snapshot_date(snapshot.meta()),
        "min_areas": 2, "max_areas": 4,
        "areas": [{"key": k, "name": area_name(k), "selected": k in selected,
                   "small_sample": bool(v["small_sample"]),
                   "flats_text": f"{v['n_flats']:,} flats in {v['n_blocks']} blocks"}
                  for k, v in areas.items() if v["in_scope"]],
        "factors": factors,
        "error": error,
    }


def _controls(key, get, getlist):
    if key == "housing_affordability":
        flat = get("flat_type", DEFAULTS["flat_type"])
        lease = get("min_remaining_lease_years", "") or ""
        return {"flat_types": [{"value": v, "label": l, "selected": v == flat}
                               for v, l in FLAT_TYPES.items()],
                "budget_min": get("budget_min", DEFAULTS["budget_min"]),
                "budget_max": get("budget_max", DEFAULTS["budget_max"]),
                "lease_choices": [{"value": "" if y is None else str(y),
                                   "label": "Any" if y is None else f"At least {y} years",
                                   "selected": ("" if y is None else str(y)) == str(lease)}
                                  for y in MIN_LEASE_YEARS]}
    if key == "amenities":
        chosen = set(getlist("amenity_types", DEFAULTS["amenity_types"]))
        return {"amenity_types": [{"value": v, "label": l.capitalize(), "checked": v in chosen}
                                  for v, l in AMENITY_TYPES.items()]}
    if key == "healthcare":
        ft = get("facility_type", DEFAULTS["facility_type"])
        return {"facility_types": [{"value": v, "label": l[0].upper() + l[1:], "selected": v == ft}
                                   for v, l in FACILITY_LABELS.items()]}
    if key == "commute":
        mode = get("mode", DEFAULTS["mode"])
        return {"modes": [{"value": v, "label": l.capitalize(), "selected": v == mode}
                          for v, l in MODES.items()],
                # Refilled only from this session's own server-side state, never a URL.
                "destination_postal": get("destination_postal", "")}
    return {}
