"""A picture for every event card.

Two tiers, in order:

1. **A photograph of the venue**, from the Wikipedia article that sits at the event's
   own coordinates. Freely licensed, so unlike Street View it can be downloaded once
   and committed, which is what keeps the cards working offline.
2. **Category artwork** (``static/img/category/<slug>.svg``) when no confident match
   exists. Always present, so a card is never blank.

Street View was considered and rejected (DECISIONS.md): it needs a billed Google key,
the key would be visible in page source, and Maps Platform terms forbid caching the
image, so every card would hit Google on every page view and the offline rehearsal
would fail.

**Resolution happens here, not in a web request.** Run

    python -m gowhere.lepak.images

after ingestion. It writes ``gowhere/web/static/venues/`` (the images) and
``manifest.json`` beside them, both committed. The web app only reads the manifest, so
serving a results page makes no outbound call and works with the network off.

A match this module gets wrong can be corrected by hand in
``data/reference/venue_images.csv``, which always wins.
"""
import argparse
import csv
import json
import logging
import re
import shutil
import sqlite3
import subprocess
import unicodedata
from difflib import SequenceMatcher

import requests

from gowhere import config
from gowhere.adapters.http import HttpError, RateLimiter, get_json
from gowhere.lepak.categories import CATEGORIES

log = logging.getLogger(__name__)

WIKI_API = "https://en.wikipedia.org/w/api.php"
# Wikimedia asks every client to identify itself and a way to be contacted.
USER_AGENT = ("GoWhere/0.1 (NTU SC2006 Team 5 student project; "
              "https://github.com/sarthaksinha2201/SC2006_SoftwareEngineering_Project)")

IMAGE_DIR = config.ROOT / "gowhere" / "web" / "static" / "venues"
MANIFEST_PATH = IMAGE_DIR / "manifest.json"
OVERRIDES_PATH = config.REFERENCE_DIR / "venue_images.csv"

SEARCH_RADIUS_M = 500        # how far from the venue a candidate article may sit
# Commons does not resize on demand: it serves whichever pre-rendered bucket is nearest
# the width asked for, and reports the requested size while handing back the larger
# file. Asking for less than 800 therefore saves nothing reliably -- the trimming has to
# happen locally, in _normalise().
THUMB_WIDTH = 800
CARD_W, CARD_H = 800, 450    # 16:9, the exact box .event-media displays
# Below this, the best candidate is treated as "something else nearby" and dropped.
# Tuned on the 33 venues in the store: it keeps Marina Bay Sands, Capitol Theatre and
# Fort Canning, and rejects the two dangerous near-misses, "Singapore National Stadium"
# -> Singapore National Eye Centre and "Esplanade Concert Hall" -> Esplanade Bridge.
MATCH_THRESHOLD = 0.62

# Words that say nothing about which building this is.
_NOISE = {"the", "a", "an", "of", "at", "singapore", "sg", "building", "centre",
          "center", "level", "lvl"}


def slugify(text):
    """A filesystem- and URL-safe key. Also the category artwork's file name."""
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", ascii_text.lower())).strip("-")


def _tokens(name):
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return {w for w in re.findall(r"[a-z0-9]+", ascii_name.lower()) if w not in _NOISE}


def match_score(venue, title):
    """How confident we are that a Wikipedia article is *this* venue, 0 to 1.

    Half character similarity, half token overlap. Character similarity alone is fooled
    by a shared prefix ("Singapore National Stadium" scores 0.73 against "Singapore
    National Eye Centre"); token overlap alone punishes a correct match that renames the
    tail ("Fort Canning Park" against "Fort Canning Hill"). Together they separate the
    two cases.
    """
    a, b = _tokens(venue), _tokens(title)
    jaccard = len(a & b) / len(a | b) if (a | b) else 0.0
    ratio = SequenceMatcher(None, venue.lower(), title.lower()).ratio()
    return 0.5 * jaccard + 0.5 * ratio


def _session():
    s = requests.Session()
    s.headers["User-Agent"] = USER_AGENT
    return s


def article_by_title(session, title, limiter=None):
    """One named Wikipedia article with its lead image. Used by the override file.

    Naming the article is a far easier correction to write than finding an image URL,
    and it keeps attribution automatic.
    """
    payload = get_json(session, WIKI_API, params={
        "action": "query", "format": "json", "formatversion": "2",
        "titles": title, "redirects": "1",
        "prop": "pageimages", "piprop": "thumbnail|name", "pithumbsize": THUMB_WIDTH,
    }, limiter=limiter)
    pages = payload.get("query", {}).get("pages", [])
    page = pages[0] if pages else None
    if not page or page.get("missing") or not page.get("thumbnail"):
        return None
    return page


def nearby_articles(session, lat, lon, limiter=None):
    """Geotagged Wikipedia articles within SEARCH_RADIUS_M of a point, with lead images."""
    payload = get_json(session, WIKI_API, params={
        "action": "query", "format": "json", "formatversion": "2",
        "generator": "geosearch", "ggscoord": f"{lat}|{lon}",
        "ggsradius": SEARCH_RADIUS_M, "ggslimit": 20,
        "prop": "pageimages|coordinates", "piprop": "thumbnail|name",
        "pithumbsize": THUMB_WIDTH,
    }, limiter=limiter)
    return payload.get("query", {}).get("pages", [])


