#!/usr/bin/env python3
"""
build.py — Reads data/orders.json and assembles the final index.html.

The HTML shell lives in scripts/template.html.
This script injects the JSON data and metadata, then writes
the result to index.html at the repo root.

Run after analyze.py completes:
  python build.py
"""

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

REPO_ROOT   = Path(__file__).parent.parent
DATA_FILE   = REPO_ROOT / "data" / "orders.json"
TEMPLATE    = Path(__file__).parent / "template.html"
OUTPUT      = REPO_ROOT / "index.html"


def load_orders() -> list[dict]:
    """Load and sort orders from JSON dataset."""
    if not DATA_FILE.exists():
        log.error(f"Dataset not found: {DATA_FILE}")
        sys.exit(1)

    with open(DATA_FILE) as f:
        data = json.load(f)

    orders = list(data.values())
    # Sort by date descending (most recent first)
    orders.sort(key=lambda o: o.get("date", ""), reverse=True)
    log.info(f"Loaded {len(orders)} orders")
    return orders


def compute_stats(orders: list[dict]) -> dict:
    """Compute summary statistics for the tool header."""
    analyzed   = [o for o in orders if o.get("analyzed")]
    circuits   = sorted(set(o.get("circuit_name", "") for o in orders))
    year_min   = min((o.get("year", 9999) for o in orders), default=0)
    year_max   = max((o.get("year", 0)    for o in orders), default=0)

    theme_counts = {}
    for o in analyzed:
        t = o.get("theme", "Unknown") or "Unknown"
        theme_counts[t] = theme_counts.get(t, 0) + 1

    disp_counts = {}
    for o in analyzed:
        d = o.get("disposition", "Unknown") or "Unknown"
        # Normalize to broad category
        if "Dismissed" in d:
            cat = "Dismissed"
        elif "Affirmed" in d:
            cat = "Affirmed"
        elif "Concluded" in d:
            cat = "Concluded"
        else:
            cat = "Other"
        disp_counts[cat] = disp_counts.get(cat, 0) + 1

    return {
        "total":        len(orders),
        "analyzed":     len(analyzed),
        "circuits":     circuits,
        "year_min":     year_min,
        "year_max":     year_max,
        "theme_counts": theme_counts,
        "disp_counts":  disp_counts,
        "updated_at":   datetime.now(timezone.utc).strftime("%B %d, %Y"),
    }


def build_html(orders: list[dict], stats: dict) -> str:
    """Read template and inject data."""
    if not TEMPLATE.exists():
        log.error(f"Template not found: {TEMPLATE}")
        sys.exit(1)

    with open(TEMPLATE) as f:
        html = f.read()

    # Inject the orders JSON
    orders_json = json.dumps(orders, ensure_ascii=False, separators=(",", ":"))
    html = html.replace("__ORDERS_JSON__", orders_json)

    # Inject stats
    html = html.replace("__TOTAL__",    str(stats["total"]))
    html = html.replace("__ANALYZED__", str(stats["analyzed"]))
    html = html.replace("__YEAR_MIN__", str(stats["year_min"]))
    html = html.replace("__YEAR_MAX__", str(stats["year_max"]))
    html = html.replace("__UPDATED__",  stats["updated_at"])
    html = html.replace("__CIRCUITS__", ", ".join(stats["circuits"]) or "First Circuit")

    return html


def run_build() -> None:
    orders = load_orders()
    stats  = compute_stats(orders)
    html   = build_html(orders, stats)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(html)

    log.info(f"Built {OUTPUT} ({len(html):,} chars)")
    log.info(f"  Orders: {stats['total']} total, {stats['analyzed']} analyzed")
    log.info(f"  Years:  {stats['year_min']}–{stats['year_max']}")
    log.info(f"  Updated: {stats['updated_at']}")


if __name__ == "__main__":
    run_build()
