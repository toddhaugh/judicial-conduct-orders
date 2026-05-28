#!/usr/bin/env python3
"""
analyze.py — The core pipeline script.

Workflow:
  1. Load existing orders.json (if it exists)
  2. Run scrapers to get current index of all orders
  3. Find orders not yet in the dataset (new) or not yet analyzed
  4. For each new/unanalyzed order, fetch the PDF and send to Claude API
  5. Parse the structured JSON response and store results
  6. Save updated orders.json

Run this script directly to perform a full update:
  python analyze.py

Or import and call run_pipeline() from other scripts.
"""

import base64
import json
import logging
import os
import sys
import time
from pathlib import Path

import anthropic
import requests

from circuits import CLAUDE_MODEL, API_DELAY, FETCH_DELAY, MAX_RETRIES
from scrape import scrape_all_enabled

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("analyze.log", mode="a"),
    ],
)
log = logging.getLogger(__name__)

# Paths
REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = REPO_ROOT / "data"
ORDERS_FILE = DATA_DIR / "orders.json"
DATA_DIR.mkdir(exist_ok=True)

# ─────────────────────────────────────────────
# Claude API system prompt
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are a legal expert analyzing U.S. federal judicial misconduct \
complaint orders. Extract structured information and respond ONLY with a valid JSON \
object — no markdown fences, no preamble, no explanation.

Required JSON fields:
{
  "subject": "Description of subject judge(s). Use title only since names are almost \
always withheld under 28 U.S.C. § 360(a) (e.g., 'Anonymous district judge', \
'Anonymous magistrate judge', 'Anonymous appellate judges (5)'). If a name IS \
explicitly stated in the document, include it.",
  "complainant": "Type of complainant: 'Pro se litigant', 'Attorney', 'Third party', \
or 'Unknown'",
  "theme": "Primary allegation — choose EXACTLY ONE: Bias, Conspiracy, Recusal, \
Procedural, Merits, Attorney, Disability, Intervening",
  "disposition": "Outcome in 3-7 words (e.g., 'Dismissed as frivolous', \
'Dismissed — not cognizable', 'Concluded — judge retired', 'Affirmed on review', \
'Dismissed — not indicative of misconduct')",
  "statute": "Primary statutory basis (e.g., '28 U.S.C. § 352(b)(1)(A)(iii)', \
'§ 352(b)(2)'). List multiple if applicable, comma-separated.",
  "repeat": "Is complainant flagged as a repeat or restricted filer? 'Yes', 'No', \
or 'Not indicated'",
  "summary": "2-4 sentences: what was alleged, what the record showed, and why the \
order reached its outcome. Be specific and factually precise."
}

Theme definitions:
- Bias: racial, ethnic, gender, political, or personal bias/prejudice in rulings
- Conspiracy: coordinated wrongdoing among multiple judges to harm complainant
- Recusal: judge failed to recuse despite conflict of interest or § 455 obligation
- Procedural: rules violations, improper procedure, or administrative misconduct
- Merits: complaint is a disguised appeal of an unfavorable ruling, no improper motive alleged
- Attorney: complaint arises from or directly relates to attorney disciplinary proceedings
- Disability: physical or mental incapacity impairing judicial function
- Intervening: complaint concluded because judge retired, died, or other mootness event

If the PDF is a scanned image (not machine-readable text), return exactly:
{"error": "PDF not machine-readable — scanned image"}

