from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
import math
from dotenv import load_dotenv


# ============================================================
# CONFIGURATION
# ============================================================

load_dotenv()

app = Flask(__name__)
CORS(app)

ONEMAP_TOKEN = os.getenv("ONEMAP_TOKEN")

if not ONEMAP_TOKEN:
    raise Exception(
        "ONEMAP_TOKEN not found. "
        "Make sure your .env file contains ONEMAP_TOKEN=..."
    )


# OneMap API URLs
SEARCH_URL = (
    "https://www.onemap.gov.sg/"
    "api/common/elastic/search"
)

NEAREST_MRT_URL = (
    "https://www.onemap.gov.sg/"
    "api/public/nearbysvc/getNearestMrtStops"
)

NEAREST_BUS_URL = (
    "https://www.onemap.gov.sg/"
    "api/public/nearbysvc/getNearestBusStops"
)

ROUTING_URL = (
    "https://www.onemap.gov.sg/"
    "api/public/routingsvc/route"
)


# Maximum distance OneMap allows for nearby transport
SEARCH_RADIUS_METERS = 5000

# Number of nearby MRT/bus candidates that we will
# check with the walking-routing API.
#
# We don't just blindly assume the first result is the
# best walking route.
MAX_TRANSPORT_CANDIDATES = 5


# ============================================================
# ONE MAP HEADERS
# ============================================================

def onemap_headers():
    return {
        "Authorization": ONEMAP_TOKEN
    }


# ============================================================
# BASIC VALIDATION
# ============================================================

