# ETL — raw data to `data/snapshot.db`

The web app reads only `data/snapshot.db` and never calls an external API. Everything in this document runs offline, ahead of time.

## Run order

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt

python -m gowhere.etl._temp_fetch_raw   # TEMPORARY until S1 (gowhere.etl.fetch_raw) lands
python -m gowhere.etl.geocode           # ~3.3 h without a OneMap token, ~1 h with one; resumable
python -m gowhere.etl.geocode --reference   # polyclinic postal codes from data/reference/
python -m gowhere.etl.build_snapshot    # offline; replaces the snapshot only if validation passes
python -m gowhere.etl.calibrate         # needs ONEMAP_TOKEN; writes docs/detour-calibration.md
pytest                                  # no network access needed
```

Put `ONEMAP_TOKEN=...` in `.env` at the repo root (gitignored). Search works without it but is limited to about 1 request/s; routing does not work without it.

## Where things live

| Path | What | In git |
|---|---|---|
| `data/raw/<name>.json`, `_manifest.json` | Unmodified API responses (S1 contract) | no |
| `data/cache/onemap_search.sqlite` | Every OneMap search response, keyed by query | no |
| `data/cache/onemap_route.sqlite` | OneMap walking routes used for calibration | no |
| `data/logs/geocode_failures.csv` | Every block that did not geocode, with the candidates OneMap returned | no |
| `data/logs/unplaced_blocks.csv` | Every residential block left out of the snapshot, with the reason | no |
| `data/reference/polyclinics.csv` | Hand-compiled polyclinic list, one source per row | **yes** |
| `data/reference/hospitals.csv` | Every MOH-licensed hospital classified by type and 24-hour care, one source per row | **yes** |
| `data/snapshot.db` | The only file the web app reads | no |

Raw dataset names (S1 must use these): `hdb_property_information`, `lta_mrt_station_exits`, `ura_mp2019_planning_areas`. A paginated `datastore_search` dataset is stored as a JSON list of the page responses, unmodified.

## Coverage (snapshot of 30 Sep 2026)

- HDB Property Information has 13,357 blocks. **10,796 are residential** (`residential = 'Y'`) and are the only ones used. They hold 1,175,956 dwelling units.
- **All 10,796 geocoded (100%)** after two matching fixes applied offline. The first pass resolved 99.71%; the 31 failures were 26 blocks on St George's Road/Lane (HDB's "ST." means Saint, not Street) and 5 long slab blocks that OneMap indexes as two points sharing one postal code.
- All 10,796 fall inside a planning area. **32 of the 55 planning areas are in scope.**
- 613 MRT/LRT exits at 190 stations (41 LRT). Tengah's Jurong Region Line stations are not open yet and are not in the dataset, so Tengah's nearest exit is Chinese Garden.

## Hand-maintained reference data

`data/reference/` holds the project's only hand-compiled data. It exists because no government dataset gives polyclinic locations or says which hospitals offer 24-hour emergency care. Every row cites its source and retrieval date, and tests check that every row has one.

- **Polyclinics (28):**
  - Membership and cluster come from each cluster's own list: SingHealth and NUP from their websites, NHG from the Singapore Government Directory.
  - Addresses come from maps.gov.sg (updated 7 Dec 2025), plus the cluster sites for Tengah and Serangoon, which opened after that.
  - Locations come from OneMap, geocoded by postal code. All 26 that maps.gov.sg also places are within 45 m of its location.
- **Hospitals (31, every hospital in MOH's OneMap theme):**
  - Category comes from CPF's list of medical institutions (21 Jul 2026).
  - 24-hour care type comes from MOH's emergency department statistics or each hospital's own site.
  - `config.HOSPITAL_CATEGORIES` and `config.HOSPITAL_CARE_24H` choose which hospitals count.
  - A newly licensed hospital missing from the file stops the build until it is classified.

## Geocoding rules

- Query `"<blk_no> <street>"` as HDB writes it. If there is no match, retry once with abbreviations expanded (`BT` → `BUKIT`, `C'WEALTH` → `COMMONWEALTH`, …).
- A result is accepted only if its block number **and** full road name match. If matches for the same block are more than 50 m apart, keep the ones whose postal code ends in the block number (HDB convention). If that doesn't settle it, the block is logged as `ambiguous`, not guessed.
- `ST.` with a full stop expands to SAINT. Matches more than 50 m apart that share a single postal code are one long block, placed at the midpoint of its points.
- A query already in the cache is never re-sent. HTTP/network errors are not cached, so they are retried on the next run.

