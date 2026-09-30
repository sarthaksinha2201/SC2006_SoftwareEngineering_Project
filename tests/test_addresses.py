import pytest

from gowhere.etl.addresses import expand_street, match_block, query_for


def result(blk, road, lat, lon, postal="NIL", building="NIL"):
    return {"BLK_NO": blk, "ROAD_NAME": road, "LATITUDE": str(lat), "LONGITUDE": str(lon),
            "POSTAL": postal, "BUILDING": building, "ADDRESS": f"{blk} {road}"}


@pytest.mark.parametrize("hdb, onemap", [
    ("BT BATOK WEST AVE 6", "BUKIT BATOK WEST AVENUE 6"),
    ("C'WEALTH CL", "COMMONWEALTH CLOSE"),
    ("UPP BOON KENG RD", "UPPER BOON KENG ROAD"),
    ("BEDOK STH AVE 1", "BEDOK SOUTH AVENUE 1"),
    ("TAMPINES ST 71", "TAMPINES STREET 71"),
])
def test_expand_street(hdb, onemap):
    assert expand_street(hdb) == onemap


def test_query_forms():
    assert query_for("1", "BEACH RD") == "1 BEACH RD"
    assert query_for("1", "BEACH RD", expanded=True) == "1 BEACH ROAD"


def test_match_requires_block_and_road():
    results = [result("10", "BEDOK SOUTH AVENUE 1", 1.32, 103.93),
               result("1", "BEDOK SOUTH AVENUE 2", 1.32, 103.93)]
    assert match_block("1", "BEDOK STH AVE 1", results) == ("no_match", None)


def test_match_ok_prefers_real_postal():
    results = [result("1", "BEDOK SOUTH AVENUE 1", 1.3200, 103.9300),
               result("1", "BEDOK SOUTH AVENUE 1", 1.3201, 103.9300, postal="460001")]
    status, m = match_block("1", "BEDOK STH AVE 1", results)
    assert status == "ok" and m["POSTAL"] == "460001"


def test_match_block_letter_case_insensitive():
    status, _ = match_block("196c", "PUNGGOL FIELD", [result("196C", "PUNGGOL FIELD", 1.4, 103.9)])
    assert status == "ok"


def test_far_apart_matches_resolved_by_postal_suffix():
    # Real case: "1 BEACH RD" is both an HDB block and Raffles Hotel, 1.3 km apart.
    results = [result("1", "BEACH ROAD", 1.303671, 103.864479, "190001", "BEACH ROAD GARDENS"),
               result("1", "BEACH ROAD", 1.295097, 103.854068, "NIL", "RAFFLES HOTEL"),
               result("1", "BEACH ROAD", 1.294801, 103.854467, "189673", "RAFFLES HOTEL SINGAPORE")]
    status, m = match_block("1", "BEACH RD", results)
    assert status == "ok" and m["POSTAL"] == "190001"


def test_far_apart_matches_without_postal_evidence_are_ambiguous():
    results = [result("5", "SOME ROAD", 1.30, 103.80, "111111"),
               result("5", "SOME ROAD", 1.35, 103.85, "222222")]
    assert match_block("5", "SOME RD", results) == ("ambiguous", None)
