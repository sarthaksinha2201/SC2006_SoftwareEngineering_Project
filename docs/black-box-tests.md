# Black-box test table (S4)

Equivalence partitioning and boundary-value analysis, from the *current* FR and the
code that implements it — not the Lab 1 numbers (`SC2006 Lab2 deliverables.pdf`'s
Functional Requirements). Every "Expected result" below is the exact message the code
produces, verified against the source cited in the last column; where an automated
test already exercises the case, it's named so the gap between this table and
`tests/` is visible.

| # | Partition / boundary | Input | Expected result | FR | Source / existing coverage |
|---|---|---|---|---|---|
| 1 | Neighbourhoods — invalid, below minimum | 1 neighbourhood selected | Comparison blocked: *"select 2 to 4 neighbourhoods"* | FR 1.1.2.1, FR 1.1.2.2 | `ScoringEngine._validate` (`gowhere/scoring/engine.py`); covered by `test_invalid_submissions_rerender_setup_with_message[over0-select 2 to 4]` (`tests/test_web.py`) |
| 2 | Neighbourhoods — valid, minimum boundary | 2 neighbourhoods selected | Comparison proceeds | FR 1.1.2.1 | Same; this is the default case used throughout `tests/test_web.py` (`form()` selects WEST, EAST) |
| 3 | Neighbourhoods — valid, maximum boundary | 4 neighbourhoods selected | Comparison proceeds | FR 1.1.2.1 | Same validator; covered by `test_four_neighbourhoods_is_the_valid_maximum` (`tests/test_engine.py`) |
| 4 | Neighbourhoods — invalid, above maximum | 5 neighbourhoods selected | Comparison blocked: *"select 2 to 4 neighbourhoods"* | FR 1.1.2.1, FR 1.1.2.2 | Same validator; covered by `test_boundary_rejections_name_things_as_users_see_them` (`tests/test_web.py`) |
| 5 | Importance weight — invalid, below minimum | weight = 0 | Rejected: *"{Factor label}: weight must be a whole number from 1 to 10"*, e.g. *"Greenery: weight must be a whole number from 1 to 10"* | FR 1.2.3.1 | `ScoringEngine._validate` (`MIN_WEIGHT, MAX_WEIGHT = 1, 10`); covered by `test_boundary_rejections_name_things_as_users_see_them` (`tests/test_web.py`) |
| 6 | Importance weight — valid, minimum boundary | weight = 1 | Accepted; weight applied | FR 1.2.3.1 | Same validator; covered by `test_weight_boundaries_accepted` (`tests/test_web.py`) |
| 7 | Importance weight — valid, maximum boundary | weight = 10 | Accepted; weight applied | FR 1.2.3.1 | Same validator; covered by `test_weight_boundaries_accepted` (`tests/test_web.py`) |
| 8 | Importance weight — invalid, above maximum | weight = 11 | Rejected: *"{Factor label}: weight must be a whole number from 1 to 10"* | FR 1.2.3.1 | Covered by `test_invalid_submissions_rerender_setup_with_message[over2-weight must be]` (`tests/test_web.py`) |
| 9 | Event categories — invalid, below minimum | 0 categories selected | Search blocked: *"Choose 1 to 4 categories."* | FR 2.1.2 | `gowhere/lepak/search.py` `validate()` (`MIN_SELECTED, MAX_SELECTED = 1, 4`); covered by `test_invalid_searches_rerender_with_message[over0-Choose 1 to 4 categories]` (`tests/test_web_lepak.py`) |
| 10 | Event categories — valid, minimum boundary | 1 category selected | Search proceeds | FR 2.1.2 | Same validator; covered by `test_one_category_is_enough` (`tests/test_web_lepak.py`) |
| 11 | Event categories — valid, maximum boundary | 4 categories selected | Search proceeds | FR 2.1.2 | Same validator; this is the default case used throughout `tests/test_web_lepak.py` (`form()` selects 4 categories) |
| 12 | Event categories — invalid, above maximum | 5 categories selected | Search blocked: *"Choose 1 to 4 categories."* | FR 2.1.2 | Same validator (`CATEGORIES` has 8 defined values, so 5 distinct valid category names is a legitimate input); covered by `test_invalid_searches_rerender_with_message` (`tests/test_web_lepak.py`) |
| 13 | Destination postal code — invalid, 5 digits | `"12345"` | Rejected: *"Commute: destination postal code must be a 6-digit Singapore postal code"* | FR 1.2.8.1 | `TextPattern(r"\d{6}", ...)` via `ScoringEngine._validate` (`gowhere/scoring/commute.py`); covered by `test_boundary_rejections_name_things_as_users_see_them` (`tests/test_web.py`), and the Where to Lepak starting-point field at the same boundary by `test_invalid_searches_rerender_with_message` (`tests/test_web_lepak.py`) |
| 14 | Destination postal code — valid, 6 digits | `"123456"` | Accepted as correctly formatted (passes the pattern check; OneMap separately determines whether it resolves to a real location) | FR 1.2.8.1 | Same validator; `POSTAL = "048583"` is used as a valid 6-digit code throughout `tests/test_web.py` |
| 15 | Destination postal code — invalid, 7 digits | `"1234567"` | Rejected: *"Commute: destination postal code must be a 6-digit Singapore postal code"* | FR 1.2.8.1 | Same validator; covered by `test_boundary_rejections_name_things_as_users_see_them` (`tests/test_web.py`) and, for the Lepak field, `test_invalid_searches_rerender_with_message` (`tests/test_web_lepak.py`) |
| 16 | Housing budget range — invalid, minimum above maximum | budget_min = 700000, budget_max = 400000 | Rejected: *"budget minimum must not exceed budget maximum"* | FR 1.2.5.3 | `HousingAffordabilityScorer.validate_options` (`gowhere/scoring/housing.py`); covered by `test_invalid_submissions_rerender_setup_with_message[over3-budget minimum must not exceed]` (`tests/test_web.py`) |
| 17 | Housing budget range — valid, minimum at or below maximum | budget_min = 400000, budget_max = 700000 | Accepted | FR 1.2.5.3 | Same validator; the default case used throughout `tests/test_web.py`'s `form()` |

**Reading the table**: rows 1–4, 5–8, 9–12 and 13–15 are each a boundary-value set
(invalid-low, valid-low, valid-high, invalid-high) around the FR's stated range; rows
16–17 are an equivalence pair (invalid vs. valid) for the one relational constraint
Sarthak.md calls out specifically. Error strings are copied verbatim from the raising
code, not reworded, so a test asserting on them won't drift from what the UI actually
shows.
