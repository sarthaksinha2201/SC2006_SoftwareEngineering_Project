"""Test doubles shared across tests."""


class FakeSources:
    """Stands in for gowhere.etl.raw.RawSources with fixed in-memory datasets."""

    def __init__(self, exits=(), parks=(), connectors=(), facilities=None,
                 exits_as_of="2025-12-02", facilities_as_of=None):
        self._exits, self._parks, self._connectors = list(exits), list(parks), list(connectors)
        self._facilities = facilities or {}
        self._exits_as_of = exits_as_of
        self._facilities_as_of = facilities_as_of or {k: "2024-06-06" for k in self._facilities}

    def mrt_exits(self):
        return self._exits

    def mrt_exits_as_of(self):
        return self._exits_as_of

    def parks(self):
        return self._parks

    def park_connectors(self):
        return self._connectors

    def facilities(self):
        return self._facilities

    def facilities_as_of(self):
        return self._facilities_as_of


class FakeResaleSources(FakeSources):
    def __init__(self, window, transactions, **kw):
        super().__init__(**kw)
        self._resale = (window, transactions)

    def resale(self):
        return self._resale


class FakeAmenitySources(FakeSources):
    def __init__(self, amenities, **kw):
        super().__init__(**kw)
        self._amenities = amenities

    def amenities(self):
        return self._amenities

    def amenities_as_of(self):
        return {"supermarket": "2024-06-06", "osm": "2026-09-30"}

    def amenities_meta(self):
        return {"supermarket_licences": 0, "supermarkets_unlocated": 0}


# ---- Where to Lepak ------------------------------------------------------------------

# The LLM stand-in lives in the package so the ingest command can replay it too.
from gowhere.adapters.llm import ReplayLlm as RecordedLlm  # noqa: E402,F401


class RecordedSearch:
    """Stands in for OneMapAdapter.search from {query: response}; unknown queries return
    no results. Counts calls."""

    def __init__(self, responses, fail=False):
        self.responses, self.fail, self.queries = responses, fail, []

    def search(self, query, page=1, redact=False):
        from gowhere.adapters.http import HttpError
        self.queries.append(query)
        if self.fail:
            raise HttpError("simulated outage")
        return self.responses.get(query, {"found": 0, "results": []})
