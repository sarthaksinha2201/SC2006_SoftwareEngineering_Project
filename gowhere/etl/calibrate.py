"""Calibrate the walking detour factor against real OneMap walking routes.

The walking model is straight-line distance x detour factor / 80 m per minute
(DECISIONS.md section 4). This samples blocks from the snapshot, fetches the OneMap
walking route from each block to its nearest exit, and compares route distance with
straight-line distance. Routes are cached, so re-running makes no repeat requests.

Needs ONEMAP_TOKEN (environment or .env) and a built snapshot.

    python -m gowhere.etl.calibrate [--n 200] [--seed 2006]
"""
import argparse
import csv
import json
import sqlite3
import statistics
from datetime import datetime, timezone
from random import Random

from gowhere import config
from gowhere.adapters.http import HttpError
from gowhere.adapters.onemap import OneMapAdapter

ROUTE_CACHE_PATH = config.CACHE_DIR / "onemap_route.sqlite"
REPORT_PATH = config.DOCS_DIR / "detour-calibration.md"
SAMPLE_CSV_PATH = config.DOCS_DIR / "detour-calibration-sample.csv"
DISTANCE_BANDS_M = [(0, 400), (400, 800), (800, 1200), (1200, float("inf"))]


class RouteCache:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute("""CREATE TABLE IF NOT EXISTS route (
            key TEXT PRIMARY KEY, response_json TEXT NOT NULL, fetched_at TEXT NOT NULL)""")

    def get(self, key):
        row = self.db.execute("SELECT response_json FROM route WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key, response):
        self.db.execute("INSERT OR REPLACE INTO route VALUES (?, ?, ?)",
                        (key, json.dumps(response),
                         datetime.now(timezone.utc).isoformat(timespec="seconds")))
        self.db.commit()


def sample_blocks(snapshot_path, n, seed):
    """Simple random sample of placed blocks, reproducible from the seed."""
    db = sqlite3.connect(snapshot_path)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute(
        "SELECT b.blk_no, b.street, b.lat, b.lon, b.planning_area, b.total_dwelling_units,"
        " b.nearest_station, b.nearest_exit_code, b.exit_distance_m, e.lat AS exit_lat,"
        " e.lon AS exit_lon"
        " FROM hdb_block b JOIN mrt_exit e"
        "   ON e.station = b.nearest_station AND e.exit_code = b.nearest_exit_code"
        " GROUP BY b.id ORDER BY b.id")]
    return Random(seed).sample(rows, min(n, len(rows)))


def fetch_routes(sample, adapter, cache):
    """Attach route_distance_m / route_time_s to each sampled block; failures are kept."""
    for b in sample:
        key = f"{b['lat']:.7f},{b['lon']:.7f}->{b['exit_lat']:.7f},{b['exit_lon']:.7f}"
        resp = cache.get(key)
        if resp is None:
            try:
                resp = adapter.walking_route((b["lat"], b["lon"]), (b["exit_lat"], b["exit_lon"]))
            except HttpError as e:
                b.update(route_status="error", route_detail=str(e))
                continue
            cache.put(key, resp)
        summary = resp.get("route_summary") or {}
        if summary.get("total_distance") is None:
            b.update(route_status="no_route", route_detail=resp.get("status_message", ""))
            continue
        b.update(route_status="ok", route_detail="",
                 route_distance_m=float(summary["total_distance"]),
                 route_time_s=float(summary.get("total_time") or 0))
    return sample


