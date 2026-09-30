import csv
import json

import pytest

from gowhere import config
from gowhere.etl.addresses import match_postal
from gowhere.etl.raw import load_hospitals
from gowhere.etl.reference import hospital_counts, load_hospital_classification, load_polyclinic_list
from gowhere.scoring.healthcare import HealthcareScorer
from tests.fakes import FakeSources


def block(i, lat, lon, area, flats=100):
    return {"id": i, "lat": lat, "lon": lon, "planning_area": area, "total_dwelling_units": flats}


def test_each_facility_type_scored_separately():
    facilities = {"gp": [{"name": "GP1", "lat": 1.300, "lon": 103.800}],
                  "hospital": [{"name": "H1", "lat": 1.400, "lon": 103.900}]}
    blocks = [block(1, 1.301, 103.800, "NEAR_GP"), block(2, 1.399, 103.900, "NEAR_H")]
    out = HealthcareScorer().precompute(blocks, FakeSources(facilities=facilities))
    s = {(r["planning_area"], r["facility_type"]): r["score"] for r in out["healthcare_area"]}
    assert s == {("NEAR_GP", "gp"): 10.0, ("NEAR_H", "gp"): 0.0,
                 ("NEAR_GP", "hospital"): 0.0, ("NEAR_H", "hospital"): 10.0}
    assert len(out["healthcare_block"]) == 4
    gp1 = next(r for r in out["healthcare_block"] if r["block_id"] == 1 and r["facility_type"] == "gp")
    assert gp1["nearest_facility"] == "GP1" and gp1["distance_m"] == pytest.approx(111.2, rel=0.01)


def test_median_distance_is_flat_weighted():
    facilities = {"gp": [{"name": "GP", "lat": 1.30, "lon": 103.80}]}
    # 300 flats ~111 m away and 100 flats ~1112 m away: weighted median is the near block
    blocks = [block(1, 1.301, 103.80, "A", 300), block(2, 1.310, 103.80, "A", 100)]
    out = HealthcareScorer().precompute(blocks, FakeSources(facilities=facilities))
    assert out["healthcare_area"][0]["median_distance_m"] == pytest.approx(111.2, rel=0.01)


def test_empty_facility_list_stops_the_build():
    with pytest.raises(ValueError, match="no gp facilities"):
        HealthcareScorer().precompute([block(1, 1.3, 103.8, "A")], FakeSources(facilities={"gp": []}))


def test_postal_match_uses_exact_code_and_midpoint():
    results = [{"POSTAL": "690302", "LATITUDE": "1.3500", "LONGITUDE": "103.7000"},
               {"POSTAL": "690302", "LATITUDE": "1.3502", "LONGITUDE": "103.7002"},
               {"POSTAL": "690303", "LATITUDE": "1.4000", "LONGITUDE": "103.8000"}]
    assert match_postal("690302", results) == pytest.approx({"lat": 1.3501, "lon": 103.7001})
    assert match_postal("123456", results) is None


def test_hospital_rule_counts_acute_and_private_with_24h_care():
    counts = lambda cat, care: hospital_counts({"category": cat, "care_24h": care})
    assert counts("public_acute", "emergency_department")
    assert counts("public_acute", "urgent_care_centre")        # Alexandra
    assert counts("private", "urgent_care_centre")
    assert not counts("private", "outpatient_24h")             # Crawfurd
    assert not counts("community", "not_assessed")
    assert not counts("public_specialty", "specialty_emergency")  # KKH
    assert not counts("prison", "not_assessed")


def test_unclassified_hospital_stops_the_build(tmp_path):
    (tmp_path / f"{config.RAW_HOSPITALS}.json").write_text(json.dumps({"SrchResults": [
        {"FeatCount": 1}, {"NAME": "NEW HOSPITAL", "LatLng": "1.3,103.8"}]}))
    with pytest.raises(ValueError, match="classify it"):
        load_hospitals({}, raw_dir=tmp_path)


# ---- the reference files themselves (in git): provenance on every row ----

def test_polyclinic_reference_rows_have_provenance():
    rows = load_polyclinic_list()
    assert len(rows) == 28
    assert {r["cluster"] for r in rows} == {"NHG", "NUP", "SingHealth"}
    for r in rows:
        assert len(r["postal_code"]) == 6 and r["postal_code"].isdigit(), r
        assert r["cluster_source_url"].startswith("https://"), r
        assert r["address_source_url"].startswith("https://"), r
        assert r["retrieved_on"], r
    assert len({r["name"] for r in rows}) == len(rows)


def test_hospital_reference_rows_have_provenance():
    rows = load_hospital_classification()
    allowed_cat = {"public_acute", "public_specialty", "private", "community", "psychiatric", "prison"}
    allowed_care = {"emergency_department", "urgent_care_centre", "specialty_emergency",
                    "outpatient_24h", "none", "not_assessed"}
    for r in rows.values():
        assert r["category"] in allowed_cat and r["care_24h"] in allowed_care, r
        assert r["category_source_url"].startswith("https://"), r
        if r["care_24h"] != "not_assessed":
            assert r["care_24h_source_url"].startswith("https://"), r
    assert sum(hospital_counts(r) for r in rows.values()) == 17
