# Golden test: Amenities, calculated by hand

This is the manual recalculation behind `tests/test_golden_amenities.py`.

## Definition

1. For each HDB block, count each selected amenity type within 800 m (straight line, boundary inclusive).
2. Cap each type's count at 3, then add the capped counts together.
3. For the area, take the flat-weighted median of that sum (the same rule as Public Transport: the first value at which the running total of flats reaches half).
4. Score the median by percentile rank across areas, with the average rank for ties.

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

- **Medians:**
  - A: sorted 2 (100 flats), 4 (100 flats). Half of 200 flats is 100, reached at **2**.
  - B: sorted 0 (100 flats), 3 (300 flats). Half of 400 flats is 200, reached at **3**.
  - C: **3**.
- **Percentile ranks** (n = 3, so PR = (rank − 1) × 5): A is rank 1 → **0**. B and C tie for ranks 2 and 3, so both take rank 2.5 → **7.5**.

The twenty cafes earn C no more than B's mix of supermarkets and a cafe. This is what the cap is for.

## Single types

- **Cafes only:**
  - Capped counts: a1 3, a2 2, b1 1, b2 0, c1 3.
  - Medians: A **2**, B **1** (half of 400 flats reached at 1), C **3**.
  - Scores: B **0**, A **5**, C **10**.
- **Supermarkets only:**
  - Capped counts: a1 1, a2 0, b1 2, b2 0, c1 0.
  - Medians: A **0**, B **2**, C **0**.
  - A and C tie for ranks 1 and 2 → rank 1.5 → **2.5**. B → **10**.
