"""Policy-source candidate discovery.

Finds candidate pages/documents on each institution's own official domain
(and genuine subdomains of it) that MIGHT be relevant AI-guidance material,
and writes them (with a transparent, explainable relevance score and an
inferred category) to a candidates CSV for human review. This module never
selects a final source and never writes to config/sources_full.csv -- see
docs/candidate_discovery.md.

Design constraints (see scripts/discover_policy_candidates.py and
docs/candidate_discovery.md for the full rationale, including the Iceland
pilot-run corrections this module was rewritten to fix):
  * Search is confined to each institution's own official domain and its
    genuine subdomains (e.g. setberg.hi.is for hi.is) -- never a general
    web search, and never a domain that merely CONTAINS the official
    domain as a substring (hi.is.evil.example is rejected).
  * robots.txt is always checked, per host, before fetching a candidate
    URL.
  * Official sitemaps are used when robots.txt declares one; a
    well-known /sitemap.xml fallback is tried otherwise, for the main
    domain and for each discovered subdomain.
  * A bounded, single-hop homepage link crawl supplements the sitemap, so
    institutions without a usable sitemap are not skipped entirely.
  * Per-institution page fetches are capped (default 25) -- this is
    discovery, not full collection.
  * A page is only ever written out as a candidate if it matches at
    least one STRONG AI-specific term (see search_terms.STRONG_TERMS):
    generic higher-ed vocabulary (exams, teaching, student guidance, ...)
    can raise a score a little but can never, by itself, create a
    candidate -- see score_candidate() and its use below.
  * Scoring is a small, fully documented, deterministic point formula
    with a human-readable explanation string -- no BERTopic, no
    embeddings, no REI/PISI, and a high score is never treated as
    automatic approval.
  * A dry-run/fixture mode (fixture_root) lets the whole pipeline run
    against local files with no network access at all, for tests and for
    environments with no outbound access to arbitrary domains.
"""

from __future__ import annotations

import csv
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from nordic_ai_policy_tracker.collection import robots as robots_module
from nordic_ai_policy_tracker.collection.html_extractor import extract_main_text, extract_title
from nordic_ai_policy_tracker.collection.pdf_extractor import extract_text_from_pdf_bytes
from nordic_ai_policy_tracker.discovery.search_terms import (
    ALL_SEARCH_TERMS,
    CONTEXTUAL_TERMS,
    POLICY_SIGNAL_TERMS,
    STRONG_TERMS,
)
from nordic_ai_policy_tracker.utils.logging import get_logger

logger = get_logger(__name__)

TEXT_PREVIEW_CHARS = 500
MAX_MATCHED_TERMS_RECORDED = 20
MAX_EXTRA_SUBDOMAINS_PER_INSTITUTION = 5

CANDIDATE_CSV_FIELDS = [
    "institution_id",
    "institution_name",
    "country",
    "candidate_url",
    "final_url",
    "page_title",
    "content_type",
    "discovery_method",
    "inferred_category",
    "matched_terms",
    "relevance_score",
    "score_explanation",
    "text_preview",
    "robots_allowed",
    "http_status",
    "checked_at",
]


# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------


@dataclass
class DiscoveryConfig:
    """Everything discovery needs, distinct from the live-collection settings
    in config/settings_full_study.yaml (which this is normally built from --
    see build_config_from_settings)."""

    user_agent: str
    request_delay_seconds: float
    request_timeout_seconds: int
    max_retries: int = 2
    max_candidate_pages_per_institution: int = 25
    max_sitemap_files_per_institution: int = 5
    max_sitemap_urls_considered: int = 2000
    # Broad net used only to decide which URLs are worth fetching at all.
    search_terms: list[str] = field(default_factory=lambda: list(ALL_SEARCH_TERMS))
    # When set, no real HTTP requests are made at all: every fetch is
    # resolved from local files under this directory instead. See
    # _FixtureTransport below and docs/candidate_discovery.md.
    fixture_root: Path | None = None


def build_config_from_settings(
    settings: dict, fixture_root: str | Path | None = None
) -> DiscoveryConfig:
    collection_cfg = settings["collection"]
    return DiscoveryConfig(
        user_agent=collection_cfg["user_agent"],
        request_delay_seconds=collection_cfg["request_delay_seconds"],
        request_timeout_seconds=collection_cfg["request_timeout_seconds"],
        max_retries=collection_cfg.get("max_retries", 2),
        fixture_root=Path(fixture_root) if fixture_root else None,
    )


# --------------------------------------------------------------------------
# URL normalization / dedup
# --------------------------------------------------------------------------


