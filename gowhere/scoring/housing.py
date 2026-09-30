"""Housing Affordability category score (DECISIONS.md section 2).

The ETL stores every HDB resale transaction from the snapshot's 12-month window,
placed in its planning area through its block. Nothing is aggregated then, because the
user's budget is only known at request time.

At request time, for the chosen flat type (and optional minimum remaining lease):
  score = % of the area's matching transactions priced within [budget min, budget max],
          divided by 10.
This is an absolute scale, not a percentile rank. An area with fewer than 10 matching
transactions has no data, so the engine drops the factor for all selected areas.
Prices are not adjusted for market movement within the window, so every figure can be
recalculated by hand from the transactions.
"""
import calendar

from gowhere import config
from gowhere.scoring.base import InvalidRequest, NumberRange, ScoringStrategy
from gowhere.scoring.stats import round1

FLAT_TYPES = {"3 ROOM": "3-room", "4 ROOM": "4-room", "5 ROOM": "5-room", "EXECUTIVE": "Executive"}
MIN_LEASE_YEARS = [None, 60, 70, 80]
MAX_BUDGET = 5_000_000


class HousingAffordabilityScorer(ScoringStrategy):
    key = "housing_affordability"
    label = "Housing Affordability"
    missing_reason = f"had fewer than {config.HOUSING_MIN_TRANSACTIONS} matching resales"

    def __init__(self, min_transactions=config.HOUSING_MIN_TRANSACTIONS):
        self.min_transactions = min_transactions
        self._matched = self._unmatched = None   # set by precompute, reported by meta

    def schema(self):
        return """
CREATE TABLE housing_transaction (
    id INTEGER PRIMARY KEY,
    block_id INTEGER NOT NULL REFERENCES hdb_block(id),
    planning_area TEXT NOT NULL REFERENCES planning_area(name),
    month TEXT NOT NULL,                  -- 'YYYY-MM', within meta.housing_window_*
    flat_type TEXT NOT NULL,              -- as HDB writes it, e.g. '4 ROOM'
    resale_price INTEGER NOT NULL,        -- SGD, not adjusted for market movement
    remaining_lease_months INTEGER NOT NULL);
CREATE INDEX housing_transaction_area_type ON housing_transaction(planning_area, flat_type);
"""

    def precompute(self, blocks, sources):
        window, transactions = sources.resale()
        block_of = {(b["blk_no"], b["street"]): b for b in blocks}
        rows, unmatched = [], 0
        for t in transactions:
            b = block_of.get((t["blk_no"], t["street"]))
            if b is None:
                unmatched += 1
                continue
            rows.append({"id": len(rows) + 1, "block_id": b["id"],
                         "planning_area": b["planning_area"], "month": t["month"],
                         "flat_type": t["flat_type"], "resale_price": t["resale_price"],
                         "remaining_lease_months": t["remaining_lease_months"]})
        self._matched, self._unmatched = len(rows), unmatched
        return {"housing_transaction": rows}

    def meta(self, sources):
        window, _ = sources.resale()
        return {"housing_window_start": window[0], "housing_window_end": window[1],
                "housing_transactions": str(self._matched),
                "housing_unmatched_transactions": str(self._unmatched),
                "housing_min_transactions": str(self.min_transactions)}

    def options(self, snapshot):
        return {"flat_type": list(FLAT_TYPES),
                "budget_min": NumberRange(0, MAX_BUDGET),
                "budget_max": NumberRange(0, MAX_BUDGET),
                "min_remaining_lease_years": MIN_LEASE_YEARS}

    def validate_options(self, options):
        if options["budget_min"] > options["budget_max"]:
            raise InvalidRequest("budget minimum must not exceed budget maximum")

    def _counts(self, snapshot, areas, options):
        """{area: (matching transactions, of which within budget)}"""
        marks = ", ".join("?" for _ in areas)
        min_lease_months = (options["min_remaining_lease_years"] or 0) * 12
        rows = snapshot.query(
            f"SELECT planning_area, COUNT(*) AS n, "
            f"SUM(resale_price BETWEEN ? AND ?) AS within "
            f"FROM housing_transaction WHERE planning_area IN ({marks}) "
            f"AND flat_type = ? AND remaining_lease_months >= ? GROUP BY planning_area",
            (options["budget_min"], options["budget_max"], *areas,
             options["flat_type"], min_lease_months))
        return {r["planning_area"]: (r["n"], r["within"]) for r in rows}

    def category_scores(self, snapshot, areas, options):
        counts = self._counts(snapshot, areas, options)
        scores = {}
        for a in areas:
            n, within = counts.get(a, (0, 0))
            scores[a] = within * 100 / n / 10 if n >= self.min_transactions else None
        return scores

    def raw_values(self, snapshot, areas, options):
        counts = self._counts(snapshot, areas, options)
        flat = FLAT_TYPES[options["flat_type"]]
        lease = options["min_remaining_lease_years"]
        lease_text = f" with at least {lease} years of lease left" if lease else ""
        out = {}
        for a in areas:
            n, within = counts.get(a, (0, 0))
            if n < self.min_transactions:
                continue
            pct = within * 100 / n
            out[a] = {"summary": f"{round1(pct):g}% of {flat} resales{lease_text} in the last "
                                 f"12 months ({within} of {n}) were within your budget",
                      "% within budget": pct, "matching resales": n, "within budget": within}
        return out

    def factor_notes(self, snapshot, options):
        meta = snapshot.meta()
        return [f"Based on HDB resale transactions registered from {_month(meta['housing_window_start'])} "
                f"to {_month(meta['housing_window_end'])}. Prices are as transacted, not "
                f"adjusted for market movement over that period."]


def _month(yyyy_mm):
    y, m = yyyy_mm.split("-")
    return f"{calendar.month_abbr[int(m)]} {y}"
