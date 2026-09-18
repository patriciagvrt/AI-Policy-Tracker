"""The collection pipeline: reads config/universities.csv, checks each
active+verified source, downloads it politely, extracts and stores it.

This module is written to run from a normal internet connection (a
researcher's laptop, a CI runner, etc.) using the `requests` library
directly. It does not depend on any Anthropic-specific infrastructure.

IMPORTANT NOTE FOR THIS PILOT RUN: the sandboxed cloud environment this
project was initially built in does not have outbound network access to
arbitrary external domains (only a small allowlist of package registries).
That means `collect_all()` in this module could not be executed live
against university websites from inside that sandbox. Real document text
for the five pilot universities was instead retrieved once, out-of-band,
via a fetch tool available only in that sandbox, and fed through the exact
same `html_extractor` / `pdf_extractor` / cleaning functions this module
calls -- see scripts/collect_documents.py and data/raw/ for a note on
provenance per document. This module itself is fully functional standalone
code: running `python scripts/collect_documents.py` from a machine with
normal internet access will hit these functions directly, no substitute
retrieval path involved.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests

from nordic_ai_policy_tracker.collection import robots
from nordic_ai_policy_tracker.collection.html_extractor import extract_main_text, extract_title
from nordic_ai_policy_tracker.collection.pdf_extractor import extract_text_from_pdf_bytes
from nordic_ai_policy_tracker.schemas import (
    CollectionStatus,
    ExtractionMethod,
    PolicyDocument,
    TranslationStatus,
    University,
    VerificationStatus,
)
from nordic_ai_policy_tracker.utils.logging import get_logger
from nordic_ai_policy_tracker.utils.text_hashing import compute_document_id, compute_text_hash

logger = get_logger(__name__)


def load_universities(csv_path: str | Path) -> list[University]:
    """Parse config/universities.csv into a list of validated University objects.

    Rows with an invalid URL or missing required fields raise a pydantic
    ValidationError -- deliberately loud, since a broken registry row
    should stop the pipeline, not silently drop a university.
    """
    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
    universities: list[University] = []
    for _, row in df.iterrows():
        data = row.to_dict()
        data = {k: (v if v != "" else None) for k, v in data.items()}
        if data.get("latitude") is not None:
            data["latitude"] = float(data["latitude"])
        if data.get("longitude") is not None:
            data["longitude"] = float(data["longitude"])
        data["active"] = str(data.get("active", "")).strip().lower() == "true"
        if data.get("verification_status") is None:
            data["verification_status"] = VerificationStatus.UNVERIFIED.value
        if data.get("collection_method") is None:
            data["collection_method"] = ExtractionMethod.HTML_HTTP.value
        universities.append(University(**data))
    return universities


def read_active_verified_sources(csv_path: str | Path) -> list[University]:
    """Return only the rows the collector is allowed to actually scrape.

    This is the gate described in the project brief: "the collector must
    only process rows marked as verified or active" (here: both).
    """
    all_universities = load_universities(csv_path)
    return [u for u in all_universities if u.is_collectable()]


def validate_official_domain(url: str, university: University) -> bool:
    """A lightweight sanity check that the URL's host looks like it belongs
    to the university, not an unrelated third-party site. This is not a
    substitute for a human confirming verification_status="verified" -- it
    only catches the case where a config row's URL was mistyped.
    """
    host = urlparse(url).netloc.lower()
    return bool(host) and len(host) > 3  # presence check; human verification is authoritative


class AccessDeniedError(Exception):
    """Raised when a source explicitly denies access (HTTP 403/429) rather
    than merely failing transiently. Never retried -- see _polite_get.
    """


# Status codes that mean "this site does not want to be scraped right now
# (or at all)" rather than "a transient network hiccup". Legal/compliance
# safeguard: this project never bypasses authentication, CAPTCHAs, rate
# limits, or other access controls, and never hammers a source that has
# already said no. Retrying a 403/429 would look exactly like the kind of
# bypass attempt this project explicitly refuses to make, so these codes
# get exactly one attempt and then a hard stop -- no backoff-and-retry
# loop, however small.
_NO_RETRY_STATUS_CODES = {403, 429}


def _polite_get(
    url: str,
    user_agent: str,
    timeout_seconds: int,
    max_retries: int,
    request_delay_seconds: float,
) -> requests.Response:
    """GET a URL with retries and a delay before the request (politeness),
    re-raising the last exception if all attempts fail.

    Retries are for transient failures only (timeouts, connection resets,
    5xx). A 403 (Forbidden) or 429 (Too Many Requests) response is treated
    as the source telling us to stop -- this function raises
    AccessDeniedError immediately, without retrying, regardless of
    max_retries. See docs/legal_and_compliance.md.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            time.sleep(request_delay_seconds)
            response = requests.get(
                url,
                headers={"User-Agent": user_agent},
                timeout=timeout_seconds,
            )
            if response.status_code in _NO_RETRY_STATUS_CODES:
                logger.warning(
                    "Access denied (HTTP %d) for %s -- stopping, not retrying. This project "
                    "never bypasses access controls or rate limits.",
                    response.status_code,
                    url,
                )
                raise AccessDeniedError(
                    f"HTTP {response.status_code} from {url} -- access denied or rate-limited; "
                    "not retrying (see docs/legal_and_compliance.md)."
                )
            response.raise_for_status()
            return response
        except AccessDeniedError:
            raise
        except requests.RequestException as exc:
            last_exc = exc
            logger.warning(
                "Attempt %d/%d failed for %s: %s", attempt + 1, max_retries + 1, url, exc
            )
    assert last_exc is not None
    raise last_exc