def valid_coordinate(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


# ============================================================
# SEARCH ONE MAP
# ============================================================

def search_onemap(location):

    """
    Search OneMap for a user-entered location.

    We try a few harmless variations so that inputs such as:

        Blk 441 Clementi Ave 3
        441 Clementi Ave 3
        441 Clementi Ave 3

    have a better chance of returning results.

    OneMap itself performs the actual geocoding.
    """

    # Remove unnecessary whitespace
    location = " ".join(location.strip().split())

    # Don't search an empty string
    if not location:
        return []

    search_variants = [
        location
    ]

    # If user starts with "Blk", also try without it.
    if location.lower().startswith("blk "):

        without_blk = location[4:].strip()

        if without_blk:
            search_variants.append(without_blk)

    # Remove commas as another harmless variation
    no_commas = location.replace(",", " ")

    if no_commas not in search_variants:
        search_variants.append(no_commas)

    all_results = []

    for search_value in search_variants:

        params = {
            "searchVal": search_value,
            "returnGeom": "Y",
            "getAddrDetails": "Y",
            "pageNum": 1
        }

        try:

            response = requests.get(
                SEARCH_URL,
                params=params,
                headers=onemap_headers(),
                timeout=10
            )

        except requests.RequestException:
            continue

        if response.status_code != 200:
            continue

        try:
            data = response.json()
        except ValueError:
            continue

        results = data.get("results", [])

        for result in results:

            try:

                lat = float(result["LATITUDE"])
                lon = float(result["LONGITUDE"])

            except (KeyError, TypeError, ValueError):
                continue

            item = {
                "name": result.get("SEARCHVAL"),
                "address": result.get("ADDRESS"),
                "postal_code": result.get("POSTAL"),
                "lat": lat,
                "lon": lon
            }

            # Avoid duplicate results
            duplicate = False

            for existing in all_results:

                if (
                    abs(existing["lat"] - lat) < 0.0000001
                    and
                    abs(existing["lon"] - lon) < 0.0000001
                ):
                    duplicate = True
                    break

            if not duplicate:
                all_results.append(item)

    # Only return a reasonable number of choices
    return all_results[:5]


# ============================================================
# SEARCH ENDPOINT
# ============================================================

@app.route("/search", methods=["GET"])
def search_location():

    location = request.args.get("location")

    if location is None:
        return jsonify({
            "error": "Please provide a location."
        }), 400

    location = location.strip()

    if not location:
        return jsonify({
            "error": "Location cannot be empty."
        }), 400

    results = search_onemap(location)

    if not results:
        return jsonify({
            "query": location,
            "results": [],
            "message": (
                "No matching locations were found. "
                "Try an address, building name, road name "
                "or postal code."
            )
        }), 404

    return jsonify({
        "query": location,
        "results": results
    })


# ============================================================
# NORMALISE NEARBY TRANSPORT RESULTS
# ============================================================

def extract_transport_results(data):

    """
    OneMap's nearby transport API returns transport records.

    This function makes the rest of our code tolerant of the
    response being either:

        [ {...}, {...} ]

    or a dictionary containing a list of records.
    """

    if isinstance(data, list):
        return data

    if isinstance(data, dict):

        # Try common list-style fields
        for key in [
            "results",
            "GeocodeInfo",
            "data",
            "stops",
            "stations"
        ]:

            value = data.get(key)

            if isinstance(value, list):
                return value

    return []


# ============================================================
# GET NEARBY MRT / LRT STATIONS
# ============================================================

def get_nearby_mrt(lat, lon):

    params = {
        "latitude": lat,
        "longitude": lon,
        "radius_in_meters": SEARCH_RADIUS_METERS
    }

    try:

        response = requests.get(
            NEAREST_MRT_URL,
            params=params,
            headers=onemap_headers(),
            timeout=10
        )

    except requests.RequestException as e:

        return {
            "success": False,
            "error": f"MRT API request failed: {str(e)}",
            "results": []
        }

    if response.status_code != 200:

        return {
            "success": False,
            "error": (
                f"MRT API returned HTTP "
                f"{response.status_code}: {response.text}"
            ),
            "results": []
        }

    try:
        data = response.json()
    except ValueError:

        return {
            "success": False,
            "error": "MRT API returned invalid JSON.",
            "results": []
        }

    raw_results = extract_transport_results(data)

    results = []

    for station in raw_results:

        try:

            station_lat = float(
                station.get("lat")
            )

            station_lon = float(
                station.get("lon")
            )

        except (TypeError, ValueError):

            continue

        results.append({
            "id": station.get("id"),
            "name": station.get("name"),
            "road": station.get("road"),
            "lat": station_lat,
            "lon": station_lon
        })

    return {
        "success": True,
        "error": None,
        "results": results
    }


# ============================================================
# GET NEARBY BUS STOPS
# ============================================================

def get_nearby_bus_stops(lat, lon):

    params = {
        "latitude": lat,
        "longitude": lon,
        "radius_in_meters": SEARCH_RADIUS_METERS
    }

    try:

        response = requests.get(
            NEAREST_BUS_URL,
            params=params,
            headers=onemap_headers(),
            timeout=10
        )

    except requests.RequestException as e:

        return {
            "success": False,
            "error": f"Bus API request failed: {str(e)}",
            "results": []
        }

    if response.status_code != 200:

        return {
            "success": False,
            "error": (
                f"Bus API returned HTTP "
                f"{response.status_code}: {response.text}"
            ),
            "results": []
        }

    try:
        data = response.json()
    except ValueError:

        return {
            "success": False,
            "error": "Bus API returned invalid JSON.",
            "results": []
        }

    raw_results = extract_transport_results(data)

    results = []

    for bus_stop in raw_results:

        try:

            stop_lat = float(
                bus_stop.get("lat")
            )

            stop_lon = float(
                bus_stop.get("lon")
            )

        except (TypeError, ValueError):

            continue

        results.append({
            "id": bus_stop.get("id"),
            "name": bus_stop.get("name"),
            "road": bus_stop.get("road"),
            "lat": stop_lat,
            "lon": stop_lon
        })

    return {
        "success": True,
        "error": None,
        "results": results
    }


# ============================================================
# HAVERSINE DISTANCE
# ============================================================

def haversine_distance(lat1, lon1, lat2, lon2):

    """
    Calculate straight-line distance between two
    latitude/longitude points in metres.

    This is NOT used as the final walking distance.
    It is only used to sort/filter nearby candidates
    before calling the walking-routing API.
    """

    earth_radius = 6371000

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    delta_lat = math.radians(lat2 - lat1)

    delta_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_lat / 2) ** 2
        +
        math.cos(lat1)
        * math.cos(lat2)
        * math.sin(delta_lon / 2) ** 2
    )

    c = 2 * math.atan2(
        math.sqrt(a),
        math.sqrt(1 - a)
    )

    return earth_radius * c