def summarise(sample, current_factor=config.DETOUR_FACTOR,
              speed=config.WALK_SPEED_M_PER_MIN, threshold=config.WALK_THRESHOLD_MIN):
    ok = [b for b in sample if b.get("route_status") == "ok" and b["exit_distance_m"] > 0]
    ratios = sorted(b["route_distance_m"] / b["exit_distance_m"] for b in ok)
    if not ratios:
        raise ValueError("no successful routes to calibrate against")
    q = statistics.quantiles(ratios, n=10, method="inclusive")
    calibrated = statistics.median(ratios)

    def agreement(factor):
        """Share of sampled blocks the model puts on the same side of 10 min as the route."""
        same = sum((b["exit_distance_m"] * factor / speed <= threshold)
                   == (b["route_distance_m"] / speed <= threshold) for b in ok)
        return same / len(ok)

    def mean_abs_error_min(factor):
        return statistics.fmean(abs(b["exit_distance_m"] * factor - b["route_distance_m"]) / speed
                                for b in ok)

    bands = []
    for lo, hi in DISTANCE_BANDS_M:
        rs = [b["route_distance_m"] / b["exit_distance_m"] for b in ok if lo <= b["exit_distance_m"] < hi]
        if rs:
            bands.append((lo, hi, len(rs), statistics.median(rs)))
    return {
        "n_sampled": len(sample), "n_ok": len(ok),
        "n_failed": len(sample) - len(ok),
        "median": calibrated, "mean": statistics.fmean(ratios),
        "p10": q[0], "p25": statistics.quantiles(ratios, n=4, method="inclusive")[0],
        "p75": statistics.quantiles(ratios, n=4, method="inclusive")[2], "p90": q[8],
        "min": ratios[0], "max": ratios[-1],
        "current_factor": current_factor, "calibrated_factor": round(calibrated, 2),
        "agreement_current": agreement(current_factor),
        "agreement_calibrated": agreement(round(calibrated, 2)),
        "mae_current_min": mean_abs_error_min(current_factor),
        "mae_calibrated_min": mean_abs_error_min(round(calibrated, 2)),
        "bands": bands,
    }


def write_outputs(sample, s, seed):
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["blk_no", "street", "planning_area", "lat", "lon", "nearest_station",
              "nearest_exit_code", "exit_distance_m", "route_distance_m", "route_time_s",
              "route_status", "route_detail"]
    with open(SAMPLE_CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(sample)

    band_rows = "\n".join(
        f"| {lo:.0f}–{'' if hi == float('inf') else f'{hi:.0f}'} m | {n} | {med:.2f} |"
        for lo, hi, n, med in s["bands"])
    REPORT_PATH.write_text(f"""# Walking detour factor — calibration

Generated {datetime.now(timezone.utc):%Y-%m-%d} by `python -m gowhere.etl.calibrate --seed {seed}`.
Raw per-block results: [detour-calibration-sample.csv](detour-calibration-sample.csv).

## Method

The snapshot estimates walking time as straight-line (Haversine) distance to the nearest MRT/LRT exit × detour factor ÷ 80 m/min. To check the detour factor, {s['n_sampled']} HDB residential blocks were drawn by simple random sample (seed {seed}), and the OneMap walking route from each block's geocoded point to the same exit was fetched. For each block, **ratio = OneMap route distance ÷ straight-line distance**. Only distances are compared; the 80 m/min walking speed is a separate assumption.

{s['n_ok']} routes succeeded; {s['n_failed']} failed and are listed in the CSV with the reason.

## Result

| Statistic | Ratio |
|---|---|
| Median | **{s['median']:.2f}** |
| Mean | {s['mean']:.2f} |
| P10 / P25 | {s['p10']:.2f} / {s['p25']:.2f} |
| P75 / P90 | {s['p75']:.2f} / {s['p90']:.2f} |
| Min / Max | {s['min']:.2f} / {s['max']:.2f} |

By straight-line distance:

| Distance | Blocks | Median ratio |
|---|---|---|
{band_rows}

## Effect on the 10-minute measure

| Factor | Same 10-min verdict as the real route | Mean absolute error |
|---|---|---|
| {s['current_factor']} (current) | {s['agreement_current']:.1%} | {s['mae_current_min']:.1f} min |
| {s['calibrated_factor']} (sample median) | {s['agreement_calibrated']:.1%} | {s['mae_calibrated_min']:.1f} min |

"Same verdict" means the model and the real route agree on whether the block is within a 10-minute walk, which is the figure the transport score depends on most.
""")


def main():
    parser = argparse.ArgumentParser(description="Calibrate the walking detour factor")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2006)
    args = parser.parse_args()
    config.load_dotenv()

    adapter = OneMapAdapter()
    if not adapter.token:
        raise SystemExit("ONEMAP_TOKEN is not set (environment or .env); routing needs it")
    sample = sample_blocks(config.SNAPSHOT_PATH, args.n, args.seed)
    fetch_routes(sample, adapter, RouteCache(ROUTE_CACHE_PATH))
    s = summarise(sample)
    write_outputs(sample, s, args.seed)
    print(f"{s['n_ok']}/{s['n_sampled']} routes; median ratio {s['median']:.2f} "
          f"(P10 {s['p10']:.2f}, P90 {s['p90']:.2f}); 10-min agreement "
          f"{s['agreement_current']:.1%} at {s['current_factor']}, "
          f"{s['agreement_calibrated']:.1%} at {s['calibrated_factor']}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
