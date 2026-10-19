"""The "notable" badge: a place with a Wikipedia article at its own coordinates
(DECISIONS.md section 29). It claims only that the place is notable enough for an
encyclopaedia article, not that the food is good, and the wording says so.

Offline, in two steps:

    python -m gowhere.eat.notable      # fetch every geotagged article in Singapore
    python -m gowhere.eat.build        # match them to places (uses the file above)

Looking up each of the 8,600 places separately would mean 8,600 calls to Wikipedia.
Instead, a grid of geosearch queries over Singapore collects every geotagged article
once (a few hundred calls, paced). Places are then matched locally, with the same
name-similarity score the event image pipeline uses (gowhere.lepak.images.match_score).
A match must be within MATCH_RADIUS_M of the place, and its name must score at least
MATCH_THRESHOLD.

One more rule, from the first run: every distinctive word of the place's own name must
appear in the article title. The name counts only up to any "@", "-" or "(", because
"Ajisen @ AMK Hub" is the shop, not the mall. Without this rule, 9 of the 34 first
matches were the building, road or area a place sits in rather than the place:
"LiHO - Seletar Mall" got Seletar Mall, "North Bridge Road Market" got North Bridge
Road, and "Golden Mile Food Centre" got the Golden Mile district. The rule costs two
true matches: Tekka Food Centre against "Tekka Centre", and Liao Fan's stall against
"Hong Kong Soya Sauce Chicken Rice and Noodle". It also gains Maxwell Food Centre,
whose name now counts without "(Kim Hua Market)". 24 places are badged (19 Oct 2026).
For a badge, a missing one is better than a wrong one.
"""
import json
import logging
import re
from datetime import datetime, timezone

from gowhere import config
from gowhere.adapters.http import RateLimiter, get_json
from gowhere.etl.geo import haversine_m
from gowhere.lepak.images import USER_AGENT, WIKI_API, _session, _tokens, match_score

log = logging.getLogger(__name__)

RAW_NAME = "wikipedia_geotags"
GRID_STEP_DEG = 0.02          # ~2.2 km between query centres
QUERY_RADIUS_M = 1600         # overlapping circles cover the gaps between centres
SG_BOX = (1.20, 1.48, 103.60, 104.05)    # lat min, lat max, lon min, lon max
MATCH_RADIUS_M = 150
MATCH_THRESHOLD = 0.62        # as for event venue photos


def fetch_geotagged(session=None, limiter=None, box=SG_BOX, step=GRID_STEP_DEG):
    """{pageid: {title, lat, lon}} for every geotagged English Wikipedia article in `box`."""
    session = session or _session()
    limiter = limiter or RateLimiter(0.5)       # Wikimedia asks for gentle, serial use
    articles = {}
    lat = box[0]
    while lat <= box[1]:
        lon = box[2]
        while lon <= box[3]:
            payload = get_json(session, WIKI_API, params={
                "action": "query", "format": "json", "formatversion": "2", "list": "geosearch",
                "gscoord": f"{lat:.4f}|{lon:.4f}", "gsradius": QUERY_RADIUS_M, "gslimit": 500,
            }, limiter=limiter)
            for a in payload.get("query", {}).get("geosearch", []):
                articles[a["pageid"]] = {"title": a["title"], "lat": a["lat"], "lon": a["lon"]}
            lon += step
        lat += step
    return articles


_BASE = re.compile(r"\s+[@|\-\u2013]\s+|\s*\(|\s*@")


def own_name(name):
    """The place's own name: "LiHO - Seletar Mall" -> "LiHO"."""
    return _BASE.split(name, maxsplit=1)[0].strip() or name


def names_this_place(name, title):
    words = _tokens(own_name(name))
    return bool(words) and words <= _tokens(title)


def match(places, articles):
    """{place index: article title} for places with a nearby article that names them."""
    out = {}
    for i, p in enumerate(places):
        best, best_score = None, 0.0
        for a in articles:
            if abs(a["lat"] - p["lat"]) > 0.002 or abs(a["lon"] - p["lon"]) > 0.002:
                continue                         # cheap box test before the exact distance
            if haversine_m(p["lat"], p["lon"], a["lat"], a["lon"]) > MATCH_RADIUS_M:
                continue
            if not names_this_place(p["name"], a["title"]):
                continue
            score = match_score(own_name(p["name"]), a["title"])
            if score > best_score:
                best, best_score = a["title"], score
        if best and best_score >= MATCH_THRESHOLD:
            out[i] = best
    return out


def load(raw_dir=None):
    """The fetched articles, or [] if the fetch was never run (then nobody is badged)."""
    path = (raw_dir or config.RAW_DIR) / f"{RAW_NAME}.json"
    if not path.exists():
        return [], None
    data = json.loads(path.read_text())
    return list(data["articles"].values()), data["fetched_at"][:10]


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    articles = fetch_geotagged()
    out = config.RAW_DIR / f"{RAW_NAME}.json"
    out.write_text(json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                               "source": WIKI_API, "user_agent": USER_AGENT,
                               "articles": articles}))
    print(f"{len(articles)} geotagged articles written to {out}")


if __name__ == "__main__":
    main()
