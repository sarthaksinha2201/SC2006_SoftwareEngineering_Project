# Black-box testing: `ScoringEngine` (Lab 4 §3.2.1, §3.2.3)

Equivalence class (EC) and boundary value (BV) testing of **one control class**, designed
from the Where to Live functional requirements (Lectures 16–17), then run.

- **Class under test:** `ScoringEngine` (`gowhere/scoring/engine.py`), method `compare(areas, choices)`.
- **Why this class:** it is the control class behind UC-4 *Compare Neighbourhoods*. It takes
  every user input of Where to Live, rejects invalid requests, and computes the weighted
  scores, ranks and recommendation. A defect here is a wrong recommendation.
- **Automated test:** `tests/test_black_box_engine.py`. Each test id (`BB-01` …) matches a row below.
- **Run:** `pytest tests/test_black_box_engine.py -v`.
- **Environment:** the real committed snapshot (`data/snapshot.db`, generated 14 Oct 2026) and
  the six real factors. OneMap is an External Service outside the class, so a fake answers
  for it: every postal code resolves, every route takes 30 min (transit) or 20 min (car).
- **Executed:** 2 Nov 2026, commit `fb927c7` plus the test file. **23 pass. 2 fail and
  show defect D1.**

> This replaces `docs/black-box-tests.md` (Lab 2/S4) for Lab 4. That table spans several
> classes, while §3.2.1 asks for one control class. It stays in the repo as the earlier version.

## 1. Input parameters and equivalence classes

Source FRs are in `lab3/lab3_FR_NFR.docx`.

| Parameter | FR | Valid classes | Invalid classes | Boundary values |
|---|---|---|---|---|
| P1 Number of areas | 1.1.2.1, 1.1.2.2 | E1: 2–4 | E2: ≤ 1 · E3: ≥ 5 | 1, **2**, **4**, 5 |
| P2 Area repeated | 1.1.2 | E4: all distinct | E5: one area twice | — |
| P3 Area name | 1.1.1 | E6: an in-scope planning area | E7: a planning area outside the 32 in scope · E8: not a planning area | — |
| P4 Number of included factors | 1.2.2.2 | E9: 1–6 | E10: 0 | 0, **1**, **6** (only 6 factors exist) |
| P5 Factor key | 1.2.1 | E11: one of the six factors | E12: any other key | — |
| P6 Importance weight | 1.2.3.1 | E13: whole number 1–10 | E14: ≤ 0 · E15: ≥ 11 · E16: not a whole number | 0, **1**, **10**, 11 |
| P7 Option set of a factor | 1.2.4–1.2.8 | E17: exactly the factor's options | E18: an option missing | — |
| P8 Discrete option value (PT mode, flat type, lease, facility type, commute mode) | 1.2.4.1, 1.2.5.1, 1.2.5.4, 1.2.7.1, 1.2.8.2 | E19: a listed value | E20: an unlisted value | small classes: every value tested once (Lecture 17) |
| P9 Budget minimum / maximum | 1.2.5.2 | E21: 0–5,000,000 | E22: < 0 · E23: > 5,000,000 | −1, **0**, **5,000,000**, 5,000,001 |
| P10 Budget minimum vs maximum | 1.2.5.3 | E24: minimum ≤ maximum | E25: minimum > maximum | **min = max**, min = max + 1 |
| P11 Amenity types | 1.2.6.1, 1.2.6.2 | E26: 1–6 distinct listed types | E27: none · E28: a type twice · E29: an unlisted type | 0, **1**, **6** |
| P12 Destination postal code | 1.2.8.2 | E30: exactly 6 digits | E31: 5 digits · E32: 7 digits · E33: 6 characters, not all digits | 5, **6**, 7 digits |

**Bold** boundary values are valid.

## 2. Test cases and results

Test-case design follows Lecture 17:
- A **valid** case combines one valid class of every parameter, so 4 cases cover all 12 valid classes.
- An **invalid** case changes exactly **one** input to an invalid class or boundary, and keeps every other input valid.

