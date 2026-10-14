"""Read-only access to data/snapshot.db: the only data source the web app uses."""
import sqlite3
import threading

from gowhere import config


class Snapshot:
    """One per app, shared by every Waitress thread. Each thread gets its own read-only
    connection: a single shared connection failed with "bad parameter or other API
    misuse" when the setup form's checks arrived together (14 Oct browser rehearsal)."""

    def __init__(self, path=config.SNAPSHOT_PATH):
        if not path.exists():
            raise FileNotFoundError(f"no snapshot at {path}; run python -m gowhere.etl.build_snapshot")
        self.path = path
        self._local = threading.local()

    @property
    def db(self):
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def query(self, sql, params=()):
        return [dict(r) for r in self.db.execute(sql, params)]

    def meta(self):
        return {r["key"]: r["value"] for r in self.query("SELECT key, value FROM meta")}

    def areas(self, names=None):
        """{name: {region, in_scope, n_blocks, n_flats, small_sample}} (all areas by default)."""
        rows = self.query("SELECT name, region, in_scope, n_blocks, n_flats, small_sample "
                          "FROM planning_area ORDER BY name")
        return {r.pop("name"): r for r in rows if names is None or r["name"] in names}

    def postal_location(self, postal):
        """(lat, lon) of the HDB block with this postal code, or None. The offline
        fallback for looking up a user's postal code when OneMap is unreachable."""
        row = self.db.execute("SELECT lat, lon FROM hdb_block WHERE postal = ?",
                              (postal,)).fetchone()
        return (row["lat"], row["lon"]) if row else None
