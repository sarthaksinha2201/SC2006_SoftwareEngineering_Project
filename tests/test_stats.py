import pytest

from gowhere.scoring.stats import (percentile_ranks, round1, weighted_quantile,
                                   weighted_share_at_most)


def test_share_threshold_is_inclusive():
    assert weighted_share_at_most([10.0, 10.0001], [1, 1], 10) == 50.0


def test_share_rejects_zero_weight():
    with pytest.raises(ValueError):
        weighted_share_at_most([1], [0], 10)


def test_quantile_lower_median_on_even_split():
    assert weighted_quantile([15, 5], [100, 100], 0.5) == 5


def test_quantile_weights_dominate():
    assert weighted_quantile([1, 2, 3], [1, 1, 98], 0.5) == 3


def test_quantile_p90_exact_fraction():
    # cumulative 90 of 100 reaches 0.9 x 100 exactly; float 0.9 must not overshoot
    assert weighted_quantile([1, 2], [90, 10], 0.9) == 1


@pytest.mark.parametrize("q", [0, 1.5])
def test_quantile_rejects_bad_q(q):
    with pytest.raises(ValueError):
        weighted_quantile([1], [1], q)


def test_percentile_ranks_spread_0_to_10():
    assert percentile_ranks({"a": 1, "b": 2, "c": 3}) == {"a": 0.0, "b": 5.0, "c": 10.0}


def test_percentile_ranks_lower_is_better():
    assert percentile_ranks({"a": 1, "b": 2, "c": 3}, higher_is_better=False) == \
        {"a": 10.0, "b": 5.0, "c": 0.0}


def test_percentile_ranks_ties_take_average_rank():
    pr = percentile_ranks({"a": 1, "b": 5, "c": 5, "d": 9})
    assert pr["b"] == pr["c"] == pytest.approx((2.5 - 1) / 3 * 10)


def test_percentile_ranks_all_tied():
    assert set(percentile_ranks({"a": 3, "b": 3}).values()) == {5.0}


def test_percentile_ranks_single_and_empty():
    assert percentile_ranks({"a": 7}) == {"a": 10.0}
    assert percentile_ranks({}) == {}


@pytest.mark.parametrize("x, expected", [(8.25, 8.3), (0.7 * 7.5 + 0.3 * 10, 8.3),
                                         (4.875, 4.9), (3.34999, 3.3), (0.05, 0.1), (10.0, 10.0)])
def test_round1_half_up(x, expected):
    assert round1(x) == expected
