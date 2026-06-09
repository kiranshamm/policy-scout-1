"""
Website Crawler
Fetches a website and discovers all internal links.
"""

import re
import logging
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

REQUEST_TIMEOUT = 15
MAX_LINKS = 500  # cap to avoid infinite crawl on huge sites


def normalize_url(base: str, href: str) -> Optional[str]:
    """Resolve a relative href against a base URL."""
    try:
        full = urljoin(base, href)
        parsed = urlparse(full)
        # Only keep http/https
        if parsed.scheme not in ("http", "https"):
            return None
        # Strip fragment
        return parsed._replace(fragment="").geturl()
    except Exception:
        return None


def is_same_domain(base_url: str, target_url: str) -> bool:
    base_host = urlparse(base_url).netloc.lower().lstrip("www.")
    target_host = urlparse(target_url).netloc.lower().lstrip("www.")
    return base_host == target_host or target_host.endswith(f".{base_host}")


def fetch_page(url: str) -> tuple[Optional[str], Optional[str]]:
    """
    Fetch a page and return (html_content, final_url_after_redirects).
    Returns (None, None) on failure.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "text/html" not in content_type:
            return None, resp.url
        return resp.text, resp.url
    except requests.exceptions.SSLError:
        # Try without SSL verification
        try:
            resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT, allow_redirects=True, verify=False)
            return resp.text, resp.url
        except Exception as e:
            logger.warning(f"SSL retry failed for {url}: {e}")
            return None, None
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None, None


def extract_links(html: str, base_url: str) -> list[dict]:
    """
    Parse all <a href> links from HTML and extract URL + anchor text.
    Returns list of {"url": str, "text": str}
    """
    soup = BeautifulSoup(html, "html.parser")
    links = []
    seen = set()

    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()
        if not href or href.startswith("#") or href.startswith("javascript:") or href.startswith("mailto:"):
            continue

        full_url = normalize_url(base_url, href)
        if not full_url or full_url in seen:
            continue
        seen.add(full_url)

        text = tag.get_text(separator=" ", strip=True)
        links.append({"url": full_url, "text": text[:200]})

    return links


def extract_footer_links(html: str, base_url: str) -> list[dict]:
    """
    Prioritize links found in <footer> tags since policy pages are often listed there.
    """
    soup = BeautifulSoup(html, "html.parser")
    footer = soup.find("footer")
    if not footer:
        # Try common footer class patterns
        for cls in ["footer", "site-footer", "page-footer"]:
            footer = soup.find(attrs={"class": re.compile(cls, re.I)})
            if footer:
                break

    if not footer:
        return []

    links = []
    seen = set()
    for tag in footer.find_all("a", href=True):
        href = tag.get("href", "").strip()
        if not href or href.startswith("#"):
            continue
        full_url = normalize_url(base_url, href)
        if not full_url or full_url in seen:
            continue
        seen.add(full_url)
        text = tag.get_text(separator=" ", strip=True)
        links.append({"url": full_url, "text": text[:200]})

    return links


def get_page_title(html: str) -> str:
    """Extract the <title> tag content."""
    soup = BeautifulSoup(html, "html.parser")
    tag = soup.find("title")
    return tag.get_text(strip=True) if tag else ""


def get_page_text_preview(html: str, max_chars: int = 2000) -> str:
    """Extract visible text from a page for content-based classification."""
    soup = BeautifulSoup(html, "html.parser")
    for script in soup(["script", "style", "noscript"]):
        script.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return text[:max_chars]


def crawl_website(start_url: str) -> dict:
    """
    Main entry point. Crawl a website and return all discovered links.

    Returns:
        {
            "base_url": str,
            "domain": str,
            "links": [{"url": str, "text": str}],
            "footer_links": [{"url": str, "text": str}],
            "total": int,
            "error": str | None
        }
    """
    # Ensure URL has scheme
    if not start_url.startswith("http"):
        start_url = f"https://{start_url}"

    parsed = urlparse(start_url)
    domain = parsed.netloc.lstrip("www.")

    html, final_url = fetch_page(start_url)
    if not html:
        # Try http fallback
        http_url = start_url.replace("https://", "http://")
        html, final_url = fetch_page(http_url)

    if not html:
        return {
            "base_url": start_url,
            "domain": domain,
            "links": [],
            "footer_links": [],
            "total": 0,
            "error": "Could not fetch the website. Please check the URL and try again.",
        }

    base_url = final_url or start_url
    all_links = extract_links(html, base_url)
    footer_links = extract_footer_links(html, base_url)

    # Filter to same-domain links only
    same_domain_links = [l for l in all_links if is_same_domain(base_url, l["url"])]
    same_domain_footer = [l for l in footer_links if is_same_domain(base_url, l["url"])]

    # Cap to avoid excessive crawling
    same_domain_links = same_domain_links[:MAX_LINKS]

    return {
        "base_url": base_url,
        "domain": domain,
        "links": same_domain_links,
        "footer_links": same_domain_footer,
        "total": len(same_domain_links),
        "error": None,
    }


def fetch_page_details(url: str) -> dict:
    """
    Fetch a specific page and return its title and text content for classification.
    """
    html, _ = fetch_page(url)
    if not html:
        return {"title": "", "content": ""}
    return {
        "title": get_page_title(html),
        "content": get_page_text_preview(html),
    }