def normalize_url(url: str) -> str:
    """Canonical form used for deduplication only -- never used as the URL
    that's actually fetched or recorded. Lowercases scheme+host, drops the
    fragment, drops a trailing slash (except for the bare root path), and
    strips a default port.
    """
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[: -len(":80")]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[: -len(":443")]
    path = parsed.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def dedupe_urls(urls: list[str]) -> tuple[list[str], int]:
    """Return (deduplicated URLs, count removed), preserving first-seen order."""
    seen: dict[str, str] = {}
    for url in urls:
        key = normalize_url(url)
        if key not in seen:
            seen[key] = url
    removed = len(urls) - len(seen)
    return list(seen.values()), removed


def _host_of(url: str) -> str:
    return urlparse(url).netloc.lower().split(":")[0]


def _registrable_domain(host: str) -> str:
    """Last two DNS labels of a hostname, used as a simple stand-in for the
    registrable domain. This works correctly for every domain this project
    currently searches (all Nordic institutions use a single-label ccTLD --
    .is, .se, .no, .dk, .fi -- so "setberg.hi.is" and "www.hi.is" both
    reduce to "hi.is"). It would need refinement (e.g. a public-suffix
    list) for a multi-label TLD such as "ac.uk", which this project does
    not currently search.
    """
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    return ".".join(labels[-2:])


def is_same_domain(url: str, domain_root: str) -> bool:
    """True if `url`'s host is the institution's own official domain or a
    genuine subdomain of it (e.g. setberg.hi.is for hi.is), compared by
    registrable domain (see _registrable_domain).

    This intentionally rejects a deceptive host that merely CONTAINS the
    official domain as a substring or prefix, such as hi.is.evil.example
    or hi.is.example.com -- both reduce to a *different* registrable
    domain (evil.example / example.com respectively), so they are never
    mistaken for a genuine hi.is subdomain.
    """
    return _registrable_domain(_host_of(url)) == _registrable_domain(_host_of(domain_root))


# --------------------------------------------------------------------------
# Term matching (left-word-boundary, not arbitrary substring)
# --------------------------------------------------------------------------

_TERM_PATTERN_CACHE: dict[str, re.Pattern] = {}


def _term_pattern(term: str) -> re.Pattern:
    pattern = _TERM_PATTERN_CACHE.get(term)
    if pattern is None:
        # A word boundary is required immediately BEFORE the term, but not
        # necessarily after it. This is deliberate, not a half-measure:
        #   - it still rejects a short/ambiguous term like "llm" matching
        #     inside an unrelated word, e.g. the surname "Kollmar" (there
        #     is no boundary between "Ko" and "llm" there -- both sides are
        #     word characters);
        #   - it still accepts Icelandic inflected/compound forms, e.g.
        #     "gervigreind" matching inside "gervigreindarinnar" (a
        #     grammatical case ending glued directly onto the stem, with
        #     no space) -- requiring a boundary on BOTH sides would wrongly
        #     reject the vast majority of real Icelandic usage.
        # See tests/test_candidate_discovery.py for the Kollmar regression
        # test this specifically fixes.
        pattern = re.compile(r"\b" + re.escape(term), re.IGNORECASE)
        _TERM_PATTERN_CACHE[term] = pattern
    return pattern


def match_terms(text: str, terms: list[str]) -> list[str]:
    """Return the subset of `terms` that appear in `text` with a left word
    boundary (see _term_pattern), in the order given in `terms` (not text
    order) so results are deterministic and easy to diff between runs.
    """
    return [term for term in terms if _term_pattern(term).search(text)]


def _url_slug(url: str) -> str:
    return re.sub(r"[-_/]+", " ", urlparse(url).path.lower())


def url_looks_relevant(url: str, terms: list[str]) -> bool:
    """A lightweight pre-filter used only to decide which sitemap/homepage
    URLs are worth actually fetching (see max_candidate_pages_per_institution)
    -- it is not the relevance score itself, and it deliberately casts a
    broad net (strong + contextual + policy-signal terms) so a page is
    never silently skipped before it has a chance to be scored and
    gated by score_candidate() below.
    """
    return bool(match_terms(_url_slug(url), terms))


# --------------------------------------------------------------------------
# Category inference (policy / guidance / news / research / course / event)
# --------------------------------------------------------------------------

# Bare substrings, not slash-delimited segments -- real institutional
# sites hyphenate freely (e.g. Bifrost's own news path is
# "/frettir-og-tilkynningar/", not a clean "/frettir/" segment), so a
# slash-wrapped check misses exactly the pages this category exists to
# catch. See the real Iceland run: several dated Bifrost announcements
# under that hyphenated path were originally mis-categorized "guidance".
NEWS_URL_SEGMENTS = ["frettir", "fréttir", "news", "tilkynning"]
RESEARCH_URL_SEGMENTS = ["rannsokn", "rannsókn", "research"]
COURSE_URL_SEGMENTS = ["namskeid", "námskeið", "/course/", "/courses/"]
EVENT_URL_SEGMENTS = ["vidburd", "viðburð", "/event/", "/events/"]


