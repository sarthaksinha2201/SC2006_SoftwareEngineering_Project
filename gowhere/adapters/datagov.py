"""Adapter for data.gov.sg: tabular datastore_search and the poll-based file download."""
import time

import requests

from gowhere.adapters.http import HttpError, RateLimiter, get_json

DATASTORE_URL = "https://data.gov.sg/api/action/datastore_search"
POLL_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{id}/poll-download"
INITIATE_DOWNLOAD_URL = "https://api-open.data.gov.sg/v1/public/api/datasets/{id}/initiate-download"


class DataGovAdapter:
    # File downloads return HTTP 429 ("try again in 10 seconds") when requested back to
    # back, so retries start at 5 s rather than the default 2 s.
    BACKOFF_S = 5.0

    def __init__(self, session=None, min_interval_s=1.0, sleep=time.sleep):
        self.session = session or requests.Session()
        self.limiter = RateLimiter(min_interval_s, sleep=sleep)
        self._sleep = sleep

    def _get(self, url, params=None):
        return get_json(self.session, url, params=params, limiter=self.limiter,
                        backoff_s=self.BACKOFF_S, sleep=self._sleep)

    def datastore_pages(self, resource_id, page_size=1000):
        """Return every page response for a tabular dataset, unmodified, in order."""
        pages, offset = [], 0
        while True:
            page = self._get(DATASTORE_URL, params={"resource_id": resource_id,
                                                    "limit": page_size, "offset": offset})
            if not page.get("success"):
                raise HttpError(f"datastore_search failed for {resource_id}: {page}")
            pages.append(page)
            total = page["result"]["total"]
            offset += len(page["result"]["records"])
            if offset >= total or not page["result"]["records"]:
                return pages

    def download_file(self, dataset_id, max_polls=20):
        """Download a file dataset (e.g. GeoJSON) via initiate/poll; returns parsed JSON."""
        self._get(INITIATE_DOWNLOAD_URL.format(id=dataset_id))
        for _ in range(max_polls):
            poll = self._get(POLL_DOWNLOAD_URL.format(id=dataset_id))
            url = (poll.get("data") or {}).get("url")
            if url:
                return self._get(url)
            self._sleep(3)
        raise HttpError(f"download for {dataset_id} never became ready")
