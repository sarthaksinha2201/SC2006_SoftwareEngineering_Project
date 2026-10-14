"""Public Transport with bus data: the three modes end to end, from build to web form."""
import pytest

from gowhere.etl.build_snapshot import compute, write_snapshot
from gowhere.scoring.engine import FactorChoice, InvalidRequest, ScoringEngine
from gowhere.scoring.public_transport import PublicTransportScorer
from gowhere.snapshot import Snapshot
from gowhere.web import create_app
from tests.fakes import FakeSources
from tests.test_geo_spatial import AREAS

EXIT = {"station": "W MRT STATION", "exit_code": "A", "lat": 1.3505, "lon": 103.75}


class BusSources(FakeSources):
    """WEST is beside a station; EAST has no station near but a busy bus stop."""

    def __init__(self, with_bus=True):
        super().__init__(exits=[EXIT])
        self.with_bus = with_bus

    def bus_stops(self):
        return [{"code": "84009", "name": "East Int", "lat": 1.3501, "lon": 103.8501,
                 "services": 12}] if self.with_bus else []

    def bus_meta(self):
        return {"bus_stops_total": "3", "bus_stops_outside_singapore": "0",
                "bus_stops_qualifying": "1", "qualifying_bus_services": "3",
                "bus_data_as_of": "2026-10-14"} if self.with_bus else {}


def snapshot(tmp_path, with_bus=True, full=False):
    blocks = [{"blk_no": "1", "street": "W", "total_dwelling_units": 100},
              {"blk_no": "1", "street": "E", "total_dwelling_units": 100}]
    geocodes = [{"blk_no": "1", "street": "W", "status": "ok", "lat": 1.35, "lon": 103.75, "detail": ""},
                {"blk_no": "1", "street": "E", "status": "ok", "lat": 1.35, "lon": 103.85, "detail": ""}]
    if full:                     # every factor, as the web app needs
        from gowhere.scoring.registry import default_strategies
        from gowhere.web.mock import FixedRouter
        from tests.test_web import AllSources

        class AllWithBus(AllSources):
            bus_stops, bus_meta = BusSources.bus_stops, BusSources.bus_meta
            with_bus = True
        sources, strategies = AllWithBus(), default_strategies(FixedRouter({}))
    else:
        sources, strategies = BusSources(with_bus), [PublicTransportScorer()]
    out = compute(blocks, geocodes, AREAS, sources, strategies)
    meta = {"generated_at": "2026-10-14T09:00:00+00:00", "small_area_blocks": "10"}
    for st in strategies:
        meta.update(st.meta(sources))
    path = tmp_path / ("bus.db" if with_bus else "rail.db")
    write_snapshot(path, out, AREAS, strategies, meta)
    return path


def test_modes_change_the_ranking(tmp_path):
    engine = ScoringEngine([PublicTransportScorer()], Snapshot(snapshot(tmp_path)))
    assert engine.strategies["public_transport"].options(engine.snapshot) == {
        "mode": ["rail", "bus", "either"]}
    first = lambda mode: engine.compare(["WEST", "EAST"], {
        "public_transport": FactorChoice(5, {"mode": mode})})["areas"][0]["name"]
    assert first("rail") == "WEST" and first("bus") == "EAST"
    # Either takes each block's nearer option: EAST's bus stop (~15 m) beats WEST's exit (~55 m).
    assert first("either") == "EAST"
    either = engine.compare(["WEST", "EAST"], {"public_transport": FactorChoice(5, {"mode": "either"})})
    assert "a bus stop with 3 or more services" in either["areas"][0]["raw"]["public_transport"]["summary"]
    assert "3 bus services" in " ".join(either["factors"][0]["notes"])


def test_bad_mode_is_rejected_in_words_users_understand(tmp_path):
    engine = ScoringEngine([PublicTransportScorer()], Snapshot(snapshot(tmp_path)))
    with pytest.raises(InvalidRequest, match="Public Transport: public transport mode must be one of"):
        engine.compare(["WEST", "EAST"], {"public_transport": FactorChoice(5, {"mode": "ferry"})})


def test_without_bus_data_the_factor_is_rail_only_with_no_option(tmp_path):
    engine = ScoringEngine([PublicTransportScorer()], Snapshot(snapshot(tmp_path, with_bus=False)))
    assert engine.strategies["public_transport"].options(engine.snapshot) == {}
    r = engine.compare(["WEST", "EAST"], {"public_transport": FactorChoice(5)})
    assert r["areas"][0]["name"] == "WEST"


def test_setup_page_offers_the_modes_with_either_by_default(tmp_path):
    app = create_app({"SNAPSHOT_PATH": snapshot(tmp_path, full=True), "SECRET_KEY": "t", "TESTING": True,
                      "EVENTS_PATH": tmp_path / "e.db"})
    c = app.test_client()
    page = c.get("/live").get_data(as_text=True)
    assert 'name="pt_mode"' in page and '<option value="either" selected>Either</option>' in page
    r = c.post("/live", data={"areas": ["WEST", "EAST"], "include_public_transport": "1",
                              "weight_public_transport": "5", "pt_mode": "bus"})
    assert r.status_code == 303
    assert "Bus" in c.get("/live").get_data(as_text=True)        # refilled from the session
    assert "bus stop with 3 or more services" in c.get("/live/results").get_data(as_text=True)
