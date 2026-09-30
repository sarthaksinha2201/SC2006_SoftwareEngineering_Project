"""LocationService: the shared Resolve Location path (DECISIONS.md section 4, Facade).

Two kinds of input, handled very differently:

* A user's postal code (Where to Lepak's starting point). Personal data under the
  Security NFR: looked up with redact=True, held in this object's memory only, never
  written to the search cache or a log. Create one service per user session for this.
* An event venue (a public place named in a public post). Its OneMap responses are
  public data and go through the on-disk search cache, so re-running ingestion does not
  repeat searches.

A venue is first looked up in the hand-kept alias list (data/reference/venue_aliases.csv:
names OneMap does not know, each mapped to a postal code with its source). Otherwise it
is tried as several queries in turn (candidate_queries) and accepted only on a
word-for-word match (match_place); anything else is left unresolved so the event is
discarded and logged, rather than placed somewhere wrong.
"""
import re
import time

from gowhere.adapters.http import HttpError
from gowhere.adapters.onemap import REQUEST_TIME, OneMapAdapter
from gowhere.etl.addresses import match_place, match_postal, normalise_place

POSTAL = re.compile(r"\b(\d{6})\b")
_NOISE = re.compile(
    r"#\s?[B\d]\d*-\d+\w*"                                        # unit numbers: #02-160
    r"|\b(level|lvl|l|b|basement)\s?\d+\b"                        # floors: Level 2, L2, B1
    r"|\b(halls?|rooms?|studios?)\s+[A-Z0-9](\s*(,|&|and)\s*[A-Z0-9])*\b"  # Halls D, E & F
    r"|\([^)]*\)",
    re.IGNORECASE)
MIN_TRIMMED_WORDS = 2
# After OneMap fails to answer a postal lookup, fail the same lookup at once for this
# long instead of waiting on the network again: reloading a page or moving a weight
# slider while offline then costs nothing, and the lookup recovers on its own.
FAILURE_MEMORY_S = 60


def _clean(text):
    return " ".join(_NOISE.sub(" ", text).replace(" ,", ",").split()).strip(" ,-")


def candidate_queries(venue, address):
    """Search queries for a venue, most specific first, without repeats.

    Venue name; each comma-separated part of the address and venue; then the venue with
    trailing words dropped one at a time, down to two words ("Marina Bay Sands Convention
    Centre" -> "Marina Bay Sands"). Unit numbers, floors and halls are removed first.
    """
    queries = []
    add = lambda q: q and q.upper() not in {x.upper() for x in queries} and queries.append(q)
    venue, address = _clean(venue or ""), _clean(address or "")
    add(venue)
    for part in address.split(",") + venue.split(","):
        add(part.strip(" -"))
    words = venue.split(",")[0].split()
    for n in range(len(words) - 1, MIN_TRIMMED_WORDS - 1, -1):
        if words[n - 1].lower() not in {"&", "and", "at", "of", "the", "-"}:
            add(" ".join(words[:n]))
    return [q for q in queries if len(q) >= 3]


class LocationService:
    def __init__(self, adapter=None, cache=None, aliases=None, clock=time.monotonic):
        self.adapter = adapter or OneMapAdapter()
        self.cache = cache                   # SearchCache for public venue queries, or None
        self.aliases = {normalise_place(k): v for k, v in (aliases or {}).items()}
        self._postal = {}                    # this session's postal lookups, memory only
        self._postal_failed = {}             # postal -> when OneMap last failed, memory only
        self._clock = clock

    @classmethod
    def for_session(cls):
        """One user's service in the web app: request-time OneMap settings."""
        return cls(OneMapAdapter(**REQUEST_TIME))

    # -- a user's own postal code: memory only ----------------------------------------
    def postal(self, postal):
        """(lat, lon) of a postal code, or None if OneMap has no such code.
        Raises HttpError if OneMap cannot be reached."""
        if postal not in self._postal:
            failed = self._postal_failed.get(postal)
            if failed is not None and self._clock() - failed < FAILURE_MEMORY_S:
                raise HttpError("OneMap was unreachable moments ago")
            try:
                response = self.adapter.search(postal, redact=True)
            except HttpError:
                self._postal_failed[postal] = self._clock()
                raise
            match = match_postal(postal, response.get("results", []))
            self._postal[postal] = (match["lat"], match["lon"]) if match else None
        return self._postal[postal]

    # -- a public venue: cached on disk ------------------------------------------------
    def _search(self, query):
        response = self.cache.get(query) if self.cache else None
        if response is None:
            response = self.adapter.search(query)
            if self.cache:
                self.cache.put(query, response)
        return response.get("results", [])

    def place(self, venue, address):
        """{lat, lon, name, query} for an event venue, or None if it cannot be placed.
        Raises HttpError if OneMap cannot be reached, so the caller can retry later
        instead of discarding the event."""
        queries = candidate_queries(venue, address)
        for query in queries:
            postal = self.aliases.get(normalise_place(query))
            if postal:
                match = match_postal(postal, self._search(postal))
                if match:
                    return {**match, "name": query, "query": f"alias {postal}"}
        text = f"{venue or ''} {address or ''}"
        for postal in POSTAL.findall(text):
            match = match_postal(postal, self._search(postal))
            if match:
                return {**match, "name": postal, "query": postal}
        for query in queries:
            match = match_place(query, self._search(query))
            if match:
                return {**match, "query": query}
        return None