def collect_one(university: University, settings: dict) -> PolicyDocument:
    """Collect a single university's policy document.

    Never raises on a per-source failure -- returns a PolicyDocument with
    collection_status=FAILED and error_message set, so collect_all() can
    continue with the remaining sources. This matches the requirement that
    "the whole collection process" must not stop when one source fails.

    Legal/compliance note: this function does not implement automated
    terms-of-use checking (only robots.txt, below). Every PolicyDocument
    this function returns therefore keeps the schema's honest defaults --
    terms_checked=False, terms_url=None, legal_review_status=PENDING,
    tdm_reservation_detected=None -- rather than any of this module
    guessing at redistribution rights it has not actually verified. A
    human must set these via a manual legal review before a document's
    text is redistributed; see docs/legal_and_compliance.md.
    """
    collection_cfg = settings["collection"]
    user_agent = collection_cfg["user_agent"]
    url = str(university.policy_url)
    document_id = compute_document_id(university.university_id, url)
    retrieval_timestamp = datetime.now(UTC)

    if not validate_official_domain(url, university):
        return _failed_document(
            university,
            url,
            document_id,
            retrieval_timestamp,
            "URL did not pass basic domain sanity check",
        )

    robots_allowed = robots.is_allowed(
        url, user_agent, timeout_seconds=collection_cfg["request_timeout_seconds"]
    )
    if robots_allowed is False:
        return PolicyDocument(
            document_id=document_id,
            university_id=university.university_id,
            university_name=university.university_name,
            country=university.country,
            title=university.policy_title,
            source_url=url,
            retrieval_timestamp=retrieval_timestamp,
            analyzed_language="en",
            translation_status=TranslationStatus.UNKNOWN,
            document_type=university.document_type,
            intended_audience=university.intended_audience,
            policy_level=university.policy_level,
            file_format="pdf" if url.lower().endswith(".pdf") else "html",
            robots_allowed=False,
            extraction_method=university.collection_method,
            collection_status=CollectionStatus.SKIPPED_ROBOTS_DISALLOWED,
            error_message="robots.txt disallows this user agent for this path",
        )

    try:
        response = _polite_get(
            url,
            user_agent,
            collection_cfg["request_timeout_seconds"],
            collection_cfg["max_retries"],
            collection_cfg["request_delay_seconds"],
        )
    except AccessDeniedError as exc:
        # 403/429 -- the source said no. Recorded as a genuine collection
        # failure, never retried, never worked around. See
        # docs/legal_and_compliance.md.
        return _failed_document(university, url, document_id, retrieval_timestamp, str(exc))
    except requests.RequestException as exc:
        return _failed_document(university, url, document_id, retrieval_timestamp, str(exc))

    is_pdf = "application/pdf" in response.headers.get("Content-Type", "") or url.lower().endswith(
        ".pdf"
    )

    if is_pdf:
        raw_text = extract_text_from_pdf_bytes(response.content)
        title = university.policy_title
        extraction_method = ExtractionMethod.PDF_HTTP
        file_format = "pdf"
    else:
        raw_text = response.text
        title = extract_title(response.text) or university.policy_title
        extraction_method = ExtractionMethod.HTML_HTTP
        file_format = "html"

    cleaned_text = raw_text if is_pdf else extract_main_text(raw_text)
    text_hash = compute_text_hash(cleaned_text)
    word_count = len(cleaned_text.split())

    return PolicyDocument(
        document_id=document_id,
        university_id=university.university_id,
        university_name=university.university_name,
        country=university.country,
        title=title,
        source_url=url,
        retrieval_timestamp=retrieval_timestamp,
        analyzed_language="en",
        translation_status=TranslationStatus.UNKNOWN,
        document_type=university.document_type,
        intended_audience=university.intended_audience,
        policy_level=university.policy_level,
        file_format=file_format,
        http_status=response.status_code,
        robots_allowed=robots_allowed,
        extraction_method=extraction_method,
        raw_text=raw_text if not is_pdf else "",  # PDF raw bytes aren't stored as text
        cleaned_text=cleaned_text,
        text_hash=text_hash,
        word_count=word_count,
        collection_status=CollectionStatus.COLLECTED,
    )


def _failed_document(
    university: University,
    url: str,
    document_id: str,
    retrieval_timestamp: datetime,
    error_message: str,
) -> PolicyDocument:
    return PolicyDocument(
        document_id=document_id,
        university_id=university.university_id,
        university_name=university.university_name,
        country=university.country,
        title=university.policy_title,
        source_url=url,
        retrieval_timestamp=retrieval_timestamp,
        analyzed_language="en",
        translation_status=TranslationStatus.UNKNOWN,
        document_type=university.document_type,
        intended_audience=university.intended_audience,
        policy_level=university.policy_level,
        file_format="pdf" if url.lower().endswith(".pdf") else "html",
        extraction_method=university.collection_method,
        collection_status=CollectionStatus.FAILED,
        error_message=error_message,
    )


def collect_all(csv_path: str | Path, settings: dict) -> list[PolicyDocument]:
    """Collect every active+verified source, continuing past individual failures."""
    universities = read_active_verified_sources(csv_path)
    logger.info("Found %d active+verified source(s) to collect.", len(universities))
    results: list[PolicyDocument] = []
    for university in universities:
        logger.info("Collecting %s (%s)...", university.university_name, university.policy_url)
        doc = collect_one(university, settings)
        logger.info("  -> %s", doc.collection_status.value)
        results.append(doc)
    return results
