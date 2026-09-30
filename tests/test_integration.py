"""ETL build -> snapshot file -> read-only Snapshot -> ScoringEngine, end to end."""
from gowhere.etl.build_snapshot import compute, write_snapshot
from gowhere.scoring.engine import FactorChoice, ScoringEngine
from gowhere.scoring.public_transport import PublicTransportScorer
from gowhere.snapshot import Snapshot
from tests.fakes import FakeSources
from tests.test_geo_spatial import AREAS


def build_fixture_snapshot(tmp_path, strategies, sources):
    # 12 WEST blocks near an exit; 1 EAST block about 2.2 km from it (far from rail)
    blocks = [{"blk_no": str(i), "street": "W", "total_dwelling_units": 100} for i in range(12)]
    blocks.append({"blk_no": "1", "street": "E", "total_dwelling_units": 55})
    geocodes = ([{"blk_no": str(i), "street": "W", "status": "ok", "lat": 1.35, "lon": 103.79,
                  "detail": ""} for i in range(12)]
                + [{"blk_no": "1", "street": "E", "status": "ok", "lat": 1.35, "lon": 103.82,
                    "detail": ""}])
    out = compute(blocks, geocodes, AREAS, sources, strategies)
    meta = {"generated_at": "2026-09-30T00:00:00+00:00"}
    for s in strategies:
        meta.update(s.meta(sources))
    path = tmp_path / "snapshot.db"
    write_snapshot(path, out, AREAS, strategies, meta)
    return Snapshot(path)


def test_public_transport_end_to_end_with_notes(tmp_path):
    sources = FakeSources(exits=[{"station": "S MRT STATION", "exit_code": "A",
                                  "lat": 1.3505, "lon": 103.79}], exits_as_of="2026-07-17")
    strategies = [PublicTransportScorer()]
    snap = build_fixture_snapshot(tmp_path, strategies, sources)
    r = ScoringEngine(strategies, snap).compare(
        ["WEST", "EAST"], {"public_transport": FactorChoice(5)})

    by = {x["name"]: x for x in r["areas"]}
    assert (by["WEST"]["rank"], by["EAST"]["rank"]) == (1, 2)
    assert (by["WEST"]["overall"], by["EAST"]["overall"]) == (10.0, 0.0)
    assert by["WEST"]["raw"]["public_transport"]["% of flats within 10 min walk"] == 100.0
    assert by["EAST"]["notes"] == [
        "East — 55 flats across 1 block. Scores are based on a small number of blocks.",
        "Public Transport scores are based on MRT/LRT stations in LTA's station-exit data "
        "as of 17 Jul 2026."]
    assert by["WEST"]["notes"] == []
    assert r["snapshot"]["rail_data_as_of"] == "2026-07-17"
    assert "raw_manifest" not in r["snapshot"]


def test_snapshot_is_read_only(tmp_path):
    import sqlite3

    import pytest
    snap = build_fixture_snapshot(tmp_path, [PublicTransportScorer()], FakeSources(
        exits=[{"station": "S", "exit_code": "A", "lat": 1.35, "lon": 103.79}]))
    with pytest.raises(sqlite3.OperationalError):
        snap.db.execute("DELETE FROM meta")
