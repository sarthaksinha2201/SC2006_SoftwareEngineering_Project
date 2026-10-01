"""ScoringEngine rules (DECISIONS.md section 2), with stub strategies and a fake snapshot.

The stubs are factors the engine has never seen, so these tests also show the
Supportability claim: any ScoringStrategy works without changing the engine.
"""
import pytest

from gowhere.scoring.base import NumberRange, ScoringStrategy
from gowhere.scoring.engine import FactorChoice, InvalidRequest, NoFactorsLeft, ScoringEngine


class FakeSnapshot:
    AREAS = {
        "ALPHA": {"region": "R", "in_scope": 1, "n_blocks": 300, "n_flats": 30000, "small_sample": 0},
        "BETA": {"region": "R", "in_scope": 1, "n_blocks": 200, "n_flats": 20000, "small_sample": 0},
        "GAMMA": {"region": "R", "in_scope": 1, "n_blocks": 2, "n_flats": 166, "small_sample": 1},
        "DELTA": {"region": "R", "in_scope": 1, "n_blocks": 50, "n_flats": 5000, "small_sample": 0},
        "EMPTY": {"region": "R", "in_scope": 0, "n_blocks": 0, "n_flats": 0, "small_sample": 0},
    }

    def areas(self, names=None):
        return {k: v for k, v in self.AREAS.items() if names is None or k in names}

    def meta(self):
        return {"generated_at": "2026-09-30T00:00:00+00:00", "raw_manifest": "{}"}


class Stub(ScoringStrategy):
    def __init__(self, key, scores, options=None, notes=None):
        self.key, self.label = key, key.title()
        self._scores, self._options, self._notes = scores, options or {}, notes or {}

    def schema(self):
        return ""

    def precompute(self, blocks, sources):
        return {}

    def options(self, snapshot):
        return self._options

    def category_scores(self, snapshot, areas, options):
        scores = self._scores[options["kind"]] if self._options else self._scores
        return {a: scores.get(a) for a in areas}

    def notes(self, snapshot, areas, options):
        return {a: n for a, n in self._notes.items() if a in areas}


def engine(*strategies):
    return ScoringEngine(list(strategies), FakeSnapshot())


def test_overall_is_weighted_mean_on_0_to_10():
    e = engine(Stub("a", {"ALPHA": 9.0, "BETA": 3.0}), Stub("b", {"ALPHA": 3.0, "BETA": 9.0}))
    r = e.compare(["ALPHA", "BETA"], {"a": FactorChoice(3), "b": FactorChoice(1)})
    overall = {x["name"]: x["overall"] for x in r["areas"]}
    assert overall == {"ALPHA": pytest.approx((9 * 3 + 3 * 1) / 4), "BETA": pytest.approx((3 * 3 + 9) / 4)}
    assert [x["name"] for x in r["areas"]] == ["ALPHA", "BETA"]


def test_scaling_all_weights_does_not_change_result():
    e = engine(Stub("a", {"ALPHA": 7.0, "BETA": 4.0}), Stub("b", {"ALPHA": 2.0, "BETA": 6.0}))
    r5 = e.compare(["ALPHA", "BETA"], {"a": FactorChoice(5), "b": FactorChoice(5)})
    r10 = e.compare(["ALPHA", "BETA"], {"a": FactorChoice(10), "b": FactorChoice(10)})
    assert [(x["name"], x["overall"]) for x in r5["areas"]] == \
        [(x["name"], x["overall"]) for x in r10["areas"]]


def test_tie_at_one_decimal_is_joint_rank():
    # 7.04 and 6.96 both display as 7.0 -> joint 1st; next area is 3rd, not 2nd
    e = engine(Stub("a", {"ALPHA": 7.04, "BETA": 6.96, "DELTA": 2.0}))
    r = e.compare(["ALPHA", "BETA", "DELTA"], {"a": FactorChoice(5)})
    assert [(x["name"], x["rank"]) for x in r["areas"]] == [("ALPHA", 1), ("BETA", 1), ("DELTA", 3)]


def test_close_call_at_exactly_point_two_despite_float_error():
    # 8.3 - 8.1 is 0.20000000000000107 in floating point; it must still count as <= 0.2
    e = engine(Stub("a", {"ALPHA": 8.3, "BETA": 8.1}))
    assert e.compare(["ALPHA", "BETA"], {"a": FactorChoice(5)})["close_call"] is True
    e = engine(Stub("a", {"ALPHA": 8.4, "BETA": 8.1}))
    assert e.compare(["ALPHA", "BETA"], {"a": FactorChoice(5)})["close_call"] is False


def test_explanation_ranks_factors_by_marginal_contribution():
    e = engine(Stub("a", {"ALPHA": 9.0, "BETA": 8.0}), Stub("b", {"ALPHA": 6.0, "BETA": 2.0}),
               Stub("c", {"ALPHA": 1.0, "BETA": 5.0}))
    r = e.compare(["ALPHA", "BETA"], {"a": FactorChoice(10), "b": FactorChoice(2), "c": FactorChoice(1)})
    ex = r["explanation"]
    assert (ex["winner"], ex["runner_up"]) == ("ALPHA", "BETA")
    assert [(f["key"], f["contribution"]) for f in ex["factors"]] == [("a", 10.0), ("b", 8.0), ("c", -4.0)]


