"""Public Transport category score (DECISIONS.md section 2).

Per area, flat-weighted over its HDB blocks (weight = total_dwelling_units):
  - % of flats within a 10-minute walk of an MRT/LRT exit
  - median and P90 walking time
Score = 0.7 x PR(% within 10 min, higher better) + 0.3 x PR(median walk, lower better),
where PR is the 0-10 percentile rank across all in-scope areas (average rank for ties).
P90 is reported, not scored.
"""
from gowhere import config
from gowhere.scoring.stats import percentile_ranks, weighted_quantile, weighted_share_at_most

WEIGHT_PCT_WITHIN = 0.7
WEIGHT_MEDIAN = 0.3


def area_metrics(walk_minutes, flats, threshold=config.WALK_THRESHOLD_MIN):
    """Flat-weighted walking metrics for one area's blocks."""
    return {
        "n_blocks": len(walk_minutes),
        "n_flats": sum(flats),
        "pct_within_10": weighted_share_at_most(walk_minutes, flats, threshold),
        "median_walk_min": weighted_quantile(walk_minutes, flats, 0.5),
        "p90_walk_min": weighted_quantile(walk_minutes, flats, 0.9),
    }


def public_transport_scores(metrics):
    """metrics: {area: area_metrics(...)} -> {area: {"pr_pct_within_10", "pr_median_walk", "score"}}"""
    pr_pct = percentile_ranks({a: m["pct_within_10"] for a, m in metrics.items()},
                              higher_is_better=True)
    pr_med = percentile_ranks({a: m["median_walk_min"] for a, m in metrics.items()},
                              higher_is_better=False)
    return {a: {"pr_pct_within_10": pr_pct[a], "pr_median_walk": pr_med[a],
                "score": WEIGHT_PCT_WITHIN * pr_pct[a] + WEIGHT_MEDIAN * pr_med[a]}
            for a in metrics}
