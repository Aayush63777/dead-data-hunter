# scraper.py
import requests
from collections import deque
from bs4 import BeautifulSoup
from validators import (
    find_outdated_dates,
    parse_url_to_absolute,
    check_link_status,
    check_link_status_with_retry,
    extract_phone_candidates,
    invalid_phone_candidates,
    is_same_domain,
    normalize_url,
    fetch_html_with_retry,
)

HEADERS = {
    "User-Agent": "DeadDataHunterBot/1.0 (+https://example.com/contact)"
}


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
    """Fetch HTML with retry logic for better reliability."""
    return fetch_html_with_retry(url, timeout=timeout, max_retries=2, backoff_factor=0.5)


def _page_signals(url, max_links_to_check=15):
    try:
        html = fetch_html(url)
    except Exception as e:
        return {"website": url, "error": f"fetch_failed: {str(e)}", "anchors": []}

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    outdated_dates = find_outdated_dates(text)

    anchors = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = parse_url_to_absolute(url, href)
        anchors.append({"href": full, "text": (a.get_text() or "").strip()})

    seen = set()
    uniq_anchors = []
    for a in anchors:
        if a["href"] not in seen:
            seen.add(a["href"])
            uniq_anchors.append(a)
    anchors = uniq_anchors

    resources = [
        a["href"]
        for a in anchors
        if a["href"].lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx'))
    ]

    internal = [a["href"] for a in anchors if is_same_domain(url, a["href"])]
    external = [a["href"] for a in anchors if not is_same_domain(url, a["href"])]
    to_check = (internal + external)[:max_links_to_check]

    link_checks = [check_link_status_with_retry(link, timeout=8, max_retries=1) for link in to_check]
    broken_links = [
        c for c in link_checks
        if (isinstance(c.get("status"), int) and c["status"] >= 400) or c.get("status") in ["error", "timeout"]
    ]

    phones = extract_phone_candidates(text)
    invalid_phones = invalid_phone_candidates(phones)

    return {
        "website": url,
        "title": (soup.title.string.strip() if soup.title and soup.title.string else ""),
        "text": text,
        "outdated_dates": outdated_dates,
        "broken_links": broken_links,
        "invalid_contacts": invalid_phones,
        "resources": resources,
        "anchors": [a["href"] for a in anchors],
        "crawled_text_snippet": text[:2000],
    }


def scrape_website(url, max_links_to_check=50, max_depth=1, max_pages=8):
    """
    Crawl the main page and a limited set of same-domain pages for deeper scan coverage.
    Uses URL normalization to prevent duplicate crawls.
    """
    # Normalize the root URL
    root_url = normalize_url(url)
    
    queue = deque([(root_url, 0)])
    visited = set()
    all_outdated = []
    all_broken = []
    all_invalid_contacts = []
    all_resources = []
    pages_crawled = 0

    while queue and pages_crawled < max_pages:
        current_url, depth = queue.popleft()
        
        # Skip if already visited
        if current_url in visited:
            continue
        visited.add(current_url)

        page = _page_signals(current_url, max_links_to_check=max(8, min(25, max_links_to_check)))
        pages_crawled += 1

        all_outdated.extend(page.get("outdated_dates", []))
        all_broken.extend(page.get("broken_links", []))
        all_invalid_contacts.extend(page.get("invalid_contacts", []))
        all_resources.extend(page.get("resources", []))

        if depth < max_depth:
            for link in page.get("anchors", []):
                normalized_link = normalize_url(link)
                if is_same_domain(url, normalized_link) and normalized_link not in visited:
                    queue.append((normalized_link, depth + 1))

    summary = classify_scan_summary(
        outdated_dates=all_outdated,
        broken_links=all_broken,
        invalid_contacts=all_invalid_contacts,
        resources=all_resources,
    )

    result = {
        "website": url,
        "title": "",
        "outdated_dates": sorted(set(all_outdated)),
        "broken_links": all_broken,
        "invalid_contacts": all_invalid_contacts,
        "resources": sorted(set(all_resources)),
        "crawled_text_snippet": "",
        "pages_crawled": pages_crawled,
        "summary": summary,
    }

    root_page = _page_signals(root_url, max_links_to_check=max(8, min(25, max_links_to_check)))
    result["title"] = root_page.get("title", "")
    result["crawled_text_snippet"] = root_page.get("crawled_text_snippet", "")[:2000]

    return result
