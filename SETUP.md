# Setup Guide
## Federal Judicial Conduct & Disability Orders — Automated Tool

This guide covers the one-time setup required to get the tool running
and self-updating on GitHub Pages. Estimated time: 30–45 minutes.

---

## Prerequisites

- A GitHub account (free at github.com)
- An Anthropic API key (see Step 1 below)
- Python 3.10 or later installed on your computer

---

## Step 1 — Get an Anthropic API Key

1. Go to **https://console.anthropic.com** and sign in (or create an account).
   Note: this is separate from your Claude.ai subscription.
2. Click **API Keys** in the left sidebar → **Create Key**.
3. Name it something like `judicial-orders`.
4. **Copy the key immediately** — it is only shown once.
   It will look like: `sk-ant-api03-...`
5. Go to **Settings → Billing** and add a credit card.
6. Recommended: set a **Spend Limit** of $25/month as a safety cap.

**Cost estimate:** The first full run (First Circuit, ~120 PDFs) will cost
approximately $2–3. Monthly updates with new orders only will cost under $1.

---

## Step 2 — Create the GitHub Repository

1. Go to **github.com** → click the **+** icon → **New repository**.
2. Name it: `judicial-conduct-orders` (or any name you prefer).
3. Set visibility to **Public** (required for free GitHub Pages hosting).
4. Check **"Add a README file"**.
5. Click **Create repository**.

---

## Step 3 — Upload the Project Files

You need to upload the following files to your repository, preserving the
folder structure exactly:

```
judicial-conduct-orders/
├── requirements.txt
├── data/                          ← Create this empty folder (GitHub requires
│   └── .gitkeep                      a placeholder file in empty folders)
├── scripts/
│   ├── circuits.py
│   ├── scrape.py
│   ├── analyze.py
│   ├── build.py
│   └── template.html
└── .github/
    └── workflows/
        └── update.yml
```

**How to upload:**

Option A (simplest — GitHub web interface):
1. In your repository, click **Add file → Upload files**.
2. Drag all files into the upload area.
3. For files in subfolders (scripts/, .github/), you must upload them
   separately by navigating into each folder first, or use Option B.

Option B (recommended — GitHub Desktop):
1. Download GitHub Desktop from **desktop.github.com**.
2. Clone your repository to your computer.
3. Copy all the project files into the cloned folder, preserving the structure.
4. In GitHub Desktop, click **Commit to main** → **Push origin**.

**Important:** Create the `data/` folder with a `.gitkeep` file inside it.
The pipeline will create `orders.json` there on first run.

To create `.gitkeep` via the web interface:
- Navigate into `data/`, click **Add file → Create new file**,
  name it `.gitkeep`, leave it empty, and commit.

---

## Step 4 — Add Your API Key as a GitHub Secret

This keeps your API key secure — it is encrypted and never visible in code.

1. In your repository, click **Settings** (top menu).
2. In the left sidebar, click **Secrets and variables → Actions**.
3. Click **New repository secret**.
4. Name: `ANTHROPIC_API_KEY` (must be exact — the workflow reads this name).
5. Value: paste your API key (`sk-ant-api03-...`).
6. Click **Add secret**.

---

## Step 5 — Enable GitHub Pages

1. In repository **Settings**, click **Pages** in the left sidebar.
2. Under **Source**, select **Deploy from a branch**.
3. Branch: select **main**, folder: **/ (root)**.
4. Click **Save**.
5. After a minute, GitHub will show your public URL:
   `https://yourusername.github.io/judicial-conduct-orders/`

---

## Step 6 — Run the Pipeline for the First Time

The monthly schedule won't trigger until the 1st of next month.
To run it immediately:

1. In your repository, click **Actions** (top menu).
2. Click **Monthly Order Update** in the left sidebar.
3. Click **Run workflow** → **Run workflow** (green button).
4. Watch the progress — the first run takes 20–40 minutes.
5. When complete, visit your GitHub Pages URL to see the populated tool.

**What happens during the first run:**
- The scraper fetches all First Circuit order index pages (2013–present).
- Each PDF is sent to Claude for analysis.
- Results are saved to `data/orders.json`.
- The HTML tool is rebuilt and committed to your repository.
- GitHub Pages serves the updated site within 1–2 minutes.

---

## Step 7 — Verify Everything Works

1. Visit your public URL: `https://yourusername.github.io/judicial-conduct-orders/`
2. Confirm orders appear with themes, dispositions, and summaries.
3. Test search, year filter, and theme filter.
4. Click a case number to confirm the PDF link opens correctly.

---

## Ongoing Maintenance

**Automatic updates:** The workflow runs on the 1st of each month.
No action required from you. New orders are detected, analyzed, and
the site is rebuilt automatically.

**Manual update:** Go to Actions → Monthly Order Update → Run workflow.
Use "Re-analyze all orders" only if you want to reprocess everything
(e.g., after a prompt improvement). This is more expensive.

**Adding more circuits (Phase 2):**
1. Edit `scripts/circuits.py` — set `"enabled": True` for additional circuits.
2. Add the corresponding scraper function to `scripts/scrape.py`.
3. Push the changes to GitHub — the next workflow run will pick up the new circuits.

**Checking costs:**
- Go to **console.anthropic.com → Usage** to see API spend by day.
- Monthly update runs should cost well under $5 once the initial
  dataset is built.

---

## Troubleshooting

**Workflow fails with "ANTHROPIC_API_KEY not set":**
→ Check Step 4. The secret name must be exactly `ANTHROPIC_API_KEY`.

**Workflow fails with rate limit errors:**
→ The script has automatic retry logic. Try running again manually.
  If it persists, increase `API_DELAY` in `scripts/circuits.py`.

**Some PDFs show "not machine-readable":**
→ These are scanned image PDFs — the court has not digitized them.
  They are flagged in the dataset and skipped on future runs.

**GitHub Pages shows a 404:**
→ Check Settings → Pages to confirm it is pointing to the main branch
  root (`/`). Also confirm `index.html` exists in the root of your repo.

**The tool shows "Not yet analyzed" for many orders:**
→ The first run may not have completed all PDFs. Run the workflow again —
  it will pick up where it left off (skipping already-analyzed orders).

---

## File Reference

| File | Purpose |
|---|---|
| `scripts/circuits.py` | Circuit configuration and constants |
| `scripts/scrape.py` | Fetches circuit index pages, extracts PDF URLs |
| `scripts/analyze.py` | Sends PDFs to Claude API, manages dataset |
| `scripts/build.py` | Assembles final index.html from template + data |
| `scripts/template.html` | HTML/CSS/JS shell for the public tool |
| `data/orders.json` | Accumulated dataset (auto-generated, do not edit) |
| `.github/workflows/update.yml` | GitHub Actions automation |
| `requirements.txt` | Python package dependencies |

---

*Last updated: May 2026*
