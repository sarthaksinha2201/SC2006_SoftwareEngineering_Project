"""Golden test: Public Transport scores for a fixed mini-dataset, calculated by hand.

The hand calculation is written out in docs/golden-public-transport.md. If this test fails,
either the scoring code or the documented definition changed; both must agree to
1 decimal place (Accuracy NFR).
"""
import ast
from pathlib import Path

import pytest

from gowhere.scoring.stats import round1
from gowhere.scoring.public_transport import area_metrics, public_transport_scores

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
    return metrics, public_transport_scores(metrics)


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


def test_x5_boundary_rounds_half_up(results):
    """Area B scores exactly 8.25. By hand that displays as 8.3; Python's round() gives 8.2.

    This is the case that breaks the Accuracy NFR while the scoring maths is entirely
    correct, so the mismatch would be hunted for in the wrong place.
    """
    _, scores = results
    assert scores["B"]["score"] == pytest.approx(8.25)
    assert round(scores["B"]["score"], 1) == 8.2      # why round() must not be used
    assert round1(scores["B"]["score"]) == 8.3


def test_no_builtin_round_outside_round1():
    """Anything that rounds a score for display or ranking must use round1, not round().

    ETL internals are exempt: they never produce a user-visible score.
    """
    pkg = Path(__file__).resolve().parent.parent / "gowhere"
    offenders = []
    for path in pkg.rglob("*.py"):
        if path.is_relative_to(pkg / "etl"):
            continue
        tree = ast.parse(path.read_text())
        allowed = {id(n) for f in ast.walk(tree)
                   if isinstance(f, ast.FunctionDef) and f.name in {"round1", "round0"}
                   for n in ast.walk(f)}
        offenders += [f"{path.relative_to(pkg.parent)}:{n.lineno}"
                      for n in ast.walk(tree)
                      if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                      and n.func.id == "round" and id(n) not in allowed]
    assert offenders == [], "use gowhere.scoring.stats.round1 at: " + ", ".join(offenders)


# ---- Bus and Either modes (FR 1.2.4; DECISIONS.md 18), hand-calculated in
# docs/golden-public-transport.md

from gowhere.scoring.public_transport import bus_scores, either_choice
from gowhere.scoring.stats import weighted_quantile

# area -> [(rail walk min, bus walk min, distinct bus services within 400 m, flats)]
GOLDEN_MODES_INPUT = {
    "P": [(12, 3, 20, 100), (14, 5, 30, 100)],     # far from rail, many bus services
    "Q": [(4, 2, 8, 100), (6, 4, 10, 100)],        # beside a station; nearest bus stops, few services
    "R": [(9, 9.5, 15, 100), (20, 12, 40, 100)],
}
# area -> (median services, median bus walk, PR(services), PR(walk), bus score)
GOLDEN_BUS = {"P": (20, 3, 10.0, 5.0, 8.5), "Q": (8, 2, 0.0, 10.0, 3.0),
              "R": (15, 9.5, 5.0, 0.0, 3.5)}
GOLDEN_RAIL = {"P": 0.0, "Q": 10.0, "R": 5.0}
# area -> (Either score, the mode it took)
GOLDEN_EITHER = {"P": (8.5, "bus"), "Q": (10.0, "rail"), "R": (5.0, "rail")}


def golden_mode_scores():
    flats = {a: [f for *_, f in b] for a, b in GOLDEN_MODES_INPUT.items()}
    rail = public_transport_scores({a: area_metrics([r for r, *_ in b], flats[a])
                                    for a, b in GOLDEN_MODES_INPUT.items()})
    bus_metrics = {a: {"median_services": weighted_quantile([s for _, _, s, _ in b], flats[a], 0.5),
                       "median_walk_min": weighted_quantile([w for _, w, _, _ in b], flats[a], 0.5)}
                   for a, b in GOLDEN_MODES_INPUT.items()}
    return rail, bus_metrics, bus_scores(bus_metrics)


def test_golden_bus_scores_services_not_distance():
    rail, metrics, bus = golden_mode_scores()
    for area, (svc, walk, pr_svc, pr_walk, score) in GOLDEN_BUS.items():
        assert metrics[area]["median_services"] == svc
        assert metrics[area]["median_walk_min"] == walk
        assert bus[area]["pr_median_services"] == pytest.approx(pr_svc)
        assert bus[area]["pr_median_walk"] == pytest.approx(pr_walk)
        assert bus[area]["score"] == pytest.approx(score)
    assert {a: r["score"] for a, r in rail.items()} == pytest.approx(GOLDEN_RAIL)


def test_golden_either_takes_the_higher_mode_score():
    rail, _, bus = golden_mode_scores()
    for area, (score, mode) in GOLDEN_EITHER.items():
        got = either_choice(rail[area]["score"], bus[area]["score"])
        assert got[0] == pytest.approx(score) and got[1] == mode


def test_either_breaks_a_tie_towards_rail():
    assert either_choice(5.0, 5.0) == (5.0, "rail")


def test_a_bus_user_gets_a_different_answer():
    """The reason for building the option: the top area changes with the mode."""
    rail, _, bus = golden_mode_scores()
    top = lambda scores: max(scores, key=scores.get)
    assert top({a: r["score"] for a, r in rail.items()}) == "Q"
    assert top({a: r["score"] for a, r in bus.items()}) == "P"
