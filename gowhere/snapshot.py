"""Read-only access to data/snapshot.db: the only data source the web app uses."""
import sqlite3

from gowhere import config


class Snapshot:
    def __init__(self, path=config.SNAPSHOT_PATH):
        if not path.exists():
            raise FileNotFoundError(f"no snapshot at {path}; run python -m gowhere.etl.build_snapshot")
        self.db = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        self.db.row_factory = sqlite3.Row

    def query(self, sql, params=()):
        return [dict(r) for r in self.db.execute(sql, params)]

    def meta(self):
        return {r["key"]: r["value"] for r in self.query("SELECT key, value FROM meta")}

    def areas(self, names=None):
        """{name: {region, in_scope, n_blocks, n_flats, small_sample}} (all areas by default)."""
        rows = self.query("SELECT name, region, in_scope, n_blocks, n_flats, small_sample "
                          "FROM planning_area ORDER BY name")
        return {r.pop("name"): r for r in rows if names is None or r["name"] in names}
