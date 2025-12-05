# scraper.py
import requests
from bs4 import BeautifulSoup
from validators import (
    find_outdated_dates,
    parse_url_to_absolute,
    check_link_status,
    extract_phone_candidates,
    invalid_phone_candidates,
    is_same_domain
)
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": "DeadDataHunterBot/1.0 (+https://example.com/contact)"
}

def fetch_html(url, timeout=12):
    res = requests.get(url, timeout=timeout, headers=HEADERS)
    res.raise_for_status()
    return res.text

def scrape_website(url, max_links_to_check=50):
    """
    Returns a dict with the scan result.
    """
    try:
        html = fetch_html(url)
    except Exception as e:
        return {"website": url, "error": f"fetch_failed: {str(e)}"}

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ", strip=True)

    # outdated dates
    outdated_dates = find_outdated_dates(text)

    # extract links (absolute)
    anchors = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full = parse_url_to_absolute(url, href)
        anchors.append({"href": full, "text": (a.get_text() or "").strip()})

    # deduplicate anchors by href
    seen = set()
    uniq_anchors = []
    for a in anchors:
        if a["href"] not in seen:
            seen.add(a["href"])
            uniq_anchors.append(a)
    anchors = uniq_anchors

    # resources (pdf/doc)
    resources = [a["href"] for a in anchors if a["href"].lower().endswith(('.pdf', '.doc', '.docx', '.xls', '.xlsx'))]

    # prepare subset of links to check: internal first, then external, up to max_links_to_check
    internal = [a["href"] for a in anchors if is_same_domain(url, a["href"])]
    external = [a["href"] for a in anchors if not is_same_domain(url, a["href"])]
    to_check = internal + external
    to_check = to_check[:max_links_to_check]

    link_checks = []
    for link in to_check:
        link_checks.append(check_link_status(link))

    broken_links = [c for c in link_checks if (isinstance(c.get("status"), int) and c["status"] >= 400) or c.get("status") == "error"]

    # phone numbers
    phones = extract_phone_candidates(text)
    invalid_phones = invalid_phone_candidates(phones)

    result = {
        "website": url,
        "title": (soup.title.string.strip() if soup.title and soup.title.string else ""),
        "outdated_dates": outdated_dates,
        "broken_links": broken_links,
        "invalid_contacts": invalid_phones,
        "resources": resources,
        "crawled_text_snippet": text[:2000]
    }

    return result
