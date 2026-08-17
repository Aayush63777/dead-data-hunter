# validators.py
import re
from datetime import datetime
import requests
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import time

HEADERS = {
    "User-Agent": "DeadDataHunterBot/1.0 (+https://example.com/contact)"
}

def find_outdated_dates(text, year_threshold=4):
    """
    Return a list of years that look outdated (older than year_threshold years).
    More restrictive: only flags content explicitly marked as outdated or not updated.
    """
    now_year = datetime.utcnow().year
    years = set()

    # Only match patterns that explicitly indicate update/modification dates
    # Patterns like "Last updated: 2019", "Modified: 2018", "Last revised: 2019"
    patterns = [
        r'last\s+updated[:\s]+(?:on\s+)?([0-9]{4})',
        r'modified[:\s]+(?:on\s+)?([0-9]{4})',
        r'last\s+revised[:\s]+(?:on\s+)?([0-9]{4})',
        r'last\s+changed[:\s]+(?:on\s+)?([0-9]{4})',
        r'updated\s+on\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)?\s*\d{1,2},?\s+([0-9]{4})',
        r'(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+([0-9]{4})',
    ]
    
    for pattern in patterns:
        for m in re.findall(pattern, text, flags=re.I):
            years.add(int(m))

    # Ignore copyright years and date ranges (e.g., "© 2006-2024")
    # Filter out if the year appears near copyright symbol
    text_lines = text.split('\n')
    filtered_years = set()
    for year in years:
        # Check if this year appears in a copyright-like context
        copyright_pattern = r'[©©\(]\s*([0-9]{4})\s*[-–]\s*([0-9]{4}|\w*)'
        is_copyright = False
        for line in text_lines:
            if str(year) in line:
                if re.search(copyright_pattern, line):
                    is_copyright = True
                    break
        if not is_copyright:
            filtered_years.add(year)
    
    years = filtered_years

    # Flag as outdated if older than year_threshold years
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
    Extract phone-like patterns. Looks for:
    - +1-234-567-8900 (with country code)
    - (123) 456-7890 (US format)
    - 123-456-7890 (dashes)
    - 123.456.7890 (dots)
    - +91 98765 43210 (international with spaces)
    """
    candidates = []
    
    # Pattern 1: +CC xxx xxx xxxx or +CC-xxx-xxx-xxxx (international)
    pattern1 = re.findall(r'\+\d{1,3}[\s\-]?\d{1,4}[\s\-]?\d{3,4}[\s\-]?\d{3,4}', text)
    candidates.extend(pattern1)
    
    # Pattern 2: (xxx) xxx-xxxx or (xxx) xxx xxxx
    pattern2 = re.findall(r'\(\d{3}\)\s?\d{3}[\s\-]?\d{4}', text)
    candidates.extend(pattern2)
    
    # Pattern 3: xxx-xxx-xxxx or xxx.xxx.xxxx (10 digits with separators)
    pattern3 = re.findall(r'\d{3}[\s\-\.]\d{3}[\s\-\.]\d{4}', text)
    candidates.extend(pattern3)
    
    # Pattern 4: 10+ consecutive digits (likely phone)
    pattern4 = re.findall(r'\d{10,}', text)
    candidates.extend(pattern4)
    
    # Remove duplicates and filter out obvious non-phones
    candidates = list(set(candidates))
    candidates = [c for c in candidates if not _is_obvious_non_phone(c)]
    
    return candidates

def _is_obvious_non_phone(text):
    """
    Filter out obvious non-phone patterns.
    """
    text_clean = re.sub(r'\D', '', text)
    
    # Skip if it's a year range (xxxx-xxxx format)
    if re.match(r'^(19|20)\d{2}[\s\-](19|20)\d{2}$', text):
        return True
    
    # Skip if it looks like a date (##-##-####)
    if re.match(r'^\d{1,2}[\s\-]\d{1,2}[\s\-]\d{4}$', text):
        return True
    
    # Skip very long digit sequences (>15 digits = probably not a phone)
    if len(text_clean) > 15:
        return True
    
    # Skip if contains only citations/references with commas
    if ',' in text and len(text_clean) < 8:
        return True
    
    return False

def invalid_phone_candidates(candidates, min_digits=10):
    """
    Identify invalid phone numbers.
    A valid phone should have at least min_digits consecutive digits.
    """
    invalid = []
    for c in candidates:
        digits = re.sub(r'\D', '', c)
        # Only flag as invalid if it has fewer than min_digits
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


def normalize_url(url):
    """
    Normalize URL to prevent duplicate crawls:
    - Remove fragment (#)
    - Remove default ports (80 for http, 443 for https)
    - Lowercase scheme and domain
    - Sort query parameters
    - Remove trailing slash (optional for root path)
    
    Returns normalized URL string.
    """
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        
        # Remove default ports
        if ':' in netloc:
            host, port = netloc.rsplit(':', 1)
            if (scheme == 'http' and port == '80') or (scheme == 'https' and port == '443'):
                netloc = host
        
        # Sort query parameters for consistency
        path = parsed.path or '/'
        query_params = parse_qs(parsed.query, keep_blank_values=True)
        sorted_query = urlencode(sorted(query_params.items()), doseq=True) if query_params else ''
        
        # Remove trailing slash unless it's the root path
        if path != '/' and path.endswith('/'):
            path = path.rstrip('/')
        
        # Reconstruct URL without fragment
        normalized = urlunparse((scheme, netloc, path, parsed.params, sorted_query, ''))
        return normalized
    except Exception:
        return url


def fetch_html_with_retry(url, timeout=12, max_retries=2, backoff_factor=1.0):
    """
    Fetch HTML with retry logic and exponential backoff.
    
    Args:
        url: URL to fetch
        timeout: Request timeout in seconds
        max_retries: Number of retries on failure
        backoff_factor: Multiplier for exponential backoff (1.0 = no backoff)
    
    Returns:
        Response text or raises exception after max retries
    """
    for attempt in range(max_retries + 1):
        try:
            resp = requests.get(url, timeout=timeout, headers=HEADERS)
            resp.raise_for_status()
            return resp.text
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
            # Don't retry on other request errors (4xx, 5xx, etc)
            raise
    return None


def check_link_status_with_retry(url, timeout=8, max_retries=1):
    """
    Check link status with retry logic.
    Attempt HEAD first, fallback to GET.
    Returns dict: {url, status (int|string), error (optional), redirect_url (optional)}
    """
    for attempt in range(max_retries + 1):
        try:
            resp = requests.head(url, allow_redirects=True, timeout=timeout, headers=HEADERS)
            status = resp.status_code
            result = {"url": url, "status": status}
            
            # Track redirect if applicable
            if resp.history:
                result["redirect_url"] = resp.url
            
            # Fallback to GET if HEAD fails with 405
            if status == 405:
                resp = requests.get(url, allow_redirects=True, timeout=timeout, headers=HEADERS)
                result["status"] = resp.status_code
                if resp.history:
                    result["redirect_url"] = resp.url
            
            return result
        except requests.exceptions.Timeout:
            if attempt < max_retries:
                time.sleep(0.5 * (2 ** attempt))
            else:
                return {"url": url, "status": "timeout", "error": "Request timeout"}
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                time.sleep(0.5 * (2 ** attempt))
            else:
                return {"url": url, "status": "error", "error": str(e)}
    
    return {"url": url, "status": "error", "error": "Max retries exceeded"}

