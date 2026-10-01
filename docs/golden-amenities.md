# Golden test: Amenities, calculated by hand

This is the manual recalculation behind `tests/test_golden_amenities.py`.

## Definition

1. For each HDB block, count each selected amenity type within 800 m (straight line, boundary inclusive).
2. Cap each type's count at 3, then add the capped counts together.
3. For the area, take the flat-weighted mean of that sum: Σ(sum × flats) ÷ Σ(flats).
4. Score the mean by percentile rank across areas, with the average rank for ties.

**Why a mean, not a median** (changed 30 Sep 2026, on measurement):
- The median was chosen to stop one block with twenty cafes distorting an area. The per-type cap already removes such outliers, so the median's only advantage was gone.
- Its cost remained: on a supermarket-only selection, 28 of 32 areas tied at the median value 3, and on library-only, 25 tied at 0.
- With the mean, the largest ties are 6 areas on each of those selections.

## Input

Blocks are about 5.5 km apart, so an amenity placed at a block counts only for that block.

| Area | Block (flats) | Supermarkets | Cafes |
|---|---|---|---|
| A | a1 (100) | 1 | 5 |
| A | a2 (100) | 0 | 2 |
| B | b1 (300) | 2 | 1 |
| B | b2 (100) | 0 | 0 |
| C | c1 (100) | 0 | **20** |

## Supermarkets + cafes

| Block | Capped sum |
|---|---|
| a1 | 1 + min(5, 3) = 4 |
| a2 | 0 + 2 = 2 |
| b1 | 2 + 1 = 3 |
| b2 | 0 |
| c1 | 0 + min(20, 3) = **3** |

- **Means:**
  - A = (4 × 100 + 2 × 100) ÷ 200 = **3**.
  - B = (3 × 300 + 0 × 100) ÷ 400 = **2.25**.
  - C = **3**.
- **Percentile ranks** (n = 3, so PR = (rank − 1) × 5): B is rank 1 → **0**. A and C tie for ranks 2 and 3, so both take rank 2.5 → **7.5**.

The twenty cafes earn C exactly what A gets from a supermarket and a handful of cafes. This is what the cap is for.

## Single types

- **Cafes only:**
  - Capped counts: a1 3, a2 2, b1 1, b2 0, c1 3.
  - Means: A (300 + 200) ÷ 200 = **2.5**; B (1 × 300) ÷ 400 = **0.75**; C **3**.
  - Scores: B **0**, A **5**, C **10**.
- **Supermarkets only:**
  - Capped counts: a1 1, a2 0, b1 2, b2 0, c1 0.
  - Means: A **0.5**, B (2 × 300) ÷ 400 = **1.5**, C **0**.
  - Scores: C **0**, A **5**, B **10**.
