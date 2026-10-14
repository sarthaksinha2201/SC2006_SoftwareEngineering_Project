"""Adapter for LTA DataMall: live carpark availability (an External Service, called at
request time; DECISIONS.md section 4), and the static bus stop and bus route lists the
offline ETL reads for the Public Transport factor's Bus option.

    GET https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2
    header AccountKey: <LTA_DATAMALL_KEY>, paged 500 records at a time with $skip.
    {"value": [{"CarParkID", "Area", "Development", "Location": "lat lon",
                "AvailableLots", "LotType": "C"|"Y"|"H", "Agency"}]}

Needs LTA_DATAMALL_KEY in .env. Nobody has registered for one yet, so the adapter is
built from DataMall's documented format and tested with fixtures; without a key every
call raises HttpError, which the parking service turns into "Parking information
unavailable".
"""
import os
import time

import requests

from gowhere.adapters.http import HttpError, get_json

BASE_URL = "https://datamall2.mytransport.sg/ltaodataservice/"
CARPARK_URL = BASE_URL + "CarParkAvailabilityv2"
BUS_STOPS = "BusStops"            # ~5,200 stops
BUS_ROUTES = "BusRoutes"          # ~26,000 (service, direction, stop) rows
PAGE = 500
MAX_PAGES = 20          # ~2,500 carparks today; stops a paging bug from looping forever
MAX_STATIC_PAGES = 200  # bus routes need ~53 pages


class DataMallAdapter:
    def __init__(self, session=None, key=None, sleep=time.sleep):
        self.session = session or requests.Session()
        self.key = key if key is not None else os.getenv("LTA_DATAMALL_KEY")
        self._sleep = sleep

    def pages(self, endpoint, max_pages=MAX_PAGES, retries=1, timeout_s=10):
        """Every page response of a DataMall list, unmodified, in order. DataMall reports
        no total, so paging stops at the first short page; a failed page raises
        HttpError rather than ending early, so a lost page can't pass as the end."""
        if not self.key:
            raise HttpError("LTA_DATAMALL_KEY is not set")
        url = endpoint if endpoint.startswith("http") else BASE_URL + endpoint
        out = []
        for page in range(max_pages):
            response = get_json(self.session, url, params={"$skip": page * PAGE},
                                headers={"AccountKey": self.key, "accept": "application/json"},
                                retries=retries, timeout_s=timeout_s, sleep=self._sleep)
            batch = response.get("value") if isinstance(response, dict) else None
            if not isinstance(batch, list):
                raise HttpError("unexpected response shape")
            out.append(response)
            if len(batch) < PAGE:
                return out
        raise HttpError(f"{endpoint}: still full after {max_pages} pages")

    def carpark_availability(self):
        """Every carpark record, all pages. Raises HttpError on any failure."""
        return [r for p in self.pages(CARPARK_URL) for r in p["value"]]
