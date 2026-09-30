"""Adapter for data.gov.sg: tabular datastore_search and the poll-based file download."""
import time

import requests

from gowhere.adapters.http import HttpError, RateLimiter, get_json

DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"
POLL_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{id}/poll-download"
INITIATE_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{id}/initiate-download"


class DataGovAdapter:
    def __init__(self, session=None, min_interval_s=1.0, sleep=time.sleep):
        self.session = session or requests.Session()
        self.limiter = RateLimiter(min_interval_s, sleep=sleep)
        self._sleep = sleep

    def datastore_pages(self, resource_id, page_size=1000):
        """Return every page response for a tabular dataset, unmodified, in order."""
        pages, offset = [], 0
        while True:
            page = get_json(self.session, DATASTORE_URL,
                            params={"resource_id": resource_id, "limit": page_size, "offset": offset},
                            limiter=self.limiter, sleep=self._sleep)
            if not page.get("success"):
                raise HttpError(f"datastore_search failed for {resource_id}: {page}")
            pages.append(page)
            total = page["result"]["total"]
            offset += len(page["result"]["records"])
            if offset >= total or not page["result"]["records"]:
                return pages

    def download_file(self, dataset_id, max_polls=20):
        """Download a file dataset (e.g. GeoJSON) via initiate/poll; returns parsed JSON."""
        get_json(self.session, INITIATE_DOWNLOAD_URL.format(id=dataset_id),
                 limiter=self.limiter, sleep=self._sleep)
        for _ in range(max_polls):
            poll = get_json(self.session, POLL_DOWNLOAD_URL.format(id=dataset_id),
                            limiter=self.limiter, sleep=self._sleep)
            url = (poll.get("data") or {}).get("url")
            if url:
                return get_json(self.session, url, limiter=self.limiter, sleep=self._sleep)
            self._sleep(3)
        raise HttpError(f"download for {dataset_id} never became ready")