# ============================================================
# WALKING ROUTE
# ============================================================

def get_walking_route(
    start_lat,
    start_lon,
    end_lat,
    end_lon
):

    params = {
        "start": f"{start_lat},{start_lon}",
        "end": f"{end_lat},{end_lon}",
        "routeType": "walk"
    }

    try:

        response = requests.get(
            ROUTING_URL,
            params=params,
            headers=onemap_headers(),
            timeout=15
        )

    except requests.RequestException as e:

        return {
            "success": False,
            "error": f"Routing API request failed: {str(e)}"
        }

    if response.status_code != 200:

        return {
            "success": False,
            "error": (
                f"Routing API returned HTTP "
                f"{response.status_code}: {response.text}"
            )
        }

    try:
        data = response.json()
    except ValueError:

        return {
            "success": False,
            "error": "Routing API returned invalid JSON."
        }

    route_summary = data.get("route_summary")

    if not route_summary:

        return {
            "success": False,
            "error": data.get(
                "status_message",
                "No walking route found."
            )
        }

    distance = route_summary.get("total_distance")
    duration = route_summary.get("total_time")

    if distance is None or duration is None:

        return {
            "success": False,
            "error": "Walking route did not contain distance/time."
        }

    return {
        "success": True,
        "error": None,
        "distance_m": float(distance),
        "duration_seconds": float(duration),
        "duration_minutes": float(duration) / 60
    }


# ============================================================
# FIND BEST WALKING ROUTE
# ============================================================

def find_nearest_by_walking(
    user_lat,
    user_lon,
    candidates
):

    """
    Take nearby MRT/bus candidates and calculate actual
    walking routes to them.

    We then choose the candidate with the shortest
    walking distance.

    This is more useful for your project than simply
    choosing the geographically closest point.
    """

    if not candidates:

        return None

    # First use straight-line distance to avoid routing
    # to obviously farther candidates.
    for candidate in candidates:

        candidate["straight_line_distance_m"] = (
            haversine_distance(
                user_lat,
                user_lon,
                candidate["lat"],
                candidate["lon"]
            )
        )

    candidates = sorted(
        candidates,
        key=lambda x: x["straight_line_distance_m"]
    )

    candidates = candidates[
        :MAX_TRANSPORT_CANDIDATES
    ]

    routed_candidates = []

    for candidate in candidates:

        route = get_walking_route(
            user_lat,
            user_lon,
            candidate["lat"],
            candidate["lon"]
        )

        if not route["success"]:
            continue

        result = candidate.copy()

        result["walking_distance_m"] = (
            route["distance_m"]
        )

        result["walking_time_minutes"] = (
            route["duration_minutes"]
        )

        routed_candidates.append(result)

    if not routed_candidates:
        return None

    # Choose the shortest actual walking distance
    routed_candidates.sort(
        key=lambda x: x["walking_distance_m"]
    )

    return routed_candidates[0]


# ============================================================
# TRANSPORT SCORE
# ============================================================