def image_credit(session, file_name, limiter=None):
    """Artist and licence for a Commons file, so the page can attribute it properly."""
    payload = get_json(session, WIKI_API, params={
        "action": "query", "format": "json", "formatversion": "2",
        "titles": f"File:{file_name}", "prop": "imageinfo",
        "iiprop": "extmetadata", "iiextmetadatafilter": "Artist|LicenseShortName",
    }, limiter=limiter)
    pages = payload.get("query", {}).get("pages", [])
    meta = (pages[0].get("imageinfo") or [{}])[0].get("extmetadata", {}) if pages else {}

    def field(key):
        raw = meta.get(key, {}).get("value", "")
        # Artist arrives as a fragment of HTML (a link to the uploader's user page).
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", raw)).strip()

    return field("Artist") or "Unknown", field("LicenseShortName") or "see Wikimedia Commons"


def best_match(venue, pages):
    """The nearest-named article with a usable photo, or None if nothing is close enough."""
    scored = [(match_score(venue, p["title"]), p) for p in pages if p.get("thumbnail")]
    if not scored:
        return None, 0.0
    score, page = max(scored, key=lambda pair: pair[0])
    return (page, score) if score >= MATCH_THRESHOLD else (None, score)


def load_overrides(path=OVERRIDES_PATH):
    """Hand-corrected venues. These always beat an automatic match.

    A row names either ``wikipedia_title`` (the common case: the geosearch picked the
    wrong neighbour, or scored the right one just under the threshold) or ``file``, for
    an image placed in the venues directory by hand.
    """
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as fh:
        return {slugify(row["venue"]): row for row in csv.DictReader(fh)
                if row.get("venue") and (row.get("wikipedia_title") or row.get("file"))}


def load_manifest(path=MANIFEST_PATH):
    """What the web app reads: venue slug -> image record. Missing file is not an error."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("venue image manifest at %s is unreadable; cards fall back to artwork",
                    path)
        return {}


class VenueImages:
    """Read-only lookup used while rendering. Never touches the network.

    Returns a path relative to the static folder, not a URL: the caller passes it to
    ``url_for("static", ...)`` so the app still works under a non-root mount point.
    """

    def __init__(self, manifest=None):
        self.manifest = load_manifest() if manifest is None else manifest

    def for_event(self, venue, category):
        """An image record for a card: a venue photo when we have one, else artwork.

        Returns ``{"path", "alt", "kind", "credit", "licence", "source_url"}``. ``kind``
        is "photo" or "artwork"; artwork carries no credit because we drew it.
        """
        record = self.manifest.get(slugify(venue or ""))
        if record:
            title = record.get("title", "")
            return {
                "path": f"venues/{record['file']}",
                # Names the building actually shown, which is not always the venue: the
                # four Esplanade halls all show the one building on the bay.
                "alt": f"{title}, the building housing {venue}" if title and title != venue
                       else (title or venue),
                "kind": "photo",
                "credit": record.get("credit") or None,
                "licence": record.get("licence") or None,
                "source_url": record.get("source_url") or None,
            }
        return {
            "path": f"img/category/{slugify(category)}.svg",
            "alt": f"{category} event",
            "kind": "artwork",
            "credit": None, "licence": None, "source_url": None,
        }


_DEFAULT = None


def default_images():
    """The process-wide lookup. The manifest is a build artefact, so one read is enough."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = VenueImages()
    return _DEFAULT


def _normalise(path):
    """Crop and resample a downloaded photo to exactly CARD_W x CARD_H, in place.

    Commons serves whatever pre-rendered bucket is nearest the requested width, and for
    the tall portraits that is often 960 px wide and half a megabyte, of which the card
    then displays a 16:9 slice. Cropping to the shape we actually show, at the size we
    actually show it, took the worst file from 513 KB to 152 KB. The centred crop is the
    same one `object-fit: cover` already performs in the browser.

    Uses `sips`, which ships with macOS, so there is no image library in requirements
    and Windows installs are unaffected. Where it is missing this is skipped and the
    full-size download is kept: larger, but correct. The resulting files are committed,
    so nobody else has to run this.
    """
    if shutil.which("sips") is None:
        return None
    try:
        subprocess.run(["sips", "--resampleWidth", str(CARD_W), str(path), "--out", str(path)],
                       check=True, capture_output=True)
        subprocess.run(["sips", "-c", str(CARD_H), str(CARD_W), str(path), "--out", str(path)],
                       check=True, capture_output=True)
        if path.suffix.lower() in (".jpg", ".jpeg"):
            subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "70",
                            str(path), "--out", str(path)], check=True, capture_output=True)
    except (subprocess.CalledProcessError, OSError) as e:
        log.warning("could not resize %s (%s); keeping the full-size download", path.name, e)
        return None
    return path.stat().st_size


