# ETL — raw data to `data/snapshot.db`

The web app reads only `data/snapshot.db` and never calls an external API. Everything in this document runs offline, ahead of time.

## Run order

```bash
python3.13 -m venv .venv && .venv/bin/pip install -r requirements.txt

python -m gowhere.etl._temp_fetch_raw   # TEMPORARY until S1 (gowhere.etl.fetch_raw) lands
python -m gowhere.etl.geocode           # ~3.3 h without a OneMap token, ~1 h with one; resumable
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
| `data/snapshot.db` | The only file the web app reads | no |

Raw dataset names (S1 must use these): `hdb_property_information`, `lta_mrt_station_exits`, `ura_mp2019_planning_areas`. A paginated `datastore_search` dataset is stored as a JSON list of the page responses, unmodified.

## Coverage (snapshot of 30 Sep 2026)

- HDB Property Information has 13,357 blocks. **10,796 are residential** (`residential = 'Y'`) and are the only ones used. They hold 1,175,956 dwelling units.
- **All 10,796 geocoded (100%)** after two matching fixes applied offline. The first pass resolved 99.71%; the 31 failures were 26 blocks on St George's Road/Lane (HDB's "ST." means Saint, not Street) and 5 long slab blocks that OneMap indexes as two points sharing one postal code.
- All 10,796 fall inside a planning area. **32 of the 55 planning areas are in scope.**
- 613 MRT/LRT exits at 190 stations (41 LRT). Tengah's Jurong Region Line stations are not open yet and are not in the dataset, so Tengah's nearest exit is Chinese Garden.

## Geocoding rules

- Query `"<blk_no> <street>"` as HDB writes it. If there is no match, retry once with abbreviations expanded (`BT` → `BUKIT`, `C'WEALTH` → `COMMONWEALTH`, …).
- A result is accepted only if its block number **and** full road name match. If matches for the same block are more than 50 m apart, keep the ones whose postal code ends in the block number (HDB convention). If that doesn't settle it, the block is logged as `ambiguous`, not guessed.
- `ST.` with a full stop expands to SAINT. Matches more than 50 m apart that share a single postal code are one long block, placed at the midpoint of its points.
- A query already in the cache is never re-sent. HTTP/network errors are not cached, so they are retried on the next run.

## Snapshot contract (`data/snapshot.db`)

Schema: `SCHEMA` in `gowhere/etl/build_snapshot.py`.

- `meta`: `generated_at`, `schema_version`, model constants, geocode coverage, the raw manifest
- `planning_area`: all 55 areas, with boundary GeoJSON and these columns:
  - `in_scope = 1` when the area contains at least one placed HDB residential block. No area is excluded for being small.
  - `n_blocks` and `n_flats`: the counts the UI shows.
  - `small_sample = 1` when an in-scope area has fewer than `meta.small_area_blocks` blocks (currently 10), so the UI can note that its scores rest on few blocks. The view reads this flag; the threshold lives only in `gowhere/config.py`.
- `hdb_block`: one row per placed block: planning area, nearest exit, straight-line distance, modelled walk time
- `mrt_exit`: every MRT **and LRT** exit point (LTA dataset: 613 exits, 190 stations, 41 of them LRT). The two are one set: "nearest exit" means the nearest MRT or LRT exit, matching the MRT/LRT wording in DECISIONS.md
- `public_transport_area`: per in-scope area: % of flats within 10 min, median and P90 walk, both percentile ranks, 0–10 score

Scoring definitions and a worked example: [golden-public-transport.md](golden-public-transport.md).
