"""Statistics used by category scores. Every definition here is chosen so that it can be
recalculated by hand; docs/scoring-definitions.md states them in words.
"""
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction


def round1(x):
    """Round to 1 decimal place, half up, as a person does by hand.

    Python's round() gives round(8.25, 1) == 8.2 (binary floats and half-to-even), which
    would make a manual recalculation disagree with the system. Rounding to 9 places
    first removes float noise such as 8.2499999999 before the half-up step.
    """
    return float(Decimal(repr(round(x, 9))).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def round0(x):
    """Round to a whole number, half up (displayed minutes and distances)."""
    return int(Decimal(repr(round(x, 9))).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def weighted_share_at_most(values, weights, threshold):
    """Percentage (0-100) of total weight whose value is <= threshold."""
    total = sum(weights)
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    inside = sum(w for v, w in zip(values, weights) if v <= threshold)
    return 100.0 * inside / total


def weighted_quantile(values, weights, q):
    """Weighted quantile, inverted-CDF definition (no interpolation).

    Sort values ascending and return the first value at which the cumulative weight
    reaches q x total weight. With weights 100/100 on values 5/15, the median is 5.
    """
    if not 0 < q <= 1:
        raise ValueError("q must be in (0, 1]")
    pairs = sorted(zip(values, weights))
    total = sum(w for _, w in pairs)
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    target = Fraction(str(q)) * total   # exact: 0.9 must not become 0.90000000000000002
    cumulative = 0
    for value, weight in pairs:
        cumulative += weight
        if cumulative >= target:
            return value
    return pairs[-1][0]


def percentile_ranks(values, higher_is_better=True):
    """Percentile rank on 0-10 for each key of `values` (a dict of key -> number).

    Rank 1 is the worst value, rank n the best; tied values share the average of the
    ranks they span. Score = (rank - 1) / (n - 1) x 10, so the worst area scores 0 and
    the best 10. A single area scores 10. Ties are exact equality of the input values.
    """
    n = len(values)
    if n == 0:
        return {}
    if n == 1:
        return {k: 10.0 for k in values}
    sign = 1 if higher_is_better else -1
    ordered = sorted(values, key=lambda k: sign * values[k])
    ranks, i = {}, 0
    while i < n:
        j = i
        while j + 1 < n and values[ordered[j + 1]] == values[ordered[i]]:
            j += 1
        avg_rank = (i + 1 + j + 1) / 2     # 1-based ranks i+1 .. j+1
        for k in ordered[i:j + 1]:
            ranks[k] = avg_rank
        i = j + 1
    return {k: (r - 1) / (n - 1) * 10 for k, r in ranks.items()}


def tenths(x):
    """x in tenths after half-up rounding to 1 d.p., as an int, for exact comparisons.

    round1(8.3) - round1(8.1) is 0.20000000000000107 in floating point; tenths makes
    "differ by 0.2 or less" an integer comparison instead.
    """
    return int(Decimal(repr(round1(x))) * 10)   # repr(2.3) is "2.3", so this is exact


def weighted_mean(values, weights):
    """Sum of value x weight divided by the sum of weights."""
    total = sum(weights)
    if total <= 0:
        raise ValueError("weights must sum to a positive number")
    return sum(v * w for v, w in zip(values, weights)) / total
