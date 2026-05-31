"""
Circuit configuration — single source of truth.
To add a new circuit, append an entry to CIRCUITS.
The scraper, analyzer, and builder all read from this file.
"""

CIRCUITS = [
    {
        "id": "01",
        "name": "First Circuit",
        "short": "1st Cir.",
        "states": "Maine, Massachusetts, New Hampshire, Rhode Island, Puerto Rico",
        "url": "https://www.ca1.uscourts.gov/judicial-conduct-disability",
        "scraper": "ca1",   # which scraper function to use
        "enabled": True,
    },
    # ── Add additional circuits here in Phase 2 ──
    # {
    #     "id": "02",
    #     "name": "Second Circuit",
    #     "short": "2nd Cir.",
    #     "states": "Connecticut, New York, Vermont",
    #     "url": "http://www.ca2.uscourts.gov/judges/judicial_conduct.html",
    #     "scraper": "ca2",
    #     "enabled": False,
    # },
    # {
    #     "id": "08",
    #     "name": "Eighth Circuit",
    #     "short": "8th Cir.",
    #     "states": "Arkansas, Iowa, Minnesota, Missouri, Nebraska, North Dakota, South Dakota",
    #     "url": "https://www.ca8.uscourts.gov/judicial-complaint-orders",
    #     "scraper": "ca8",
    #     "enabled": False,
    # },
]

# Committee on Judicial Conduct & Disability (national level)
COMMITTEE = {
    "id": "committee",
    "name": "Committee on Judicial Conduct & Disability",
    "short": "Committee",
    "states": "All Circuits",
    "url": "https://www.uscourts.gov/administration-policies/judicial-conduct-disability/judicial-conduct-and-disability-orders",
    "scraper": "committee",
    "enabled": False,   # Enable in Phase 2
}

# Model to use for PDF analysis
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

# Seconds to wait between API calls (respect rate limits)
API_DELAY = 1.2

# Seconds to wait between HTTP fetches
FETCH_DELAY = 2.0

# Maximum retries for failed API calls
MAX_RETRIES = 3