If the PDF is a Judicial Council affirmance order with minimal content, return:
{"subject": "Anonymous (subject of underlying CJ order)", "complainant": "Unknown",
 "theme": "Merits", "disposition": "Affirmed on review",
 "statute": "Rules of Judicial-Conduct, Rule 19(b)(1)",
 "repeat": "Not indicated",
 "summary": "Judicial Council affirmed the Chief Judge's dismissal order without \
additional findings."}"""


# ─────────────────────────────────────────────
# Dataset management
# ─────────────────────────────────────────────

def load_dataset() -> dict:
    """Load existing orders.json. Returns dict keyed by order id."""
    if ORDERS_FILE.exists():
        with open(ORDERS_FILE, "r") as f:
            data = json.load(f)
        log.info(f"Loaded {len(data)} existing orders from {ORDERS_FILE}")
        return data
    log.info("No existing dataset found — starting fresh")
    return {}


def save_dataset(data: dict) -> None:
    """Save orders dict to orders.json."""
    with open(ORDERS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log.info(f"Saved {len(data)} orders to {ORDERS_FILE}")


# ─────────────────────────────────────────────
# PDF fetching
# ─────────────────────────────────────────────

FETCH_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; JudicialOrdersBot/1.0; "
        "academic research tool)"
    )
}


def fetch_pdf_as_base64(url: str) -> str | None:
    """Fetch a PDF URL and return base64-encoded bytes."""
    for attempt in range(MAX_RETRIES):
        try:
            r = requests.get(url, headers=FETCH_HEADERS, timeout=30)
            r.raise_for_status()
            if "pdf" not in r.headers.get("content-type", "").lower() and len(r.content) < 1000:
                log.warning(f"Unexpected content type for {url}")
            time.sleep(FETCH_DELAY)
            return base64.standard_b64encode(r.content).decode("utf-8")
        except Exception as e:
            log.warning(f"PDF fetch attempt {attempt+1} failed for {url}: {e}")
            time.sleep(FETCH_DELAY * 2)
    log.error(f"Failed to fetch PDF: {url}")
    return None


# ─────────────────────────────────────────────
# Claude API analysis
# ─────────────────────────────────────────────

def analyze_pdf(client: anthropic.Anthropic, pdf_b64: str) -> dict:
    """Send a PDF to Claude and return parsed JSON result."""
    for attempt in range(MAX_RETRIES):
        try:
            response = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=1000,
                system=SYSTEM_PROMPT,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "document",
                                "source": {
                                    "type": "base64",
                                    "media_type": "application/pdf",
                                    "data": pdf_b64,
                                },
                            },
                            {
                                "type": "text",
                                "text": "Extract the structured information from this judicial misconduct order.",
                            },
                        ],
                    }
                ],
            )
            time.sleep(API_DELAY)

            # Parse response
            raw = response.content[0].text if response.content else ""
            clean = raw.replace("```json", "").replace("```", "").strip()
            return json.loads(clean)

        except json.JSONDecodeError as e:
            log.warning(f"JSON parse error (attempt {attempt+1}): {e}")
            time.sleep(API_DELAY * 2)
        except anthropic.RateLimitError:
            wait = 30 * (attempt + 1)
            log.warning(f"Rate limit hit — waiting {wait}s")
            time.sleep(wait)
        except anthropic.APIError as e:
            log.warning(f"API error (attempt {attempt+1}): {e}")
            time.sleep(API_DELAY * 2)

    return {"error": f"Analysis failed after {MAX_RETRIES} attempts"}


# ─────────────────────────────────────────────
# Main pipeline
# ─────────────────────────────────────────────

def run_pipeline(force_reanalyze: bool = False) -> dict:
    """
    Full update pipeline. Returns the updated dataset dict.

    Args:
        force_reanalyze: If True, re-analyze all orders even if already done.
                         Useful for bulk re-processing after prompt changes.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.error("ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # ── Step 1: Load existing dataset ──
    dataset = load_dataset()

    # ── Step 2: Scrape current index pages ──
    log.info("=== Scraping circuit index pages ===")
    scraped = scrape_all_enabled()

    # ── Step 3: Merge new orders into dataset ──
    new_count = 0
    for order in scraped:
        oid = order["id"]
        if oid not in dataset:
            dataset[oid] = order
            new_count += 1

    log.info(f"Found {new_count} new orders not in existing dataset")

    # ── Step 4: Analyze orders that need it ──
    to_analyze = [
        o for o in dataset.values()
        if (not o.get("analyzed") or force_reanalyze)
        and o.get("pdf_url")
        and not o.get("analysis_error", "").startswith("PDF not machine-readable")
    ]

    log.info(f"=== Analyzing {len(to_analyze)} orders ===")

    for i, order in enumerate(to_analyze, 1):
        oid = order["id"]
        log.info(f"[{i}/{len(to_analyze)}] {order.get('case_num', oid)} ({order.get('order_type')})")

        # Fetch PDF
        pdf_b64 = fetch_pdf_as_base64(order["pdf_url"])
        if not pdf_b64:
            dataset[oid]["analysis_error"] = "Failed to fetch PDF"
            dataset[oid]["analyzed"] = False
            # Save progress periodically
            if i % 10 == 0:
                save_dataset(dataset)
            continue

        # Analyze
        result = analyze_pdf(client, pdf_b64)

        if "error" in result:
            dataset[oid]["analysis_error"] = result["error"]
            dataset[oid]["analyzed"] = False
            log.warning(f"  Error: {result['error']}")
        else:
            # Merge analysis fields into order record
            dataset[oid].update({
                "subject":    result.get("subject", "Unknown"),
                "complainant": result.get("complainant", "Unknown"),
                "theme":      result.get("theme", "Unknown"),
                "disposition": result.get("disposition", "Unknown"),
                "statute":    result.get("statute", ""),
                "repeat":     result.get("repeat", "Not indicated"),
                "summary":    result.get("summary", ""),
                "analyzed":   True,
                "analysis_error": None,
            })
            log.info(f"  ✓ Theme: {result.get('theme')} | {result.get('disposition')}")

        # Save progress every 10 orders (resilience against interruption)
        if i % 10 == 0:
            save_dataset(dataset)

    # ── Step 5: Final save ──
    save_dataset(dataset)

    # ── Step 6: Summary report ──
    analyzed = sum(1 for o in dataset.values() if o.get("analyzed"))
    errors = sum(1 for o in dataset.values() if o.get("analysis_error"))
    log.info(f"=== Pipeline complete ===")
    log.info(f"  Total orders in dataset: {len(dataset)}")
    log.info(f"  Successfully analyzed:   {analyzed}")
    log.info(f"  Errors / skipped:        {errors}")

    return dataset


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Analyze judicial misconduct orders")
    parser.add_argument(
        "--force", action="store_true",
        help="Re-analyze all orders, even those already processed"
    )
    args = parser.parse_args()
    run_pipeline(force_reanalyze=args.force)
