import hashlib

import pytest

from velox.fetch import Fetched, fetch, utc_now


class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200):
        self.content = content
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_utc_now_is_iso8601_zulu():
    stamp = utc_now()
    assert stamp.endswith("Z")
    assert "T" in stamp
    assert len(stamp) == 20


def test_fetch_hashes_content(monkeypatch):
    payload = b"hello autovelox"
    monkeypatch.setattr("velox.fetch.requests.get", lambda *a, **k: _FakeResponse(payload))
    result = fetch("https://example.invalid/x.pdf")
    assert isinstance(result, Fetched)
    assert result.content == payload
    assert result.sha256 == hashlib.sha256(payload).hexdigest()
    assert result.url == "https://example.invalid/x.pdf"


def test_fetch_retries_then_raises(monkeypatch):
    calls = {"n": 0}

    def _boom(*a, **k):
        calls["n"] += 1
        raise OSError("network down")

    monkeypatch.setattr("velox.fetch.requests.get", _boom)
    monkeypatch.setattr("velox.fetch.time.sleep", lambda _s: None)
    with pytest.raises(OSError):
        fetch("https://example.invalid/x.pdf", retries=3)
    assert calls["n"] == 3


def test_fetch_rejects_empty_body(monkeypatch):
    monkeypatch.setattr("velox.fetch.requests.get", lambda *a, **k: _FakeResponse(b""))
    monkeypatch.setattr("velox.fetch.time.sleep", lambda _s: None)
    with pytest.raises(ValueError):
        fetch("https://example.invalid/x.pdf")
