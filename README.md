# Job Search Tools (`Job_Search_Tools`)

A production-grade recruitment intelligence, job scraping, multi-dimensional filtering, and automated application workflow platform.

This project streamlines the job search and application lifecycle by combining high-speed REST API scrapers, fine-grained negative filtering, an interactive Streamlit analytics dashboard, and automated browser dispatching powered by Playwright.

---

## 📁 Repository Structure

```text
Job_Search_Tools/
├── .gitignore              # Global gitignore (excludes data, venv, browser sessions, and personal PII)
├── .vscode/                # Workspace editor settings
├── README.md               # Project documentation
│
├── 104_scrappers/          # Module 1: 104 Job Bank Scrapers & Data Sync
│   ├── crawl_listings.py   # High-speed batch listing collector across 46 target categories
│   ├── scraper.py          # Core 104 REST API scraper with anti-ban protections
│   ├── db_sync.py          # Optional SQLite synchronization and UPSERT engine
│   ├── query_filter.py     # CLI-based multi-criteria filtering demo
│   └── data/               # Scraper data store (JSONL, SQLite, target taxonomy)
│       ├── target_categories.json # 46 target job categories taxonomy
│       └── job_categories.json    # Complete 104 official category taxonomy tree
│
└── 104_job_search/         # Module 2: 104 Interactive Dashboard & Auto-Applier
    ├── app.py              # Streamlit interactive dashboard & batch application hub
    ├── applier.py          # Core Playwright browser automation module for real 104 application
    ├── login_tool.py       # One-time browser authorization and session persistence helper
    └── data/               # User state & configuration (strictly local / gitignored)
        ├── filter_rules.json      # Negative noise filtering rules
        ├── default_cv.json        # Custom cover letter templates (optional override)
        └── user_pipeline.json     # Application progress and interaction history
```

---

## 🚀 Key Modules & Architecture

### 1. High-Efficiency API Crawler (`104_scrappers/`)
- **Direct REST Interface**: Directly queries 104's internal JSON API endpoints, bypassing browser rendering overhead for maximum throughput.
- **Systematic Taxonomy Traversal**: Traverses 46 targeted job categories (Software Engineering, AI/Machine Learning, Cloud/DevOps, and Technical PM) to achieve full listing coverage without hitting 104's 100-page query ceiling.
- **Anti-Ban Protection & Stealth**:
  - Dynamic randomized jitter delays (2.5s ~ 4.5s).
  - Periodic batch cooldowns to prevent IP flooding.
  - Exponential backoff retry handler on HTTP 429 / 403 status codes.
  - User-Agent header rotation matching genuine modern browsers.
- **Stream-Friendly Storage**: Appends records sequentially to `104_scrappers/data/jobs_104.jsonl`, enabling interruption recovery and instant deduplication via `job_id`.

### 2. Multi-Dimensional Funnel Filtering & Intelligence
- **Negative Noise Elimination**: Automatically filters out irrelevant postings (security guards, custodial labor, telemarketing, direct sales, low-level hardware/firmware, and fake AI data annotation gigs) using customizable keywords in `104_job_search/data/filter_rules.json`.
- **Salary Normalization**: Distinguishes numeric pay brackets from legal "Negotiable (> NT$40,000)" postings.
- **Experience Mapping**: Translates 104 internal integer codes (`0` to `11`) into human-readable brackets (Entry-level, 1~3 years, 3~5 years, etc.).

### 3. Interactive Web Dashboard & Real Auto-Applier (`104_job_search/`)
- **Real-Time Search Bar**: Top-level instant full-text search across job titles, company names, job descriptions, and skills within the filtered dataset.
- **Multi-Browser Playwright Engine**: Supports executing automated applications using your preferred browser:
  - Brave Browser (`brave-browser`)
  - Google Chrome (`google-chrome`)
  - Microsoft Edge (`microsoft-edge`)
  - Mozilla Firefox (`firefox`)
- **Clear Dropdown Pagination**: Selectbox navigation displaying the exact total page count and job range, with 10 postings per page.
- **Configurable Batch Apply Quota**: Set your desired sequential daily limit (e.g. 20~50 jobs/day) with randomized human delays (10~16 seconds) between submissions.
- **State Persistence**: Application statuses (`unprocessed`, `shortlisted`, `applied`, `skipped`) are stored in `104_job_search/data/user_pipeline.json`. Applied jobs are excluded from the unprocessed view so you can seamlessly resume the next day without re-applying.

---

## 🛠️ Environment Setup & Quick Start

This project uses [`uv`](https://github.com/astral-sh/uv) for fast, isolated Python environment and dependency management.

### 1. Clone & Setup Environment

```bash
# Clone the repository
git clone https://github.com/<your-username>/Job_Search_Tools.git
cd Job_Search_Tools

# Create virtual environment with Python 3.12 (managed by uv)
uv venv --python 3.12
source .venv/bin/activate

# Install dependencies & Playwright browser drivers
uv pip install requests pandas openpyxl beautifulsoup4 streamlit playwright
playwright install chromium
```

### 2. Run the Batch Crawler (Optional / On-demand)

```bash
# Crawls listings across the 46 configured target categories
python 104_scrappers/crawl_listings.py
```

### 3. Launch the Streamlit Web Application

```bash
streamlit run 104_job_search/app.py
```

Access the interactive dashboard in your browser at `http://localhost:8501`.

---

## 🔒 Privacy & Security

This repository maintains strict anonymity and privacy in `.gitignore`:
- **Local Browser Sessions & Screenshots**: Persistent cookies and session data (`104_job_search/browser_data/`) and verification screenshots (`104_job_search/screenshots/`) are strictly untracked.
- **Scraped Raw Databases**: Raw data dumps (`104_scrappers/data/*.jsonl`, `*.db`) are excluded from Git.
- **Application History**: User pipelines, application timestamps, and custom cover letter overrides (`104_job_search/data/user_pipeline.json`, `104_job_search/data/default_cv.json`) remain strictly local.
- **Zero Plaintext Credentials**: Authentication runs through local persistent browser profiles without storing plaintext account passwords.

---

## ⚖️ Disclaimer

This repository is developed for personal career intelligence, research, and educational purposes only. Users are responsible for complying with the Terms of Service and acceptable use policies of target platforms. The author assumes no liability for any misuse or service disruption.
