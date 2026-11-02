"""White-box basis path tests (Lab 4 3.2.2, Lectures 19-21) for two methods with
non-trivial control flow. The control flow graphs, cyclomatic complexity and the choice
of basis paths are in docs/testing/basis-path.md; the ids here (WQ-n, DW-n) match its
tables.
"""
from datetime import datetime

import pytest

from gowhere.lepak.search import date_window
from gowhere.scoring.stats import weighted_quantile


# ---- gowhere/scoring/stats.py: weighted_quantile, CC = 5 -----------------------------
# Decisions: D1 q out of range, D2 total weight <= 0, D3 loop has another pair,
# D4 cumulative weight reached the target. WQ-4 (loop never entered, reaching
# `return pairs[-1][0]`) is infeasible, so 4 of the 5 basis paths have a test.

def test_wq1_baseline_returns_inside_first_iteration():
    # D1 F, D2 F, D3 T, D4 T  -> the docstring's own example
    assert weighted_quantile([5, 15], [100, 100], 0.5) == 5


def test_wq2_q_out_of_range_is_rejected():
    # D1 T
    with pytest.raises(ValueError, match=r"q must be in \(0, 1\]"):
        weighted_quantile([5, 15], [100, 100], 0)


def test_wq3_zero_total_weight_is_rejected():
    # D1 F, D2 T
    with pytest.raises(ValueError, match="weights must sum to a positive number"):
        weighted_quantile([5, 15], [0, 0], 0.5)


def test_wq5_loop_iterates_before_reaching_the_target():
    # D1 F, D2 F, D3 T, D4 F, back to D3 T, D4 T  -> P90 of ten equal-weight values
    values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    assert weighted_quantile(values, [1] * 10, 0.9) == 90


# ---- gowhere/lepak/search.py: date_window, CC = 5 ------------------------------------
# Decisions: D1 option == "today", D2 == "tomorrow", D3 == "weekend",
# D4 already Saturday or Sunday. Wednesday 4 Nov 2026 and Saturday 7 Nov 2026.

WEDNESDAY = datetime(2026, 11, 4, 15, 30)
SATURDAY = datetime(2026, 11, 7, 15, 30)


@pytest.mark.parametrize("option, now, expected", [
    # DW-1 baseline: D1 F, D2 F, D3 T, D4 F -> the coming Saturday and Sunday
    pytest.param("weekend", WEDNESDAY,
                 (datetime(2026, 11, 7, 0, 0), datetime(2026, 11, 8, 23, 59)), id="DW-1"),
    # DW-2: D1 T -> from now to the end of today
    pytest.param("today", WEDNESDAY,
                 (WEDNESDAY, datetime(2026, 11, 4, 23, 59)), id="DW-2"),
    # DW-3: D1 F, D2 T -> all of tomorrow
    pytest.param("tomorrow", WEDNESDAY,
                 (datetime(2026, 11, 5, 0, 0), datetime(2026, 11, 5, 23, 59)), id="DW-3"),
    # DW-4: D1 F, D2 F, D3 F -> the next 7 days
    pytest.param("week", WEDNESDAY,
                 (WEDNESDAY, datetime(2026, 11, 11, 23, 59)), id="DW-4"),
    # DW-5: D1 F, D2 F, D3 T, D4 T -> already the weekend: from now to Sunday night
    pytest.param("weekend", SATURDAY,
                 (SATURDAY, datetime(2026, 11, 8, 23, 59)), id="DW-5"),
])
def test_date_window_basis_paths(option, now, expected):
    assert date_window(option, now) == expected
