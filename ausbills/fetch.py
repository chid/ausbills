from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol

import requests

from .errors import SourceBlockedError, SourceUnavailableError


BROWSER_INSTALL_GUIDANCE = (
    'Install browser support with: pip install "ausbills[browser]" '
    "and playwright install chromium"
)


BLOCKED_MARKERS = (
    "cf-browser-verification",
    "cf-challenge",
    "cloudflare",
    "checking your browser",
    "just a moment",
    "attention required",
    "access denied",
    "akamai",
    "datadome",
    "incapsula",
    "perimeterx",
    "bobcmn",
    "tspd",
    "failureconfig",
    "challenge.support_id",
)


class Fetcher(Protocol):
    def get_text(self, url: str, **kwargs) -> str:
        ...

    def get_json(self, url: str, **kwargs) -> object:
        ...


def is_blocked_response(text: str, status_code: int | None = None) -> bool:
    if status_code in {401, 403, 429, 503}:
        return True
    lowered = (text or "").lower()
    return any(marker in lowered for marker in BLOCKED_MARKERS)


@dataclass
class RequestsFetcher:
    timeout: int = 30
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome Safari"
    )

    def __post_init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def get_text(self, url: str, **kwargs) -> str:
        try:
            response = self.session.get(url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise SourceUnavailableError(f"Could not fetch {url}: {exc}") from exc
        text = response.text
        if is_blocked_response(text, response.status_code):
            raise SourceBlockedError(f"{url} appears to require browser access")
        if response.status_code >= 400:
            raise SourceUnavailableError(f"{url} returned HTTP {response.status_code}")
        return text

    def get_json(self, url: str, **kwargs) -> object:
        text = self.get_text(url, **kwargs)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SourceUnavailableError(f"{url} did not return JSON") from exc


class BrowserFetcher:
    def __init__(self, timeout: int = 30000):
        self.timeout = timeout

    def get_text(self, url: str, **kwargs) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise SourceBlockedError(BROWSER_INSTALL_GUIDANCE) from exc

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout)
                return page.content()
            finally:
                browser.close()

    def get_json(self, url: str, **kwargs) -> object:
        text = self.get_text(url, **kwargs)
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise SourceUnavailableError(f"{url} did not return JSON") from exc


class AutoFetcher:
    def __init__(self):
        self.requests = RequestsFetcher()
        self.browser = BrowserFetcher()

    def get_text(self, url: str, **kwargs) -> str:
        try:
            return self.requests.get_text(url, **kwargs)
        except SourceBlockedError:
            return self.browser.get_text(url, **kwargs)

    def get_json(self, url: str, **kwargs) -> object:
        try:
            return self.requests.get_json(url, **kwargs)
        except SourceBlockedError:
            return self.browser.get_json(url, **kwargs)


def make_fetcher(backend: str = "auto") -> Fetcher:
    if backend == "auto":
        return AutoFetcher()
    if backend == "requests":
        return RequestsFetcher()
    if backend == "browser":
        return BrowserFetcher()
    raise ValueError("backend must be one of: auto, requests, browser")
