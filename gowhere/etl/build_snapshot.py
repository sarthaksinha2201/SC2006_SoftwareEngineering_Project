"""Build data/snapshot.db from data/raw/ and the geocode cache. Makes no network calls.

The build places every HDB block in its planning area, then asks each scoring strategy
(gowhere.scoring.registry) for its tables. The snapshot is written to a temporary file
and only replaces the active snapshot once validation passes, so a failed build leaves
the previous snapshot in place.

    python -m gowhere.etl.build_snapshot [--min-geocode-coverage 0.98]
"""
import argparse
import csv
import json
import os
import sqlite3
from datetime import datetime, timezone

from gowhere import config
from gowhere.etl.geo import PlanningAreaIndex
from gowhere.etl.geocode import load_geocodes
from gowhere.etl.raw import load_hdb_residential, load_planning_areas
from gowhere.etl.sources import RawSources
from gowhere.etl.spatial import place_blocks
from gowhere.scoring.base import group_by_area
from gowhere.scoring.registry import default_strategies

SCHEMA_VERSION = "3"   # 3: factor tables owned by strategies; hdb_block holds location only
UNPLACED_LOG = config.LOG_DIR / "unplaced_blocks.csv"

CORE_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE planning_area (
    name TEXT PRIMARY KEY, region TEXT NOT NULL,
    in_scope INTEGER NOT NULL,            -- 1 if it contains >= 1 HDB residential block
    n_blocks INTEGER NOT NULL, n_flats INTEGER NOT NULL,
    small_sample INTEGER NOT NULL,        -- 1 if in scope with < meta.small_area_blocks blocks
    geometry_geojson TEXT NOT NULL);
CREATE TABLE hdb_block (
    id INTEGER PRIMARY KEY, blk_no TEXT NOT NULL, street TEXT NOT NULL, postal TEXT,
    lat REAL NOT NULL, lon REAL NOT NULL,
    planning_area TEXT NOT NULL REFERENCES planning_area(name),
    total_dwelling_units INTEGER NOT NULL,
    UNIQUE (blk_no, street));
