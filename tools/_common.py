"""Shared helpers for Stack Scout tools: paths, .env loading, cached HTTP GET.

Every network call goes through `http_get`, which caches responses in
`.tmp/cache/` so repeated runs don't burn free API rate limits.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP_DIR = ROOT / ".tmp"
CACHE_DIR = TMP_DIR / "cache"
DATA_DIR = Path(__file__).resolve().parent / "data"

USER_AGENT = "stack-scout-mcp/0.1"
DEFAULT_TTL = 6 * 60 * 60  # 6 hours


class RateLimitError(RuntimeError):
    """A free API said 'slow down'. `reset_at` is a unix timestamp when known."""

    def __init__(self, message: str, reset_at: int | None = None):
        super().__init__(message)
        self.reset_at = reset_at


class FetchError(RuntimeError):
    """Any other HTTP or network failure."""


_env_loaded = False


def load_env() -> None:
    """Load KEY=VALUE pairs from the project .env into os.environ (no overrides)."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and value:
            os.environ.setdefault(key, value)


def _cache_file(url: str) -> Path:
    return CACHE_DIR / (hashlib.sha256(url.encode("utf-8")).hexdigest()[:32] + ".json")


def http_get(url: str, headers: dict | None = None, ttl: int = DEFAULT_TTL, timeout: int = 20) -> str:
    """GET `url` and return the body as text. Cached on disk for `ttl` seconds (0 = no cache)."""
    cache_file = _cache_file(url)
    if ttl > 0 and cache_file.exists():
        try:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            if time.time() - cached["fetched_at"] < ttl:
                return cached["body"]
        except (ValueError, KeyError):
            pass  # corrupt cache entry: refetch

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")[:300]
        if e.code == 429 or (e.code == 403 and "rate limit" in detail.lower()):
            reset = e.headers.get("X-RateLimit-Reset")
            reset_at = int(reset) if reset and reset.isdigit() else None
            wait = f" Resets in ~{max(0, reset_at - int(time.time()))}s." if reset_at else ""
            raise RateLimitError(f"Rate limited by {url.split('/')[2]}.{wait}", reset_at) from e
        raise FetchError(f"HTTP {e.code} for {url}: {detail}") from e
    except urllib.error.URLError as e:
        raise FetchError(f"Network error for {url}: {e.reason}") from e

    if ttl > 0:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(
            json.dumps({"url": url, "fetched_at": time.time(), "body": body}), encoding="utf-8"
        )
    return body
