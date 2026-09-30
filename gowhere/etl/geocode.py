"""Task 1: geocode every HDB residential block with OneMap Search. Resumable.

Every raw OneMap response is cached by query string, and a query already in the cache
is never sent again. Matching (which result is the right block) runs over the cache, so
the matching rules can be improved and re-applied without any new requests.
Network/HTTP errors are not cached: they are logged and retried on the next run.

    python -m gowhere.etl.geocode [--limit N]
"""
import argparse
import csv
import json
import logging
import sqlite3
import sys
from datetime import datetime, timezone

from gowhere import config
from gowhere.adapters.http import HttpError
from gowhere.adapters.onemap import OneMapAdapter
from gowhere.etl.addresses import match_postal, match_block, query_for
from gowhere.etl.raw import load_hdb_residential

CACHE_PATH = config.CACHE_DIR / "onemap_search.sqlite"
FAILURE_LOG = config.LOG_DIR / "geocode_failures.csv"


class SearchCache:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS search (
            query TEXT PRIMARY KEY, response_json TEXT NOT NULL, fetched_at TEXT NOT NULL)""")

    def get(self, query):
        row = self.db.execute("SELECT response_json FROM search WHERE query = ?", (query,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, query, response):
        self.db.execute("INSERT OR REPLACE INTO search VALUES (?, ?, ?)",
                        (query, json.dumps(response),
                         datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.db.commit()

    def __len__(self):
        return self.db.execute("SELECT COUNT(*) FROM search").fetchone()[0]


def geocode_block(block, adapter, cache, stats):
    """Resolve one block. Returns a result dict; status is ok/no_match/ambiguous/error."""
    result = {"blk_no": block["blk_no"], "street": block["street"],
              "status": "no_match", "detail": ""}
    tried = []
    for expanded in (False, True):
        query = query_for(block["blk_no"], block["street"], expanded)
        if query in tried:
            continue
        tried.append(query)
        response = cache.get(query)
        if response is None:
            try:
                response = adapter.search(query)
            except HttpError as e:
                stats["requests"] += 1
                result.update(status="error", detail=f"{query!r}: {e}")
                return result
            stats["requests"] += 1
            cache.put(query, response)
        status, match = match_block(block["blk_no"], block["street"], response.get("results", []))
        if status == "ok":
            result.update(status="ok", query=query, lat=float(match["LATITUDE"]),
                          lon=float(match["LONGITUDE"]), postal=match.get("POSTAL"),
                          address=match.get("ADDRESS"), detail="")
            return result
        candidates = "; ".join(f"{r.get('BLK_NO')} {r.get('ROAD_NAME')}"
                               for r in response.get("results", [])[:5])
        result.update(status=status, detail=f"{query!r} -> [{candidates}]")
    return result


def geocode_all(blocks, adapter, cache, progress_every=250, out=sys.stdout):
    stats = {"requests": 0}
    results = []
    for i, block in enumerate(blocks, 1):
        results.append(geocode_block(block, adapter, cache, stats))
        if progress_every and i % progress_every == 0:
            ok = sum(r["status"] == "ok" for r in results)
            print(f"{i}/{len(blocks)} blocks, {ok} ok, {stats['requests']} new requests",
                  file=out, flush=True)
    return results, stats


def write_failure_log(results, path=FAILURE_LOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    failures = [r for r in results if r["status"] != "ok"]
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["blk_no", "street", "status", "detail"])
        for r in failures:
            writer.writerow([r["blk_no"], r["street"], r["status"], r["detail"]])
    return failures


def load_geocodes(cache_path=CACHE_PATH, blocks=None):
    """Offline: resolve blocks from the cache only. Blocks with no cached answer are 'uncached'."""
    cache = SearchCache(cache_path)

    class _Offline:
        def search(self, query):
            raise HttpError("not in cache (offline)")

    results, _ = geocode_all(blocks if blocks is not None else load_hdb_residential(),
                             _Offline(), cache, progress_every=0)
    for r in results:
        if r["status"] == "error":
            r["status"] = "uncached"
    return results


def geocode_postal(postal, adapter, cache):
    """{lat, lon} for a postal code (cached like block queries), or None if OneMap has none."""
    response = cache.get(postal)
    if response is None:
        response = adapter.search(postal)
        cache.put(postal, response)
    return match_postal(postal, response.get("results", []))


def load_postal_geocodes(postals, cache_path=CACHE_PATH):
    """Offline: {postal: {lat, lon} or None}; a postal code never searched maps to None."""
    cache = SearchCache(cache_path)
    return {p: (match_postal(p, cache.get(p).get("results", [])) if cache.get(p) else None)
            for p in postals}


def geocode_reference(adapter, cache):
    """Geocode every postal code in data/reference/polyclinics.csv. Failures are printed."""
    from gowhere.etl.reference import load_polyclinic_list
    failures = []
    for clinic in load_polyclinic_list():
        try:
            if geocode_postal(clinic["postal_code"], adapter, cache) is None:
                failures.append(f"{clinic['name']} ({clinic['postal_code']}): no OneMap match")
        except HttpError as e:
            failures.append(f"{clinic['name']} ({clinic['postal_code']}): {e}")
    return failures


def main():
    parser = argparse.ArgumentParser(description="Geocode HDB residential blocks via OneMap")
    parser.add_argument("--limit", type=int, help="only the first N blocks (for testing)")
    parser.add_argument("--reference", action="store_true",
                        help="geocode the postal codes in data/reference/ instead of HDB blocks")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    config.load_dotenv()   # a token lifts the search rate limit

    if args.reference:
        failures = geocode_reference(OneMapAdapter(), SearchCache(CACHE_PATH))
        print("\n".join(failures) or "all reference postal codes geocoded")
        raise SystemExit(1 if failures else 0)

    blocks = load_hdb_residential()[:args.limit]
    cache = SearchCache(CACHE_PATH)
    print(f"{len(blocks)} residential blocks; {len(cache)} queries already cached", flush=True)
    results, stats = geocode_all(blocks, OneMapAdapter(), cache)
    failures = write_failure_log(results)

    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    print(f"done: {counts}; {stats['requests']} new requests")
    print(f"{len(failures)} failures logged to {FAILURE_LOG}")


if __name__ == "__main__":
    main()
