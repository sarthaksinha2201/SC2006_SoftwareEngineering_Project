"""Turn engine output into exactly what a template needs.

Templates do no computation beyond looping and printing: every number here is already
formatted (scores rounded half up to 1 d.p. by the engine), every sentence already
written. tests/fixtures/mock_results.json is an example of results_view()'s output and
is the contract the front-end templates are built against.
"""
import json
from datetime import datetime, timedelta, timezone

from shapely.geometry import mapping, shape

from gowhere.scoring.amenities import AMENITY_TYPES
from gowhere.scoring.commute import MODES
from gowhere.scoring.healthcare import FACILITY_LABELS
from gowhere.scoring.housing import FLAT_TYPES, MIN_LEASE_YEARS
from gowhere.scoring.public_transport import DEFAULT_MODE, MODE_LABELS
from gowhere.web.forms import FACTOR_ORDER

CLOSE_CALL_POINTS = "0.2"
STALE_AFTER = timedelta(days=365)       # FR 3.1.6: warn when the snapshot is over 12 months old
MAP_TOLERANCE_DEG = 0.0001   # ~11 m: boundaries stay accurate at street zoom, page stays light
PICKER_TOLERANCE_DEG = 0.0006   # ~66 m: the setup picker is only ever seen at island zoom
# One hue per compared neighbourhood, at most four because that is the comparison cap,
# so the list is never cycled. Checked with the dataviz validator against the page's
# #FBFBFA surface: all four inside the lightness band, above the chroma floor, worst
# adjacent pair deltaE 16.5 under deuteranopia and 24.0 with normal vision, all above
# 3:1 contrast. Changing any value means re-running that check.
CHART_COLOURS = ("#1F6C9F", "#B5651D", "#6940A5", "#00897B")
# DECISIONS.md section 16: five factors on by default; Commute off (it needs a destination
# only the user can give, and switching it on reveals that field); every amenity type
# ticked (FR 1.2.6.2); GP clinics for healthcare (FR 1.2.7.1).
DEFAULTS = {
    "weight": 5,
    "excluded": {"commute"},
    "flat_type": "4 ROOM", "budget_min": 400_000, "budget_max": 700_000,
    "min_remaining_lease_years": None,
    "amenity_types": list(AMENITY_TYPES),
    "facility_type": "gp",
    "mode": "pt",
    "pt_mode": DEFAULT_MODE,         # FR 1.2.4.1: Either
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


def stale_warning(meta, now=None):
    """FR 3.1.6: a warning when the active snapshot is more than 12 months old, else ""."""
    built = datetime.fromisoformat(meta["generated_at"])
    if built.tzinfo is None:
        built = built.replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    if now - built <= STALE_AFTER:
        return ""
    return (f"This data was generated on {snapshot_date(meta)}, more than 12 months ago. "
            f"Neighbourhoods may have changed since, so treat these scores with care.")


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
        # Where to eat in the recommended neighbourhood (both, when joint first): a
        # browse with no journey (DECISIONS.md section 27).
        "eat_links": [{"area": key, "label": f"Where to eat in {area_name(key)}"}
                      for key in ([ex["winner"], ex["runner_up"]] if joint else [ex["winner"]])],
    }


def _signed(x):
    return f"{'+' if x >= 0 else '−'}{abs(x):.1f}"


def breakdown(result, all_factors=None):
    """FR 1.4.4, the Transparency NFR's evidence: for each included factor its weight,
    the recommended and runner-up neighbourhoods' category scores and raw values, and
    the marginal contribution, sorted by size; the overall formula with the user's
    weights; and every factor left out, with why. `all_factors` is [{key, label}] for
    every factor the app offers, so user-excluded ones can be listed."""
    ex = result["explanation"]
    by_name = {a["name"]: a for a in result["areas"]}
    win, run = by_name[ex["winner"]], by_name[ex["runner_up"]]
    weights = {f["key"]: f["weight"] for f in result["factors"]}
    rows = []
    for f in sorted(ex["factors"], key=lambda f: -abs(f["contribution"])):
        k = f["key"]
        rows.append({
            "label": f["label"], "weight": weights[k],
            "winner_score": _fmt(win["category_display"][k]),
            "runner_up_score": _fmt(run["category_display"][k]),
            "winner_raw": win["raw"].get(k, {}).get("summary", ""),
            "runner_up_raw": run["raw"].get(k, {}).get("summary", ""),
            "contribution": _signed(f["contribution"]),
            "favours": area_name(ex["winner"] if f["contribution"] >= 0 else ex["runner_up"]),
        })
    included = result["factors"]
    total = sum(f["weight"] for f in included)
    terms = " + ".join(f"{f['weight']} × {f['label']}" for f in included)
    filled = lambda a: " + ".join(f"{f['weight']} × {_fmt(a['category_display'][f['key']])}"
                                  for f in included)
    dropped = {d["key"]: d for d in result["dropped"]}
    excluded = [{"label": d["label"], "reason": "Data unavailable: "
                 + dropped_messages([d])[0].split(" because ", 1)[1].rstrip(".")}
                for d in result["dropped"]]
    used = {f["key"] for f in included} | set(dropped)
    excluded += [{"label": f["label"], "reason": "Excluded by you"}
                 for f in (all_factors or []) if f["key"] not in used]
    return {
        "winner": area_name(ex["winner"]), "runner_up": area_name(ex["runner_up"]),
        "rows": rows,
        "formula": f"Overall score = ({terms}) ÷ {total}",
        "formula_examples": [f"{area_name(a['name'])} = ({filled(a)}) ÷ {total} = "
                             f"{_fmt(a['overall_display'])}" for a in (win, run)],
        "excluded": excluded,
        "formula_note": ("The worked lines use scores rounded to 1 decimal place; the ranking "
                         "uses unrounded scores, so a hand recalculation can differ by 0.1."),
    }


