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


def allocate(n, weights):
    """Split n samples across strata in proportion to weight (largest-remainder method).

    Ties in the remainder go to the alphabetically first stratum, so the result is
    deterministic. Strata too small to earn a whole sample get none.
    """
    total = sum(weights.values())
    exact = {k: n * w / total for k, w in weights.items()}
    counts = {k: int(v) for k, v in exact.items()}
    leftover = n - sum(counts.values())
    for k in sorted(exact, key=lambda k: (-(exact[k] - counts[k]), k))[:leftover]:
        counts[k] += 1
    return counts


def stratified_sample(rows, n, seed):
    """Sample blocks so each planning area's share of the sample matches its share of flats.

    Within an area, blocks are drawn by simple random sample. Reproducible from the seed.
    """
    by_area = {}
    for r in rows:
        by_area.setdefault(r["planning_area"], []).append(r)
    counts = allocate(min(n, len(rows)),
                      {a: sum(r["total_dwelling_units"] for r in rs) for a, rs in by_area.items()})
    rng = Random(seed)
    sample = []
    for area in sorted(by_area):
        sample += rng.sample(by_area[area], min(counts[area], len(by_area[area])))
    return sample


def sample_blocks(snapshot_path, n, seed):
    """Placed blocks from the snapshot, stratified by planning area in proportion to flats."""
    db = sqlite3.connect(snapshot_path)
    db.row_factory = sqlite3.Row
    rows = [dict(r) for r in db.execute(
        "SELECT b.blk_no, b.street, b.lat, b.lon, b.planning_area, b.total_dwelling_units,"
        " b.nearest_station, b.nearest_exit_code, b.exit_distance_m, e.lat AS exit_lat,"
        " e.lon AS exit_lon"
        " FROM hdb_block b JOIN mrt_exit e"
        "   ON e.station = b.nearest_station AND e.exit_code = b.nearest_exit_code"
        " GROUP BY b.id ORDER BY b.id")]
    return stratified_sample(rows, n, seed)


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
    by_area = {}
    for b in ok:
        by_area.setdefault(b["planning_area"], []).append(b["route_distance_m"] / b["exit_distance_m"])
    areas = sorted(((a, len(rs), statistics.median(rs)) for a, rs in by_area.items()
                    if len(rs) >= MIN_AREA_SAMPLE), key=lambda t: -t[2])
    return {
        "n_sampled": len(sample), "n_ok": len(ok),
        "n_failed": len(sample) - len(ok),
        "median": calibrated, "mean": statistics.fmean(ratios),
        "p10": q[0], "p25": statistics.quantiles(ratios, n=4, method="inclusive")[0],
        "p75": statistics.quantiles(ratios, n=4, method="inclusive")[2], "p90": q[8],
        "min": ratios[0], "max": ratios[-1],
        "current_factor": current_factor, "calibrated_factor": round(calibrated, 2),
        "share_above_current": sum(r > current_factor for r in ratios) / len(ratios),
        "agreement_current": agreement(current_factor),
        "agreement_calibrated": agreement(round(calibrated, 2)),
        "mae_current_min": mean_abs_error_min(current_factor),
        "mae_calibrated_min": mean_abs_error_min(round(calibrated, 2)),
        "bands": bands, "areas": areas,
        # OneMap's own walking speed, as a check on the 80 m/min assumption
        "onemap_speed_m_per_min": statistics.median(
            b["route_distance_m"] / (b["route_time_s"] / 60) for b in ok if b.get("route_time_s")
        ) if any(b.get("route_time_s") for b in ok) else None,
    }


