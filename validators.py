import re
import time
from datetime import datetime
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import requests


HEADERS = {
    "User-Agent": "DeadDataHunterBot/1.0 (+https://example.com/contact)"
}


def find_outdated_dates(text, year_threshold=4):
    """
    Return years that are explicitly associated with update/modification/revision dates.
    Copyright years, ranges, and unrelated historical years are ignored.
    """
    now_year = datetime.utcnow().year
    years = set()

    patterns = [
    r"\blast\s+updated\b[:\s]*(?:on\s+)?(?:[A-Za-z]+\s+\d{1,2},?\s+)?([12]\d{3})\b",
    r"\bupdated\s+on\b[:\s]*(?:[A-Za-z]+\s+\d{1,2},?\s+)?([12]\d{3})\b",
    r"\bmodified\b[:\s]*(?:on\s+)?(?:[A-Za-z]+\s+\d{1,2},?\s+)?([12]\d{3})\b",
    r"\blast\s+revised\b[:\s]*(?:on\s+)?(?:[A-Za-z]+\s+\d{1,2},?\s+)?([12]\d{3})\b",
    r"\brevised\b[:\s]*(?:on\s+)?(?:[A-Za-z]+\s+\d{1,2},?\s+)?([12]\d{3})\b",
    r"\blast\s+changed\b[:\s]*(?:on\s+)?(?:[A-Za-z]+\s+\d{1,2},?\s+)?([12]\d{3})\b",
]

    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.I):
            year = int(match)

            if 1900 <= year <= now_year:
                years.add(year)

    outdated = sorted(
        year
        for year in years
        if now_year - year >= year_threshold
    )

    return outdated


def parse_url_to_absolute(base_url, href):
    """
    Convert a relative URL into an absolute URL.
    """
    if not href:
        return ""

    if href.startswith("//"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}:{href}"

    if href.startswith("http://") or href.startswith("https://"):
        return href

    return requests.compat.urljoin(base_url, href)


def check_link_status(url, timeout=8):
    """
    Attempt HEAD first and fall back to GET when necessary.

    Returns:
        {
            "url": url,
            "status": int | "error"
        }
    """
    try:
        response = requests.head(
            url,
            allow_redirects=True,
            timeout=timeout,
            headers=HEADERS,
        )

        status = response.status_code

        # Some servers do not properly support HEAD.
        if status is None or status == 405:
            response = requests.get(
                url,
                allow_redirects=True,
                timeout=timeout,
                headers=HEADERS,
            )
            status = response.status_code

        return {
            "url": url,
            "status": status,
        }

    except requests.exceptions.RequestException as exc:
        return {
            "url": url,
            "status": "error",
            "error": str(exc),
        }


def extract_phone_candidates(text):
    """
    Extract phone-like patterns.

    Supports:
    - +1-234-567-8900
    - (123) 456-7890
    - 123-456-7890
    - 123.456.7890
    - +91 98765 43210
    """
    candidates = []

    # International numbers.
    pattern1 = re.findall(
        r"\+\d{1,3}[\s\-]?\d{1,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4}",
        text,
    )
    candidates.extend(pattern1)

    # US-style numbers.
    pattern2 = re.findall(
        r"\(\d{3}\)\s?\d{3}[\s\-]?\d{4}",
        text,
    )
    candidates.extend(pattern2)

    # Numbers separated by spaces, dashes, or dots.
    pattern3 = re.findall(
        r"\d{3}[\s\-\.]\d{3}[\s\-\.]\d{4}",
        text,
    )
    candidates.extend(pattern3)

    # Long consecutive digit sequences.
    pattern4 = re.findall(
        r"\d{10,}",
        text,
    )
    candidates.extend(pattern4)

    candidates = list(set(candidates))

    candidates = [
        candidate
        for candidate in candidates
        if not _is_obvious_non_phone(candidate)
    ]

    return candidates


def _is_obvious_non_phone(text):
    """
    Filter out obvious non-phone patterns.
    """
    text_clean = re.sub(r"\D", "", text)

    # Skip year ranges.
    if re.match(
        r"^(19|20)\d{2}[\s\-](19|20)\d{2}$",
        text,
    ):
        return True

    # Skip dates such as 12-05-2024.
    if re.match(
        r"^\d{1,2}[\s\-]\d{1,2}[\s\-]\d{4}$",
        text,
    ):
        return True

    # Skip extremely long digit sequences.
    if len(text_clean) > 15:
        return True

    # Skip obvious short references.
    if "," in text and len(text_clean) < 8:
        return True

    return False


