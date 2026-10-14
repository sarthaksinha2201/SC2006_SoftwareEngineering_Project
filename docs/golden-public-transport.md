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


## Bus and Either modes (FR 1.2.4)

The mode only decides which walking time each block contributes:

- **rail:** the walk to the nearest MRT/LRT exit;
- **bus:** the walk to the nearest Qualifying Bus Stop (one served by 3 or more
  services);
- **either:** the shorter of the two.

The scoring above then runs unchanged, ranked separately for each mode.
`test_golden_modes` checks the following by hand. Every block has 100 flats.

| Area | Block 1 (rail, bus) | Block 2 (rail, bus) |
|---|---|---|
| P | 12, 3 | 14, 5 |
| Q | 4, 11 | 6, 13 |
| R | 9, 9.5 | 20, 12 |

The walking time each mode uses per block, and the area values that follow (with 2
equal-weight blocks, the median is the lower walk):

| Mode | P | Q | R |
|---|---|---|---|
| rail | 12, 14 → 0%, median 12 | 4, 6 → 100%, median 4 | 9, 20 → 50%, median 9 |
| bus | 3, 5 → 100%, median 3 | 11, 13 → 0%, median 11 | 9.5, 12 → 50%, median 9.5 |
| either | 3, 5 → 100%, median 3 | 4, 6 → 100%, median 4 | 9, 12 → 50%, median 9 |

Percentile ranks across the three areas, then score = 0.7 × PR(%) + 0.3 × PR(median):

| Mode | P | Q | R |
|---|---|---|---|
| rail | 0.7 × 0 + 0.3 × 0 = **0.0** | 0.7 × 10 + 0.3 × 10 = **10.0** | 0.7 × 5 + 0.3 × 5 = **5.0** |
| bus | 0.7 × 10 + 0.3 × 10 = **10.0** | **0.0** | **5.0** |
| either | 0.7 × 7.5 + 0.3 × 10 = **8.25 → 8.3** | 0.7 × 7.5 + 0.3 × 5 = **6.75 → 6.8** | **0.0** |

Under Either, P and Q tie on 100%: they share ranks 2 and 3, so each gets
(2.5 − 1) / 2 × 10 = 7.5. The top area is Q for rail, and P for bus and for either.
`test_a_bus_user_gets_a_different_answer` holds the code to that.

### A property of the real data (14 Oct 2026 snapshot)

Qualifying bus stops are dense in HDB estates, so the 10-minute measure saturates for
bus:

| Mode | Areas with 100% of flats within 10 min | Lowest % | Median walk range |
|---|---|---|---|
| rail | 6 of 32 | 0% | 0.4–61.1 min |
| bus | 30 of 32 | 97.4% | 0.5–2.7 min |
| either | 31 of 32 | 99.9% | 0.4–2.7 min |

For Bus and Either, the percentile rank of "% within 10 min" therefore ranks
differences of a few tenths of a percent. That term still carries 70% of the score, so
small real differences become large score gaps. Even a 5-minute threshold leaves every
area at 87% or more. This follows the Data Dictionary as written, and has been raised
for a decision rather than changed in code.