def classify_category(url: str, title: str, matched_strong: list[str]) -> str:
    """Infer a coarse category for human review -- never used to silently
    drop a candidate (see docs/candidate_discovery.md); "news" is labeled
    and penalized, not excluded (score_candidate below), so an AI news
    item is still a discoverable lead for a researcher who wants one.
    """
    path = urlparse(url).path.lower()
    title_lower = title.lower()

    if any(segment in path for segment in NEWS_URL_SEGMENTS):
        return "news"
    if match_terms(path, POLICY_SIGNAL_TERMS) or match_terms(title, POLICY_SIGNAL_TERMS):
        return "policy"
    if any(segment in path for segment in RESEARCH_URL_SEGMENTS) or "rannsókn" in title_lower:
        return "research"
    if any(segment in path for segment in COURSE_URL_SEGMENTS):
        return "course"
    if any(segment in path for segment in EVENT_URL_SEGMENTS):
        return "event"
    if matched_strong:
        return "guidance"
    return "unknown"


# --------------------------------------------------------------------------
# Transport: real HTTP, or a local-fixture stand-in for dry-run/tests
# --------------------------------------------------------------------------


@dataclass
class FetchResult:
    status_code: int
    text: str
    content: bytes
    headers: dict
    final_url: str


class _FixtureTransport:
    """Resolves every 'fetch' from local files under fixture_root, with no
    network access at all. See tests/fixtures/discovery/ for the expected
    layout: <fixture_root>/<netloc>/robots.txt, .../sitemap.xml, and one
    file per page path (see _fixture_path_for_url).
    """

    def __init__(self, fixture_root: Path):
        self.fixture_root = fixture_root

    def _fixture_path_for_url(self, url: str) -> Path:
        parsed = urlparse(url)
        path = parsed.path or "/"
        if path == "/":
            path = "/index.html"
        rel = path.lstrip("/")
        return self.fixture_root / parsed.netloc / rel

    def get(self, url: str, **_kwargs) -> FetchResult:
        path = self._fixture_path_for_url(url)
        if not path.exists():
            # Clean/extensionless URLs (e.g. "/en/ai-guidance-for-students")
            # are stored as "<path>.html" in the fixture tree -- try that
            # before giving up, mirroring how a real webserver would map a
            # clean URL to a static file.
            html_path = (
                path.with_suffix(path.suffix + ".html")
                if path.suffix
                else path.with_name(path.name + ".html")
            )
            if html_path.exists():
                path = html_path
            else:
                return FetchResult(status_code=404, text="", content=b"", headers={}, final_url=url)
        content = path.read_bytes()
        content_type = "application/pdf" if path.suffix == ".pdf" else "text/html; charset=utf-8"
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = ""
        return FetchResult(
            status_code=200,
            text=text,
            content=content,
            headers={"Content-Type": content_type},
            final_url=url,
        )


class _HttpTransport:
    def __init__(self, user_agent: str, timeout_seconds: int):
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    def get(self, url: str, **_kwargs) -> FetchResult:
        response = requests.get(
            url, headers={"User-Agent": self.user_agent}, timeout=self.timeout_seconds
        )
        return FetchResult(
            status_code=response.status_code,
            text=response.text if response.status_code < 400 else "",
            content=response.content if response.status_code < 400 else b"",
            headers=dict(response.headers),
            final_url=response.url,
        )


# --------------------------------------------------------------------------
# Sitemap handling
# --------------------------------------------------------------------------


