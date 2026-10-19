"""Resolve a Google place ID for each place, offline (DECISIONS.md section 29).

    python -m gowhere.eat.google_ids        # needs GOOGLE_MAPS_API_KEY in .env
    python -m gowhere.eat.build             # copies the IDs into eat.db

Uses Text Search asking only for the place ID, the "Text Search Essentials (IDs Only)"
SKU, which Google does not charge for. The place ID is the one piece of Places content
Google's policies allow to be stored indefinitely, so it is all that is kept, in
data/raw/google_place_ids.json, keyed by our place's source URL so a rebuild re-attaches
it. Restartable: places already resolved are skipped.

An IDs-only search returns no name, so a match can't be checked here. It is checked at
request time instead, when the rating call returns Google's name (gowhere.eat.ratings).
"""
import json
import logging
import time

from gowhere import config
from gowhere.adapters.google_places import GooglePlacesAdapter, PlacesError

log = logging.getLogger(__name__)
RAW_NAME = "google_place_ids"
PAUSE_S = 0.15                # well under the default per-minute quota


def path(raw_dir=None):
    return (raw_dir or config.RAW_DIR) / f"{RAW_NAME}.json"


def load(raw_dir=None):
    p = path(raw_dir)
    return json.loads(p.read_text()) if p.exists() else {}


def resolve(places, adapter, known=None, sleep=time.sleep, save=None, every=200):
    """{source_url: place ID or None}. `known` entries are kept, not re-asked."""
    ids = dict(known or {})
    for n, p in enumerate(places, 1):
        if p["source_url"] in ids:
            continue
        try:
            ids[p["source_url"]] = adapter.find_place_id(p["name"], p["lat"], p["lon"])
        except PlacesError as e:
            log.warning("stopped at %d of %d: %s", n, len(places), e)
            break
        sleep(PAUSE_S)
        if save and n % every == 0:
            save(ids)
    return ids


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config.load_dotenv()
    from gowhere.eat.store import PlaceStore
    places = PlaceStore.load(config.EAT_PATH).places
    adapter = GooglePlacesAdapter()
    if not adapter.configured:
        raise SystemExit("GOOGLE_MAPS_API_KEY is not set in .env")
    save = lambda ids: path().write_text(json.dumps(ids))
    ids = resolve(places, adapter, known=load(), save=save)
    save(ids)
    found = sum(v is not None for v in ids.values())
    print(f"{found} of {len(places)} places have a Google place ID ({len(ids)} asked)")


if __name__ == "__main__":
    main()
