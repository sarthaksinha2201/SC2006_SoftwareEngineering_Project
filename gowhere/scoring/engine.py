"""Compare neighbourhoods: combine category scores into an overall score and ranking.

The engine knows nothing about individual factors. It asks each ScoringStrategy for
category scores and applies the rules in DECISIONS.md section 2:
  - overall score = sum(score x weight) / sum(weight), on 0-10
  - a factor with no data for any selected area is dropped for all of them, and reported
  - a tie is equality at 1 decimal place and gives a joint rank
  - the result warns when the top two differ by 0.2 or less
  - the explanation ranks factors by marginal contribution, (winner - runner-up) x weight
"""
from dataclasses import dataclass, field

from gowhere.scoring import notes as notes_text
from gowhere.scoring.base import InvalidRequest, NumberRange, TextPattern
from gowhere.scoring.stats import round1, tenths

MIN_AREAS, MAX_AREAS = 2, 4
MIN_WEIGHT, MAX_WEIGHT = 1, 10
CLOSE_CALL_TENTHS = 2   # 0.2


class NoFactorsLeft(Exception):
    """Every included factor was dropped for missing data."""

    def __init__(self, dropped):
        super().__init__("no factor has data for all selected areas")
        self.dropped = dropped


@dataclass(frozen=True)
class FactorChoice:
    weight: int
    options: dict = field(default_factory=dict)


class ScoringEngine:
    def __init__(self, strategies, snapshot):
        self.strategies = {s.key: s for s in strategies}
        self.snapshot = snapshot

    def factors(self):
        """[{key, label, options}] for building the setup screen."""
        def describe(allowed):
            if isinstance(allowed, NumberRange):
                return {"min": allowed.minimum, "max": allowed.maximum}
            if isinstance(allowed, TextPattern):
                return {"pattern": allowed.pattern, "description": allowed.description}
            return list(allowed)
        return [{"key": s.key, "label": s.label,
                 "options": {k: describe(v) for k, v in s.options(self.snapshot).items()}}
                for s in self.strategies.values()]

    def compare(self, areas, choices):
        """areas: 2-4 planning area names. choices: {factor key: FactorChoice} for the
        included factors (an excluded factor is simply absent)."""
        info = self._validate(areas, choices)

        scores, raw, notes, dropped = {}, {}, {a: [] for a in areas}, []
        for key, choice in choices.items():
            s = self.strategies[key]
            cat = s.category_scores(self.snapshot, areas, choice.options)
            missing = [a for a in areas if cat.get(a) is None]
            if missing:
                dropped.append({"key": key, "label": s.label, "missing_for": missing})
                continue
            scores[key] = cat
            raw[key] = s.raw_values(self.snapshot, areas, choice.options)
            for a, texts in s.notes(self.snapshot, areas, choice.options).items():
                notes[a].extend(texts)
        if not scores:
            raise NoFactorsLeft(dropped)

        total_weight = sum(choices[k].weight for k in scores)
        overall = {a: sum(scores[k][a] * choices[k].weight for k in scores) / total_weight
                   for a in areas}
        for a in areas:
            if info[a]["small_sample"]:
                notes[a].insert(0, notes_text.small_area_note(a, info[a]["n_blocks"],
                                                              info[a]["n_flats"]))

        order = sorted(areas, key=lambda a: (-tenths(overall[a]), a))
        ranks, prev = {}, None
        for i, a in enumerate(order, 1):
            ranks[a] = ranks[prev] if prev and tenths(overall[a]) == tenths(overall[prev]) else i
            prev = a

        winner, runner_up = order[0], order[1]
        explanation = sorted(
            ({"key": k, "label": self.strategies[k].label,
              "contribution": (scores[k][winner] - scores[k][runner_up]) * choices[k].weight}
             for k in scores), key=lambda e: -e["contribution"])

        return {
            "areas": [{"name": a, "rank": ranks[a], "overall": overall[a],
                       "overall_display": round1(overall[a]),
                       "category": {k: scores[k][a] for k in scores},
                       "category_display": {k: round1(scores[k][a]) for k in scores},
                       "raw": {k: raw[k].get(a, {}) for k in scores},
                       "notes": notes[a], **info[a]} for a in order],
            "factors": [{"key": k, "label": self.strategies[k].label,
                         "weight": choices[k].weight, "options": choices[k].options,
                         "notes": self.strategies[k].factor_notes(self.snapshot, choices[k].options)}
                        for k in scores],
            "dropped": dropped,
            "close_call": tenths(overall[winner]) - tenths(overall[runner_up]) <= CLOSE_CALL_TENTHS,
            "explanation": {"winner": winner, "runner_up": runner_up, "factors": explanation},
            "snapshot": {k: v for k, v in self.snapshot.meta().items() if k != "raw_manifest"},
        }

    def _validate(self, areas, choices):
        if len(set(areas)) != len(areas):
            raise InvalidRequest("each neighbourhood can be selected once")
        if not MIN_AREAS <= len(areas) <= MAX_AREAS:
            raise InvalidRequest(f"select {MIN_AREAS} to {MAX_AREAS} neighbourhoods")
        info = self.snapshot.areas(areas)
        unknown = [a for a in areas if a not in info or not info[a]["in_scope"]]
        if unknown:
            raise InvalidRequest(f"not an in-scope neighbourhood: {', '.join(unknown)}")
        if not choices:
            raise InvalidRequest("include at least one factor")
        for key, choice in choices.items():
            if key not in self.strategies:
                raise InvalidRequest(f"unknown factor: {key}")
            if not isinstance(choice.weight, int) or not MIN_WEIGHT <= choice.weight <= MAX_WEIGHT:
                raise InvalidRequest(f"{key}: weight must be a whole number "
                                     f"from {MIN_WEIGHT} to {MAX_WEIGHT}")
            allowed = self.strategies[key].options(self.snapshot)
            if set(choice.options) != set(allowed):
                raise InvalidRequest(f"{key}: options must be exactly {sorted(allowed)}")
            for name, value in choice.options.items():
                if value not in allowed[name]:
                    if isinstance(allowed[name], TextPattern):
                        raise InvalidRequest(f"{key}: {name} must be {allowed[name].description}")
                    if isinstance(allowed[name], NumberRange):
                        raise InvalidRequest(f"{key}: {name} must be a number from "
                                             f"{allowed[name].minimum:g} to {allowed[name].maximum:g}")
                    raise InvalidRequest(f"{key}: {name} must be one of {allowed[name]}")
            self.strategies[key].validate_options(choice.options)
        return {a: {k: info[a][k] for k in ("region", "n_blocks", "n_flats", "small_sample")}
                for a in areas}
