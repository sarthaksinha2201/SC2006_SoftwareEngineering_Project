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


## Bus and Either modes (FR 1.2.4; DECISIONS §18)

The two modes are measured differently, because they differ in kind:

- **rail** (above): 0.7 × PR(% of flats within a 10-minute walk of an exit) + 0.3 × PR(median walk).
- **bus**: 0.7 × PR(median number of **distinct bus services** stopping within 400 m of a
  block, higher better) + 0.3 × PR(median walk to the nearest Qualifying Bus Stop, lower
  better). A Qualifying Bus Stop is served by 3 or more services. The 400 m count uses
  every stop, so a 2-service stop still adds its services. A service is counted once
  however many nearby stops it calls at.
- **either**: the **higher** of the rail and bus scores, area by area. A tie counts as
  rail.

The higher of two percentile ranks is not itself a percentile rank. Either scores
therefore sit above either mode alone. This is expected, not a bug.

`test_golden_bus_scores_services_not_distance` and
`test_golden_either_takes_the_higher_mode_score` check the following by hand. Every block
has 100 flats; with two equal-weight blocks, the weighted median is the lower value.

| Area | Block 1 (rail walk, bus walk, services) | Block 2 | Median services | Median bus walk |
|---|---|---|---|---|
| P | 12, 3, 20 | 14, 5, 30 | 20 | 3 |
| Q | 4, 2, 8 | 6, 4, 10 | 8 | 2 |
| R | 9, 9.5, 15 | 20, 12, 40 | 15 | 9.5 |

**Rail**, as in the first section: P 0%, median 12; Q 100%, median 4; R 50%, median 9.
Scores: P **0.0**, Q **10.0**, R **5.0**.

**Bus.** Services, ranked from worst to best: Q 8, R 15, P 20, giving PRs 0, 5 and 10.
Bus walk, worst to best: R 9.5, P 3, Q 2, giving PRs 0, 5 and 10.

| Area | 0.7 × PR(services) + 0.3 × PR(walk) | Bus score |
|---|---|---|
| P | 0.7 × 10 + 0.3 × 5 | **8.5** |
| Q | 0.7 × 0 + 0.3 × 10 | **3.0** |
| R | 0.7 × 5 + 0.3 × 0 | **3.5** |

Q has the *nearest* bus stops, yet scores lowest on bus because few services stop there.
That is the point of the measure.

**Either:**

| Area | max(rail, bus) | Takes |
|---|---|---|
| P | max(0.0, 8.5) = **8.5** | bus |
| Q | max(10.0, 3.0) = **10.0** | rail |
| R | max(5.0, 3.5) = **5.0** | rail |

The top area is Q for rail and P for bus, so a bus user gets a different answer
(`test_a_bus_user_gets_a_different_answer`).

## Result: walking distance cannot rank bus access (14 Oct 2026)

We first built Bus as the Data Dictionary specified, with the same measure as rail
(% within 10 minutes, median walk) and the walk taken to a Qualifying Bus Stop. On the
real data it could not tell areas apart:

| Mode, distance measure | Areas with 100% of flats within 10 min | Lowest % | Median walk range |
|---|---|---|---|
| rail | 6 of 32 | 0% | 0.4–61.1 min |
| bus | 30 of 32 | 97.4% | 0.5–2.7 min |
| either (nearer of the two) | 31 of 32 | 99.9% | 0.4–2.7 min |

Even a 5-minute threshold left every area at 87% or more, so a stricter threshold only
moves the saturation point. The 70% term would have ranked differences of a few tenths
of a percent.

This is a real fact about Singapore, not a defect in the code. Rail is scarce, so how far
you walk to it is the whole question. A bus stop is within about three minutes of
almost every HDB flat, so distance cannot discriminate. What does vary is how many places
the nearby buses go. We therefore changed the measure for Bus only, keeping the same
0.7/0.3 shape. The services data was already in hand: 26,833 DataMall route rows.

On the same snapshot, the new measure spreads the areas out:

| Measure | Range across 32 areas | Distinct values |
|---|---|---|
| median distinct services within 400 m | 9 (Tanglin) to 59 (Downtown Core) | 14 |
| Bus score | 0.9 (Woodlands) to 9.9 (Downtown Core) | — |

Queenstown shows the difference. Its rail score is 6.4, but its Bus score is 1.3,
because only a median of 12 services stop within 400 m of a flat.
