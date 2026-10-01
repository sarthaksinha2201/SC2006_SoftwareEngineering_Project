"""Turn the Where to Live form into the engine's (areas, choices).

Form fields:
    areas                       2-4 planning area names (repeated field)
    include_<factor>            present when the factor is included
    weight_<factor>             whole number 1-10
    housing_affordability: flat_type, budget_min, budget_max, min_remaining_lease_years ("" = any)
    amenities: amenity_types    (repeated field)
    healthcare: facility_type
    commute: destination_postal, mode

Parsing only converts types. The engine validates the values (ranges, allowed choices,
2-4 areas), so the rules live in one place. Messages never echo what the user typed,
because one of the fields is a postal code.
"""
from gowhere.scoring.engine import FactorChoice

FACTOR_ORDER = ["public_transport", "housing_affordability", "amenities", "greenery",
                "healthcare", "commute"]


class FormError(ValueError):
    pass


def _int(form, name, label):
    raw = (form.get(name) or "").strip().replace(",", "")
    try:
        return int(raw)
    except ValueError:
        raise FormError(f"{label} must be a whole number")


def _options(form, key):
    if key == "housing_affordability":
        lease = (form.get("min_remaining_lease_years") or "").strip()
        return {"flat_type": form.get("flat_type", ""),
                "budget_min": _int(form, "budget_min", "Budget minimum"),
                "budget_max": _int(form, "budget_max", "Budget maximum"),
                "min_remaining_lease_years": int(lease) if lease.isdigit() else None}
    if key == "amenities":
        return {"amenity_types": form.getlist("amenity_types")}
    if key == "healthcare":
        return {"facility_type": form.get("facility_type", "")}
    if key == "commute":
        return {"destination_postal": (form.get("destination_postal") or "").strip(),
                "mode": form.get("mode", "")}
    return {}


def parse_live_form(form, factor_keys, skip=()):
    """(areas, {factor key: FactorChoice}) for the included factors, minus `skip`."""
    areas = [a for a in form.getlist("areas") if a]
    choices = {}
    for key in factor_keys:
        if key in skip or not form.get(f"include_{key}"):
            continue
        weight = _int(form, f"weight_{key}", "Each weight")
        choices[key] = FactorChoice(weight, _options(form, key))
    return areas, choices
