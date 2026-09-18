"""Main-content extraction from HTML pages.

University pages carry a lot of boilerplate around the actual policy text:
navigation menus, cookie-consent banners, footers, "related pages" widgets.
This module's job is to strip that out and return just the policy content,
using BeautifulSoup with a few heuristics rather than a heavyweight
readability library, so the logic stays easy to audit and adjust per site.
"""

from __future__ import annotations

from bs4 import BeautifulSoup

# Tags that are essentially never part of the main policy content.
BOILERPLATE_TAGS = [
    "nav",
    "header",
    "footer",
    "script",
    "style",
    "noscript",
    "svg",
    "form",
    "aside",
]

# Common class/id substrings used by university CMSs for chrome we don't want.
# Matched case-insensitively as a substring, so "cookie-banner" matches "cookie".
BOILERPLATE_CLASS_HINTS = [
    "cookie",
    "consent",
    "breadcrumb",
    "site-header",
    "site-footer",
    "skip-link",
    "skip-to-content",
    "navigation",
    "nav-menu",
    "sidebar",
    "share-buttons",
    "social-share",
    "related-content",
    "related-links",
    "search-form",
    "language-switch",
    "back-to-top",
]

# Candidate containers for main content, in priority order. The first one
# found with a reasonable amount of text wins.
MAIN_CONTENT_SELECTORS = [
    "main",
    "article",
    "[role=main]",
    "#main-content",
    "#content",
    ".main-content",
    ".content-area",
    ".page-content",
]

MIN_MAIN_CONTENT_CHARS = 200


def _strip_boilerplate(soup: BeautifulSoup) -> None:
    for tag_name in BOILERPLATE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    for hint in BOILERPLATE_CLASS_HINTS:
        for tag in soup.select(f"[class*='{hint}'], [id*='{hint}']"):
            tag.decompose()


def extract_main_text(html: str) -> str:
    """Return cleaned, boilerplate-free text extracted from an HTML page.

    Strategy: parse the page, remove known boilerplate tags/classes, then
    look for a semantic main-content container (<main>, <article>, common
    CMS class names). If none is found or it's suspiciously short, fall
    back to the whole (already-stripped) <body>, on the theory that some
    text -- even if it includes a stray widget -- beats returning nothing.
    """
    soup = BeautifulSoup(html, "lxml")
    _strip_boilerplate(soup)

    for selector in MAIN_CONTENT_SELECTORS:
        container = soup.select_one(selector)
        if container is not None:
            text = _clean_whitespace(container.get_text(separator="\n"))
            if len(text) >= MIN_MAIN_CONTENT_CHARS:
                return text

    body = soup.find("body")
    if body is not None:
        return _clean_whitespace(body.get_text(separator="\n"))
    return _clean_whitespace(soup.get_text(separator="\n"))


def extract_title(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    if h1 is not None and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    if soup.title is not None and soup.title.get_text(strip=True):
        return soup.title.get_text(strip=True)
    return None


def _clean_whitespace(text: str) -> str:
    lines = [line.strip() for line in text.splitlines()]
    non_empty = [line for line in lines if line]
    return "\n".join(non_empty)
