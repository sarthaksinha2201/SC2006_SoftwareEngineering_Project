# Commute origin: centroid-nearest block vs medoid

Checked 30 Sep 2026. **Decision: keep the current rule**, the HDB block nearest the area's flat-weighted centroid.

## The alternative tested

The **medoid** is the block with the smallest flat-weighted total distance to all the area's blocks. Because it is always a real block inside a cluster, it cannot land in a gap between clusters. It was expected to fix Bukit Timah, whose centroid-nearest block is 1,026 m from the centroid.

## Result across all 32 in-scope areas

| | |
|---|---|
| Origins that stay on the same block | 9 of 32 |
| Median shift | 91 m |
| Largest shift | 369 m (Toa Payoh: Lorong 7 → Lorong 5) |
| Shifts over 200 m | 2 (Toa Payoh, Jurong East) |
| Largest gain in flat-weighted mean distance to the area's flats | 4% (Jurong East, 1,098 → 1,055 m) |

The medoid moves most origins a little and makes none of them materially more representative. On a 30–60 minute commute, a 100–300 m change of starting block is a minute or two.

## Bukit Timah: why neither rule fixes it

Bukit Timah's HDB flats are in two clusters about 4 km apart:

| Cluster | Blocks | Flats |
|---|---|---|
| Toh Yi Drive | 20 | 1,713 (72%) |
| Queen's Road / Empress Road | 5 | 675 (28%) |

- **Current origin:** 7 Toh Yi Drive, 219 m from the Toh Yi cluster's centre and about 4.1 km from Queen's Road.
- **Medoid:** 5 Toh Yi Drive, 108 m away from the current origin.

Any single origin has to sit in one cluster and is 4 km from the other, so no one-block rule can serve both. The "1,026 m from the centroid" figure measured the wrong thing: the centroid lies in empty ground between the clusters, and distance to it says nothing about how well the origin represents residents. Both rules put the origin in the cluster where most of the flats are.

## Limitation, as stated for the report

Bukit Timah's HDB flats form two clusters about 4 km apart. Commute is timed from Toh Yi Drive, where 72% of them are, so the figure describes most of the area's flats but not the Queen's Road and Empress Road blocks.