def _download(session, url, dest, limiter=None):
    if limiter:
        limiter.wait()
    resp = session.get(url, timeout=60)
    if resp.status_code != 200:
        raise HttpError(f"HTTP {resp.status_code} fetching image", status=resp.status_code)
    dest.write_bytes(resp.content)
    return len(resp.content)


def build(events_path=None, refresh=False, session=None):
    """Resolve a photo for every distinct venue in the event store and cache it.

    Skips venues already in the manifest unless ``refresh``. Returns counts for the log.
    """
    events_path = events_path or config.EVENTS_PATH
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    session = session or _session()
    limiter = RateLimiter(0.3)          # polite with Wikimedia; well under their limits
    manifest, overrides = load_manifest(), load_overrides()
    counts = {"photo": 0, "artwork": 0, "override": 0, "kept": 0, "failed": 0}

    db = sqlite3.connect(events_path)
    try:
        venues = db.execute(
            "SELECT venue, AVG(lat), AVG(lon) FROM event "
            "WHERE venue IS NOT NULL AND TRIM(venue) <> '' GROUP BY venue").fetchall()
    finally:
        db.close()

    def store(slug, page, source, score=None):
        """Download a page's lead image, read its credit, and record it. True on success.

        The file is named after the **article**, not the venue, so venues that share a
        building share one file: the four Esplanade halls are one photograph, not four
        identical copies of it.
        """
        thumb_url = page["thumbnail"]["source"]
        suffix = (re.search(r"\.(jpg|jpeg|png|webp)(?:$|\?)", thumb_url, re.I)
                  or [None, "jpg"])[1]
        name = f"{slugify(page['title'])}.{suffix.lower()}"
        dest = IMAGE_DIR / name
        try:
            if dest.exists() and not refresh:
                size = dest.stat().st_size          # another venue already fetched it
                credit, licence = image_credit(session, page.get("pageimage", ""), limiter)
            else:
                size = _download(session, thumb_url, dest, limiter)
                size = _normalise(dest) or size
                credit, licence = image_credit(session, page.get("pageimage", ""), limiter)
        except HttpError as e:
            log.warning("venue %r: download failed (%s); artwork", slug, e)
            return False
        manifest[slug] = {
            "file": name, "title": page["title"], "credit": credit, "licence": licence,
            "source_url": "https://en.wikipedia.org/wiki/" + page["title"].replace(" ", "_"),
            "source": source,
        }
        if score is not None:
            # Recorded so a bad match can be traced, never shown. Formatted rather than
            # round()ed: the repo reserves rounding for scoring.stats (see
            # tests/test_golden_public_transport.py::test_no_builtin_round_outside_round1).
            manifest[slug]["match"] = float(f"{score:.3f}")
        log.info("venue %r -> %s (%s, %d bytes)", slug, page["title"],
                 f"{score:.2f}" if score is not None else source, size)
        return True

    for venue, lat, lon in venues:
        slug = slugify(venue)
        row = overrides.get(slug)
        if row and row.get("file"):
            manifest[slug] = {"file": row["file"], "title": row.get("title", venue),
                              "credit": row.get("credit", ""), "licence": row.get("licence", ""),
                              "source_url": row.get("source_url", ""), "source": "override"}
            counts["override"] += 1
            continue
        if slug in manifest and not refresh and manifest[slug].get("source") != "override":
            counts["kept"] += 1
            continue
        if row:
            try:
                page = article_by_title(session, row["wikipedia_title"], limiter)
            except HttpError as e:
                log.warning("venue %r: override lookup failed (%s)", venue, e)
                counts["failed"] += 1
                continue
            if not page:
                log.warning("venue %r: override article %r has no lead image; artwork",
                            venue, row["wikipedia_title"])
                counts["artwork"] += 1
                continue
            counts["override" if store(slug, page, "override") else "failed"] += 1
            continue
        try:
            page, score = best_match(venue, nearby_articles(session, lat, lon, limiter))
        except HttpError as e:
            log.warning("venue %r: lookup failed (%s); falling back to artwork", venue, e)
            counts["failed"] += 1
            continue
        if not page:
            log.info("venue %r: no article close enough (best %.2f); artwork", venue, score)
            counts["artwork"] += 1
            continue
        counts["photo" if store(slug, page, "wikipedia", score) else "failed"] += 1

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True,
                                        ensure_ascii=False) + "\n", encoding="utf-8")
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refresh", action="store_true",
                        help="look up every venue again, not only the new ones")
    parser.add_argument("--events", default=None, help="path to events.db")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    counts = build(events_path=args.events, refresh=args.refresh)
    print(" ".join(f"{k}={v}" for k, v in counts.items()))
    print(f"manifest: {MANIFEST_PATH}")
    missing = sorted({slugify(c) for c in CATEGORIES}
                     - {p.stem for p in (config.ROOT / "gowhere" / "web" / "static"
                                         / "img" / "category").glob("*.svg")})
    if missing:
        print(f"WARNING missing category artwork: {', '.join(missing)}")


if __name__ == "__main__":
    main()
