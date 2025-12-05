# validators.py
import re
from datetime import datetime
import requests
from urllib.parse import urlparse

HEADERS = {
    "User-Agent": "DeadDataHunterBot/1.0 (+https://example.com/contact)"
}

def find_outdated_dates(text, year_threshold=2):
    """
    Return a list of years that look outdated (older than year_threshold years).
    """
    now_year = datetime.utcnow().year
    years = set()

    # match 4-digit years like 2018, 2019, 2020...
    for m in re.findall(r'\b(20[0-2]\d|201\d)\b', text):
        years.add(int(m))

    # patterns like "Last updated: 2019" or "Updated on 2019"
    for m in re.findall(r'last\s*updated[:\s]*([0-9]{4})', text, flags=re.I):
        years.add(int(m))
    for m in re.findall(r'updated[:\s]*([0-9]{4})', text, flags=re.I):
        years.add(int(m))

    outdated = [y for y in years if (now_year - y) >= year_threshold]
    outdated.sort()
    return outdated

def parse_url_to_absolute(base_url, href):
    if href.startswith("//"):
        parsed = urlparse(base_url)
        return f"{parsed.scheme}:{href}"
    if href.startswith("http://") or href.startswith("https://"):
        return href
    # relative path
    return requests.compat.urljoin(base_url, href)

def check_link_status(url, timeout=8):
    """
    Attempt HEAD first, fallback to GET.
    Returns dict: {url, status (int|string), error (optional)}
    """
    try:
        resp = requests.head(url, allow_redirects=True, timeout=timeout, headers=HEADERS)
        status = resp.status_code
        # some servers block HEAD properly; fallback when 405 or no content
        if status is None or status == 405:
            resp = requests.get(url, allow_redirects=True, timeout=timeout, headers=HEADERS)
            status = resp.status_code
        return {"url": url, "status": status}
    except requests.exceptions.RequestException as e:
        return {"url": url, "status": "error", "error": str(e)}

def extract_phone_candidates(text):
    """
    Rough extraction of phone-like tokens.
    """
    # capture segments with digits, spaces, parentheses, pluses and hyphens
    candidates = set(re.findall(r'\+?\d[\d\-\s\(\)]{6,}\d', text))
    return list(candidates)

def invalid_phone_candidates(candidates, min_digits=10):
    invalid = []
    for c in candidates:
        digits = re.sub(r'\D', '', c)
        if len(digits) < min_digits:
            invalid.append({"raw": c, "digits": digits})
    return invalid

def is_same_domain(base_url, other_url):
    try:
        b = urlparse(base_url).netloc.lower()
        o = urlparse(other_url).netloc.lower()
        return b == o or o.endswith("."+b)
    except Exception:
        return False
