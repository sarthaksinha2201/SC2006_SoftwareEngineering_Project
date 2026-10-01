# Golden test — Public Transport score, calculated by hand

This is the manual recalculation behind `tests/test_golden_public_transport.py`. The system must agree with it to 1 decimal place (Accuracy NFR).

## Definitions

- **% within 10 min** = flats in blocks with walk ≤ 10.0 min ÷ all flats in the area × 100. Exactly 10.0 min counts as within.
- **Weighted median / P90**: sort blocks by walk time and add up flats as you go. The median is the walk time of the first block where the running total reaches 50% of the area's flats; P90 is the same at 90%. No interpolation.
- **Percentile rank (PR)** on 0–10: rank areas from worst (rank 1) to best (rank n). Tied values share the average of the ranks they span. PR = (rank − 1) ÷ (n − 1) × 10. A higher % within 10 min is better; a lower median walk is better.
- **Score** = 0.7 × PR(% within 10) + 0.3 × PR(median walk).
- **Display** rounds to 1 d.p., halves rounded up (8.25 → 8.3).

## Input

| Area | Blocks (walk min, flats) | Total flats |
|---|---|---|
| A | (4, 100), (8, 100), (12, 200) | 400 |
| B | (3, 300), (15, 100) | 400 |
| C | (9, 50), (11, 50), (20, 100) | 200 |
| D | (6, 200), (10, 200) | 400 |
| E | (5, 100), (25, 100) | 200 |

## Step 1 — per-area figures

| Area | Within 10 min | % | Median (target, reached at) | P90 (target, reached at) |
|---|---|---|---|---|
| A | 4, 8 → 200 | 50 | 200 → 8 (running 100, **200**) | 360 → 12 (**400**) |
| B | 3 → 300 | 75 | 200 → 3 (**300**) | 360 → 15 (**400**) |
| C | 9 → 50 | 25 | 100 → 11 (50, **100**) | 180 → 20 (**200**) |
| D | 6, 10 → 400 | 100 | 200 → 6 (**200**) | 360 → 10 (**400**) |
| E | 5 → 100 | 50 | 100 → 5 (**100**) | 180 → 25 (**200**) |

## Step 2 — percentile ranks (n = 5, so PR = (rank − 1) × 2.5)

**% within 10**, worst to best: C 25 (rank 1), A 50 and E 50 (ranks 2 and 3 → both 2.5), B 75 (4), D 100 (5).
PR: C 0, A 3.75, E 3.75, B 7.5, D 10.

**Median walk**, worst (longest) to best: C 11 (1), A 8 (2), D 6 (3), E 5 (4), B 3 (5).
PR: C 0, A 2.5, D 5, E 7.5, B 10.

## Step 3 — scores

| Area | 0.7 × PR(%) | 0.3 × PR(median) | Score | Displayed |
|---|---|---|---|---|
| A | 0.7 × 3.75 = 2.625 | 0.3 × 2.5 = 0.75 | 3.375 | 3.4 |
| B | 0.7 × 7.5 = 5.25 | 0.3 × 10 = 3.0 | 8.25 | 8.3 |
| C | 0 | 0 | 0 | 0.0 |
| D | 0.7 × 10 = 7.0 | 0.3 × 5 = 1.5 | 8.5 | 8.5 |
| E | 0.7 × 3.75 = 2.625 | 0.3 × 7.5 = 2.25 | 4.875 | 4.9 |

B's 8.25 is deliberate: Python's built-in `round(8.25, 1)` returns 8.2, which would disagree with this hand calculation. The system uses `gowhere.scoring.stats.round1` (half-up) for display.