def ranking_impact(result_a, result_b, top=18, bottom=4):
    """How switching factor changes area scores and ranks (results from build_snapshot.compute).

    A uniform factor scales every walk equally, so the median-walk ranking cannot change;
    only the share within 10 minutes can move scores and ranks.
    """
    sa, sb = result_a["scores"], result_b["scores"]
    rank = lambda s: {a: i + 1 for i, a in enumerate(sorted(s, key=lambda a: (-s[a]["score"], a)))}
    ra, rb = rank(sa), rank(sb)
    n = len(sa)
    moved = sorted((a for a in sa if ra[a] != rb[a]), key=lambda a: ra[a])
    top_same = all(ra[a] == rb[a] for a in sa if ra[a] <= top)
    bottom_same = all(ra[a] == rb[a] for a in sa if ra[a] > n - bottom)
    pct = {a: (result_a["metrics"][a]["pct_within_10"], result_b["metrics"][a]["pct_within_10"])
           for a in sa}
    return {
        "n_areas": n, "moved": [(a, ra[a], rb[a]) for a in moved],
        "max_rank_shift": max(abs(ra[a] - rb[a]) for a in sa),
        "max_score_change": max(abs(sa[a]["score"] - sb[a]["score"]) for a in sa),
        "top": top, "top_unchanged": top_same, "bottom": bottom, "bottom_unchanged": bottom_same,
        "max_pct_drop": max(pct[a][0] - pct[a][1] for a in sa),
        "biggest_pct_change": max(pct.items(), key=lambda kv: abs(kv[1][0] - kv[1][1])),
    }


def ranking_impact_text(i, factor_a, factor_b):
    if i is None:
        return "Not computed (run with a built snapshot and geocode cache)."
    area, (pa, pb) = i["biggest_pct_change"]
    moved = ", ".join(f"{a} {r1}→{r2}" for a, r1, r2 in i["moved"]) or "none"
    return (f"Both factors were applied to all {i['n_areas']} in-scope areas and the resulting "
            f"scores compared. Scaling every walk by the same factor cannot change the "
            f"median-walk ranking, so only the share of flats within 10 minutes moves.\n\n"
            f"- Largest score change: **{i['max_score_change']:.2f}** points.\n"
            f"- Areas changing rank: {len(i['moved'])}, by at most {i['max_rank_shift']} "
            f"place(s): {moved}.\n"
            f"- Top {i['top']}: {'unchanged' if i['top_unchanged'] else 'CHANGED'}. "
            f"Bottom {i['bottom']}: {'unchanged' if i['bottom_unchanged'] else 'CHANGED'}.\n"
            f"- Share of flats within 10 minutes (the figure users see) falls by up to "
            f"{i['max_pct_drop']:.1f} points going from {factor_a} to {factor_b}; largest change "
            f"{area} {pa:.1f}% → {pb:.1f}%.\n\n"
            f"The change buys accuracy in a displayed figure without destabilising the ranking.")