def invalid_phone_candidates(candidates, min_digits=10):
    """
    Identify phone candidates with fewer than min_digits digits.
    """
    invalid = []

    for candidate in candidates:
        digits = re.sub(r"\D", "", candidate)

        if len(digits) < min_digits:
            invalid.append(
                {
                    "raw": candidate,
                    "digits": digits,
                }
            )

    return invalid


def is_same_domain(base_url, other_url):
    """
    Check whether two URLs belong to the same domain.
    """
    try:
        base_domain = urlparse(base_url).netloc.lower()
        other_domain = urlparse(other_url).netloc.lower()

        return (
            base_domain == other_domain
            or other_domain.endswith("." + base_domain)
        )

    except Exception:
        return False


def normalize_url(url):
    """
    Normalize URLs to prevent duplicate crawls.

    Normalization includes:
    - lowercase scheme
    - lowercase domain
    - remove default ports
    - remove URL fragments
    - sort query parameters
    - remove trailing slash except for root paths
    """
    try:
        parsed = urlparse(url)

        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()

        # Remove default HTTP/HTTPS ports.
        if ":" in netloc:
            host, port = netloc.rsplit(":", 1)

            if (
                (scheme == "http" and port == "80")
                or (scheme == "https" and port == "443")
            ):
                netloc = host

        path = parsed.path or "/"

        # Remove trailing slash except from root.
        if path != "/" and path.endswith("/"):
            path = path.rstrip("/")

        # Normalize query parameter ordering.
        query_params = parse_qs(
            parsed.query,
            keep_blank_values=True,
        )

        sorted_query = (
            urlencode(
                sorted(query_params.items()),
                doseq=True,
            )
            if query_params
            else ""
        )

        # Fragment intentionally removed.
        normalized = urlunparse(
            (
                scheme,
                netloc,
                path,
                parsed.params,
                sorted_query,
                "",
            )
        )

        return normalized

    except Exception:
        return url


def fetch_html_with_retry(
    url,
    timeout=12,
    max_retries=2,
    backoff_factor=1.0,
):
    """
    Fetch HTML with retry logic and exponential backoff.

    Retries are performed for timeout and connection errors.
    Other HTTP/request errors are not retried.
    """
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers=HEADERS,
            )

            response.raise_for_status()

            return response.text

        except requests.exceptions.Timeout:
            if attempt < max_retries:
                wait_time = backoff_factor * (2 ** attempt)
                time.sleep(wait_time)
            else:
                raise

        except requests.exceptions.ConnectionError:
            if attempt < max_retries:
                wait_time = backoff_factor * (2 ** attempt)
                time.sleep(wait_time)
            else:
                raise

        except requests.exceptions.RequestException:
            raise

    return None


def check_link_status_with_retry(
    url,
    timeout=8,
    max_retries=1,
):
    """
    Check link status with retry logic.

    Attempts HEAD first and falls back to GET when HEAD
    returns 405.

    Returns:
        {
            "url": url,
            "status": int | "error" | "timeout",
            "error": optional string,
            "redirect_url": optional string
        }
    """
    for attempt in range(max_retries + 1):
        try:
            response = requests.head(
                url,
                allow_redirects=True,
                timeout=timeout,
                headers=HEADERS,
            )

            status = response.status_code

            result = {
                "url": url,
                "status": status,
            }

            # Track final URL after redirects.
            if response.history:
                result["redirect_url"] = response.url

            # Some servers reject HEAD requests.
            if status == 405:
                response = requests.get(
                    url,
                    allow_redirects=True,
                    timeout=timeout,
                    headers=HEADERS,
                )

                result["status"] = response.status_code

                if response.history:
                    result["redirect_url"] = response.url

            return result

        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(0.5 * (2 ** attempt))
            else:
                return {
                    "url": url,
                    "status": "timeout",
                    "error": "Request timeout",
                }

        except requests.exceptions.RequestException as exc:
            if attempt < max_retries:
                time.sleep(0.5 * (2 ** attempt))
            else:
                return {
                    "url": url,
                    "status": "error",
                    "error": str(exc),
                }

    return {
        "url": url,
        "status": "error",
        "error": "Max retries exceeded",
    }