def results_view(result, snapshot, all_factors=None, now=None):
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
    # A neighbourhood's colour follows the neighbourhood, not its position in the
    # ranking: re-weighting the factors reorders `rows`, and if colour came from that
    # order every town on the chart would change colour for no reason the reader can
    # see. Alphabetical within the selection is stable against any re-weighting.
    chart_slot = {name: i for i, name in enumerate(sorted(r["name"] for r in rows))}
    geometry = {r["name"]: _simplified(r["geometry_geojson"]) for r in snapshot.query(
        f"SELECT name, geometry_geojson FROM planning_area WHERE name IN "
        f"({', '.join('?' for _ in rows)})", tuple(r["key"] for r in rows))}
    return {
        "snapshot_date": snapshot_date(result["snapshot"]),
        "stale_warning": stale_warning(result["snapshot"], now),
        "breakdown": breakdown(result, all_factors),
        "factors": [{"key": f["key"], "label": f["label"], "weight": f["weight"],
                     "notes": f["notes"]} for f in factors],
        "areas": rows,
        "dropped": dropped_messages(result["dropped"]),
        "recommendation": recommendation(result),
        "chart": {"labels": [f["label"] for f in factors],
                  "datasets": [{"label": r["name"],
                                "colour": CHART_COLOURS[chart_slot[r["name"]]],
                                "data": [float(c["score"]) for c in r["categories"]]}
                               for r in rows]},
        # The same colour the chart gives this neighbourhood, so a reader moving between
        # the chart, the map and the table tracks one town by one hue.
        "map": {"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": geometry[r["key"]],
             "properties": {"name": r["name"], "rank": r["rank"], "overall": r["overall"],
                            "colour": CHART_COLOURS[chart_slot[r["name"]]]}}
            for r in rows]},
    }


def _simplified(geojson_text, tolerance=MAP_TOLERANCE_DEG):
    geom = shape(json.loads(geojson_text)).simplify(tolerance, preserve_topology=True)
    return json.loads(json.dumps(mapping(geom)))   # tuples -> lists, as JSON has them


def picker_map(snapshot):
    """Every in-scope neighbourhood as a polygon, for the setup screen's map picker.

    Served from its own endpoint rather than inlined: it is the same for every visitor
    and every session, so the browser caches it once instead of re-parsing it on each
    page load. Simplified harder than the results map (PICKER_TOLERANCE_DEG) because it
    is only ever seen at island zoom, which cuts it to a fraction of the size.

    `flats` drives the 3D extrusion height, so the taller blocks are the bigger towns.
    """
    areas = snapshot.areas()
    rows = snapshot.query("SELECT name, geometry_geojson FROM planning_area WHERE in_scope = 1")
    return {"type": "FeatureCollection", "features": [
        {"type": "Feature",
         "id": index,                      # feature-state needs an id; names are not numeric
         "geometry": _simplified(r["geometry_geojson"], PICKER_TOLERANCE_DEG),
         "properties": {
             "key": r["name"],
             "name": area_name(r["name"]),
             "flats": areas[r["name"]]["n_flats"],
             "small_sample": bool(areas[r["name"]]["small_sample"]),
             "flats_text": f"{areas[r['name']]['n_flats']:,} flats in "
                           f"{areas[r['name']]['n_blocks']} blocks",
         }}
        for index, r in enumerate(sorted(rows, key=lambda r: r["name"]))]}


# ---- setup --------------------------------------------------------------------

def setup_view(engine, snapshot, form=None, error=None):
    """The setup screen. `form` is the last submitted form (to refill it), or None."""
    get = (lambda k, d=None: form.get(k, d)) if form else (lambda k, d=None: d)
    getlist = (lambda k, d: form.getlist(k)) if form else (lambda k, d: d)
    described = {f["key"]: f for f in engine.factors()}
    labels = {k: f["label"] for k, f in described.items()}
    areas = snapshot.areas()
    selected = set(getlist("areas", []))
    factors = []
    for key in FACTOR_ORDER:
        if key not in labels:
            continue
        included = bool(get(f"include_{key}")) if form else key not in DEFAULTS["excluded"]
        factors.append({"key": key, "label": labels[key], "included": included,
                        # as typed, so an invalid entry is shown back rather than crashing
                        "weight": str(get(f"weight_{key}", DEFAULTS["weight"]) or DEFAULTS["weight"]),
                        "controls": _controls(key, get, getlist, described[key]["options"])})
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


def _controls(key, get, getlist, options=None):
    if key == "public_transport":
        modes = (options or {}).get("mode")
        if not modes:
            return {}                      # rail-only snapshot: nothing to choose
        chosen = get("pt_mode", DEFAULTS["pt_mode"])
        return {"pt_modes": [{"value": m, "label": MODE_LABELS[m], "selected": m == chosen}
                             for m in modes]}
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
