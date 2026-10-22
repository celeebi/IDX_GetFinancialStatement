"""
HTTP client for communicating with IDX endpoints with Cloudflare bypass.
Uses curl_cffi to match browser TLS and HTTP/2 fingerprints.
"""

import os
import time
import random
import logging
from typing import Optional, Dict, Any
from curl_cffi import requests

logger = logging.getLogger("idx_scraper.client")

BASE_URL = "https://www.idx.co.id"
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9,id;q=0.8",
    "Referer": "https://www.idx.co.id/id/perusahaan-tercatat/laporan-keuangan-dan-tahunan",
}


class IDXClient:
    """Session-based HTTP client for IDX with anti-bot handling and retries."""

    def __init__(self, request_delay: float = 0.6, max_retries: int = 4, impersonate: str = "chrome131"):
        self.request_delay = request_delay
        self.max_retries = max_retries
        self.impersonate = impersonate
        self.session = requests.Session(impersonate=self.impersonate)
        self.session.headers.update(DEFAULT_HEADERS)
        self._last_request_time = 0.0

    def _throttle(self):
        """Enforce polite rate limiting between consecutive calls."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.request_delay:
            sleep_time = (self.request_delay - elapsed) + random.uniform(0.05, 0.2)
            time.sleep(sleep_time)

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 25) -> requests.Response:
        """Perform a GET request with automatic retry and rate-limiting."""
        if not url.startswith("http"):
            url = BASE_URL + ("/" if not url.startswith("/") else "") + url

        request_headers = {}
        if headers:
            request_headers.update(headers)

        for attempt in range(1, self.max_retries + 1):
            self._throttle()
            try:
                self._last_request_time = time.time()
                resp = self.session.get(url, params=params, headers=request_headers, timeout=timeout)
                
                # Check status
                if resp.status_code == 200:
                    return resp
                elif resp.status_code in (429, 502, 503, 504):
                    wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                    logger.warning(f"HTTP {resp.status_code} received from {url}. Retrying in {wait:.1f}s (Attempt {attempt}/{self.max_retries})...")
                    time.sleep(wait)
                elif resp.status_code == 403:
                    # Cloudflare challenge or forbidden
                    wait = (2 ** attempt) + random.uniform(1.0, 2.0)
                    logger.warning(f"HTTP 403 Forbidden on {url}. Renewing session and retrying in {wait:.1f}s...")
                    self.session = requests.Session(impersonate=self.impersonate)
                    self.session.headers.update(DEFAULT_HEADERS)
                    time.sleep(wait)
                else:
                    resp.raise_for_status()
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error(f"Failed to fetch {url} after {self.max_retries} attempts: {e}")
                    raise
                wait = (2 ** attempt) + random.uniform(0.5, 1.5)
                logger.warning(f"Request error: {e}. Retrying in {wait:.1f}s (Attempt {attempt}/{self.max_retries})...")
                time.sleep(wait)

        raise RuntimeError(f"Unable to complete GET request to {url}")

    def download_file(self, file_path_or_url: str, dest_path: str, overwrite: bool = False) -> bool:
        """
        Download a remote file from IDX to local disk.
        Returns True if newly downloaded, False if skipped (already exists).
        """
        if os.path.exists(dest_path) and not overwrite:
            if os.path.getsize(dest_path) > 0:
                logger.info(f"File already exists: {dest_path}. Skipping.")
                return False

        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        resp = self.get(file_path_or_url)
        with open(dest_path, "wb") as f:
            f.write(resp.content)
        logger.info(f"Saved: {dest_path} ({len(resp.content):,} bytes)")
        return True
