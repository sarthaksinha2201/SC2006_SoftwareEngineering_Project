"""Task 2: place each geocoded block in its planning area and find its nearest MRT/LRT exit."""
from gowhere import config
from gowhere.etl.geo import nearest, walk_minutes


def enrich_blocks(blocks, geocodes, area_index, exits, detour=config.DETOUR_FACTOR):
    """Join HDB blocks to their geocodes, planning area and nearest exit.

    Returns (placed, unplaced). `unplaced` holds every block that could not be used,
    with a reason, so that nothing is dropped silently.
    """
    by_key = {(g["blk_no"], g["street"]): g for g in geocodes}
    placed, unplaced = [], []
    for block in blocks:
        g = by_key.get((block["blk_no"], block["street"]))
        if g is None or g["status"] != "ok":
            unplaced.append({**block, "reason": f"geocode {g['status'] if g else 'missing'}",
                             "detail": g["detail"] if g else ""})
            continue
        area = area_index.area_of(g["lat"], g["lon"])
        if area is None:
            unplaced.append({**block, "reason": "outside every planning area",
                             "detail": f"{g['lat']},{g['lon']}"})
            continue
        exit_, dist = nearest(g["lat"], g["lon"], exits)
        placed.append({**block, "lat": g["lat"], "lon": g["lon"], "postal": g.get("postal"),
                       "planning_area": area, "nearest_station": exit_["station"],
                       "nearest_exit_code": exit_["exit_code"], "exit_distance_m": dist,
                       "walk_min": walk_minutes(dist, detour=detour)})
    return placed, unplaced
