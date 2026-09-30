"""Street-name normalisation and OneMap search-result matching for HDB blocks.

HDB writes streets abbreviated ("BT BATOK WEST AVE 6"); OneMap spells them out
("BUKIT BATOK WEST AVENUE 6"). Both sides are expanded to full words before comparing.
"""
import math

# HDB abbreviation -> OneMap full word. Built from the tokens in the HDB dataset.
ABBREVIATIONS = {
    "AVE": "AVENUE", "BLVD": "BOULEVARD", "BT": "BUKIT", "C'WEALTH": "COMMONWEALTH",
    "CL": "CLOSE", "CRES": "CRESCENT", "CTR": "CENTRE", "CTRL": "CENTRAL", "DR": "DRIVE",
    "GDN": "GARDEN", "GDNS": "GARDENS", "HTS": "HEIGHTS", "JLN": "JALAN", "KG": "KAMPONG",
    "LOR": "LORONG", "MKT": "MARKET", "NTH": "NORTH", "PK": "PARK", "PL": "PLACE",
    "RD": "ROAD", "SQ": "SQUARE", "ST": "STREET", "STH": "SOUTH", "TER": "TERRACE",
    "TG": "TANJONG", "UPP": "UPPER",
}

# Results for one block that lie within this distance are the same building.
SAME_BUILDING_M = 50.0


def expand_street(street):
    # "ST." with a full stop is Saint (HDB: "ST. GEORGE'S RD"); plain "ST" is Street.
    words = street.upper().replace("ST.", "SAINT ").replace(".", " ").split()
    return " ".join(ABBREVIATIONS.get(w, w) for w in words)


def normalise_road(road):
    """Canonical form for comparing an HDB street with a OneMap ROAD_NAME."""
    return expand_street(road).replace("'", "")


def query_for(blk_no, street, expanded=False):
    return f"{blk_no} {expand_street(street) if expanded else street}"


def _haversine_m(lat1, lon1, lat2, lon2):
    r = 6_371_008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def match_block(blk_no, street, results):
    """Pick the OneMap result for an HDB block.

    Returns (status, match) where status is "ok", "no_match" or "ambiguous".
    A candidate matches only if its block number and full road name both agree;
    anything looser risks placing a block on the wrong street.
    """
    target_blk, target_road = blk_no.strip().upper(), normalise_road(street)
    matches = [r for r in results
               if (r.get("BLK_NO") or "").strip().upper() == target_blk
               and normalise_road(r.get("ROAD_NAME") or "") == target_road]
    if not matches:
        return "no_match", None
    if not _one_building(matches):
        # e.g. "1 BEACH ROAD" is both an HDB block and Raffles Hotel. HDB postal codes
        # end in the block number (Blk 1 -> 190001), so keep the candidates that do.
        suffix = _block_postal_suffix(target_blk)
        matches = [m for m in matches if (m.get("POSTAL") or "").endswith(suffix)]
        if not matches:
            return "ambiguous", None
        if not _one_building(matches):
            # A Singapore postal code identifies one building, so points that share one
            # are the same (long) block that OneMap indexes twice: use their midpoint.
            if len({m["POSTAL"] for m in matches}) != 1:
                return "ambiguous", None
            return "ok", _midpoint(matches)
    # Prefer a result that carries a real postal code.
    best = next((m for m in matches if (m.get("POSTAL") or "NIL") != "NIL"), matches[0])
    return "ok", best


def _midpoint(matches):
    lat = sum(float(m["LATITUDE"]) for m in matches) / len(matches)
    lon = sum(float(m["LONGITUDE"]) for m in matches) / len(matches)
    return {**matches[0], "LATITUDE": str(lat), "LONGITUDE": str(lon)}


def _one_building(matches):
    lat0, lon0 = float(matches[0]["LATITUDE"]), float(matches[0]["LONGITUDE"])
    return all(_haversine_m(lat0, lon0, float(m["LATITUDE"]), float(m["LONGITUDE"])) <= SAME_BUILDING_M
               for m in matches[1:])


def _block_postal_suffix(blk_no):
    digits = "".join(c for c in blk_no if c.isdigit())
    return digits[-3:].zfill(3)


def match_postal(postal, results):
    """{lat, lon} for a postal code: the midpoint of results carrying exactly that code.

    A Singapore postal code identifies one building, so all matches are the same place.
    """
    matches = [r for r in results if (r.get("POSTAL") or "").strip() == postal]
    if not matches:
        return None
    m = _midpoint(matches)
    return {"lat": float(m["LATITUDE"]), "lon": float(m["LONGITUDE"])}
