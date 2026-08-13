"""HTTP fetching with retries, content hashing, and an explicit empty-body rejection.

An empty response is treated as a failure, not as "no data": the whole pipeline
depends on absence never being mistaken for emptiness.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests

USER_AGENT = "velox-italia/0.1 (+https://github.com/tfcfun/ftc-autovelox)"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Fetched:
    url: str
    content: bytes
    sha256: str
    fetched_at: str


def fetch(url: str, *, timeout: int = 60, retries: int = 3) -> Fetched:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            response = requests.get(
                url, timeout=timeout, headers={"User-Agent": USER_AGENT}
            )
            response.raise_for_status()
            content = response.content
            if not content:
                raise ValueError(f"empty body from {url}")
            return Fetched(
                url=url,
                content=content,
                sha256=hashlib.sha256(content).hexdigest(),
                fetched_at=utc_now(),
            )
        except Exception as exc:  # noqa: BLE001 - retried and re-raised below
            last = exc
            if attempt < retries - 1:
                time.sleep(2**attempt)
    assert last is not None
    raise last
