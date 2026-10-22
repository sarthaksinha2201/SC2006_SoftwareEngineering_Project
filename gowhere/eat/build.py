"""Build data/eat.db, the Where to Eat place list (offline, like the snapshot).

    python -m gowhere.etl._temp_fetch_raw        # once: fetches osm_food with the rest
    python -m gowhere.eat.build

Sources, both already in data/raw:
  - OpenStreetMap food venues (`osm_food`: restaurants, cafes, fast food, food courts,
    ice cream, markets), © OpenStreetMap contributors, ODbL.
  - NEA hawker centres (`nea_hawker_centres`), with their cooked-food stall counts.

Each hawker centre appears once, from NEA, carrying its stall count (§25: a food
destination is one entry). OSM food courts and markets that are the same centre (within
SAME_CENTRE_M and sharing a distinctive word of the name, or within NEAR_M whatever the
name) are dropped in its favour. Unnamed OSM venues are dropped, because a result with no
name can't be found, and so are venues outside every planning area (the download box
includes part of Johor). Both counts are recorded in `meta`.

Price tier comes from the venue type, not from menus (§25): hawker centres, food
courts, markets and kopitiams (by name: cuisines.is_kopitiam) are "budget"; cafes, fast
food and ice cream are "casual"; other restaurants are "restaurant".
"""
import json
import re
import sqlite3
from datetime import datetime, timezone

from gowhere import config
from gowhere.eat import google_ids, notable
from gowhere.eat.cuisines import groups_for, is_kopitiam
from gowhere.eat.hours import parse
from gowhere.etl import raw
from gowhere.etl.geo import PlanningAreaIndex, haversine_m

SAME_CENTRE_M = 200
NEAR_M = 60
OPEN_STATUSES = {"Existing", "Existing (new)", "Existing (replacement)", "Interim Centre"}
DESTINATION_KINDS = {"hawker_centre", "food_court", "marketplace"}
_GENERIC = set("food centre center market hawker the blk block and court complex village "
               "stalls stall street st road rd avenue ave".split())

