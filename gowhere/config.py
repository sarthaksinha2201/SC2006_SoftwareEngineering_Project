"""Filesystem locations and model constants shared by the ETL and the web app."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"            # unmodified API responses (S1 contract)
REFERENCE_DIR = DATA_DIR / "reference"  # hand-compiled, sourced reference files (in git)
CACHE_DIR = DATA_DIR / "cache"        # resumable API caches (geocoding, routing)
LOG_DIR = DATA_DIR / "logs"
SNAPSHOT_PATH = DATA_DIR / "snapshot.db"   # the only file the web app reads
DOCS_DIR = ROOT / "docs"

# Raw dataset names under data/raw/. S1 (fetch_raw) must write these names.
RAW_HDB_PROPERTY = "hdb_property_information"
RAW_MRT_EXITS = "lta_mrt_station_exits"
RAW_PLANNING_AREAS = "ura_mp2019_planning_areas"
RAW_PARKS = "nparks_parks"                        # park and nature reserve boundaries
RAW_PARK_CONNECTORS = "nparks_park_connectors"    # built park connector network (lines)
RAW_CHAS_CLINICS = "moh_chas_clinics"
RAW_HOSPITALS = "moh_hospitals"                   # MOH layer served as a OneMap theme

# Walking model (DECISIONS.md section 4). The detour factor is the median ratio of
# OneMap walking-route distance to straight-line distance over 200 sampled blocks;
# it replaced a 1.3 placeholder. Re-run `python -m gowhere.etl.calibrate` to check it.
DETOUR_FACTOR = 1.39
DETOUR_FACTOR_CALIBRATED_ON = "2026-09-30"
DETOUR_FACTOR_SOURCE = "median of 200 OneMap walking routes; docs/detour-calibration.md"
WALK_SPEED_M_PER_MIN = 80.0
WALK_THRESHOLD_MIN = 10.0

# An in-scope area with fewer HDB blocks than this is flagged small_sample in the
# snapshot, so the UI can say its scores rest on few blocks. Areas are never excluded
# for being small (DECISIONS.md section 1).
SMALL_AREA_BLOCKS = 10


def load_dotenv(path=ROOT / ".env"):
    """Load KEY=VALUE lines from .env into os.environ without overriding what is set."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))

# Greenery: a flat counts as near green space within this straight-line distance of a
# park, nature reserve or park connector (DECISIONS.md section 2).
GREEN_SPACE_RADIUS_M = 400.0

# Healthcare: which hospitals count, by their classification in
# data/reference/hospitals.csv (every MOH-licensed hospital, with a source per row).
# Provisional (30 Sep 2026): acute and private hospitals with 24-hour emergency or urgent
# care. Community, psychiatric and specialty hospitals and the prison facility never count.
HOSPITAL_CATEGORIES = {"public_acute", "private"}
HOSPITAL_CARE_24H = {"emergency_department", "urgent_care_centre"}
REFERENCE_CLASSIFIED_ON = "2026-09-30"   # date both reference files were compiled

# Public Transport: an area whose flat-weighted median distance to the nearest rail exit
# exceeds this is flagged far_from_rail, so the UI can say which stations the score
# reflects (e.g. Tengah before the Jurong Region Line opens).
FAR_FROM_RAIL_M = 1500.0
