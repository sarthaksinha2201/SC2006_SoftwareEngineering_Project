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

class RecordedLlm:
    """Stands in for LlmAdapter: answers each batch from {post_id: [events]}, the way the
    model would, numbering events by their post's position in the batch. Records every
    prompt it was sent. `fail_on` post ids make the whole call fail, like an outage."""

    def __init__(self, replies, fail_on=()):
        self.replies, self.fail_on, self.calls = replies, set(fail_on), []

    def call_tool(self, system, user, tool):
        import re
        from gowhere.adapters.llm import LlmError
        self.calls.append({"system": system, "user": user, "tool": tool})
        ids = re.findall(r'<post number="(\d+)" id="([^"]+)"', user)
        if self.fail_on & {pid for _, pid in ids}:
            raise LlmError("simulated outage")
        return {"events": [{"post": int(n), **e} for n, pid in ids
                           for e in self.replies.get(pid, [])]}


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
