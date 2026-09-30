"""The Strategy interface every scoring factor implements (DECISIONS.md section 4).

A factor is one class. It owns its snapshot tables, computes them offline in the ETL,
and answers score requests at runtime from the snapshot. Adding a factor means writing
one subclass and listing it in gowhere.scoring.registry; neither the ETL build nor the
ScoringEngine changes (Supportability NFR).
"""
from abc import ABC, abstractmethod
from collections import defaultdict

from gowhere.scoring.stats import percentile_ranks


class ScoringStrategy(ABC):
    key = ""     # identifier in code, JSON and CSS, e.g. "public_transport"
    label = ""   # name shown to users, e.g. "Public Transport"

    # ---- ETL time (offline, builds the snapshot) --------------------------------

    @abstractmethod
    def schema(self):
        """SQL CREATE statements for this factor's snapshot tables."""

    @abstractmethod
    def precompute(self, blocks, sources):
        """{table name: [row dict]} computed from placed HDB blocks and raw sources.

        blocks: dicts with id, lat, lon, planning_area, total_dwelling_units.
        sources: gowhere.etl.raw.RawSources (or a test double with the same methods).
        Any row carrying a "score" key must have it on 0-10; the build validates this.
        """

    def meta(self, sources):
        """Extra snapshot metadata, e.g. the date a source dataset was last updated."""
        return {}

    # ---- request time (web app, reads the snapshot only) ------------------------

    def options(self, snapshot):
        """{option name: [allowed values]} the user must choose, e.g. a facility type."""
        return {}

    @abstractmethod
    def category_scores(self, snapshot, areas, options):
        """{area: 0-10 score, or None when this factor has no data for the area}."""

    def raw_values(self, snapshot, areas, options):
        """{area: {label: value}} the figures behind the score, for display."""
        return {}

    def notes(self, snapshot, areas, options):
        """{area: [note text]} caveats specific to this factor."""
        return {}


def group_by_area(blocks, value_of):
    """{area: ([values], [flats])} for flat-weighted statistics."""
    grouped = defaultdict(lambda: ([], []))
    for b in blocks:
        values, flats = grouped[b["planning_area"]]
        values.append(value_of(b))
        flats.append(b["total_dwelling_units"])
    return dict(grouped)


def add_percentile_scores(rows, metric, higher_is_better, key="score"):
    """Set rows[i][key] to the 0-10 percentile rank of rows[i][metric] across all rows."""
    pr = percentile_ranks({i: r[metric] for i, r in enumerate(rows)}, higher_is_better)
    for i, r in enumerate(rows):
        r[key] = pr[i]
    return rows


def select_by_area(snapshot, table, columns, areas, where="", params=()):
    """{area: row} for the given areas from a per-area table."""
    marks = ", ".join("?" for _ in areas)
    sql = (f"SELECT planning_area, {', '.join(columns)} FROM {table} "
           f"WHERE planning_area IN ({marks}){' AND ' + where if where else ''}")
    return {r["planning_area"]: r for r in snapshot.query(sql, (*areas, *params))}
