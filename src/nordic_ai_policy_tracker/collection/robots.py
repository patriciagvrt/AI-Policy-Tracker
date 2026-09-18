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
