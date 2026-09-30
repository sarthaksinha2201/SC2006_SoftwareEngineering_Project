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
