# scraper.py
from collections import deque

from bs4 import BeautifulSoup

from validators import (
    find_outdated_dates,
    parse_url_to_absolute,
    check_link_status_with_retry,
    extract_phone_candidates,
    invalid_phone_candidates,
    is_same_domain,
    normalize_url,
    fetch_html_with_retry,
)


def classify_scan_summary(
    outdated_dates=None,
    broken_links=None,
    invalid_contacts=None,
    resources=None,
):
    """Summarize scan findings and assign an issue severity level."""

    counts = {
        "outdated_dates": len(outdated_dates or []),
        "broken_links": len(broken_links or []),
        "invalid_contacts": len(invalid_contacts or []),
    }

    # Resources are informational, not issues.
    # Count only unique resource URLs.
    resource_count = len(set(resources or []))

    # Resources are intentionally excluded from total issues.
    total_issues = sum(counts.values())

    if total_issues >= 25:
        severity = "critical"
    elif total_issues >= 15:
        severity = "high"
    elif total_issues >= 8:
        severity = "medium"
    else:
        severity = "low"

    return {
        "counts": counts,
        "resource_count": resource_count,
        "total_issues": total_issues,
        "severity": severity,
    }


def fetch_html(url, timeout=12):
    """Fetch HTML with retry logic for better reliability."""

    return fetch_html_with_retry(
        url,
        timeout=timeout,
        max_retries=2,
        backoff_factor=0.5,
    )


def _page_signals(url, max_links_to_check=15):
    """Collect findings from a single page."""

    try:
        html = fetch_html(url)
    except Exception as e:
        return {
            "website": url,
            "error": f"fetch_failed: {str(e)}",
            "anchors": [],
            "title": "",
            "outdated_dates": [],
            "broken_links": [],
            "invalid_contacts": [],
            "resources": [],
            "crawled_text_snippet": "",
        }

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    # Find outdated dates.
    outdated_dates = find_outdated_dates(text)

    # Extract links and convert them to absolute normalized URLs.
    anchors = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()

        full = parse_url_to_absolute(url, href)

        if not full:
            continue

        normalized = normalize_url(full)

        if not normalized:
            continue

        anchors.append(
            {
                "href": normalized,
                "text": (a.get_text() or "").strip(),
            }
        )

    # Deduplicate anchors by normalized URL.
    seen = set()
    uniq_anchors = []

    for anchor in anchors:
        href = anchor["href"]

        if href not in seen:
            seen.add(href)
            uniq_anchors.append(anchor)

    anchors = uniq_anchors

    # Find resources.
    # Query strings are ignored when checking the file extension.
    resources = [
        anchor["href"]
        for anchor in anchors
        if anchor["href"]
        .lower()
        .split("?")[0]
        .endswith(
            (
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
            )
        )
    ]

    # Check internal links first, then external links.
    internal = [
        anchor["href"]
        for anchor in anchors
        if is_same_domain(url, anchor["href"])
    ]

    external = [
        anchor["href"]
        for anchor in anchors
        if not is_same_domain(url, anchor["href"])
    ]

    to_check = (internal + external)[:max_links_to_check]

    # Check links with retry logic.
    link_checks = [
        check_link_status_with_retry(
            link,
            timeout=8,
            max_retries=1,
        )
        for link in to_check
    ]

    broken_links = [
        check
        for check in link_checks
        if (
            isinstance(check.get("status"), int)
            and check["status"] >= 400
        )
        or check.get("status") in ["error", "timeout"]
    ]

    # Find phone numbers and invalid contacts.
    phones = extract_phone_candidates(text)
    invalid_phones = invalid_phone_candidates(phones)

    return {
        "website": url,
        "title": (
            soup.title.string.strip()
            if soup.title and soup.title.string
            else ""
        ),
        "text": text,
        "outdated_dates": outdated_dates,
        "broken_links": broken_links,
        "invalid_contacts": invalid_phones,
        "resources": resources,
        "anchors": [anchor["href"] for anchor in anchors],
        "crawled_text_snippet": text[:2000],
    }


def scrape_website(
    url,
    max_links_to_check=50,
    max_depth=1,
    max_pages=8,
):
    """
    Crawl a website using normalized URLs.

    max_depth:
        Maximum crawl depth.

    max_pages:
        Maximum number of pages to crawl.

    max_links_to_check:
        Maximum number of links checked per page.
    """

    # Normalize the root URL before starting the crawl.
    root_url = normalize_url(url)

    queue = deque([(root_url, 0)])
    visited = set()

    all_outdated = []
    all_broken = []
    all_invalid_contacts = []
    all_resources = []

    pages_crawled = 0

    # Store root page information while it is being crawled.
    # This avoids requesting the root page a second time later.
    root_title = ""
    root_snippet = ""

    while queue and pages_crawled < max_pages:
        current_url, depth = queue.popleft()

        # Prevent duplicate crawls.
        if current_url in visited:
            continue

        visited.add(current_url)

        page = _page_signals(
            current_url,
            max_links_to_check=max(
                8,
                min(25, max_links_to_check),
            ),
        )

        pages_crawled += 1

        # Save root page title and snippet from the existing crawl.
        if current_url == root_url:
            root_title = page.get("title", "")
            root_snippet = page.get(
                "crawled_text_snippet",
                "",
            )

        # Collect findings from the current page.
        all_outdated.extend(
            page.get("outdated_dates", [])
        )

        all_broken.extend(
            page.get("broken_links", [])
        )

        all_invalid_contacts.extend(
            page.get("invalid_contacts", [])
        )

        all_resources.extend(
            page.get("resources", [])
        )

        # Continue crawling same-domain pages
        # until the configured maximum depth is reached.
        if depth < max_depth:
            for link in page.get("anchors", []):
                normalized_link = normalize_url(link)

                if not normalized_link:
                    continue

                if (
                    is_same_domain(
                        root_url,
                        normalized_link,
                    )
                    and normalized_link not in visited
                ):
                    queue.append(
                        (
                            normalized_link,
                            depth + 1,
                        )
                    )

    # Remove duplicate resources across all crawled pages.
    unique_resources = sorted(
        set(all_resources)
    )

    # Build scan summary.
    summary = classify_scan_summary(
        outdated_dates=all_outdated,
        broken_links=all_broken,
        invalid_contacts=all_invalid_contacts,
        resources=unique_resources,
    )

    result = {
        "website": url,
        "title": root_title,
        "outdated_dates": sorted(
            set(all_outdated)
        ),
        "broken_links": all_broken,
        "invalid_contacts": all_invalid_contacts,
        "resources": unique_resources,
        "crawled_text_snippet": root_snippet[:2000],
        "pages_crawled": pages_crawled,
        "summary": summary,
    }

    return result