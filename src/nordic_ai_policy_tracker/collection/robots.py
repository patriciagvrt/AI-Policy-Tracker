"""robots.txt checking.

Kept as its own module (rather than folded into crawler.py) because it's a
discrete, easily-testable concern: given a URL and a user agent, is this
collector allowed to fetch it? Python's standard library already has a
robots.txt parser (urllib.robotparser), so we wrap that rather than writing
our own.
"""

from __future__ import annotations

import urllib.robotparser
from urllib.parse import urljoin, urlparse

import requests


def get_robots_txt_url(url: str) -> str:
    parsed = urlparse(url)
    return urljoin(f"{parsed.scheme}://{parsed.netloc}", "/robots.txt")


def is_allowed(url: str, user_agent: str, timeout_seconds: int = 10) -> bool | None:
    """Check whether `user_agent` may fetch `url` per that site's robots.txt.

    Returns:
        True if allowed, False if disallowed, and None if robots.txt could
        not be retrieved or parsed (e.g. the site has none, or it errored).
        A caller should treat None conservatively -- this project's crawler
        treats "unknown" as "proceed, but record robots_allowed=None" rather
        than silently assuming permission, so the ambiguity is visible in
        the data rather than hidden.
    """
    robots_url = get_robots_txt_url(url)
    parser = urllib.robotparser.RobotFileParser()
    try:
        response = requests.get(
            robots_url, timeout=timeout_seconds, headers={"User-Agent": user_agent}
        )
        if response.status_code == 404:
            # No robots.txt published -- conventionally this means "allowed".
            return True
        if response.status_code >= 400:
            return None
        parser.parse(response.text.splitlines())
    except requests.RequestException:
        return None

    try:
        return parser.can_fetch(user_agent, url)
    except Exception:
        return None


def get_sitemap_urls(url: str, user_agent: str, timeout_seconds: int = 10) -> list[str]:
    """Return sitemap URLs declared in this site's robots.txt (the ``Sitemap:``
    directive), or an empty list if robots.txt is unreachable, unparsable, or
    declares none.

    This is intentionally separate from is_allowed() above: a caller doing
    discovery (rather than fetching a single already-known URL) needs the
    list of sitemaps, not just a yes/no answer for one path. Written
    defensively -- a malformed or unreachable robots.txt yields an empty
    list rather than raising, matching is_allowed()'s "unknown means don't
    crash the caller" philosophy.
    """
    robots_url = get_robots_txt_url(url)
    try:
        response = requests.get(
            robots_url, timeout=timeout_seconds, headers={"User-Agent": user_agent}
        )
        if response.status_code >= 400:
            return []
        sitemap_urls: list[str] = []
        for line in response.text.splitlines():
            stripped = line.strip()
            if stripped.lower().startswith("sitemap:"):
                sitemap_url = stripped.split(":", 1)[1].strip()
                if sitemap_url:
                    sitemap_urls.append(sitemap_url)
        return sitemap_urls
    except requests.RequestException:
        return []