def _parse_sitemap_xml(xml_text: str) -> tuple[list[str], list[str]]:
    """Return (page_urls, nested_sitemap_urls) from one sitemap document,
    handling both <urlset> (a page listing) and <sitemapindex> (a listing
    of other sitemaps) per the standard sitemap protocol. Malformed XML
    yields ([], []) rather than raising -- one bad sitemap must not stop
    discovery for the rest of the institution's candidates.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return [], []

    tag = root.tag.rsplit("}", 1)[-1].lower()
    page_urls: list[str] = []
    nested_sitemaps: list[str] = []

    for child in root:
        child_tag = child.tag.rsplit("}", 1)[-1].lower()
        if child_tag not in ("url", "sitemap"):
            continue
        loc = None
        for grandchild in child:
            gtag = grandchild.tag.rsplit("}", 1)[-1].lower()
            if gtag == "loc" and grandchild.text:
                loc = grandchild.text.strip()
                break
        if loc is None:
            continue
        if tag == "sitemapindex" or child_tag == "sitemap":
            nested_sitemaps.append(loc)
        else:
            page_urls.append(loc)

    return page_urls, nested_sitemaps


def discover_sitemap_page_urls(
    transport, sitemap_urls: list[str], config: DiscoveryConfig
) -> tuple[list[str], list[str]]:
    """Fetch each declared sitemap (following one level of <sitemapindex>
    nesting), returning (all page urls found, sitemap urls actually
    fetched successfully). Bounded by max_sitemap_files_per_institution so
    a very large sitemap index can't turn discovery into a full crawl.
    """
    fetched: list[str] = []
    all_page_urls: list[str] = []
    queue = list(sitemap_urls)[: config.max_sitemap_files_per_institution]

    while queue and len(fetched) < config.max_sitemap_files_per_institution:
        sitemap_url = queue.pop(0)
        try:
            result = transport.get(sitemap_url)
        except requests.RequestException as exc:
            logger.warning("Could not fetch sitemap %s: %s", sitemap_url, exc)
            continue
        if result.status_code != 200:
            continue
        fetched.append(sitemap_url)
        page_urls, nested = _parse_sitemap_xml(result.text)
        all_page_urls.extend(page_urls)
        for nested_url in nested:
            if len(fetched) + len(queue) < config.max_sitemap_files_per_institution:
                queue.append(nested_url)

    return all_page_urls[: config.max_sitemap_urls_considered], fetched


# --------------------------------------------------------------------------
# Homepage single-hop link crawl (fallback / supplement)
# --------------------------------------------------------------------------


def discover_homepage_links(transport, domain_root: str) -> list[str]:
    """Fetch the homepage and return same-domain (including subdomain)
    links found on it. A single hop only -- this supplements the sitemap,
    it is not a crawler.
    """
    try:
        result = transport.get(domain_root)
    except requests.RequestException as exc:
        logger.warning("Could not fetch homepage %s: %s", domain_root, exc)
        return []
    if result.status_code != 200 or not result.text:
        return []
    soup = BeautifulSoup(result.text, "lxml")
    links: list[str] = []
    for a in soup.find_all("a", href=True):
        href = urljoin(domain_root, a["href"])
        if is_same_domain(href, domain_root) and href.startswith(("http://", "https://")):
            links.append(href)
    return links


def discover_subdomain_pages(
    transport, homepage_links: list[str], domain_root: str, config: DiscoveryConfig
) -> tuple[list[tuple[str, str]], list[str]]:
    """For any homepage link that points to a genuine subdomain of the
    institution's domain (e.g. setberg.hi.is for hi.is) rather than the
    exact host in domain_root, also consider that subdomain's own
    homepage and (bounded) its own sitemap -- institutions sometimes run
    an AI-guidance portal entirely on a dedicated subdomain that the main
    site's own sitemap never lists (this is the fix for the real-world
    finding that hi.is returned zero candidates despite relevant material
    existing under setberg.hi.is).

    Returns (extra_urls_with_method, sitemap_urls_fetched). Bounded to
    MAX_EXTRA_SUBDOMAINS_PER_INSTITUTION distinct subdomains so this can't
    turn into an unbounded crawl of every subdomain an institution owns.
    """
    root_host = _host_of(domain_root)
    extra_hosts = sorted(
        {
            _host_of(link)
            for link in homepage_links
            if _host_of(link) and _host_of(link) != root_host and is_same_domain(link, domain_root)
        }
    )[:MAX_EXTRA_SUBDOMAINS_PER_INSTITUTION]

    extra_urls: list[tuple[str, str]] = []
    sitemaps_fetched: list[str] = []
    for host in extra_hosts:
        subdomain_root = f"https://{host}/"
        extra_urls.append((subdomain_root, "subdomain_homepage"))
        sub_page_urls, fetched = discover_sitemap_page_urls(
            transport, [urljoin(subdomain_root, "/sitemap.xml")], config
        )
        sitemaps_fetched.extend(fetched)
        extra_urls.extend((u, "subdomain_sitemap") for u in sub_page_urls)

    return extra_urls, sitemaps_fetched


# --------------------------------------------------------------------------
# Scoring (transparent, explainable -- see docs/candidate_discovery.md)
# --------------------------------------------------------------------------

# Point values are deliberately small integers with one clear reason each,
# recorded in a human-readable explanation string, so a reviewer can
# recompute a candidate's score by eye -- this is NOT a machine-learned or
# embedding-based score. See the module docstring for the strong/
# contextual/policy-signal split this formula is built on.
STRONG_TITLE_POINTS = 4
STRONG_URL_POINTS = 3
STRONG_PREVIEW_POINTS = 1
MAX_STRONG_PREVIEW_MATCHES = 5

CONTEXTUAL_TITLE_POINTS = 1
CONTEXTUAL_URL_POINTS = 1
# Contextual preview matches are recorded in matched_terms but award no
# points -- this is what stops a page like an "examinations" timetable
# from scoring highly on generic vocabulary alone (see module docstring).

POINTS_FOR_PDF = 1

POLICY_SIGNAL_TITLE_BOOST = 5
POLICY_SIGNAL_URL_BOOST = 3

NEWS_PENALTY = 4


@dataclass
class ScoreResult:
    score: int
    matched_terms: list[str]
    matched_strong_terms: list[str]
    category: str
    explanation: str


def score_candidate(url: str, title: str, text_preview: str, content_type: str) -> ScoreResult:
    """Score one already-fetched candidate. Returns a ScoreResult whose
    `matched_strong_terms` the caller uses to decide whether this page is
    allowed to become a candidate at all (see discover_candidates_for_institution:
    a page with zero strong-term matches is dropped, however many
    contextual terms it matches).
    """
    slug = _url_slug(url)

    title_strong = match_terms(title, STRONG_TERMS)
    url_strong = match_terms(slug, STRONG_TERMS)
    preview_strong = match_terms(text_preview, STRONG_TERMS)

    title_context = match_terms(title, CONTEXTUAL_TERMS)
    url_context = match_terms(slug, CONTEXTUAL_TERMS)
    preview_context = match_terms(text_preview, CONTEXTUAL_TERMS)

    title_policy = match_terms(title, POLICY_SIGNAL_TERMS)
    url_policy = match_terms(slug, POLICY_SIGNAL_TERMS)

    matched_strong = list(dict.fromkeys(title_strong + url_strong + preview_strong))
    matched_context = list(dict.fromkeys(title_context + url_context + preview_context))
    matched_policy = list(dict.fromkeys(title_policy + url_policy))
    matched_all = (matched_strong + matched_context + matched_policy)[:MAX_MATCHED_TERMS_RECORDED]

    category = classify_category(url, title, matched_strong)

    score = 0
    explanation_parts: list[str] = []

    strong_points = (
        STRONG_TITLE_POINTS * len(title_strong)
        + STRONG_URL_POINTS * len(url_strong)
        + STRONG_PREVIEW_POINTS * min(len(preview_strong), MAX_STRONG_PREVIEW_MATCHES)
    )
    if strong_points:
        score += strong_points
        explanation_parts.append(
            f"+{strong_points} strong AI term(s) "
            f"(title x{len(title_strong)}, url x{len(url_strong)}, preview x{min(len(preview_strong), MAX_STRONG_PREVIEW_MATCHES)})"
        )

    context_points = CONTEXTUAL_TITLE_POINTS * len(title_context) + CONTEXTUAL_URL_POINTS * len(
        url_context
    )
    if context_points:
        score += context_points
        explanation_parts.append(
            f"+{context_points} contextual term(s) (title x{len(title_context)}, url x{len(url_context)})"
        )
    elif preview_context:
        explanation_parts.append(
            f"+0 contextual term(s) in preview only (x{len(preview_context)}) -- preview matches never score"
        )

    if content_type == "pdf":
        score += POINTS_FOR_PDF
        explanation_parts.append(f"+{POINTS_FOR_PDF} PDF document")

    policy_boost = 0
    if title_policy:
        policy_boost += POLICY_SIGNAL_TITLE_BOOST
    if url_policy:
        policy_boost += POLICY_SIGNAL_URL_BOOST
    if policy_boost:
        score += policy_boost
        where = "+".join(
            p for p, matched in (("title", title_policy), ("url", url_policy)) if matched
        )
        explanation_parts.append(f"+{policy_boost} policy-signal term in {where}")

    if category == "news":
        score -= NEWS_PENALTY
        explanation_parts.append(
            f"-{NEWS_PENALTY} news/announcement page (penalized, not excluded)"
        )

    score = max(score, 0)
    if not explanation_parts:
        explanation_parts.append("+0 no scoring terms matched")

    return ScoreResult(
        score=score,
        matched_terms=matched_all,
        matched_strong_terms=matched_strong,
        category=category,
        explanation="; ".join(explanation_parts),
    )


# --------------------------------------------------------------------------
# Per-institution / overall discovery run
# --------------------------------------------------------------------------


@dataclass
class InstitutionAudit:
    institution_id: str
    institution_name: str
    country: str
    domain_root: str
    robots_txt_fetched: bool = False
    sitemaps_declared: list[str] = field(default_factory=list)
    sitemaps_fetched: list[str] = field(default_factory=list)
    sitemap_urls_found: int = 0
    homepage_links_found: int = 0
    subdomains_discovered: list[str] = field(default_factory=list)
    requests_attempted: int = 0
    candidates_found: int = 0
    pages_fetched_but_rejected_no_strong_term: int = 0
    duplicates_removed: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class DiscoveryRunResult:
    candidates: list[dict]
    institution_audits: list[InstitutionAudit]


def _content_type_for(url: str, headers: dict) -> str:
    content_type_header = headers.get("Content-Type", "")
    if "application/pdf" in content_type_header or url.lower().endswith(".pdf"):
        return "pdf"
    return "html"


def _build_robots_parser(host: str, config: DiscoveryConfig):
    """Build (uncached here -- callers should cache per host) a robots
    parser for a given host, live or from fixtures, so each host's OWN
    robots.txt is respected -- including a subdomain discovered via
    discover_subdomain_pages, which may have different rules than the
    institution's main domain.
    """
    root_url = f"https://{host}/"
    if config.fixture_root is not None:
        return _fixture_robots_parser(config.fixture_root, root_url)
    return _live_robots_parser(root_url, config.user_agent, config.request_timeout_seconds)


def discover_candidates_for_institution(
    institution: dict, config: DiscoveryConfig
) -> tuple[list[dict], InstitutionAudit]:
    domain_root = institution["official_website"]
    audit = InstitutionAudit(
        institution_id=institution["institution_id"],
        institution_name=institution["institution_name"],
        country=institution["country"],
        domain_root=domain_root,
    )

    transport = (
        _FixtureTransport(config.fixture_root)
        if config.fixture_root is not None
        else _HttpTransport(config.user_agent, config.request_timeout_seconds)
    )

    robots_parsers: dict[str, object] = {}

    def robots_parser_for(url: str):
        host = _host_of(url)
        if host not in robots_parsers:
            robots_parsers[host] = _build_robots_parser(host, config)
        return robots_parsers[host]

    # --- robots.txt + sitemap discovery (main domain) -------------------
    main_host = _host_of(domain_root)
    robots_parsers[main_host] = _build_robots_parser(main_host, config)
    audit.robots_txt_fetched = robots_parsers[main_host] is not None

    if config.fixture_root is not None:
        sitemap_urls = _fixture_sitemap_declarations(config.fixture_root, domain_root)
    else:
        sitemap_urls = robots_module.get_sitemap_urls(
            domain_root, config.user_agent, timeout_seconds=config.request_timeout_seconds
        )
    audit.sitemaps_declared = list(sitemap_urls)
    if not sitemap_urls:
        sitemap_urls = [urljoin(domain_root, "/sitemap.xml")]

    sitemap_page_urls, sitemaps_fetched = discover_sitemap_page_urls(
        transport, sitemap_urls, config
    )
    audit.sitemaps_fetched = sitemaps_fetched
    audit.sitemap_urls_found = len(sitemap_page_urls)

    # --- homepage single-hop supplement ---------------------------------
    # Gated by robots.txt just like any other page fetch below -- a
    # disallowed homepage means we don't even fetch it to look for links.
    main_robots_allowed = True
    if robots_parsers[main_host] is not None:
        try:
            main_robots_allowed = robots_parsers[main_host].can_fetch(
                config.user_agent, domain_root
            )
        except Exception:
            main_robots_allowed = True  # unknown -> don't block discovery on a parser error
    homepage_links = discover_homepage_links(transport, domain_root) if main_robots_allowed else []
    audit.homepage_links_found = len(homepage_links)

    # --- genuine-subdomain supplement (e.g. setberg.hi.is for hi.is) ----
    subdomain_urls, subdomain_sitemaps_fetched = discover_subdomain_pages(
        transport, homepage_links, domain_root, config
    )
    audit.subdomains_discovered = sorted({_host_of(u) for u, _ in subdomain_urls})
    audit.sitemaps_fetched = audit.sitemaps_fetched + subdomain_sitemaps_fetched

    all_discovered = (
        [(url, "sitemap") for url in sitemap_page_urls]
        + [(url, "homepage_link_crawl") for url in homepage_links]
        + subdomain_urls
    )
    # Always consider the institution's own homepage too.
    all_discovered.append((domain_root, "homepage"))

    raw_urls = [url for url, _ in all_discovered]
    deduped_urls, duplicates_removed = dedupe_urls(raw_urls)
    audit.duplicates_removed = duplicates_removed

    method_by_normalized = {}
    for url, method in all_discovered:
        method_by_normalized.setdefault(normalize_url(url), method)

    same_domain_urls = [u for u in deduped_urls if is_same_domain(u, domain_root)]

    # A URL is always worth checking if it's the main homepage or a
    # subdomain's own homepage (the content there may be AI-relevant even
    # when the bare root path itself contains no keyword); everything
    # else goes through the keyword pre-filter.
    always_check = {normalize_url(domain_root)} | {
        normalize_url(u) for u, method in subdomain_urls if method == "subdomain_homepage"
    }
    relevant_urls = [
        u
        for u in same_domain_urls
        if normalize_url(u) in always_check or url_looks_relevant(u, config.search_terms)
    ]
    relevant_urls = relevant_urls[: config.max_candidate_pages_per_institution]

    candidates: list[dict] = []
    for url in relevant_urls:
        if config.fixture_root is None and config.request_delay_seconds:
            time.sleep(config.request_delay_seconds)

        parser = robots_parser_for(url)
        robots_allowed: bool | None
        if parser is None:
            robots_allowed = None
        else:
            try:
                robots_allowed = parser.can_fetch(config.user_agent, url)
            except Exception:
                robots_allowed = None

        checked_at = datetime.now(UTC).isoformat()

        if robots_allowed is False:
            candidates.append(
                _candidate_row(
                    institution,
                    candidate_url=url,
                    final_url=url,
                    page_title="",
                    content_type="",
                    discovery_method=method_by_normalized.get(normalize_url(url), "unknown"),
                    score_result=ScoreResult(
                        score=0,
                        matched_terms=[],
                        matched_strong_terms=[],
                        category="unknown",
                        explanation="robots.txt disallowed -- not fetched",
                    ),
                    text_preview="",
                    robots_allowed=False,
                    http_status=None,
                    checked_at=checked_at,
                )
            )
            continue

        audit.requests_attempted += 1
        try:
            result = transport.get(url)
        except requests.RequestException as exc:
            audit.errors.append(f"{url}: {exc}")
            continue

        if result.status_code == 404:
            continue
        if result.status_code >= 400:
            audit.errors.append(f"{url}: HTTP {result.status_code}")
            continue

        content_type = _content_type_for(url, result.headers)
        if content_type == "pdf":
            text = extract_text_from_pdf_bytes(result.content)
            title = ""
        else:
            text = extract_main_text(result.text) if result.text else ""
            title = (extract_title(result.text) or "") if result.text else ""

        text_preview = text[:TEXT_PREVIEW_CHARS]
        score_result = score_candidate(url, title, text_preview, content_type)

        if not score_result.matched_strong_terms:
            # Requirement: generic/contextual terms alone must never
            # create a candidate -- see search_terms.py and the module
            # docstring. The page was fetched (so it's reflected in
            # requests_attempted/errors for audit purposes) but is not
            # written out as a row.
            audit.pages_fetched_but_rejected_no_strong_term += 1
            continue

        candidates.append(
            _candidate_row(
                institution,
                candidate_url=url,
                final_url=result.final_url,
                page_title=title,
                content_type=content_type,
                discovery_method=method_by_normalized.get(normalize_url(url), "unknown"),
                score_result=score_result,
                text_preview=text_preview,
                robots_allowed=robots_allowed,
                http_status=result.status_code,
                checked_at=checked_at,
            )
        )

    audit.candidates_found = len(candidates)
    return candidates, audit


def _candidate_row(
    institution: dict,
    *,
    candidate_url: str,
    final_url: str,
    page_title: str,
    content_type: str,
    discovery_method: str,
    score_result: ScoreResult,
    text_preview: str,
    robots_allowed: bool | None,
    http_status: int | None,
    checked_at: str,
) -> dict:
    return {
        "institution_id": institution["institution_id"],
        "institution_name": institution["institution_name"],
        "country": institution["country"],
        "candidate_url": candidate_url,
        "final_url": final_url,
        "page_title": page_title,
        "content_type": content_type,
        "discovery_method": discovery_method,
        "inferred_category": score_result.category,
        "matched_terms": ";".join(score_result.matched_terms),
        "relevance_score": score_result.score,
        "score_explanation": score_result.explanation,
        "text_preview": text_preview.replace("\n", " ").strip(),
        "robots_allowed": "" if robots_allowed is None else str(robots_allowed),
        "http_status": "" if http_status is None else str(http_status),
        "checked_at": checked_at,
    }


def _live_robots_parser(domain_root: str, user_agent: str, timeout_seconds: int):
    import urllib.robotparser

    robots_url = robots_module.get_robots_txt_url(domain_root)
    parser = urllib.robotparser.RobotFileParser()
    try:
        response = requests.get(
            robots_url, timeout=timeout_seconds, headers={"User-Agent": user_agent}
        )
        if response.status_code == 404:
            parser.parse([])  # no robots.txt published -- treat as allow-all
            return parser
        if response.status_code >= 400:
            return None
        parser.parse(response.text.splitlines())
        return parser
    except requests.RequestException:
        return None


def _fixture_robots_parser(fixture_root: Path, domain_root: str):
    import urllib.robotparser

    netloc = urlparse(domain_root).netloc
    robots_path = fixture_root / netloc / "robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    if not robots_path.exists():
        parser.parse([])
        return parser
    parser.parse(robots_path.read_text(encoding="utf-8").splitlines())
    return parser


def _fixture_sitemap_declarations(fixture_root: Path, domain_root: str) -> list[str]:
    netloc = urlparse(domain_root).netloc
    robots_path = fixture_root / netloc / "robots.txt"
    if not robots_path.exists():
        return []
    sitemap_urls = []
    for line in robots_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            sitemap_urls.append(stripped.split(":", 1)[1].strip())
    return sitemap_urls


# --------------------------------------------------------------------------
# Institution registry loading
# --------------------------------------------------------------------------


def load_institutions_for_discovery(csv_path: str | Path, country: str | None = None) -> list[dict]:
    """Read config/institutions_full.csv and return rows as plain dicts,
    optionally filtered by country. Rows with no official_website are
    skipped (with a warning) rather than raising, since discovery has
    nothing to search without a domain.
    """
    rows: list[dict] = []
    with Path(csv_path).open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if country and row.get("country") != country:
                continue
            if not row.get("official_website", "").strip():
                logger.warning(
                    "Skipping %s: no official_website in institutions_full.csv",
                    row.get("institution_id"),
                )
                continue
            rows.append(row)
    return rows


# --------------------------------------------------------------------------
# Top-level run + output writing
# --------------------------------------------------------------------------


def run_discovery(institutions: list[dict], config: DiscoveryConfig) -> DiscoveryRunResult:
    all_candidates: list[dict] = []
    audits: list[InstitutionAudit] = []
    for institution in institutions:
        logger.info(
            "Discovering candidates for %s (%s)...",
            institution["institution_name"],
            institution["official_website"],
        )
        candidates, audit = discover_candidates_for_institution(institution, config)
        all_candidates.extend(candidates)
        audits.append(audit)
        logger.info("  -> %d candidate(s)", len(candidates))
    return DiscoveryRunResult(candidates=all_candidates, institution_audits=audits)


def write_candidates_csv(candidates: list[dict], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(
        candidates, key=lambda c: (-int(c["relevance_score"] or 0), c["institution_id"])
    )
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CANDIDATE_CSV_FIELDS)
        writer.writeheader()
        for row in ordered:
            writer.writerow(row)


def write_audit_report(
    result: DiscoveryRunResult, output_path: str | Path, country_label: str
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = []
    lines.append(f"# Policy-source candidate discovery report -- {country_label}")
    lines.append("")
    lines.append(f"Generated: {datetime.now(UTC).isoformat()}")
    lines.append("")
    lines.append(
        "**This report describes discovery only.** Every row in "
        "data/candidates/source_candidates.csv is a candidate for human "
        "review -- none has been added to config/sources_full.csv, and no "
        "candidate is automatically approved regardless of its relevance "
        "score. See docs/candidate_discovery.md."
    )
    lines.append("")

    lines.append("## Institutions searched")
    lines.append("")
    for audit in result.institution_audits:
        lines.append(
            f"- {audit.institution_name} (`{audit.institution_id}`) -- {audit.domain_root}"
        )
    lines.append("")

    lines.append("## Per-institution detail")
    lines.append("")
    total_requests = 0
    total_candidates = 0
    total_duplicates = 0
    total_errors = 0
    total_rejected_no_strong_term = 0
    for audit in result.institution_audits:
        total_requests += audit.requests_attempted
        total_candidates += audit.candidates_found
        total_duplicates += audit.duplicates_removed
        total_errors += len(audit.errors)
        total_rejected_no_strong_term += audit.pages_fetched_but_rejected_no_strong_term

        lines.append(f"### {audit.institution_name} (`{audit.institution_id}`)")
        lines.append("")
        lines.append(f"- Domain searched: {audit.domain_root}")
        lines.append(f"- robots.txt reachable: {audit.robots_txt_fetched}")
        lines.append(
            f"- Sitemaps declared in robots.txt: {audit.sitemaps_declared or '(none declared)'}"
        )
        lines.append(f"- Sitemaps successfully fetched: {audit.sitemaps_fetched or '(none)'}")
        lines.append(f"- URLs found via sitemap(s): {audit.sitemap_urls_found}")
        lines.append(f"- Links found via homepage single-hop crawl: {audit.homepage_links_found}")
        lines.append(
            f"- Genuine subdomains discovered and also searched: {audit.subdomains_discovered or '(none)'}"
        )
        lines.append(f"- Duplicate URLs removed: {audit.duplicates_removed}")
        lines.append(
            f"- Requests attempted (post-dedup, keyword-filtered): {audit.requests_attempted}"
        )
        lines.append(
            f"- Pages fetched but rejected (no strong AI-specific term matched): "
            f"{audit.pages_fetched_but_rejected_no_strong_term}"
        )
        lines.append(f"- Candidates found: {audit.candidates_found}")
        if audit.errors:
            lines.append(f"- Errors ({len(audit.errors)}):")
            for err in audit.errors:
                lines.append(f"  - {err}")
        else:
            lines.append("- Errors: none")
        lines.append("")

    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Institutions searched: {len(result.institution_audits)}")
    lines.append(f"- Requests attempted: {total_requests}")
    lines.append(f"- Candidates found: {total_candidates}")
    lines.append(
        f"- Pages fetched but rejected (contextual terms only, no strong AI term): {total_rejected_no_strong_term}"
    )
    lines.append(f"- Duplicate URLs removed: {total_duplicates}")
    lines.append(f"- Errors: {total_errors}")
    lines.append("")

    lines.append("## Candidate scores (all candidates, highest first)")
    lines.append("")
    lines.append(
        "| institution_id | relevance_score | category | content_type | discovery_method | matched_terms | candidate_url |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    ordered = sorted(
        result.candidates, key=lambda c: (-int(c["relevance_score"] or 0), c["institution_id"])
    )
    for c in ordered:
        lines.append(
            f"| {c['institution_id']} | {c['relevance_score']} | {c['inferred_category']} | {c['content_type']} | "
            f"{c['discovery_method']} | {c['matched_terms']} | {c['candidate_url']} |"
        )
    lines.append("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
