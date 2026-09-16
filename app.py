from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv

# ============================================================
# SETUP
# ============================================================

load_dotenv()

app = Flask(__name__)
CORS(app)

ONEMAP_TOKEN = os.getenv("ONEMAP_TOKEN")

if not ONEMAP_TOKEN:
    raise Exception("ONEMAP_TOKEN not found in .env")


# ============================================================
# ONE-MAP HELPER
# ============================================================

def onemap_headers():

    return {
        "Authorization": ONEMAP_TOKEN
    }


# ============================================================
# 1. SEARCH FOR USER'S LOCATION
# ============================================================

@app.route("/search")
def search_location():

    location = request.args.get("location")

    if not location:

        return jsonify({
            "error": "Please provide a location."
        }), 400


    url = (
        "https://www.onemap.gov.sg/"
        "api/common/elastic/search"
    )


    params = {

        "searchVal": location,

        "returnGeom": "Y",

        "getAddrDetails": "Y",

        "pageNum": 1
    }


    try:

        response = requests.get(
            url,
            params=params,
            headers=onemap_headers()
        )


        if response.status_code != 200:

            return jsonify({
                "error": "OneMap search failed.",
                "status": response.status_code
            }), 500


        data = response.json()


        # ----------------------------------------------------
        # NO RESULTS
        # ----------------------------------------------------

        if data.get("found", 0) == 0:

            return jsonify({
                "error":
                f'Could not find "{location}".'
            }), 404


        # ----------------------------------------------------
        # RETURN MULTIPLE RESULTS
        #
        # This is better than blindly taking result #1.
        # For example, "NTU" might have multiple matches.
        # ----------------------------------------------------

        results = []


        for result in data["results"][:5]:

            results.append({

                "name":
                    result.get("SEARCHVAL"),

                "address":
                    result.get("ADDRESS"),

                "lat":
                    float(result["LATITUDE"]),

                "lon":
                    float(result["LONGITUDE"])

            })


        return jsonify({

            "query": location,

            "results": results

        })


    except requests.RequestException as e:

        return jsonify({

            "error":
                "Could not connect to OneMap.",

            "details":
                str(e)

        }), 500


# ============================================================
# 2. FIND NEARBY MRT STATIONS
# ============================================================

@app.route("/nearby-mrt")
def nearby_mrt():

    try:

        latitude = float(
            request.args.get("lat")
        )

        longitude = float(
            request.args.get("lon")
        )

    except (TypeError, ValueError):

        return jsonify({

            "error":
                "Invalid latitude or longitude."

        }), 400


    url = (
        "https://www.onemap.gov.sg/"
        "api/public/nearbysvc/"
        "getNearestMrtStops"
    )


    params = {

        "latitude": latitude,

        "longitude": longitude,

        "radius_in_meters": 2000

    }


    try:

        response = requests.get(

            url,

            params=params,

            headers=onemap_headers()

        )


        if response.status_code != 200:

            return jsonify({

                "error":
                    "OneMap MRT search failed.",

                "status":
                    response.status_code

            }), 500


        data = response.json()


        return jsonify(data)


    except requests.RequestException as e:

        return jsonify({

            "error":
                "Could not connect to OneMap.",

            "details":
                str(e)

        }), 500


# ============================================================
# 3. WALKING ROUTE
# ============================================================

@app.route("/walking-route")
def walking_route():

    try:

        start_lat = float(
            request.args.get("startLat")
        )

        start_lon = float(
            request.args.get("startLon")
        )

        end_lat = float(
            request.args.get("endLat")
        )

        end_lon = float(
            request.args.get("endLon")
        )

    except (TypeError, ValueError):

        return jsonify({

            "error":
                "Invalid coordinates."

        }), 400


    url = (
        "https://www.onemap.gov.sg/"
        "api/public/routingsvc/route"
    )


    params = {

        "start":
            f"{start_lat},{start_lon}",

        "end":
            f"{end_lat},{end_lon}",

        "routeType":
            "walk"

    }


    try:

        response = requests.get(

            url,

            params=params,

            headers=onemap_headers()

        )


        if response.status_code != 200:

            return jsonify({

                "error":
                    "OneMap routing failed.",

                "status":
                    response.status_code

            }), 500


        data = response.json()


        summary = data["route_summary"]


        return jsonify({

            "distance":
                summary["total_distance"],

            "time":
                summary["total_time"] / 60

        })


    except requests.RequestException as e:

        return jsonify({

            "error":
                "Could not connect to OneMap.",

            "details":
                str(e)

        }), 500


# ============================================================
# 4. FIND NEAREST MRT
#
# This combines:
#
#     nearby MRT
#          +
#     walking route
#
# ============================================================

@app.route("/nearest-mrt")
def nearest_mrt():

    try:

        latitude = float(
            request.args.get("lat")
        )

        longitude = float(
            request.args.get("lon")
        )

    except (TypeError, ValueError):

        return jsonify({

            "error":
                "Invalid latitude or longitude."

        }), 400


    # --------------------------------------------------------
    # STEP 1
    # Get nearby MRT stations
    # --------------------------------------------------------

    mrt_url = (
        "https://www.onemap.gov.sg/"
        "api/public/nearbysvc/"
        "getNearestMrtStops"
    )


    mrt_params = {

        "latitude":
            latitude,

        "longitude":
            longitude,

        "radius_in_meters":
            2000

    }


    try:

        response = requests.get(

            mrt_url,

            params=mrt_params,

            headers=onemap_headers()

        )


        if response.status_code != 200:

            return jsonify({

                "error":
                    "Could not find MRT stations."

            }), 500


        stations = response.json()


    except requests.RequestException as e:

        return jsonify({

            "error":
                "Could not connect to OneMap.",

            "details":
                str(e)

        }), 500


    # --------------------------------------------------------
    # STEP 2
    # Calculate walking route to every MRT
    # --------------------------------------------------------

    routes = []


    for station in stations:

        try:

            station_lat = float(
                station["lat"]
            )

            station_lon = float(
                station["lon"]
            )


            route_url = (
                "https://www.onemap.gov.sg/"
                "api/public/routingsvc/route"
            )


            route_params = {

                "start":
                    f"{latitude},{longitude}",

                "end":
                    f"{station_lat},{station_lon}",

                "routeType":
                    "walk"

            }


            route_response = requests.get(

                route_url,

                params=route_params,

                headers=onemap_headers()

            )


            if route_response.status_code != 200:

                continue


            route_data = route_response.json()


            summary = (
                route_data["route_summary"]
            )


            distance = (
                summary["total_distance"]
            )


            time_minutes = (
                summary["total_time"] / 60
            )


            routes.append({

                "name":
                    station["name"],

                "lat":
                    station_lat,

                "lon":
                    station_lon,

                "distance":
                    distance,

                "time":
                    time_minutes

            })


        except Exception as e:

            print(
                "Could not route to station:",
                e
            )


    # --------------------------------------------------------
    # STEP 3
    # Make sure we found something
    # --------------------------------------------------------

    if not routes:

        return jsonify({

            "error":
                "Could not calculate any MRT routes."

        }), 404


    # --------------------------------------------------------
    # STEP 4
    # Sort by walking distance
    # --------------------------------------------------------

    routes.sort(
        key=lambda x: x["distance"]
    )


    nearest = routes[0]


    # --------------------------------------------------------
    # STEP 5
    # Return nearest station + alternatives
    # --------------------------------------------------------

    return jsonify({

        "nearest": nearest,

        "alternatives":
            routes[1:5]

    })


# ============================================================
# 5. TRANSPORT SCORE
# ============================================================

def calculate_transport_score(
    walking_minutes
):

    if walking_minutes <= 5:

        return 10

    elif walking_minutes <= 10:

        return 8

    elif walking_minutes <= 15:

        return 6

    elif walking_minutes <= 20:

        return 4

    else:

        return 2


