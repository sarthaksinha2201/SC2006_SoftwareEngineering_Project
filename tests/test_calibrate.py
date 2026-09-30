import pytest

from gowhere.adapters.http import HttpError
from gowhere.etl.calibrate import (RouteCache, allocate, fetch_routes, limitation_text,
                                    stratified_sample, summarise)


class FakeRouter:
    def __init__(self, distances):
        self.distances, self.calls = distances, 0

    def walking_route(self, start, end):
        self.calls += 1
        d = self.distances[start]
        if d is None:
            raise HttpError("HTTP 500", status=500)
        return {"route_summary": {"total_distance": d, "total_time": d / 1.2}}


def block(lat, straight_m):
    return {"lat": lat, "lon": 103.8, "exit_lat": 1.0, "exit_lon": 103.9,
            "exit_distance_m": straight_m, "planning_area": "X"}


def test_fetch_is_cached_and_failures_kept(tmp_path):
    sample = [block(1.1, 500), block(1.2, 700), block(1.3, 900)]
    router = FakeRouter({(1.1, 103.8): 650, (1.2, 103.8): 1050, (1.3, 103.8): None})
    cache = RouteCache(tmp_path / "r.sqlite")
    fetch_routes(sample, router, cache)
    assert [b["route_status"] for b in sample] == ["ok", "ok", "error"]

    again = [block(1.1, 500), block(1.2, 700)]
    router2 = FakeRouter({})
    fetch_routes(again, router2, cache)
    assert router2.calls == 0 and again[1]["route_distance_m"] == 1050


def test_summary_ratio_and_threshold_agreement():
    # ratios 1.3, 1.5, 1.7 -> median 1.5
    sample = [dict(block(1.1, 500), route_status="ok", route_distance_m=650),
              dict(block(1.2, 600), route_status="ok", route_distance_m=900),
              dict(block(1.3, 500), route_status="ok", route_distance_m=850),
              dict(block(1.4, 500), route_status="error")]
    s = summarise(sample, current_factor=1.3, speed=80, threshold=10)
    assert s["median"] == pytest.approx(1.5) and s["calibrated_factor"] == 1.5
    assert (s["n_ok"], s["n_failed"]) == (3, 1)
    assert s["onemap_speed_m_per_min"] is None   # no route times in this sample
    # route minutes 8.1, 11.25, 10.6 -> within: T, F, F
    # model @1.3 minutes: 8.1, 9.75, 8.1 -> T, T, T  -> agrees 1/3
    # model @1.5 minutes: 9.4, 11.25, 9.4 -> T, F, T  -> agrees 2/3
    assert s["agreement_current"] == pytest.approx(1 / 3)
    assert s["agreement_calibrated"] == pytest.approx(2 / 3)


def stats_with(median, p25, p75, agreement_gain=0.0):
    return {"n_sampled": 3, "n_ok": 3, "n_failed": 0, "median": median, "mean": median + 0.1,
            "p10": p25 - 0.1, "p25": p25, "p75": p75, "p90": p75 + 0.1, "min": 1.0, "max": 3.0,
            "current_factor": 1.3, "calibrated_factor": round(median, 2),
            "share_above_current": 0.6, "agreement_current": 0.9,
            "agreement_calibrated": 0.9 + agreement_gain,
            "mae_current_min": 1.0, "mae_calibrated_min": 0.9, "bands": [(0, 400, 3, median)],
            "areas": [("A", 6, median + 0.3), ("B", 5, median - 0.1)]}


def test_close_median_keeps_factor_and_narrow_spread_not_flagged():
    from gowhere.etl.calibrate import recommendation_text, spread_text
    s = stats_with(1.35, 1.25, 1.45, agreement_gain=0.005)
    assert "1.3 is kept" in recommendation_text(s) and "60% of sampled blocks" in recommendation_text(s)
    assert "spread is wide" not in spread_text(s)


def test_far_median_is_proposed_not_applied_and_wide_spread_flagged():
    from gowhere.etl.calibrate import recommendation_text, spread_text
    s = stats_with(1.6, 1.3, 1.9, agreement_gain=0.035)
    text = recommendation_text(s)
    assert "Proposed new factor: 1.6" in text and "has not been changed" in text
    assert "spread is wide" in spread_text(s)


def test_adopted_detour_factor_is_the_calibrated_median():
    """Pins the team decision of 30 Sep 2026 (DECISIONS.md section 4): 1.39, not 1.3."""
    from gowhere import config
    assert config.DETOUR_FACTOR == 1.39
    assert config.DETOUR_FACTOR_CALIBRATED_ON == "2026-09-30"