CREATE INDEX hdb_block_area ON hdb_block(planning_area);
"""


class ValidationError(Exception):
    pass


def is_small_sample(n_blocks, threshold=config.SMALL_AREA_BLOCKS):
    """True for an in-scope area whose scores rest on too few blocks to be stable."""
    return 0 < n_blocks < threshold


def compute(blocks, geocodes, areas, sources, strategies=None):
    """Everything the snapshot holds, as plain data. No I/O beyond `sources`."""
    strategies = default_strategies() if strategies is None else strategies
    placed, unplaced = place_blocks(blocks, geocodes, PlanningAreaIndex(areas))
    counts = {a: (len(f), sum(f))
              for a, (_, f) in group_by_area(placed, lambda b: None).items()}
    tables = {}
    for s in strategies:
        for name, rows in s.precompute(placed, sources).items():
            if name in tables:
                raise ValueError(f"{s.key}: table {name} already produced by another factor")
            tables[name] = rows
    return {"placed": placed, "unplaced": unplaced, "counts": counts, "tables": tables}


def validate(result, n_residential, min_geocode_coverage):
    coverage = len(result["placed"]) / n_residential if n_residential else 0
    if coverage < min_geocode_coverage:
        raise ValidationError(f"only {coverage:.1%} of residential blocks placed "
                              f"(need {min_geocode_coverage:.0%}); see {UNPLACED_LOG}")
    if not result["counts"]:
        raise ValidationError("no in-scope planning areas")
    for table, rows in result["tables"].items():
        for r in rows:
            if "score" in r and not 0 <= r["score"] <= 10:
                raise ValidationError(f"{table}: {r.get('planning_area')} score {r['score']} "
                                      f"outside 0-10")
    return coverage


def _insert_rows(db, table, rows):
    if not rows:
        return
    cols = list(rows[0])
    db.executemany(f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})",
                   [tuple(r[c] for c in cols) for r in rows])


def write_snapshot(path, result, areas, strategies, meta):
    if path.exists():
        path.unlink()
    db = sqlite3.connect(path)
    db.executescript(CORE_SCHEMA)
    for s in strategies:
        db.executescript(s.schema())
    db.executemany("INSERT INTO meta VALUES (?, ?)", sorted(meta.items()))
    for a in areas:
        n_blocks, n_flats = result["counts"].get(a["name"], (0, 0))
        db.execute("INSERT INTO planning_area VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (a["name"], a["region"], int(n_blocks > 0), n_blocks, n_flats,
                    int(is_small_sample(n_blocks)), json.dumps(a["geometry"])))
    _insert_rows(db, "hdb_block", [
        {k: b[k] for k in ("id", "blk_no", "street", "postal", "lat", "lon", "planning_area",
                           "total_dwelling_units")} for b in result["placed"]])
    for table, rows in result["tables"].items():
        _insert_rows(db, table, rows)
    db.commit()
    db.close()


def write_unplaced_log(unplaced, path=UNPLACED_LOG):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["blk_no", "street", "total_dwelling_units", "reason", "detail"])
        for b in unplaced:
            w.writerow([b["blk_no"], b["street"], b["total_dwelling_units"], b["reason"], b["detail"]])


def load_inputs():
    """(blocks, geocodes, areas, sources) from data/raw and the geocode cache. Offline."""
    blocks = load_hdb_residential()
    return blocks, load_geocodes(blocks=blocks), load_planning_areas(), RawSources()


def build(snapshot_path=config.SNAPSHOT_PATH, min_geocode_coverage=0.98, strategies=None):
    strategies = default_strategies() if strategies is None else strategies
    blocks, geocodes, areas, sources = load_inputs()
    result = compute(blocks, geocodes, areas, sources, strategies)
    write_unplaced_log(result["unplaced"])
    coverage = validate(result, len(blocks), min_geocode_coverage)

    manifest_path = config.RAW_DIR / "_manifest.json"
    meta = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "schema_version": SCHEMA_VERSION,
        "factors": ",".join(s.key for s in strategies),
        "detour_factor_calibrated_on": config.DETOUR_FACTOR_CALIBRATED_ON,
        "detour_factor_source": config.DETOUR_FACTOR_SOURCE,
        "walk_speed_m_per_min": str(config.WALK_SPEED_M_PER_MIN),
        "walk_threshold_min": str(config.WALK_THRESHOLD_MIN),
        "small_area_blocks": str(config.SMALL_AREA_BLOCKS),
        "residential_blocks": str(len(blocks)),
        "placed_blocks": str(len(result["placed"])),
        "geocode_coverage": f"{coverage:.4f}",
        "raw_manifest": manifest_path.read_text() if manifest_path.exists() else "{}",
    }
    for s in strategies:
        for key, value in s.meta(sources).items():
            if key in meta:
                raise ValueError(f"{s.key}: meta key {key} already set")
            meta[key] = value
    tmp = snapshot_path.with_suffix(".db.tmp")
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    write_snapshot(tmp, result, areas, strategies, meta)
    os.replace(tmp, snapshot_path)
    return result, meta


def main():
    parser = argparse.ArgumentParser(description="Build data/snapshot.db (offline)")
    parser.add_argument("--min-geocode-coverage", type=float, default=0.98)
    args = parser.parse_args()
    try:
        result, meta = build(min_geocode_coverage=args.min_geocode_coverage)
    except ValidationError as e:
        raise SystemExit(f"validation failed, previous snapshot kept: {e}")
    print(f"snapshot written: {meta['placed_blocks']}/{meta['residential_blocks']} blocks placed, "
          f"{len(result['counts'])} in-scope areas, {len(result['unplaced'])} unplaced "
          f"(logged to {UNPLACED_LOG}); factors: {meta['factors']}")
    for table, rows in result["tables"].items():
        if rows and "score" in rows[0]:
            print(f"  {table}: {len(rows)} rows")


if __name__ == "__main__":
    main()
