"""The event store: a read-write SQLite file, separate from the read-only snapshot.

Holds only extracted fields plus source links (DECISIONS.md section 3): never the post
text and never who posted it. Times are naive Singapore time, "YYYY-MM-DD HH:MM", so
they sort as text. ends_at is the moment an event stops being worth showing: its end,
or the end of its start day when it has none.

Duplicates (the same event posted by two channels, or twice by one) merge into one row
that keeps every source link: same start date, similar title, venues within
EVENT_MERGE_RADIUS_M.
"""
import json
import re
import sqlite3

from gowhere import config
from gowhere.etl.geo import haversine_m
from gowhere.lepak import sgt_now

SCHEMA = """
CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    category TEXT NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT,                          -- NULL when the post gave no end
    ends_at TEXT NOT NULL,                -- end_at, or the end of the start day
    all_day INTEGER NOT NULL,             -- 1 when the post gave a date but no time
    venue TEXT, address TEXT,
    place_name TEXT NOT NULL,             -- what OneMap matched
    lat REAL NOT NULL, lon REAL NOT NULL,
    summary TEXT NOT NULL,
    added_at TEXT NOT NULL,               -- for the "recently added" sort
    updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS event_ends ON event(ends_at);
CREATE TABLE IF NOT EXISTS event_source (
    event_id INTEGER NOT NULL REFERENCES event(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    PRIMARY KEY (event_id, source_url));
CREATE TABLE IF NOT EXISTS channel_state (
    channel TEXT PRIMARY KEY,
    last_post_id INTEGER NOT NULL,        -- every post up to this one has been handled
    updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ingest_run (
    id INTEGER PRIMARY KEY,
    started_at TEXT NOT NULL, finished_at TEXT NOT NULL,
    counts_json TEXT NOT NULL);           -- yield-rate counts, discards by reason
"""

_STOPWORDS = {"a", "an", "the", "at", "of", "in", "on", "and", "to", "for", "with", "by",
              "free", "entry", "sg", "singapore"}


def title_tokens(title):
    words = re.findall(r"[a-z0-9]+", title.lower())
    return {w for w in words if w not in _STOPWORDS and not re.fullmatch(r"20\d\d", w)}


def similar_titles(a, b):
    """Token overlap of at least half, or one title's words all inside the other's."""
    ta, tb = title_tokens(a), title_tokens(b)
    if not ta or not tb:
        return False
    return len(ta & tb) / len(ta | tb) >= 0.5 or ta <= tb or tb <= ta


def _fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


class EventStore:
    def __init__(self, path=config.EVENTS_PATH):
        if str(path) != ":memory:":
            path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        if str(path) != ":memory:":
            self.db.execute("PRAGMA journal_mode = WAL")   # the web app reads while ingest writes
        self.db.executescript(SCHEMA)

    # -- ingestion ----------------------------------------------------------------
    def last_post_id(self, channel):
        row = self.db.execute("SELECT last_post_id FROM channel_state WHERE channel = ?",
                              (channel,)).fetchone()
        return row[0] if row else None

    def commit_batch(self, events, channel, last_post_id, now):
        """Store (or merge) the batch's events and advance the channel's marker, as one
        transaction: a crash leaves both or neither. Returns (added, merged)."""
        added = merged = 0
        with self.db:
            for e in events:
                if self._merge(e, now):
                    merged += 1
                else:
                    self._insert(e, now)
                    added += 1
            self.db.execute(
                "INSERT INTO channel_state VALUES (?, ?, ?) ON CONFLICT(channel) DO UPDATE "
                "SET last_post_id = max(last_post_id, excluded.last_post_id), "
                "updated_at = excluded.updated_at", (channel, last_post_id, _fmt(now)))
        return added, merged

    def _insert(self, e, now):
        cur = self.db.execute(
            "INSERT INTO event (title, category, start_at, end_at, ends_at, all_day, venue, "
            "address, place_name, lat, lon, summary, added_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (e["title"], e["category"], e["start_at"], e["end_at"], e["ends_at"],
             int(e["all_day"]), e["venue"], e["address"], e["place_name"], e["lat"], e["lon"],
             e["summary"], _fmt(now), _fmt(now)))
        self.db.execute("INSERT INTO event_source VALUES (?, ?)", (cur.lastrowid, e["source_url"]))

    def find_duplicate(self, e):
        """Id of a stored event this one duplicates, or None."""
        for row in self.db.execute(
                "SELECT id, title, lat, lon FROM event WHERE substr(start_at, 1, 10) = ?",
                (e["start_at"][:10],)):
            if (haversine_m(row["lat"], row["lon"], e["lat"], e["lon"]) <= config.EVENT_MERGE_RADIUS_M
                    and similar_titles(row["title"], e["title"])):
                return row["id"]
        return None

    def _merge(self, e, now):
        """Fold `e` into a duplicate if there is one: keep the stored fields, fill in
        what the stored row lacks, keep the later end, add the source link."""
        dup = self.find_duplicate(e)
        if dup is None:
            return False
        self.db.execute(
            "UPDATE event SET end_at = coalesce(end_at, ?), address = coalesce(address, ?), "
            "summary = CASE WHEN summary = '' THEN ? ELSE summary END, "
            "ends_at = max(ends_at, ?), updated_at = ? WHERE id = ?",
            (e["end_at"], e["address"], e["summary"], e["ends_at"], _fmt(now), dup))
        self.db.execute("INSERT OR IGNORE INTO event_source VALUES (?, ?)", (dup, e["source_url"]))
        return True

    def purge_ended(self, now):
        """Delete events that have ended. Returns how many."""
        with self.db:
            return self.db.execute("DELETE FROM event WHERE ends_at < ?", (_fmt(now),)).rowcount

    def record_run(self, started_at, finished_at, counts):
        with self.db:
            self.db.execute("INSERT INTO ingest_run (started_at, finished_at, counts_json) "
                            "VALUES (?, ?, ?)", (_fmt(started_at), _fmt(finished_at),
                                                 json.dumps(counts, sort_keys=True)))

    # -- reading ------------------------------------------------------------------
    def events(self, now=None):
        """Every stored event that has not ended, with its source links."""
        now = now or sgt_now()
        rows = [dict(r) for r in self.db.execute(
            "SELECT * FROM event WHERE ends_at >= ? ORDER BY start_at, id", (_fmt(now),))]
        links = {}
        for r in self.db.execute("SELECT event_id, source_url FROM event_source ORDER BY source_url"):
            links.setdefault(r["event_id"], []).append(r["source_url"])
        for r in rows:
            r["all_day"] = bool(r["all_day"])
            r["sources"] = links.get(r["id"], [])
        return rows

    def event(self, event_id):
        row = self.db.execute("SELECT * FROM event WHERE id = ?", (event_id,)).fetchone()
        if row is None:
            return None
        r = dict(row)
        r["all_day"] = bool(r["all_day"])
        r["sources"] = [s[0] for s in self.db.execute(
            "SELECT source_url FROM event_source WHERE event_id = ? ORDER BY source_url", (event_id,))]
        return r