def test_report_renders(tmp_path, monkeypatch):
    from gowhere.etl import calibrate
    monkeypatch.setattr(calibrate.config, "DOCS_DIR", tmp_path)
    monkeypatch.setattr(calibrate, "REPORT_PATH", tmp_path / "r.md")
    monkeypatch.setattr(calibrate, "SAMPLE_CSV_PATH", tmp_path / "s.csv")
    calibrate.write_outputs([block(1.1, 500)], stats_with(1.35, 1.25, 1.45), seed=1)
    report = (tmp_path / "r.md").read_text()
    assert "## Spread" in report and "## Recommendation" in report and "{" not in report


def test_allocate_is_proportional_and_sums_to_n():
    # exact shares 7 / 2.5 / 0.5; the tied 0.5 remainders go to "mid" (alphabetical)
    assert allocate(10, {"big": 700, "mid": 250, "tiny": 50}) == {"big": 7, "mid": 3, "tiny": 0}


def test_allocate_largest_remainder():
    # exact shares 3.33 / 3.33 / 3.33 -> one extra sample to the first name alphabetically
    assert allocate(10, {"b": 1, "a": 1, "c": 1}) == {"a": 4, "b": 3, "c": 3}


def test_stratified_sample_follows_flat_share_not_row_order():
    # Area "EARLY" comes first in row order with many blocks but few flats.
    rows = ([{"planning_area": "EARLY", "total_dwelling_units": 10, "i": i} for i in range(100)]
            + [{"planning_area": "LATE", "total_dwelling_units": 90, "i": i} for i in range(100)])
    sample = stratified_sample(rows, 20, seed=1)
    by_area = {a: sum(r["planning_area"] == a for r in sample) for a in ("EARLY", "LATE")}
    assert by_area == {"EARLY": 2, "LATE": 18}
    assert sample == stratified_sample(rows, 20, seed=1)


def test_summary_reports_per_area_medians_for_areas_with_enough_samples():
    sample = ([dict(block(1.1, 100), planning_area="A", route_status="ok", route_distance_m=150)
               for _ in range(5)]
              + [dict(block(1.1, 100), planning_area="B", route_status="ok", route_distance_m=120)
                 for _ in range(5)]
              + [dict(block(1.1, 100), planning_area="C", route_status="ok", route_distance_m=300)])
    s = summarise(sample)
    assert s["areas"] == [("A", 5, 1.5), ("B", 5, 1.2)]   # C has too few samples


def test_limitation_always_stated_and_area_gap_flagged():
    s = {"areas": [("A", 6, 1.7), ("B", 5, 1.2)]}
    text = limitation_text(s)
    assert "stated modelling limitation" in text and "Future work" in text
    assert "differ noticeably" in text and "1.20 (B)" in text
    assert "close" in limitation_text({"areas": [("A", 6, 1.35), ("B", 5, 1.3)]})


def test_onemap_implied_speed():
    sample = [dict(block(1.1, 500), route_status="ok", route_distance_m=800, route_time_s=600),
              dict(block(1.2, 500), route_status="ok", route_distance_m=900, route_time_s=600)]
    assert summarise(sample)["onemap_speed_m_per_min"] == pytest.approx((80 + 90) / 2)


def test_ranking_impact_reports_moves_and_stable_ends():
    from gowhere.etl.calibrate import ranking_impact, ranking_impact_text

    def result(scores, pcts):
        return {"scores": {a: {"score": v} for a, v in scores.items()},
                "metrics": {a: {"pct_within_10": v} for a, v in pcts.items()}}
    a = result({"P": 9.0, "Q": 5.0, "R": 4.9, "S": 1.0}, {"P": 100, "Q": 60, "R": 58, "S": 10})
    b = result({"P": 9.0, "Q": 4.7, "R": 4.95, "S": 1.0}, {"P": 100, "Q": 52, "R": 57, "S": 10})
    i = ranking_impact(a, b, top=1, bottom=1)
    assert i["moved"] == [("Q", 2, 3), ("R", 3, 2)] and i["max_rank_shift"] == 1
    assert i["max_score_change"] == pytest.approx(0.3)
    assert i["top_unchanged"] and i["bottom_unchanged"]
    assert i["max_pct_drop"] == pytest.approx(8)
    text = ranking_impact_text(i, 1.3, 1.39)
    assert "Q 2→3" in text and "Top 1: unchanged" in text and "Q 60.0% → 52.0%" in text


def test_recommendation_says_adopted_once_config_matches():
    from gowhere.etl.calibrate import recommendation_text
    text = recommendation_text(stats_with(1.39, 1.29, 1.57, agreement_gain=0.035))
    assert "1.39 is adopted" in text and "Pending" not in text