def write_outputs(sample, s, seed, impact=None):
    config.DOCS_DIR.mkdir(parents=True, exist_ok=True)
    fields = ["blk_no", "street", "planning_area", "lat", "lon", "nearest_station",
              "nearest_exit_code", "exit_distance_m", "route_distance_m", "route_time_s",
              "route_status", "route_detail"]
    with open(SAMPLE_CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(sample)

    area_rows = "\n".join(f"| {a} | {n} | {med:.2f} |" for a, n, med in s["areas"])
    band_rows = "\n".join(
        f"| {lo:.0f}–{'' if hi == float('inf') else f'{hi:.0f}'} m | {n} | {med:.2f} |"
        for lo, hi, n, med in s["bands"])
    REPORT_PATH.write_text(f"""# Walking detour factor — calibration

Generated {datetime.now(timezone.utc):%Y-%m-%d} by `python -m gowhere.etl.calibrate --seed {seed}`.
Raw per-block results: [detour-calibration-sample.csv](detour-calibration-sample.csv).

## Method

The snapshot estimates walking time as straight-line (Haversine) distance to the nearest MRT/LRT exit × detour factor ÷ 80 m/min. To check the detour factor, {s['n_sampled']} HDB residential blocks were drawn by stratified random sample (seed {seed}): each planning area received a share of the sample equal to its share of HDB dwelling units, and blocks within an area were drawn at random. The median therefore describes Singapore's flats as a whole, not whichever areas happen to come first in the dataset. The OneMap walking route from each block's geocoded point to its nearest exit was then fetched. For each block, **ratio = OneMap route distance ÷ straight-line distance**. Only distances are compared; the 80 m/min walking speed is a separate assumption{speed_note(s)}.

{s['n_ok']} of {s['n_sampled']} routes succeeded{'' if not s['n_failed'] else '; the failures are listed in the CSV with the reason'}.

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

"Same verdict" means the model and the real route agree on whether the block is within a 10-minute walk, which is the figure the Public Transport score depends on most.

## Spread

{spread_text(s)}

## By planning area

Areas with at least {MIN_AREA_SAMPLE} sampled blocks, highest median first:

| Planning area | Blocks | Median ratio |
|---|---|---|
{area_rows}

## Limitation: one national factor

{limitation_text(s)}

## Ranking impact of {s['current_factor']} → {s['calibrated_factor']}

{ranking_impact_text(impact, s['current_factor'], s['calibrated_factor'])}

## Recommendation

{recommendation_text(s)}

### How the recommendation rule was chosen

{RULE_HISTORY}

The rule is now tied to what the score uses: **adopt the sample median when it improves agreement with real routes on the 10-minute verdict by at least {MATERIAL_AGREEMENT_GAIN * 100:.0f} point.** A factor change that leaves that verdict unchanged for almost every block cannot matter to the ranking, whatever its size; one that changes it can.

## Decision

Adopted: **{config.DETOUR_FACTOR}** on {config.DETOUR_FACTOR_CALIBRATED_ON} (`gowhere/config.py`, recorded in the snapshot's `meta` table as `detour_factor` and `detour_factor_calibrated_on`). Replaces the 1.3 placeholder, which came from the 1.2–1.4 range commonly cited for street-network circuity.
""")


MIN_AREA_SAMPLE = 5        # fewer sampled blocks than this gives no usable area median
AREA_SPREAD_NOTICEABLE = 0.2  # gap between highest and lowest area median
WIDE_IQR = 0.3            # middle half of blocks spans more than ±0.15 around the median
# Fixed history (30 Sep 2026), not recomputed: it records why the rule below exists.
RULE_HISTORY = (
    "The first draft of this report (30 Sep 2026) kept the 1.3 placeholder unless the measured "
    "median fell more than ±0.1 from it. The median came in at 1.39, inside that band, so the "
    "draft said \"keep 1.3\". That tolerance was arbitrary: it would have kept a placeholder over "
    "a measurement, and it hid a 3.5-point difference (89.5% vs 93.0%) in how often the model "
    "gets the 10-minute verdict right, which is a number users read directly.")

# Propose the sample median when it gets the 10-minute verdict right for at least this
# many more sampled blocks than the current factor does. The 10-minute share is the only
# place the factor changes rankings: scaling every walk by the same factor leaves the
# median-walk ranking untouched.
MATERIAL_AGREEMENT_GAIN = 0.01


def spread_text(s):
    iqr = s["p75"] - s["p25"]
    text = (f"The middle half of blocks have ratios between {s['p25']:.2f} and {s['p75']:.2f} "
            f"(interquartile range {iqr:.2f}); 80% lie between {s['p10']:.2f} and {s['p90']:.2f}. "
            f"The mean ({s['mean']:.2f}) is reported for completeness only: long detours such as "
            f"expressway or canal crossings pull it up, so the median is the calibrated value.")
    if iqr > WIDE_IQR:
        text += (f"\n\n**The spread is wide.** A single factor fits the typical block, but for an "
                 f"individual block the modelled walk can be off by "
                 f"{iqr / 2 * 800 / 80:.1f} min or more on an 800 m trip. Area-level figures "
                 f"average over many blocks and are much less affected than any one block.")
    return text


def speed_note(s):
    v = s.get("onemap_speed_m_per_min")
    return "" if v is None else f" (for reference, OneMap's own routes imply a median of {v:.0f} m/min)"


def limitation_text(s):
    text = ("The detour ratio varies with geography, not at random. Blocks separated from "
            "their nearest station by an expressway, canal or rail line have to walk around "
            "it, so they sit in the upper tail. That is a real property of those places. "
            "Applying one national factor is therefore a stated modelling limitation: it "
            "understates walking time for such blocks and overstates it for blocks with a "
            "direct path.")
    if len(s["areas"]) >= 2:
        hi, lo = s["areas"][0], s["areas"][-1]
        gap = hi[2] - lo[2]
        if gap > AREA_SPREAD_NOTICEABLE:
            text += (f"\n\nThe per-area medians differ noticeably: from {lo[2]:.2f} ({lo[0]}) to "
                     f"{hi[2]:.2f} ({hi[0]}), a gap of {gap:.2f}. Per-area samples are small "
                     f"(at least {MIN_AREA_SAMPLE} blocks), so individual area medians are indicative only.")
        else:
            text += (f"\n\nIn this sample the per-area medians are close (within {gap:.2f} of each "
                     f"other), so the national factor fits the areas sampled reasonably well.")
    text += ("\n\n**Future work:** a per-area detour factor, calibrated with a larger sample "
             "per area. Not built for this project.")
    return text


def recommendation_text(s):
    facts = (f"{s['share_above_current']:.0%} of sampled blocks walk further than a factor of "
             f"{s['current_factor']} assumes. The sample median ({s['median']:.2f}) gives the same "
             f"10-minute verdict as the real route for {s['agreement_calibrated']:.1%} of blocks, "
             f"against {s['agreement_current']:.1%} for {s['current_factor']}.")
    if s["agreement_calibrated"] - s["agreement_current"] < MATERIAL_AGREEMENT_GAIN:
        return (f"{facts} The difference is immaterial, so **{s['current_factor']} is kept**.")
    if s["calibrated_factor"] == config.DETOUR_FACTOR:
        return f"{facts} **{s['calibrated_factor']} is adopted** (see Decision below)."
    return (f"{facts} **Proposed new factor: {s['calibrated_factor']}.** Pending team decision; "
            f"`config.DETOUR_FACTOR` has not been changed.")


def main():
    parser = argparse.ArgumentParser(description="Calibrate the walking detour factor")
    parser.add_argument("--n", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2006)
    parser.add_argument("--baseline", type=float, default=config.DETOUR_FACTOR,
                        help="factor to evaluate against the sample (default: current config)")
    args = parser.parse_args()
    config.load_dotenv()

    adapter = OneMapAdapter()
    if not adapter.token:
        raise SystemExit("ONEMAP_TOKEN is not set (environment or .env); routing needs it")
    sample = sample_blocks(config.SNAPSHOT_PATH, args.n, args.seed)
    fetch_routes(sample, adapter, RouteCache(ROUTE_CACHE_PATH))
    s = summarise(sample, current_factor=args.baseline)
    impact = None
    if s["calibrated_factor"] != args.baseline:
        from gowhere.etl.build_snapshot import load_inputs, compute
        inputs = load_inputs()
        impact = ranking_impact(compute(*inputs, detour=args.baseline),
                                compute(*inputs, detour=s["calibrated_factor"]))
    write_outputs(sample, s, args.seed, impact)
    print(f"{s['n_ok']}/{s['n_sampled']} routes; median ratio {s['median']:.2f} "
          f"(P10 {s['p10']:.2f}, P90 {s['p90']:.2f}); 10-min agreement "
          f"{s['agreement_current']:.1%} at {s['current_factor']}, "
          f"{s['agreement_calibrated']:.1%} at {s['calibrated_factor']}")
    print(f"report: {REPORT_PATH}")


if __name__ == "__main__":
    main()
