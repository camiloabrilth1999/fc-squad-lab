"""Cliente HTTP prudente: espaciado entre peticiones, reintentos, caché en disco."""

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from fcsl_api.settings import get_settings


class SourceBlocked(Exception):
    """La fuente respondió 403/429: no se reintenta."""


class PoliteClient:
    RETRIES = 2
    BACKOFF_S = 2.0

    def __init__(
        self,
        base_url: str,
        min_interval_s: float = 1.0,
        cache_dir: Path | None = None,
        user_agent: str = "fc-squad-lab/0.1 (uso personal)",
        headers: dict[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        wall_clock: Callable[[], float] = time.time,
    ) -> None:
        self._min_interval_s = min_interval_s
        self._cache_dir = cache_dir
        self._clock = clock
        self._sleep = sleep
        self._wall_clock = wall_clock
        self._last_request: float | None = None
        self._http = httpx.Client(
            base_url=base_url,
            headers={"User-Agent": user_agent, **(headers or {})},
            transport=transport,
            timeout=20.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._http.close()

    def _wait_turn(self) -> None:
        if self._last_request is not None:
            wait = self._min_interval_s - (self._clock() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def _cache_path(self, path: str, params: dict | None) -> Path | None:
        if self._cache_dir is None:
            return None
        query = sorted((str(k), str(v)) for k, v in (params or {}).items())
        key = f"GET {self._http.base_url}{path} {query}"
        return self._cache_dir / f"{hashlib.sha256(key.encode()).hexdigest()}.json"

    def _read_cache(self, file: Path | None, ttl_s: int) -> tuple[bool, Any]:
        if file is None or ttl_s <= 0 or not file.exists():
            return False, None
        try:
            entry = json.loads(file.read_text())
            age = self._wall_clock() - entry["fetched_at"]
        except (ValueError, KeyError, TypeError):
            return False, None
        if age < ttl_s:
            return True, entry["data"]
        return False, None

    def get_json(self, path: str, params: dict | None = None, cache_ttl_s: int = 0) -> Any:
        return self._get(path, params, cache_ttl_s, lambda r: r.json())

    def get_text(self, path: str, params: dict | None = None, cache_ttl_s: int = 0) -> str:
        """Como `get_json` pero devuelve el cuerpo como texto (p. ej. HTML)."""
        return self._get(path, params, cache_ttl_s, lambda r: r.text)

    def _get(
        self,
        path: str,
        params: dict | None,
        cache_ttl_s: int,
        decode: Callable[[httpx.Response], Any],
    ) -> Any:
        file = self._cache_path(path, params)
        hit, data = self._read_cache(file, cache_ttl_s)
        if hit:
            return data
        data = self._fetch(path, params, decode)
        if file is not None and cache_ttl_s > 0:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(json.dumps({"fetched_at": self._wall_clock(), "data": data}))
        return data

    def _fetch(
        self, path: str, params: dict | None, decode: Callable[[httpx.Response], Any]
    ) -> Any:
        for attempt in range(self.RETRIES + 1):
            self._wait_turn()
            try:
                response = self._http.get(path, params=params)
            except httpx.TransportError:
                if attempt == self.RETRIES:
                    raise
            else:
                if response.status_code in (403, 429):
                    raise SourceBlocked(f"{response.status_code} en {response.url}")
                if response.status_code < 500:
                    response.raise_for_status()
                    return decode(response)
                if attempt == self.RETRIES:
                    response.raise_for_status()
            self._sleep(self.BACKOFF_S * (attempt + 1))


def make_client(base_url: str, **kwargs: Any) -> PoliteClient:
    """PoliteClient con el User-Agent de FCSL_HTTP_USER_AGENT (salvo que se pase user_agent)."""
    kwargs.setdefault("user_agent", get_settings().http_user_agent)
    return PoliteClient(base_url, **kwargs)
