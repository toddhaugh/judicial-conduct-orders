#!/usr/bin/env python3
"""
scrape.py — Fetches judicial misconduct order index pages for each
enabled circuit and returns a list of order metadata dicts.

Each dict contains:
  circuit_id, circuit_name, case_num, order_type,
  date, url, pdf_url

This module is called by analyze.py, which then compares
against the existing dataset to find only new entries.
"""

import re
import time
import logging
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

from circuits import CIRCUITS, FETCH_DELAY

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; JudicialOrdersBot/1.0; "
        "academic research tool; contact via GitHub)"
    )
}


# ─────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────

def fetch(url: str, retries: int = 3) -> Optional[str]:
    """Fetch a URL and return HTML text, or None on failure."""
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            time.sleep(FETCH_DELAY)
            return r.text
        except Exception as e:
            log.warning(f"Fetch attempt {attempt+1} failed for {url}: {e}")
            time.sleep(FETCH_DELAY * 2)
    log.error(f"All fetch attempts failed for {url}")
    return None


def make_order_id(circuit_id: str, case_num: str, order_type: str) -> str:
    """Create a stable unique ID for deduplication."""
    safe_num = re.sub(r"[^\w-]", "_", case_num)
    safe_type = "CJ" if order_type == "Chief Judge" else "JC"
    return f"{circuit_id}-{safe_num}-{safe_type}"


# ─────────────────────────────────────────────
# First Circuit scraper  (ca1.uscourts.gov)
# ─────────────────────────────────────────────

# The First Circuit publishes orders on per-year pages:
# https://www.ca1.uscourts.gov/YYYY
# Each page lists links to PDFs with anchor text like
# "01-24-90034 – 01-24-90035" and nearby date text.

CA1_BASE = "https://www.ca1.uscourts.gov"
CA1_YEARS = list(range(2013, datetime.now().year + 1))


def scrape_ca1_year(year: int) -> list[dict]:
    """Scrape one year page from the First Circuit."""
    url = f"{CA1_BASE}/{year}"
    html = fetch(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    orders = []

    # The page renders complaint orders as links inside
    # div.view-content or similar containers.
    # Each block typically looks like:
    #   <a href="/sites/ca1/files/...pdf">01-24-90034 – 01-24-90035</a>
    #   with date text nearby.

    # Find all links that point to PDFs
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True)

        # Only interested in links containing complaint numbers
        # Pattern: two-digit-dash-two-digit-dash-five-digit
        if not re.search(r"\d{2}-\d{2}-\d{5}", text):
            continue

        # Resolve relative URLs
        if href.startswith("/"):
            pdf_url = CA1_BASE + href
        elif href.startswith("http"):
            pdf_url = href
        else:
            continue

        # Must end in .pdf (or contain .pdf in path)
        if ".pdf" not in pdf_url.lower():
            continue

        # Try to extract a date from surrounding text
        # Walk up to find a parent element that might have date context
        date_str = _extract_ca1_date(a, year)

        # Determine order type from PDF filename
        # .O.pdf = Chief Judge order, .J.pdf = Judicial Council order
        fname = pdf_url.split("/")[-1].lower()
        if ".j.pdf" in fname or "judicial%20council" in fname.lower() or "affirmance" in fname.lower():
            order_type = "Judicial Council"
        else:
            order_type = "Chief Judge"

        # Extract all case numbers from the link text
        case_nums = re.findall(r"\d{2}-\d{2}-\d{5}", text)
        if not case_nums:
            continue

        # Use the first case number as the primary identifier
        primary_num = case_nums[0]

        order = {
            "id": make_order_id("01", primary_num + ("-" + order_type[0]), order_type),
            "circuit_id": "01",
            "circuit_name": "First Circuit",
            "circuit_short": "1st Cir.",
            "case_num": text,          # full display text e.g. "01-24-90034 – 01-24-90035"
            "primary_num": primary_num,
            "order_type": order_type,
            "date": date_str,
            "year": year,
            "pdf_url": pdf_url,
            # Analysis fields — populated by analyze.py
            "subject": None,
            "complainant": None,
            "theme": None,
            "disposition": None,
            "statute": None,
            "repeat": None,
            "summary": None,
            "analyzed": False,
            "analysis_error": None,
        }
        orders.append(order)

    # Deduplicate by pdf_url + order_type (multiple case numbers
    # pointing to the same PDF should yield one record)
    seen_pdfs = {}
    deduped = []
    for o in orders:
        key = (o["pdf_url"], o["order_type"])
        if key not in seen_pdfs:
            seen_pdfs[key] = True
            # Generate a stable id based on pdf filename + type
            fname_stem = o["pdf_url"].split("/")[-1].replace(".pdf", "").replace("%20", "_")
            o["id"] = f"01-{fname_stem}-{'CJ' if o['order_type']=='Chief Judge' else 'JC'}"
            deduped.append(o)

    log.info(f"  CA1 {year}: found {len(deduped)} unique orders")
    return deduped


def _extract_ca1_date(link_tag, fallback_year: int) -> str:
    """
    Try to find a date near the link tag.
    Returns ISO date string YYYY-MM-DD or YYYY-01-01 as fallback.
    """
    # Look in parent elements for date-like text
    date_pattern = re.compile(
        r"(January|February|March|April|May|June|July|August|September|October|November|December)"
        r"\s+\d{1,2},\s+\d{4}"
        r"|(\d{1,2}/\d{1,2}/\d{2,4})"
        r"|(\d{4}-\d{2}-\d{2})"
    )

    # Check up to 5 ancestor elements
    node = link_tag
    for _ in range(5):
        node = node.parent
        if node is None:
            break
        text = node.get_text(" ", strip=True)
        m = date_pattern.search(text)
        if m:
            raw = m.group(0)
            try:
                # Try various formats
                for fmt in ("%B %d, %Y", "%m/%d/%Y", "%m/%d/%y", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
                    except ValueError:
                        continue
            except Exception:
                pass

    return f"{fallback_year}-01-01"


def scrape_ca1() -> list[dict]:
    """Scrape all years for the First Circuit."""
    log.info("Scraping First Circuit...")
    all_orders = []
    for year in reversed(CA1_YEARS):
        year_orders = scrape_ca1_year(year)
        all_orders.extend(year_orders)
    log.info(f"First Circuit total: {len(all_orders)} orders found")
    return all_orders


# ─────────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────────

SCRAPERS = {
    "ca1": scrape_ca1,
    # "ca2": scrape_ca2,   # Add in Phase 2
    # "ca8": scrape_ca8,
}


def scrape_all_enabled() -> list[dict]:
    """Run all scrapers for enabled circuits and return combined list."""
    all_orders = []
    for circuit in CIRCUITS:
        if not circuit["enabled"]:
            continue
        scraper_key = circuit["scraper"]
        if scraper_key not in SCRAPERS:
            log.warning(f"No scraper implemented for {circuit['name']} ({scraper_key})")
            continue
        orders = SCRAPERS[scraper_key]()
        all_orders.extend(orders)
    log.info(f"Total orders scraped across all circuits: {len(all_orders)}")
    return all_orders


if __name__ == "__main__":
    orders = scrape_all_enabled()
    print(f"\nFound {len(orders)} total orders")
    for o in orders[:5]:
        print(f"  {o['id']}: {o['case_num']} ({o['order_type']}) — {o['date']}")
