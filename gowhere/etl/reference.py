"""Readers for data/reference/: small hand-compiled files, each row carrying its source.

These are the project's only hand-maintained data. They exist because no government
dataset lists polyclinic locations or says which hospitals offer 24-hour emergency care.
"""
import csv

from gowhere import config

POLYCLINICS = "polyclinics.csv"
HOSPITALS = "hospitals.csv"


def _rows(name, ref_dir=None):
    with open((ref_dir or config.REFERENCE_DIR) / name, newline="") as f:
        return list(csv.DictReader(f))


def load_polyclinic_list(ref_dir=None):
    """[{name, cluster, address, postal_code, ...source columns}]"""
    return _rows(POLYCLINICS, ref_dir)


def load_hospital_classification(ref_dir=None):
    """{hospital name as in the OneMap moh_hospitals theme: row}"""
    return {r["name"]: r for r in _rows(HOSPITALS, ref_dir)}


def hospital_counts(hospital):
    """Whether a classified hospital is in the Healthcare factor's 'hospital' type."""
    return (hospital["category"] in config.HOSPITAL_CATEGORIES
            and hospital["care_24h"] in config.HOSPITAL_CARE_24H)
