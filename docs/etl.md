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

## Geocoding rules

- Query `"<blk_no> <street>"` as HDB writes it. If there is no match, retry once with abbreviations expanded (`BT` → `BUKIT`, `C'WEALTH` → `COMMONWEALTH`, …).
- A result is accepted only if its block number **and** full road name match. If matches for the same block are more than 50 m apart, keep the ones whose postal code ends in the block number (HDB convention). If that doesn't settle it, the block is logged as `ambiguous`, not guessed.
- A query already in the cache is never re-sent. HTTP/network errors are not cached, so they are retried on the next run.

## Snapshot contract (`data/snapshot.db`)

Schema: `SCHEMA` in `gowhere/etl/build_snapshot.py`.

- `meta`: `generated_at`, `schema_version`, model constants, geocode coverage, the raw manifest
- `planning_area`: all 55 areas; `in_scope = 1` when it contains at least one placed HDB residential block; boundary GeoJSON
- `hdb_block`: one row per placed block: planning area, nearest exit, straight-line distance, modelled walk time
- `mrt_exit`: every MRT/LRT exit point
- `transport_area`: per in-scope area: % of flats within 10 min, median and P90 walk, both percentile ranks, 0–10 score

Scoring definitions and a worked example: [golden-transport.md](golden-transport.md).
