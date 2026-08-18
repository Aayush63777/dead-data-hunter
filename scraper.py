from collections import deque

from bs4 import BeautifulSoup

from validators import (
    check_link_status_with_retry,
    extract_phone_candidates,
    fetch_html_with_retry,
    find_outdated_dates,
    invalid_phone_candidates,
    is_same_domain,
    normalize_url,
    parse_url_to_absolute,
)


def classify_scan_summary(
    outdated_dates=None,
    broken_links=None,
    invalid_contacts=None,
    resources=None,
):
    """
    Build a scan summary containing issue counts, resource count,
    total issues, and severity.
    """

    counts = {
        "outdated_dates": len(outdated_dates or []),
        "broken_links": len(broken_links or []),
        "invalid_contacts": len(invalid_contacts or []),
    }

    # Resources are informational and must not be counted as issues.
    resource_count = len(set(resources or []))

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
    """
    Fetch HTML using retry logic.
    """

    return fetch_html_with_retry(
        url,
        timeout=timeout,
        max_retries=2,
        backoff_factor=0.5,
    )


def _page_signals(url, max_links_to_check=15):
    """
    Scan a single page and return all detected signals.
    """

    try:
        html = fetch_html(url)
    except Exception as exc:
        return {
            "website": url,
            "error": f"fetch_failed: {exc}",
            "anchors": [],
            "title": "",
            "outdated_dates": [],
            "broken_links": [],
            "invalid_contacts": [],
            "resources": [],
            "crawled_text_snippet": "",
        }

    soup = BeautifulSoup(html, "html.parser")

    text = soup.get_text(
        separator=" ",
        strip=True,
    )

    # Detect explicitly outdated update/revision dates.
    outdated_dates = find_outdated_dates(text)

    # Convert all discovered links to normalized absolute URLs.
    anchors = []

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()

        full_url = parse_url_to_absolute(
            url,
            href,
        )

        if not full_url:
            continue

        normalized_url = normalize_url(full_url)

        if not normalized_url:
            continue

        anchors.append(
            {
                "href": normalized_url,
                "text": (
                    anchor.get_text() or ""
                ).strip(),
            }
        )

    # Remove duplicate links from the current page.
    unique_anchors = []
    seen_urls = set()

    for anchor in anchors:
        href = anchor["href"]

        if href in seen_urls:
            continue

        seen_urls.add(href)
        unique_anchors.append(anchor)

    anchors = unique_anchors

    # Detect supported document resources.
    resources = []

    for anchor in anchors:
        href = anchor["href"]

        path_without_query = (
            href.lower()
            .split("?", 1)[0]
        )

        if path_without_query.endswith(
            (
                ".pdf",
                ".doc",
                ".docx",
                ".xls",
                ".xlsx",
            )
        ):
            resources.append(href)

    # Check internal links first, followed by external links.
    internal_links = [
        anchor["href"]
        for anchor in anchors
        if is_same_domain(
            url,
            anchor["href"],
        )
    ]

    external_links = [
        anchor["href"]
        for anchor in anchors
        if not is_same_domain(
            url,
            anchor["href"],
        )
    ]

    links_to_check = (
        internal_links + external_links
    )[:max_links_to_check]

    # Check link availability with retry support.
    link_checks = []

    for link in links_to_check:
        result = check_link_status_with_retry(
            link,
            timeout=8,
            max_retries=1,
        )

        link_checks.append(result)

    # Treat HTTP 4xx/5xx responses, errors, and timeouts as broken.
    broken_links = []

    for check in link_checks:
        status = check.get("status")

        if (
            isinstance(status, int)
            and status >= 400
        ):
            broken_links.append(check)
            continue

        if status in {
            "error",
            "timeout",
        }:
            broken_links.append(check)

    # Extract phone-like values and identify invalid contacts.
    phones = extract_phone_candidates(text)

    invalid_contacts = invalid_phone_candidates(
        phones
    )

    title = ""

    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    return {
        "website": url,
        "title": title,
        "text": text,
        "outdated_dates": outdated_dates,
        "broken_links": broken_links,
        "invalid_contacts": invalid_contacts,
        "resources": resources,
        "anchors": [
            anchor["href"]
            for anchor in anchors
        ],
        "crawled_text_snippet": text[:2000],
    }


def scrape_website(
    url,
    max_links_to_check=50,
    max_depth=1,
    max_pages=8,
):
    """
    Crawl a website and collect:

    - outdated dates
    - broken links
    - invalid contacts
    - document resources

    The crawl stays within the root domain and respects
    max_depth and max_pages.
    """

    # Normalize the starting URL so duplicate URLs are avoided.
    root_url = normalize_url(url)

    queue = deque(
        [
            (
                root_url,
                0,
            )
        ]
    )

    visited = set()

    all_outdated_dates = []
    all_broken_links = []
    all_invalid_contacts = []
    all_resources = []

    pages_crawled = 0

    root_title = ""
    root_snippet = ""

    while queue and pages_crawled < max_pages:
        current_url, depth = queue.popleft()

        # Do not crawl the same normalized URL more than once.
        if current_url in visited:
            continue

        visited.add(current_url)

        page = _page_signals(
            current_url,
            max_links_to_check=max(
                8,
                min(
                    25,
                    max_links_to_check,
                ),
            ),
        )

        pages_crawled += 1

        # Save title/snippet from the initial page.
        if current_url == root_url:
            root_title = page.get(
                "title",
                "",
            )

            root_snippet = page.get(
                "crawled_text_snippet",
                "",
            )

        # Collect findings from this page.
        all_outdated_dates.extend(
            page.get(
                "outdated_dates",
                [],
            )
        )

        all_broken_links.extend(
            page.get(
                "broken_links",
                [],
            )
        )

        all_invalid_contacts.extend(
            page.get(
                "invalid_contacts",
                [],
            )
        )

        all_resources.extend(
            page.get(
                "resources",
                [],
            )
        )

        # Continue crawling same-domain pages
        # until the configured depth is reached.
        if depth >= max_depth:
            continue

        for link in page.get(
            "anchors",
            [],
        ):
            normalized_link = normalize_url(link)

            if not normalized_link:
                continue

            if not is_same_domain(
                root_url,
                normalized_link,
            ):
                continue

            if normalized_link in visited:
                continue

            queue.append(
                (
                    normalized_link,
                    depth + 1,
                )
            )

    # Remove duplicate outdated years.
    unique_outdated_dates = sorted(
        set(all_outdated_dates)
    )

    # Remove duplicate resources.
    unique_resources = sorted(
        set(all_resources)
    )

    # Build final scan summary.
    summary = classify_scan_summary(
        outdated_dates=unique_outdated_dates,
        broken_links=all_broken_links,
        invalid_contacts=all_invalid_contacts,
        resources=unique_resources,
    )

    return {
        "website": url,
        "title": root_title,
        "outdated_dates": unique_outdated_dates,
        "broken_links": all_broken_links,
        "invalid_contacts": all_invalid_contacts,
        "resources": unique_resources,
        "crawled_text_snippet": root_snippet[:2000],
        "pages_crawled": pages_crawled,
        "summary": summary,
    }