def calculate_transport_score(
    mrt_minutes,
    bus_minutes
):

    """
    Score based on the closest walking option.

        <= 5 min   -> 10
        <= 10 min  -> 8
        <= 15 min  -> 6
        <= 20 min  -> 4
        > 20 min   -> 2

    If neither MRT nor bus can be reached by walking route,
    return None.
    """

    available_times = []

    if mrt_minutes is not None:
        available_times.append(mrt_minutes)

    if bus_minutes is not None:
        available_times.append(bus_minutes)

    if not available_times:
        return None

    closest_minutes = min(available_times)

    if closest_minutes <= 5:
        return 10

    elif closest_minutes <= 10:
        return 8

    elif closest_minutes <= 15:
        return 6

    elif closest_minutes <= 20:
        return 4

    else:
        return 2


# ============================================================
# TRANSPORT ENDPOINT
# ============================================================

@app.route("/transport", methods=["GET"])
def transport():

    lat = request.args.get("lat")
    lon = request.args.get("lon")

    # --------------------------------------------------------
    # Validate coordinates
    # --------------------------------------------------------

    if lat is None or lon is None:

        return jsonify({
            "error": (
                "Please provide both latitude and longitude."
            )
        }), 400

    if not valid_coordinate(lat) or not valid_coordinate(lon):

        return jsonify({
            "error": (
                "Latitude and longitude must be valid numbers."
            )
        }), 400

    lat = float(lat)
    lon = float(lon)

    # Singapore approximate coordinate bounds.
    #
    # This prevents accidental calls such as:
    # /transport?lat=100&lon=500
    if not (
        1.15 <= lat <= 1.50
        and
        103.55 <= lon <= 104.10
    ):

        return jsonify({
            "error": (
                "The coordinates do not appear to be "
                "within Singapore."
            )
        }), 400


    # --------------------------------------------------------
    # FIND NEARBY MRT
    # --------------------------------------------------------

    mrt_data = get_nearby_mrt(
        lat,
        lon
    )


    # --------------------------------------------------------
    # FIND NEARBY BUS STOPS
    # --------------------------------------------------------

    bus_data = get_nearby_bus_stops(
        lat,
        lon
    )


    # --------------------------------------------------------
    # FIND ACTUAL WALKING-NEAREST MRT
    # --------------------------------------------------------

    nearest_mrt = None

    if mrt_data["success"]:

        nearest_mrt = find_nearest_by_walking(
            lat,
            lon,
            mrt_data["results"]
        )


    # --------------------------------------------------------
    # FIND ACTUAL WALKING-NEAREST BUS STOP
    # --------------------------------------------------------

    nearest_bus = None

    if bus_data["success"]:

        nearest_bus = find_nearest_by_walking(
            lat,
            lon,
            bus_data["results"]
        )


    # --------------------------------------------------------
    # GET WALKING TIMES
    # --------------------------------------------------------

    mrt_minutes = None

    if nearest_mrt:

        mrt_minutes = nearest_mrt[
            "walking_time_minutes"
        ]


    bus_minutes = None

    if nearest_bus:

        bus_minutes = nearest_bus[
            "walking_time_minutes"
        ]


    # --------------------------------------------------------
    # CALCULATE TRANSPORT SCORE
    # --------------------------------------------------------

    transport_score = calculate_transport_score(
        mrt_minutes,
        bus_minutes
    )


    # --------------------------------------------------------
    # RETURN RESPONSE
    # --------------------------------------------------------

    return jsonify({

        "user_location": {
            "lat": lat,
            "lon": lon
        },

        "nearest_mrt": nearest_mrt,

        "nearest_bus_stop": nearest_bus,

        "transport_score": transport_score,

        "api_status": {
            "mrt_search": mrt_data["success"],
            "bus_search": bus_data["success"]
        },

        "errors": {
            "mrt": mrt_data["error"],
            "bus": bus_data["error"]
        }
    })


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/", methods=["GET"])
def home():

    return jsonify({
        "message": "SC2006 Transport Backend is running.",
        "endpoints": {
            "search": "/search?location=YOUR_LOCATION",
            "transport": "/transport?lat=LAT&lon=LON"
        }
    })


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )