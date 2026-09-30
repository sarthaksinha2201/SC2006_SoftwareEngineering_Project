"""Adapter for LTA DataMall carpark availability (an External Service, called at
request time; DECISIONS.md section 4).

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

CARPARK_URL = "https://datamall2.mytransport.sg/ltaodataservice/CarParkAvailabilityv2"
PAGE = 500
MAX_PAGES = 20          # ~2,500 carparks today; stops a paging bug from looping forever


class DataMallAdapter:
    def __init__(self, session=None, key=None, sleep=time.sleep):
        self.session = session or requests.Session()
        self.key = key if key is not None else os.getenv("LTA_DATAMALL_KEY")
        self._sleep = sleep

    def carpark_availability(self):
        """Every carpark record, all pages. Raises HttpError on any failure."""
        if not self.key:
            raise HttpError("LTA_DATAMALL_KEY is not set")
        records = []
        for page in range(MAX_PAGES):
            response = get_json(self.session, CARPARK_URL, params={"$skip": page * PAGE},
                                headers={"AccountKey": self.key, "accept": "application/json"},
                                retries=1, timeout_s=10, sleep=self._sleep)
            batch = response.get("value") if isinstance(response, dict) else None
            if not isinstance(batch, list):
                raise HttpError("unexpected response shape")
            records.extend(batch)
            if len(batch) < PAGE:
                return records
        return records
