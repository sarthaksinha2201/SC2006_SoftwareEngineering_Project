# Walking detour factor — calibration

Generated 2026-09-30 by `python -m gowhere.etl.calibrate --seed 2006`.
Raw per-block results: [detour-calibration-sample.csv](detour-calibration-sample.csv).

## Method

The snapshot estimates walking time as straight-line (Haversine) distance to the nearest MRT/LRT exit × detour factor ÷ 80 m/min. To check the detour factor, 200 HDB residential blocks were drawn by stratified random sample (seed 2006): each planning area received a share of the sample equal to its share of HDB dwelling units, and blocks within an area were drawn at random. The median therefore describes Singapore's flats as a whole, not whichever areas happen to come first in the dataset. The OneMap walking route from each block's geocoded point to its nearest exit was then fetched. For each block, **ratio = OneMap route distance ÷ straight-line distance**. Only distances are compared; the 80 m/min walking speed is a separate assumption (for reference, OneMap's own routes imply a median of 83 m/min).

200 of 200 routes succeeded.

## Result

| Statistic | Ratio |
|---|---|
| Median | **1.39** |
| Mean | 1.52 |
| P10 / P25 | 1.22 / 1.29 |
| P75 / P90 | 1.57 / 1.86 |
| Min / Max | 0.76 / 5.57 |

By straight-line distance:

| Distance | Blocks | Median ratio |
|---|---|---|
| 0–400 m | 74 | 1.39 |
| 400–800 m | 81 | 1.39 |
| 800–1200 m | 28 | 1.37 |
| 1200– m | 17 | 1.36 |

## Effect on the 10-minute measure

| Factor | Same 10-min verdict as the real route | Mean absolute error |
|---|---|---|
| 1.3 (current) | 89.5% | 1.6 min |
| 1.39 (sample median) | 93.0% | 1.4 min |

"Same verdict" means the model and the real route agree on whether the block is within a 10-minute walk, which is the figure the Public Transport score depends on most.

## Spread

The middle half of blocks have ratios between 1.29 and 1.57 (interquartile range 0.27); 80% lie between 1.22 and 1.86. The mean (1.52) is reported for completeness only: long detours such as expressway or canal crossings pull it up, so the median is the calibrated value.

## By planning area

Areas with at least 5 sampled blocks, highest median first:

| Planning area | Blocks | Median ratio |
|---|---|---|
| HOUGANG | 10 | 1.70 |
| PUNGGOL | 11 | 1.55 |
| SENGKANG | 13 | 1.51 |
| CLEMENTI | 5 | 1.46 |
| BUKIT MERAH | 9 | 1.46 |
| TOA PAYOH | 8 | 1.43 |
| CHOA CHU KANG | 9 | 1.43 |
| SEMBAWANG | 6 | 1.40 |
| QUEENSTOWN | 6 | 1.39 |
| PASIR RIS | 5 | 1.37 |
| YISHUN | 12 | 1.36 |
| ANG MO KIO | 9 | 1.35 |
| WOODLANDS | 13 | 1.35 |
| GEYLANG | 6 | 1.34 |
| TAMPINES | 15 | 1.34 |
| BUKIT PANJANG | 6 | 1.34 |
| BUKIT BATOK | 8 | 1.33 |
| KALLANG | 6 | 1.32 |
| JURONG WEST | 13 | 1.32 |
| BEDOK | 11 | 1.31 |

## Limitation: one national factor

The detour ratio varies with geography, not at random. Blocks separated from their nearest station by an expressway, canal or rail line have to walk around it, so they sit in the upper tail. That is a real property of those places. Applying one national factor is therefore a stated modelling limitation: it understates walking time for such blocks and overstates it for blocks with a direct path.

The per-area medians differ noticeably: from 1.31 (BEDOK) to 1.70 (HOUGANG), a gap of 0.39. Per-area samples are small (at least 5 blocks), so individual area medians are indicative only.

**Future work:** a per-area detour factor, calibrated with a larger sample per area. Not built for this project.

## Recommendation

73% of sampled blocks walk further than a factor of 1.3 assumes. The sample median (1.39) gives the same 10-minute verdict as the real route for 93.0% of blocks, against 89.5% for 1.3. **Proposed new factor: 1.39.** Pending team decision; `config.DETOUR_FACTOR` has not been changed.