SCHEMA = """
CREATE TABLE place (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    kind TEXT NOT NULL,          -- hawker_centre, food_court, marketplace, restaurant, cafe, fast_food, ice_cream
    destination INTEGER NOT NULL, -- 1 for a place with many stalls under one roof
    stalls INTEGER,              -- cooked-food stalls: NEA hawker centres only
    price_tier TEXT NOT NULL,    -- budget, casual or restaurant (by venue type)
    cuisines TEXT NOT NULL,      -- JSON list of cuisine groups; [] = not listed
    cuisine_tag TEXT,            -- the OSM value as tagged
    opening_hours TEXT,          -- the OSM value as tagged
    address TEXT,
    lat REAL NOT NULL, lon REAL NOT NULL,
    planning_area TEXT NOT NULL,
    source TEXT NOT NULL,        -- osm or nea
    source_url TEXT NOT NULL,
    wikipedia_title TEXT,        -- a Wikipedia article at this place (gowhere.eat.notable)
    google_place_id TEXT);       -- the only Google content stored (gowhere.eat.google_ids)
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def _words(name):
    return {w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if w not in _GENERIC}


def _osm_address(tags):
    street = " ".join(p for p in (tags.get("addr:housenumber"), tags.get("addr:street")) if p)
    unit = tags.get("addr:unit") or tags.get("addr:floor")
    parts = [street, f"#{unit}" if unit and not unit.startswith("#") else unit,
             f"Singapore {tags['addr:postcode']}" if tags.get("addr:postcode") else None]
    return ", ".join(p for p in parts if p) or None


def price_tier(kind, name):
    if kind in DESTINATION_KINDS or is_kopitiam(name):
        return "budget"
    if kind in ("cafe", "fast_food", "ice_cream"):
        return "casual"
    return "restaurant"


def hawker_centres(features):
    out = []
    for f in features:
        p = f["properties"]
        if p.get("STATUS") not in OPEN_STATUSES:
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        stalls = int(p.get("NUMBER_OF_COOKED_FOOD_STALLS") or 0) or None
        street = " ".join(x for x in (p.get("ADDRESSBLOCKHOUSENUMBER"), p.get("ADDRESSSTREETNAME")) if x)
        address = ", ".join(x for x in (street, f"Singapore {p['ADDRESSPOSTALCODE']}"
                                        if p.get("ADDRESSPOSTALCODE") else None) if x)
        out.append({"name": p["NAME"].strip(), "kind": "hawker_centre", "destination": 1,
                    "stalls": stalls, "price_tier": "budget",
                    "cuisines": ["Local"], "cuisine_tag": None, "opening_hours": None,
                    "address": address or None, "lat": float(lat), "lon": float(lon),
                    "source": "nea",
                    "source_url": f"https://data.gov.sg/datasets/{_HAWKER_ID}/view"})
    return out


_HAWKER_ID = "d_4a086da0a5553be1d89383cd90d07ecd"


def osm_venues(elements):
    out = []
    for e in elements:
        tags = e.get("tags", {})
        lat = e.get("lat") or e.get("center", {}).get("lat")
        lon = e.get("lon") or e.get("center", {}).get("lon")
        if lat is None or lon is None:
            continue
        kind = tags.get("amenity")
        name = (tags.get("name:en") or tags.get("name") or "").strip()
        cuisine_tag = tags.get("cuisine")
        cuisines = groups_for(cuisine_tag)
        if (kind in DESTINATION_KINDS or is_kopitiam(name)) and "Local" not in cuisines:
            cuisines = ["Local"] + cuisines   # food court, market or kopitiam: local stalls
        out.append({"name": name,
                    "kind": kind, "destination": int(kind in DESTINATION_KINDS),
                    "stalls": None, "price_tier": price_tier(kind, name),
                    "cuisines": cuisines, "cuisine_tag": cuisine_tag,
                    "opening_hours": tags.get("opening_hours"),
                    "address": _osm_address(tags), "lat": float(lat), "lon": float(lon),
                    "source": "osm",
                    "source_url": f"https://www.openstreetmap.org/{e['type']}/{e['id']}"})
    return out


def is_same_centre(venue, centre):
    if venue["kind"] not in ("food_court", "marketplace"):
        return False
    d = haversine_m(venue["lat"], venue["lon"], centre["lat"], centre["lon"])
    return d <= NEAR_M or (d <= SAME_CENTRE_M and _words(venue["name"]) & _words(centre["name"]))


def build(osm_elements, hawker_features, areas):
    """(places, counts). Pure: no I/O, so tests can feed small fixtures."""
    index = PlanningAreaIndex(areas)
    centres = hawker_centres(hawker_features)
    counts = {"osm_elements": len(osm_elements), "hawker_centres": len(centres),
              "osm_outside_singapore": 0, "osm_unnamed": 0, "osm_same_as_hawker_centre": 0}
    places = []
    for c in centres:
        c["planning_area"] = index.area_of(c["lat"], c["lon"]) or ""
        places.append(c)
    for v in osm_venues(osm_elements):
        area = index.area_of(v["lat"], v["lon"])
        if not area:
            counts["osm_outside_singapore"] += 1
            continue
        if not v["name"]:
            counts["osm_unnamed"] += 1
            continue
        if any(is_same_centre(v, c) for c in centres):
            counts["osm_same_as_hawker_centre"] += 1
            continue
        places.append({**v, "planning_area": area})
    counts["places"] = len(places)
    return places, counts


def coverage(places):
    """The figures the UI states (§25): how many places have a listed cuisine and
    understood opening hours. Hawker centres come from NEA, which has no hours."""
    n = len(places) or 1
    listed = sum(bool(p["cuisines"]) for p in places if p["source"] == "osm")
    osm = sum(p["source"] == "osm" for p in places) or 1
    hours = sum(parse(p["opening_hours"]) is not None for p in places)
    return {"cuisine_listed_pct": f"{listed / osm * 100:.1f}",
            "hours_known_pct": f"{hours / n * 100:.1f}"}


def write(path, places, meta):
    tmp = path.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    db = sqlite3.connect(tmp)
    db.executescript(SCHEMA)
    db.executemany(
        "INSERT INTO place (name, kind, destination, stalls, price_tier, cuisines, cuisine_tag, "
        "opening_hours, address, lat, lon, planning_area, source, source_url, wikipedia_title, "
        "google_place_id) "
        "VALUES (:name, :kind, :destination, :stalls, :price_tier, :cuisines, :cuisine_tag, "
        ":opening_hours, :address, :lat, :lon, :planning_area, :source, :source_url, "
        ":wikipedia_title, :google_place_id)",
        [{"wikipedia_title": None, "google_place_id": None, **p,
          "cuisines": json.dumps(p["cuisines"])} for p in places])
    db.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
    db.commit()
    db.close()
    tmp.replace(path)


def main():
    raw_dir = config.RAW_DIR
    osm = json.loads((raw_dir / f"{config.RAW_OSM_FOOD}.json").read_text())
    hawkers = json.loads((raw_dir / f"{config.RAW_HAWKER_CENTRES}.json").read_text())
    manifest = json.loads((raw_dir / "_manifest.json").read_text())
    places, counts = build(osm["elements"], hawkers["features"], raw.load_planning_areas())
    articles, wiki_as_of = notable.load(raw_dir)
    for i, title in notable.match(places, articles).items():
        places[i]["wikipedia_title"] = title
    counts["notable"] = sum(bool(p.get("wikipedia_title")) for p in places)
    gids = google_ids.load(raw_dir)
    for p in places:
        p["google_place_id"] = gids.get(p["source_url"])
    counts["google_place_ids"] = sum(bool(p["google_place_id"]) for p in places)
    meta = {**{k: str(v) for k, v in counts.items()}, **coverage(places),
            "wikipedia_as_of": wiki_as_of or "",
            "osm_data_as_of": osm.get("osm3s", {}).get("timestamp_osm_base", "")[:10],
            "hawker_data_as_of": manifest[config.RAW_HAWKER_CENTRES]["fetched_at"][:10],
            "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    write(config.EAT_PATH, places, meta)
    print(f"eat.db: {counts['places']} places ({counts['hawker_centres']} hawker centres); "
          f"dropped {counts['osm_outside_singapore']} outside Singapore, {counts['osm_unnamed']} "
          f"unnamed, {counts['osm_same_as_hawker_centre']} duplicates of a hawker centre; "
          f"cuisine listed {meta['cuisine_listed_pct']}%, hours known {meta['hours_known_pct']}%; "
          f"{counts['notable']} with a Wikipedia article")


if __name__ == "__main__":
    main()