The five ingredients of a test case (Lecture 16) are mapped as follows:
- **Name:** the ID column.
- **Location:** `tests/test_black_box_engine.py::<test>[ID]`.
- **Input:** the Input column.
- **Oracle:** the Expected column.
- **Log:** the Actual column.

### Valid cases

Oracle: no error; every selected area ranked, rank 1 first, overall 0–10; every included
factor is either scored or reported as dropped (FR 1.3).

| ID | Classes / BVs covered | Input | Actual (log) | Result |
|---|---|---|---|---|
| BB-01 | E1 (BV 2), E4, E6, E9 (BV 1), E11, E13 (BV 1) | BEDOK, TAMPINES; Greenery only, weight 1 | BEDOK #1 3.5 · TAMPINES #2 2.3 | ok Pass |
| BB-02 | E1 (BV 4), E9 (BV 6), E13 (BV 10), E17, E19 (either, 4-room, any lease, polyclinic, transit), E21 (BV 0 and 5,000,000), E24, E26 (BV 6), E30 | BEDOK, TAMPINES, BISHAN, PUNGGOL; all six factors; Public Transport weight 10, mode Either; budget 0–5,000,000; all 6 amenity types; postal 018956 | PUNGGOL #1 6.4 · BEDOK #2 5.7 · BISHAN #3 5.4 · TAMPINES #4 5.3; 6 factors scored | ok Pass |
| BB-03 | E1 (3, nominal), E19 (rail, Executive, 80 years, GP, drive), E24 (BV min = max), E26 (BV 1) | ANG MO KIO, BUKIT BATOK, QUEENSTOWN; 5 factors; budget 800,000–800,000; lease ≥ 80; library only | BUKIT BATOK #1 6.8 · QUEENSTOWN #2 6.3 · ANG MO KIO #3 6.1; Housing Affordability dropped (no matching sales for every area) and reported | ok Pass |
| BB-04 | E19 (bus, 3-room, 60 years, hospital), E13 (2, 9) | JURONG WEST, WOODLANDS; Public Transport (bus, weight 2), Healthcare (hospital, weight 9), Housing (3-room, lease ≥ 60) | WOODLANDS #1 6.9 · JURONG WEST #2 4.4 | ok Pass |

### Invalid cases (one invalid input each)

Unless stated, the input is BB-01's with the one change listed. Oracle: the request is
rejected with exactly the message shown (FR 1.1.2.2: "state the allowed range").

| ID | Class / BV | Changed input | Expected (oracle) | Actual (log) | Result |
|---|---|---|---|---|---|
| BB-05 | E2 (BV 1) | 1 area: BEDOK | select 2 to 4 neighbourhoods | same | ok Pass |
| BB-06 | E3 (BV 5) | 5 areas | select 2 to 4 neighbourhoods | same | ok Pass |
| BB-07 | E5 | BEDOK, BEDOK | each neighbourhood can be selected once | same | ok Pass |
| BB-08 | E7 | BEDOK, BOON LAY | not an in-scope neighbourhood: BOON LAY | same | ok Pass |
| BB-09 | E8 | BEDOK, ATLANTIS | not an in-scope neighbourhood: ATLANTIS | same | ok Pass |
| BB-10 | E10 (BV 0) | no factors | include at least one factor | same | ok Pass |
| BB-11 | E12 | factor `crowdedness` | unknown factor: crowdedness | same | ok Pass |
| BB-12 | E14 (BV 0) | weight 0 | Greenery: weight must be a whole number from 1 to 10 | same | ok Pass |
| BB-13 | E15 (BV 11) | weight 11 | Greenery: weight must be a whole number from 1 to 10 | same | ok Pass |
| BB-14 | E16 | weight 5.5 | Greenery: weight must be a whole number from 1 to 10 | same | ok Pass |
| BB-15 | E18 | Healthcare with no facility type | Healthcare: options must be exactly facility type | same | ok Pass |
| BB-16 | E20 | facility type `clinic` | Healthcare: facility type must be one of ['gp', 'hospital', 'polyclinic'] | same | ok Pass (see O1) |
| BB-17 | E22 (BV −1) | budget minimum −1 | Housing Affordability: budget minimum must be a number from 0 to 5,000,000 | …from 0 to **5e+06** | no **Fail: D1** |
| BB-18 | E23 (BV 5,000,001) | budget maximum 5,000,001 | Housing Affordability: budget maximum must be a number from 0 to 5,000,000 | …from 0 to **5e+06** | no **Fail: D1** |
| BB-19 | E25 (BV max + 1) | budget 700,001–700,000 | budget minimum must not exceed budget maximum | same | ok Pass (see O2) |
| BB-20 | E27 (BV 0) | no amenity types | Amenities: choose one or more of supermarket, hawker_centre, library, mall, gym, cafe, each once | same | ok Pass (see O1) |
| BB-21 | E28 | gym, gym | as BB-20 | same | ok Pass |
| BB-22 | E29 | `cinema` | as BB-20 | same | ok Pass |
| BB-23 | E31 (BV 5) | postal 12345 | Commute: destination postal code must be a 6-digit Singapore postal code | same | ok Pass |
| BB-24 | E32 (BV 7) | postal 1234567 | as BB-23 | same | ok Pass |
| BB-25 | E33 | postal 12345A | as BB-23 | same | ok Pass |

In code the two failing cases are marked `xfail(strict=True)`. The suite stays green while
the defect is open. Once the message is fixed, the two cases pass, `strict` turns that
into a failure, and the marker must be removed. A fix cannot go unrecorded.

## 3. Defects and observations

| ID | Severity | Finding | Reachable by a user? | Fix |
|---|---|---|---|---|
| **D1** | Medium | The budget limit is printed with `:g`, so the message reads "from 0 to 5e+06" (`engine.py` line 147). | **Yes.** The budget fields on the setup page are free number inputs. Typing 6000000 for the maximum shows "budget maximum must be a number from 0 to 5e+06." (checked through the real Flask app, HTTP 400). | Format whole numbers with thousands separators, then remove the `xfail` marker. |
| O1 | Low | Two messages show code keys, not the names users see: `['gp', 'hospital', 'polyclinic']`, `hawker_centre`. The engine's own comment (line 127) says messages must name things as users see them. | No. These values come from radio buttons and checkboxes, so only a forged request reaches them. | Optional: use the factors' display labels. |
| O2 | Low | The min > max message has no "Housing Affordability:" prefix, unlike every other option message. It comes from `HousingAffordabilityScorer.validate_options`, not the engine. | Yes, but the message is still clear. | Optional. |

## 4. Why 25 cases is enough (§3.2.3)

- **All combinations:** testing every class of every parameter together would multiply the
  class counts (3 × 2 × 3 × 2 × … ) into thousands of cases.
- **Lecture 17 rule instead:**
  - Combine valid classes into as few cases as possible: **4 cases cover 12 valid classes**,
    including both ends of every valid range.
  - Give each invalid class or invalid boundary its own case, so a failure points at one
    input: **21 cases, one per invalid class**; each invalid boundary value is one of them.
- **Total: 25 cases covering 33 classes and all 23 boundary values.**
- Small discrete classes (P8) are covered value by value inside the 4 valid cases, at no extra cost.

## 5. Other EC/BV tests already in the suite

`tests/test_engine.py` covers the engine's *output* rules with stub factors:
- a tie at one decimal place gives a joint rank;
- "close call" fires at exactly 0.2 and not above it;
- a factor missing for one area is dropped for all areas;
- when every factor is dropped, the comparison stops with the reasons.

Those rules depend on score values, which the real snapshot cannot be made to produce on demand, so they stay there.
