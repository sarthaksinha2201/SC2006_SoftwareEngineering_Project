"""User-facing caveat wording, kept in one place so it stays neutral and consistent.

Every note states a fact about the data. None says a score is unreliable: two of the three
small areas score near the top, so a note that read as a warning would mislead.
"""
from datetime import date


def small_area_note(area, n_blocks, n_flats):
    return (f"{area.title()} — {n_flats:,} flats across {n_blocks} "
            f"{'block' if n_blocks == 1 else 'blocks'}. "
            f"Scores are based on a small number of blocks.")


def rail_data_note(as_of_iso):
    return (f"Public Transport scores are based on MRT/LRT stations in LTA's station-exit "
            f"data as of {_day_month_year(as_of_iso)}.")


def hospital_scope_note():
    return ("The hospital option measures distance to the 9 public acute general hospitals, "
            "where emergency cases are taken. Private hospitals are not included.")


def gp_data_note(as_of_iso):
    return (f"GP clinic locations come from MOH's CHAS clinic list, last updated "
            f"{_day_month_year(as_of_iso)}. Clinics opened or closed since then are not reflected.")


def _day_month_year(iso):
    d = date.fromisoformat(iso)
    return f"{d.day} {d:%b %Y}"
