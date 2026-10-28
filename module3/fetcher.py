# -*- coding: utf-8 -*-
"""HTTP 抓取層：UA、timeout、retry/backoff、per-host 限速、robots.txt。

設計要點：
  - transport 可注入（`transport(url, ua, timeout) -> (status, body)`），
    所以喺冇網絡嘅環境都可以完整測試 retry / 429 / 5xx 行為。
  - robots.txt 有 cache，尊重 Disallow。
  - 限速係 per-host（同一 host 最小間隔），clock / sleep 可注入。
"""
from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlparse

DEFAULT_UA = "PrizeIntelBot/0.1 (+https://example.com/bot; contact=ops@example.com)"
RETRY_STATUS = {429, 500, 502, 503, 504}


@dataclass
class FetchResult:
    url: str
    status: str                      # ok / http_error / network_error / blocked_by_robots
    http_status: int | None = None
    html: str | None = None
    attempts: int = 0
    elapsed_ms: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.status == "ok"


def urllib_transport(url: str, ua: str, timeout: int) -> tuple[int, str]:
    """預設 transport。回傳 (status_code, body)。網絡錯誤會 raise OSError。"""
    req = urllib.request.Request(url, headers={
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "ja,en;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return resp.status, raw.decode(charset, errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except urllib.error.URLError as e:
        raise OSError(str(e.reason)) from e


class RateLimiter:
    """per-host 最小間隔。"""

    def __init__(self, min_interval: float = 1.0,
                 clock=time.monotonic, sleep=time.sleep):
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self.sleeps: list[float] = []      # 測試用

    def wait(self, url: str) -> float:
        host = urlparse(url).netloc
        now = self._clock()
        last = self._last.get(host)
        waited = 0.0
        if last is not None:
            gap = now - last
            if gap < self.min_interval:
                waited = round(self.min_interval - gap, 4)
                self._sleep(waited)
                self.sleeps.append(waited)
                now = self._clock()
        self._last[host] = now
        return waited


def parse_robots(text: str) -> list[str]:
    """抽 User-agent: * 嘅 Disallow 規則（夠用嘅極簡版）。"""
    disallows: list[str] = []
    applies = False
    for raw in (text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip().lower(), val.strip()
        if key == "user-agent":
            applies = val == "*"
        elif key == "disallow" and applies:
            if val:
                disallows.append(val)
    return disallows


class RobotsCache:
    def __init__(self, transport, ua: str, timeout: int = 10, ttl: int = 3600,
                 clock=time.monotonic):
        self._transport = transport
        self._ua = ua
        self._timeout = timeout
        self._ttl = ttl
        self._clock = clock
        self._cache: dict[str, tuple[float, list[str]]] = {}

    def _rules(self, host_root: str) -> list[str]:
        hit = self._cache.get(host_root)
        now = self._clock()
        if hit and now - hit[0] < self._ttl:
            return hit[1]
        try:
            status, body = self._transport(host_root + "/robots.txt", self._ua, self._timeout)
            rules = parse_robots(body) if status == 200 else []
        except OSError:
            rules = []          # robots.txt 攞唔到 → 當冇限制（業界慣例）
        self._cache[host_root] = (now, rules)
        return rules

    def is_allowed(self, url: str) -> bool:
        p = urlparse(url)
        root = f"{p.scheme}://{p.netloc}"
        path = p.path or "/"
        for rule in self._rules(root):
            if rule == "/":
                return False
            if path.startswith(rule):
                return False
        return True


class HttpFetcher:
    def __init__(self, ua: str = DEFAULT_UA, timeout: int = 20,
                 max_attempts: int = 3, backoff: float = 0.5,
                 transport=urllib_transport, limiter: RateLimiter | None = None,
                 robots: RobotsCache | None = None,
                 sleep=time.sleep, clock=time.monotonic):
        self.ua = ua
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.backoff = backoff
        self._transport = transport
        self.limiter = limiter
        self.robots = robots
        self._sleep = sleep
        self._clock = clock

    def get(self, url: str) -> FetchResult:
        if self.robots and not self.robots.is_allowed(url):
            return FetchResult(url, "blocked_by_robots", error="robots.txt disallow")

        start = self._clock()
        last_err = None
        last_status: int | None = None
        for attempt in range(1, self.max_attempts + 1):
            if self.limiter:
                self.limiter.wait(url)
            status: int | None
            try:
                status, body = self._transport(url, self.ua, self.timeout)
            except OSError as e:
                last_err = f"network: {e}"
                status, body = None, ""

            if status == 200:
                return FetchResult(url, "ok", http_status=200, html=body,
                                   attempts=attempt,
                                   elapsed_ms=int((self._clock() - start) * 1000))

            last_status = status
            if status is not None:
                last_err = f"http {status}"
                # 4xx（除 429）唔值得重試
                if status not in RETRY_STATUS:
                    break
            if attempt < self.max_attempts:
                self._sleep(self.backoff * (2 ** (attempt - 1)))
                continue

        kind = "http_error" if (last_err or "").startswith("http") else "network_error"
        return FetchResult(url, kind, http_status=last_status if kind == "http_error" else None,
                           attempts=attempt,
                           elapsed_ms=int((self._clock() - start) * 1000),
                           error=last_err)
