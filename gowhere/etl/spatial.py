"""Place each geocoded HDB block in its planning area. Factor-specific distances
(rail exits, parks, clinics) are computed by the scoring strategies."""


def place_blocks(blocks, geocodes, area_index):
    """Join HDB blocks to their geocodes and planning area.

    Returns (placed, unplaced). Placed blocks get a stable integer id in dataset order.
    `unplaced` holds every block that could not be used, with a reason, so that nothing
    is dropped silently.
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
        placed.append({**block, "id": len(placed) + 1, "lat": g["lat"], "lon": g["lon"],
                       "postal": g.get("postal"), "planning_area": area})
    return placed, unplaced