## Snapshot contract (`data/snapshot.db`, schema_version 3)

Core tables are defined in `CORE_SCHEMA` in `gowhere/etl/build_snapshot.py`. Each factor's tables are defined by its strategy's `schema()` in `gowhere/scoring/`.

- `meta`: `generated_at`, `schema_version`, `factors` (keys of the factors built), model constants, `detour_factor` with `detour_factor_calibrated_on`, `rail_data_as_of` (when LTA's exits data last changed), geocode coverage, the raw manifest.
- `planning_area`: all 55 areas with boundary GeoJSON.
  - `in_scope = 1` when the area contains at least one placed HDB residential block. No area is excluded for being small.
  - `n_blocks` and `n_flats`: the counts the UI shows.
  - `small_sample = 1` when an in-scope area has fewer than `meta.small_area_blocks` blocks (currently 10).
- `hdb_block`: one row per placed block: location, planning area, dwelling units.
- Public Transport (`PublicTransportScorer`):
  - `mrt_exit`: every MRT **and LRT** exit, one set: "nearest exit" means the nearest MRT or LRT exit.
  - `public_transport_block`: nearest exit, straight-line distance and modelled walk time per block.
  - `public_transport_area`: % of flats within 10 min, median and P90 walk, the median distance to an exit, `far_from_rail` (median distance above `meta.far_from_rail_m`), both percentile ranks, and the 0–10 score.

- Housing Affordability (`HousingAffordabilityScorer`):
  - `housing_transaction`: every HDB resale in the window, placed in its area through its block. Not aggregated, because the user's budget is only known at request time.
  - The window is `meta.housing_window_start`–`end`: the 12 complete months before the resale data was fetched. It is fixed in the snapshot, so answers never depend on today's date.
  - The download is checked month by month against the API's own totals.
  - Options: `flat_type`, `budget_min`, `budget_max`, `min_remaining_lease_years` (None/60/70/80).
  - Score = % of matching sales within budget ÷ 10 (absolute). Fewer than 10 matching sales means no data. Worked example: [golden-housing.md](golden-housing.md).
- Greenery (`GreeneryScorer`):
  - `greenery_block`: distance to the nearest park, nature reserve or park connector, measured to its boundary.
  - `greenery_area`: % of flats within `meta.green_space_radius_m` (400 m), median distance, 0–10 score.
- Healthcare (`HealthcareScorer`), with the facility type chosen by the user as option `facility_type`:
  - `healthcare_facility`: every facility counted, by type.
  - `healthcare_block`: distance from each block to its nearest facility of each type (`gp`, `polyclinic`, `hospital`).
  - `healthcare_area`: flat-weighted median distance and 0–10 score per area and type.
  - `meta` records each source's date: `gp_data_as_of` (when the CHAS records last changed) and the reference files' compilation date.

**Web app access:** read the snapshot only through `gowhere.snapshot.Snapshot` (read-only) and `gowhere.scoring.engine.ScoringEngine`. `engine.compare(areas, {factor_key: FactorChoice(weight, options)})` returns a JSON-ready dict: ranked areas with overall and category scores, `_display` values rounded half-up, raw figures, `notes`, dropped factors, `close_call`, and the marginal-contribution explanation. All user-facing note wording is in `gowhere/scoring/notes.py`.

## Adding a factor

Write a `ScoringStrategy` subclass (`gowhere/scoring/base.py`) that implements `schema`, `precompute` and `category_scores`, plus optionally `meta`, `options`, `raw_values` and `notes`. Then add it to `default_strategies()` in `gowhere/scoring/registry.py`. The build and the engine need no changes.

Scoring definitions and worked examples: [golden-public-transport.md](golden-public-transport.md), [golden-housing.md](golden-housing.md). Hospital definition: [hospital-rule.md](hospital-rule.md).
