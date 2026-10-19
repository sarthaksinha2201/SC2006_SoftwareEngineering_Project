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
RAW_RESALE = "hdb_resale_prices"                  # last 12 complete months only
RAW_HAWKER_CENTRES = "nea_hawker_centres"
RAW_LIBRARIES = "nlb_libraries"                   # NLB layer served as a OneMap theme
RAW_SUPERMARKETS = "sfa_supermarkets"             # licence list: addresses, no coordinates
RAW_OSM_AMENITIES = "osm_amenities"               # malls, gyms, cafes (Overpass)
RAW_OSM_FOOD = "osm_food"                         # Where to Eat: every food venue (Overpass)
RAW_BUS_STOPS = "lta_bus_stops"                   # LTA DataMall BusStops (needs LTA_DATAMALL_KEY)
RAW_BUS_ROUTES = "lta_bus_routes"                 # LTA DataMall BusRoutes: services per stop

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
# Decided 30 Sep 2026 (DECISIONS.md section 9): the 9 public acute general hospitals.
# In an emergency SCDF conveys patients to public emergency departments, so a nearby
# private hospital does not improve emergency access. Alexandra (urgent care centre,
# no full ED) is included so the category holds every public general hospital.
HOSPITAL_CATEGORIES = {"public_acute"}
HOSPITAL_CARE_24H = {"emergency_department", "urgent_care_centre"}
REFERENCE_CLASSIFIED_ON = "2026-09-30"   # date both reference files were compiled

# Public Transport: an area whose flat-weighted median distance to the nearest rail exit
# exceeds this is flagged far_from_rail, so the UI can say which stations the score
# reflects (e.g. Tengah before the Jurong Region Line opens).
FAR_FROM_RAIL_M = 1500.0
# A Qualifying Bus Stop (Data Dictionary) is served by at least this many bus services.
QUALIFYING_BUS_SERVICES = 3
BUS_CATCHMENT_M = 400               # Bus score: distinct services within this radius (DECISIONS.md 18)

# Housing Affordability (DECISIONS.md section 2): resale transactions from the 12 complete
# calendar months before the resale data was fetched. The window is fixed in the snapshot,
# so the same snapshot always gives the same answer, whatever today's date.
RESALE_WINDOW_MONTHS = 12
HOUSING_MIN_TRANSACTIONS = 10    # fewer matching transactions -> no data for the area

# Amenities (DECISIONS.md section 2): per block, count each selected amenity type within
# 800 m (straight line), capping each type at 3 so twenty cafes cannot outweigh having no
# supermarket; per area, the flat-weighted mean of the sum; scored by percentile rank.
AMENITY_RADIUS_M = 800.0
AMENITY_CAP = 3
# OpenStreetMap tags for the amenity types that have no government dataset.
OSM_AMENITY_TAGS = {"mall": '["shop"="mall"]', "gym": '["leisure"="fitness_centre"]',
                    "cafe": '["amenity"="cafe"]'}

# ---- Where to Eat (DECISIONS.md sections 25 and 25a) ----
EAT_PATH = DATA_DIR / "eat.db"           # built offline by gowhere.eat.build; committed
# Google Place Details calls per Singapore day, counted before each call. Ratings are the
# "Place Details Enterprise" SKU: 1,000 free a month, then US$20 per 1,000. 32 a day is
# 992 in a 31-day month, inside the free tier. Raise it only with a budget in mind
# (DECISIONS.md 29).
GOOGLE_DAILY_CAP = 32
RATING_WORKERS = 8                       # parallel Place Details calls per search
OSM_FOOD_TAGS = ['["amenity"="restaurant"]', '["amenity"="cafe"]', '["amenity"="fast_food"]',
                 '["amenity"="food_court"]', '["amenity"="ice_cream"]',
                 '["amenity"="marketplace"]']

# ---- Where to Lepak (DECISIONS.md sections 3 and 11) ----
EVENTS_PATH = DATA_DIR / "events.db"     # read-write event store; the snapshot stays read-only
# Public broadcast channels with a t.me/s/ view (DECISIONS.md section 7). sgbestnightlife
# is on probation: its yield decides whether it stays.
LEPAK_CHANNELS = ["sgweekend", "sgwhereto", "SGArtsChannel", "sgconcerts", "dateideas",
                  "sgfitnesshealth"]
# Dropped (DECISIONS.md section 7): TimeOutSG, dormant since June; sgbestnightlife, on
# probation, stored 0 events from 20 posts in the first real run (14 Oct 2026).
LLM_MODEL = "gpt-6-luna"                 # OpenAI: cheapest model for bulk structured extraction
LLM_REASONING_EFFORT = "low"             # reasoning tokens bill as output; extraction needs little
LLM_BATCH_SIZE = 10                      # posts per extraction call
EVENT_MERGE_RADIUS_M = 200.0             # duplicates: same date, similar title, this close
EVENT_MAX_DAYS_AHEAD = 400               # an event dated further out is treated as a misread
INGEST_INTERVAL_H = 6
