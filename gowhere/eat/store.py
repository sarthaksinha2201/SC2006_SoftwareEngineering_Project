"""Read-only access to data/eat.db. The whole list (about 8,600 places) is read once into
memory when the app starts and shared by every request thread. It is never written at
request time, so no connection is shared between threads."""
import json
import sqlite3


class PlaceStore:
    def __init__(self, places, meta):
        self.places = places
        self.meta = meta
        self._by_id = {p["id"]: p for p in places}

    @classmethod
    def load(cls, path):
        if not path.exists():
            raise FileNotFoundError(f"no place list at {path}; run python -m gowhere.eat.build")
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        try:
            places = [{**dict(r), "cuisines": json.loads(r["cuisines"]),
                       "destination": bool(r["destination"])}
                      for r in db.execute("SELECT * FROM place ORDER BY id")]
            meta = {r["key"]: r["value"] for r in db.execute("SELECT key, value FROM meta")}
        finally:
            db.close()
        return cls(places, meta)

    def get(self, place_id):
        return self._by_id.get(place_id)