def test_factor_missing_for_one_area_is_dropped_for_all():
    e = engine(Stub("a", {"ALPHA": 9.0, "BETA": 1.0}), Stub("b", {"ALPHA": 1.0}))
    r = e.compare(["ALPHA", "BETA"], {"a": FactorChoice(5), "b": FactorChoice(5)})
    assert r["dropped"] == [{"key": "b", "label": "B", "missing_for": ["BETA"],
                             "reason": "has no data for this factor"}]
    assert [f["key"] for f in r["factors"]] == ["a"]
    assert all(set(x["category"]) == {"a"} for x in r["areas"])
    assert r["areas"][0]["overall"] == 9.0


def test_all_factors_dropped_raises_with_reasons():
    e = engine(Stub("a", {"ALPHA": 9.0}))
    with pytest.raises(NoFactorsLeft) as err:
        e.compare(["ALPHA", "BETA"], {"a": FactorChoice(5)})
    assert err.value.dropped[0]["missing_for"] == ["BETA"]


def test_options_select_the_precomputed_variant():
    s = Stub("h", {"gp": {"ALPHA": 9.0, "BETA": 1.0}, "hospital": {"ALPHA": 1.0, "BETA": 9.0}},
             options={"kind": ["gp", "hospital"]})
    r = engine(s).compare(["ALPHA", "BETA"], {"h": FactorChoice(5, {"kind": "hospital"})})
    assert r["areas"][0]["name"] == "BETA"


def test_small_area_note_is_neutral_and_factor_notes_are_added():
    e = engine(Stub("a", {"ALPHA": 5.0, "GAMMA": 9.4}, notes={"ALPHA": ["factor note"]}))
    r = e.compare(["ALPHA", "GAMMA"], {"a": FactorChoice(5)})
    by = {x["name"]: x for x in r["areas"]}
    assert by["GAMMA"]["notes"] == [
        "Gamma — 166 flats across 2 blocks. Scores are based on a small number of blocks."]
    assert by["ALPHA"]["notes"] == ["factor note"]
    text = " ".join(by["GAMMA"]["notes"]).lower()
    assert not any(w in text for w in ("unreliable", "caution", "warning", "inaccurate"))


@pytest.mark.parametrize("areas, choices, message", [
    (["ALPHA"], {"a": FactorChoice(5)}, "select 2 to 4"),
    (["ALPHA", "BETA", "GAMMA", "DELTA", "EMPTY"], {"a": FactorChoice(5)}, "select 2 to 4"),
    (["ALPHA", "ALPHA"], {"a": FactorChoice(5)}, "once"),
    (["ALPHA", "NOWHERE"], {"a": FactorChoice(5)}, "not an in-scope"),
    (["ALPHA", "EMPTY"], {"a": FactorChoice(5)}, "not an in-scope"),
    (["ALPHA", "BETA"], {}, "at least one factor"),
    (["ALPHA", "BETA"], {"zzz": FactorChoice(5)}, "unknown factor"),
    (["ALPHA", "BETA"], {"a": FactorChoice(0)}, "weight"),
    (["ALPHA", "BETA"], {"a": FactorChoice(11)}, "weight"),
    (["ALPHA", "BETA"], {"a": FactorChoice(5.5)}, "weight"),
    (["ALPHA", "BETA"], {"a": FactorChoice(5, {"kind": "gp"})}, "options"),
])
def test_invalid_requests(areas, choices, message):
    with pytest.raises(InvalidRequest, match=message):
        engine(Stub("a", {"ALPHA": 1.0, "BETA": 2.0})).compare(areas, choices)


def test_weight_boundaries_accepted():
    e = engine(Stub("a", {"ALPHA": 1.0, "BETA": 2.0}))
    for w in (1, 10):
        e.compare(["ALPHA", "BETA"], {"a": FactorChoice(w)})


def test_option_value_must_be_allowed():
    s = Stub("h", {"gp": {}}, options={"kind": ["gp"]})
    with pytest.raises(InvalidRequest, match="kind must be one of"):
        engine(s).compare(["ALPHA", "BETA"], {"h": FactorChoice(5, {"kind": "vet"})})


class RangedStub(Stub):
    """A factor with numeric options and a cross-option rule, like a budget."""

    def options(self, snapshot):
        return {"low": NumberRange(0, 100), "high": NumberRange(0, 100)}

    def validate_options(self, options):
        if options["low"] > options["high"]:
            raise InvalidRequest("low must not exceed high")

    def category_scores(self, snapshot, areas, options):
        return {a: self._scores.get(a) for a in areas}

    def factor_notes(self, snapshot, options):
        return [f"covers {options['low']}-{options['high']}"]


@pytest.mark.parametrize("opts, message", [
    ({"low": -1, "high": 50}, "low must be a number from 0 to 100"),
    ({"low": 10, "high": 101}, "high must be a number"),
    ({"low": "10", "high": 50}, "low must be a number"),
    ({"low": True, "high": 50}, "low must be a number"),
    ({"low": 60, "high": 50}, "low must not exceed high"),
])
def test_number_range_and_cross_option_validation(opts, message):
    e = engine(RangedStub("r", {"ALPHA": 1.0, "BETA": 2.0}))
    with pytest.raises(InvalidRequest, match=message):
        e.compare(["ALPHA", "BETA"], {"r": FactorChoice(5, opts)})


def test_range_boundaries_accepted_and_factor_notes_returned():
    e = engine(RangedStub("r", {"ALPHA": 1.0, "BETA": 2.0}))
    r = e.compare(["ALPHA", "BETA"], {"r": FactorChoice(5, {"low": 0, "high": 100})})
    assert r["factors"][0]["notes"] == ["covers 0-100"]
    assert e.factors()[0]["options"] == {"low": {"min": 0, "max": 100}, "high": {"min": 0, "max": 100}}
