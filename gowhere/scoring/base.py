"""The Strategy interface every scoring factor implements (DECISIONS.md section 4).

A factor is one class. It owns its snapshot tables, computes them offline in the ETL,
and answers score requests at runtime from the snapshot. Adding a factor means writing
one subclass and listing it in gowhere.scoring.registry; neither the ETL build nor the
ScoringEngine changes (Supportability NFR).
"""
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass

from gowhere.scoring.stats import percentile_ranks


class InvalidRequest(ValueError):
    """A comparison request the engine or a factor cannot accept; shown to the user."""


@dataclass(frozen=True)
class NumberRange:
    """An option taking any number in [minimum, maximum], e.g. a budget."""
    minimum: float
    maximum: float

    def __contains__(self, value):
        return (isinstance(value, (int, float)) and not isinstance(value, bool)
                and self.minimum <= value <= self.maximum)


@dataclass(frozen=True)
class TextPattern:
    """An option taking any text matching a regular expression, e.g. a postal code."""
    pattern: str
    description: str

    def __contains__(self, value):
        import re
        return isinstance(value, str) and re.fullmatch(self.pattern, value) is not None


@dataclass(frozen=True)
class SubsetOf:
    """An option taking a non-empty list of distinct values from `choices`."""
    choices: tuple

    def __contains__(self, value):
        return (isinstance(value, list) and len(value) > 0 and len(set(value)) == len(value)
                and all(v in self.choices for v in value))


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
        """{option name: allowed values} the user must supply: a list of choices, a
        NumberRange, a TextPattern or a SubsetOf. Every option must be present in a request (use None in a list for
        "no preference")."""
        return {}

    def validate_options(self, options):
        """Checks across options, e.g. budget minimum <= maximum. Raise InvalidRequest."""

    @abstractmethod
    def category_scores(self, snapshot, areas, options):
        """{area: 0-10 score, or None when this factor has no data for the area}."""

    def raw_values(self, snapshot, areas, options):
        """{area: {label: value}} the figures behind the score, for display."""
        return {}

    def notes(self, snapshot, areas, options):
        """{area: [note text]} caveats about this factor for particular areas."""
        return {}

    def factor_notes(self, snapshot, options):
        """[note text] caveats about this factor as a whole, e.g. what a figure covers."""
        return []


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
