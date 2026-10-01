# Golden test: Housing Affordability, calculated by hand

This is the manual recalculation behind `tests/test_golden_housing.py`. The system must agree with it to 1 decimal place (Accuracy NFR).

## Definition

For the chosen flat type, and at least the chosen remaining lease if one is set, take the area's resale transactions from the snapshot's 12-month window. Then:

**score = (transactions priced within budget ÷ matching transactions × 100) ÷ 10**

- Both budget bounds are inclusive.
- A lease of exactly the minimum counts.
- Fewer than 10 matching transactions means no data, and the factor is dropped for all selected areas.
- Prices are used exactly as transacted, with no adjustment for market movement.

This is an absolute scale, not a percentile rank.

## Request

4-room, budget $400,000–$600,000, at least 70 years of lease left.

## WEST

| Sale | Counts as matching? | Within budget? |
|---|---|---|
| 10 × 4-room at 400,000 / 600,000 / 450,000 / 480,000 / 500,000 / 520,000 / 540,000 / 560,000 / 580,000 / 590,000 | yes | yes (both bounds count) |
| 6 × 4-room at 399,999 / 600,001 / 700,000 ×4 | yes | no |
| 3-room at 450,000 | no: flat type | |
| 4-room at 450,000 with 69 years 11 months left | no: lease | |

Matching 16, within budget 10. Share = 10 ÷ 16 = 62.5%. **Score = 6.25, displayed 6.3** (half up; Python's `round` would give 6.2).

Without the lease filter, the short-lease sale also counts: 11 ÷ 17 × 10 = 6.47.

## EAST

10 × 4-room with exactly 70 years left (counts): 7 at 500,000 and 3 at 650,000. Matching 10, the minimum needed. Within budget 7. **Score = 7.0.**

## Shown to the user

"62.5% of 4-room resales with at least 70 years of lease left in the last 12 months (10 of 16) were within your budget"
