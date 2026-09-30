"""Golden test: transport scores for a fixed mini-dataset, calculated by hand.

The hand calculation is written out in docs/golden-transport.md. If this test fails,
either the scoring code or the documented definition changed; both must agree to
1 decimal place (Accuracy NFR).
"""
import pytest

from gowhere.scoring.stats import round1
from gowhere.scoring.transport import area_metrics, transport_scores

# area -> [(walk minutes, flats)]
GOLDEN_INPUT = {
    "A": [(4, 100), (8, 100), (12, 200)],
    "B": [(3, 300), (15, 100)],
    "C": [(9, 50), (11, 50), (20, 100)],
    "D": [(6, 200), (10, 200)],        # 10.0 min exactly: counts as within 10
    "E": [(5, 100), (25, 100)],        # ties A on % within 10
}

# area -> (pct_within_10, median, p90, PR(pct), PR(median), score)
EXPECTED = {
    "A": (50.0, 8, 12, 3.75, 2.5, 3.375),
    "B": (75.0, 3, 15, 7.5, 10.0, 8.25),
    "C": (25.0, 11, 20, 0.0, 0.0, 0.0),
    "D": (100.0, 6, 10, 10.0, 5.0, 8.5),
    "E": (50.0, 5, 25, 3.75, 7.5, 4.875),
}

# What the user sees: hand rounding (half up) of the scores above.
EXPECTED_DISPLAY = {"A": 3.4, "B": 8.3, "C": 0.0, "D": 8.5, "E": 4.9}


@pytest.fixture(scope="module")
def results():
    metrics = {a: area_metrics([w for w, _ in blocks], [f for _, f in blocks])
               for a, blocks in GOLDEN_INPUT.items()}
    return metrics, transport_scores(metrics)


@pytest.mark.parametrize("area", sorted(EXPECTED))
def test_golden_metrics_and_scores(results, area):
    metrics, scores = results
    pct, median, p90, pr_pct, pr_med, score = EXPECTED[area]
    assert metrics[area]["pct_within_10"] == pytest.approx(pct)
    assert metrics[area]["median_walk_min"] == median
    assert metrics[area]["p90_walk_min"] == p90
    assert scores[area]["pr_pct_within_10"] == pytest.approx(pr_pct)
    assert scores[area]["pr_median_walk"] == pytest.approx(pr_med)
    assert scores[area]["score"] == pytest.approx(score)


@pytest.mark.parametrize("area", sorted(EXPECTED_DISPLAY))
def test_golden_display_matches_hand_rounding(results, area):
    _, scores = results
    assert round1(scores[area]["score"]) == EXPECTED_DISPLAY[area]