# ============================================================
# 6. COMPLETE ENDPOINT
#
# User provides:
#
#     "Clementi Mall"
#
# Backend:
#
#     Search location
#          ↓
#     Coordinates
#          ↓
#     Nearby MRT
#          ↓
#     Walking routes
#          ↓
#     Nearest MRT
#          ↓
#     Transport score
# ============================================================

@app.route("/transport")
def transport():

    location = request.args.get("location")

    if not location:

        return jsonify({

            "error":
                "Please provide a location."

        }), 400


    # --------------------------------------------------------
    # SEARCH LOCATION
    # --------------------------------------------------------

    search_url = (
        "https://www.onemap.gov.sg/"
        "api/common/elastic/search"
    )


    search_params = {

        "searchVal":
            location,

        "returnGeom":
            "Y",

        "getAddrDetails":
            "Y",

        "pageNum":
            1

    }


    try:

        search_response = requests.get(

            search_url,

            params=search_params,

            headers=onemap_headers()

        )


        data = search_response.json()


        if data.get("found", 0) == 0:

            return jsonify({

                "error":
                    f'Could not find "{location}".'

            }), 404


        selected = data["results"][0]


        latitude = float(
            selected["LATITUDE"]
        )

        longitude = float(
            selected["LONGITUDE"]
        )


        # ----------------------------------------------------
        # FIND NEAREST MRT
        # ----------------------------------------------------

        mrt_url = (
            "https://www.onemap.gov.sg/"
            "api/public/nearbysvc/"
            "getNearestMrtStops"
        )


        mrt_params = {

            "latitude":
                latitude,

            "longitude":
                longitude,

            "radius_in_meters":
                2000

        }


        mrt_response = requests.get(

            mrt_url,

            params=mrt_params,

            headers=onemap_headers()

        )


        stations = mrt_response.json()


        routes = []


        # ----------------------------------------------------
        # ROUTE TO EVERY MRT
        # ----------------------------------------------------

        for station in stations:

            station_lat = float(
                station["lat"]
            )

            station_lon = float(
                station["lon"]
            )


            route_url = (
                "https://www.onemap.gov.sg/"
                "api/public/routingsvc/route"
            )


            route_params = {

                "start":
                    f"{latitude},{longitude}",

                "end":
                    f"{station_lat},{station_lon}",

                "routeType":
                    "walk"

            }


            route_response = requests.get(

                route_url,

                params=route_params,

                headers=onemap_headers()

            )


            if route_response.status_code != 200:

                continue


            route_data = route_response.json()


            summary = (
                route_data["route_summary"]
            )


            distance = (
                summary["total_distance"]
            )


            time_minutes = (
                summary["total_time"] / 60
            )


            routes.append({

                "name":
                    station["name"],

                "distance":
                    distance,

                "time":
                    time_minutes,

                "lat":
                    station_lat,

                "lon":
                    station_lon

            })


        # ----------------------------------------------------
        # NO ROUTES
        # ----------------------------------------------------

        if not routes:

            return jsonify({

                "error":
                    "Could not calculate MRT routes."

            }), 404


        # ----------------------------------------------------
        # SORT
        # ----------------------------------------------------

        routes.sort(
            key=lambda x: x["distance"]
        )


        nearest = routes[0]


        # ----------------------------------------------------
        # CALCULATE SCORE
        # ----------------------------------------------------

        score = calculate_transport_score(
            nearest["time"]
        )


        # ----------------------------------------------------
        # FINAL RESPONSE
        # ----------------------------------------------------

        return jsonify({

            "starting_location": {

                "name":
                    selected["SEARCHVAL"],

                "address":
                    selected.get("ADDRESS"),

                "latitude":
                    latitude,

                "longitude":
                    longitude

            },

            "nearest_mrt": {

                "name":
                    nearest["name"],

                "walking_distance":
                    round(
                        nearest["distance"]
                    ),

                "walking_time":
                    round(
                        nearest["time"],
                        1
                    ),

                "transport_score":
                    score

            },

            "other_mrt_options":
                routes[1:5]

        })


    except requests.RequestException as e:

        return jsonify({

            "error":
                "OneMap request failed.",

            "details":
                str(e)

        }), 500


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )