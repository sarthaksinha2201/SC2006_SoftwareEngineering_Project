# Where to Eat: measurements before building (19 Oct 2026)

DECISIONS.md §25 fixed the scope, but left three numbers to measure before the design
was settled: hygiene-grade spread, OSM cuisine coverage and OSM opening-hours coverage.
This file records those numbers, plus two availability checks (Michelin terms, hawker
stall counts), and how they bear on each signal.

## OpenStreetMap food venues

The query covered `amenity` = restaurant, cafe, fast_food, food_court, ice_cream and
marketplace, through Overpass (OSM data as of 2026-10-19 13:10 UTC). Venues outside every
planning area were dropped, because the bounding box includes part of Johor.

| Type | Venues | `cuisine` | `opening_hours` | `diet:halal` | `diet:vegetarian`/`vegan` |
|---|---|---|---|---|---|
| restaurant | 4,748 | 48.9% | 21.1% | 3.9% | 4.2% |
| cafe | 1,873 | 52.7% | 25.5% | 0.9% | 0.9% |
| fast_food | 1,410 | 75.7% | 21.1% | 7.2% | 3.0% |
| food_court | 799 | 6.9% | 14.3% | 4.1% | 3.6% |
| ice_cream | 123 | 17.9% | 29.3% | 1.6% | 2.4% |
| marketplace | 72 | 0.0% | 6.9% | 0.0% | 0.0% |
| **All** | **9,025** | **49.4%** | **21.4%** | **3.7%** | **3.2%** |

95.7% of the venues have a name.

### Cuisine

There are 218 distinct `cuisine` values. The most common is `coffee_shop` (653). In
Singapore that tag mostly marks kopitiams, not cafés. A reasonable mapping into §25's
eight groups gives:

| Venues | Count | Share |
|---|---|---|
| Fall into one of the eight groups | 3,203 | 35.5% of all, 71.9% of the tagged |
| Tagged only as local fare (`coffee_shop`, `local`, `singaporean`, `noodle`, `asian`, `regional`) | 872 | 9.7% |
| Tagged, but with no group (`chicken`, `snacks`, `salad`, ...) | 379 | 4.2% |
| **No `cuisine` tag at all** | **4,571** | **50.6%** |

Per group: Western 951, Chinese 702, Japanese & Korean 617, Cafés & Desserts 403,
Indian 275, Thai & Vietnamese 205, Malay & Indonesian 135, Seafood 133.

**Consequence:** the untagged bucket (50.6%) is larger than all eight groups combined, so
the "cuisine not listed" label matters more than the categories. Seafood is the smallest
group (1.5% of venues). The local-fare tags have no group at all, although local food is
a main reason to use the feature.

### Opening hours

1,930 venues (21.4%) have `opening_hours`, in 1,146 distinct strings. A simple grammar
handles 90.3% of them: day ranges, time ranges, `24/7` and `off`. That is 19.3% of all
venues. The rest are mostly comma-separated split shifts, which a fuller parser can read,
plus a few free-text values such as `"varies by stall"`.

**Consequence:** "Open now" can be judged for about one venue in five. Four in five will
say "hours unknown".

### Dietary tags

`diet:halal` covers 3.7% of venues, and vegetarian/vegan tags cover 3.2%. A halal filter
built on OSM would hide about 96% of venues. It would show "halal" only where an OSM
contributor happened to tag it, which no one should rely on for a religious requirement.
The authoritative source is the MUIS certification register, and it is not in our data.

## Hygiene grades

The only bulk source is data.gov.sg's *List of NEA Licensed Eating Establishments*
(`d_227473e811b09731e64725f140b77697`). Its coverage runs from **11 Jun 2015 to 6 Sep
2016**. It was last re-published 6 Jun 2024, and it has 36,687 records.

| Grade | Count | Share of all | Share of graded |
|---|---|---|---|
| A | 16,477 | 44.9% | 52.5% |
| B | 14,686 | 40.0% | 46.8% |
| C | 222 | 0.6% | 0.7% |
| D | 0 | 0% | 0% |
| `na` (not graded: eating houses, food courts and canteens; only their stalls are graded) | 5,302 | 14.5% | — |

The grading scheme itself has since changed. Food licensing moved from NEA to SFA in
2019. On 19 Jan 2026, SFA replaced the A–D annual grade with the **SAFE framework**,
which grades A, B, C, or "New" for outlets under a year old. **There is no D any more.**
The current SAFE grades are published only through SFA's per-establishment search page
(*Track Records*). That page has no dataset, no API and no stated terms for bulk use.

**Consequence:** in the 2015–16 data, a "hide C and D" floor would hide 0.7% of
establishments. A against B was a real 52/47 split, so the "nearly everything is A or
B, so grading can't discriminate" premise holds for the floor but not for A against B.
More decisively, no current bulk grades exist. Grades from 2016 attached to 2026 venues
would be wrong for most of them, so neither a floor nor a sort can be built honestly.

## Michelin Guide

The terms of use for guide.michelin.com forbid using "any robot, spider, other automatic
device or manual process to monitor or copy web pages or content". Michelin's site terms
also forbid "repeated and systematic extraction or reuse of even a small part" of its
databases without prior authorisation. A curated reference file built from the guide is a
manual process of copying its selection. The site serves automated requests an empty
HTTP 202, so the terms were read through a search engine's copy, not fetched directly.

**Consequence:** no Michelin badge without written permission from Michelin.

## Hawker centres (food destinations)

The NEA hawker centre dataset already in `data/raw` (fetched 30 Sep 2026) has 129
centres:

- 123 are operating, 6 are under construction.
- The `NUMBER_OF_COOKED_FOOD_STALLS` field is filled for 125 of them (median 45, maximum
  226).
- 111 have a photo URL.

The 799 OSM food courts include mall food courts, which come with no stall count.

**Consequence:** hawker centres as one entry with their stall count, as §25 specifies,
are fully supported by data we already hold.
