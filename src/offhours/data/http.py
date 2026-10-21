"""Polite HTTP: fixed pause between calls, retries with exponential backoff."""

from __future__ import annotations

import logging
import time

import requests

from offhours.config import cfg

log = logging.getLogger(__name__)
_session = requests.Session()


def request(
    method: str,
    url: str,
    *,
    sleep: float = 0.5,
    max_retries: int = 5,
    ok_statuses: tuple[int, ...] = (200,),
    **kwargs,
) -> requests.Response:
    """Send a request, sleeping `sleep` seconds first and retrying on errors.

    Retries on connection errors, 429 and 5xx with backoff 2, 4, 8, ... seconds. Statuses in
    `ok_statuses` are returned to the caller (e.g. 404 for a non-trading day's Reg SHO file).
    """
    headers = {"User-Agent": cfg()["http"]["user_agent"], **kwargs.pop("headers", {})}
    for attempt in range(max_retries):
        time.sleep(sleep)
        try:
            resp = _session.request(method, url, headers=headers, timeout=120, **kwargs)
        except requests.RequestException as exc:
            log.warning("%s %s failed (%s); retry %d", method, url, exc, attempt + 1)
        else:
            if resp.status_code in ok_statuses:
                return resp
            if resp.status_code != 429 and resp.status_code < 500:
                resp.raise_for_status()
            log.warning("%s %s -> %d; retry %d", method, url, resp.status_code, attempt + 1)
        time.sleep(2 ** (attempt + 1))
    raise RuntimeError(f"giving up on {method} {url} after {max_retries} attempts")
