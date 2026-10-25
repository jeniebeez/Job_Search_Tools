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
└── 104/                    # 104 Job Bank Intelligence Platform
    ├── 104_scrappers/      # Submodule 1: High-Speed Web Scrapers & Taxonomy Data
    │   ├── crawl_listings.py   # High-speed batch listing collector across targeted categories
    │   ├── scraper.py          # Core 104 REST API scraper with anti-ban protections
    │   └── data/               # Scraper data store (JSONL, SQLite, target taxonomy)
    │       ├── target_categories.json # Selected categories to crawl (customizable)
    │       ├── job_categories.json    # Complete 104 official category taxonomy tree
    │       └── jobs_104.jsonl         # Scraped raw jobs stream (local / gitignored)
    │
    └── 104_job_search/     # Submodule 2: Interactive Dashboard, Querying & Auto-Applier
        ├── app.py              # Streamlit interactive dashboard & batch application hub
        ├── applier.py          # Core Playwright browser automation module for real 104 application
        ├── login_tool.py       # One-time browser authorization and session persistence helper
        ├── db_sync.py          # Optional SQLite synchronization and UPSERT engine
        ├── query_filter.py     # CLI-based multi-criteria filtering demo
        ├── browser_data/       # Persistent browser profile & login cookies (local / gitignored)
        ├── screenshots/        # Proof-of-application & verification screenshots (local / gitignored)
        └── data/               # User state & configuration (strictly local / gitignored)
            ├── filter_rules.json      # Negative noise filtering rules
            ├── default_cv.json        # Custom cover letter templates (optional override)
            └── user_pipeline.json     # Application progress and interaction history
```

---

## 🚀 Key Modules & Architecture

### 1. High-Efficiency API Crawler (`104/104_scrappers/`)
- **Direct REST Interface**: Directly queries 104's internal JSON API endpoints, bypassing browser rendering overhead for maximum throughput.
- **Systematic Taxonomy Traversal**: Traverses configured job categories (by default: Software Engineering, AI/Machine Learning, Cloud/DevOps, and Technical PM) to achieve full listing coverage without hitting 104's 100-page query ceiling.
- **Anti-Ban Protection & Stealth**:
  - Dynamic randomized jitter delays (2.5s ~ 4.5s).
  - Periodic batch cooldowns to prevent IP flooding.
  - Exponential backoff retry handler on HTTP 429 / 403 status codes.
  - User-Agent header rotation matching genuine modern browsers.
- **Stream-Friendly Storage**: Appends records sequentially to `104/104_scrappers/data/jobs_104.jsonl`, enabling interruption recovery and instant deduplication via `job_id`.

### 2. Multi-Dimensional Funnel Filtering & Intelligence (`104/104_job_search/`)
- **Negative Noise Elimination**: Automatically filters out irrelevant postings (security guards, custodial labor, telemarketing, direct sales, low-level hardware/firmware, and fake AI data annotation gigs) using customizable keywords in `104/104_job_search/data/filter_rules.json`.
- **Salary Normalization**: Distinguishes numeric pay brackets from legal "Negotiable (> NT$40,000)" postings.
- **Experience Mapping**: Translates 104 internal integer codes (`0` to `11`) into human-readable brackets (Entry-level, 1~3 years, 3~5 years, etc.).
- **Query & DB Sync Engines (`db_sync.py`, `query_filter.py`)**:
  - `db_sync.py`: Synchronizes JSONL data into an indexed SQLite database (`jobs.db`), auto-tagging noise classifications.
  - `query_filter.py`: Lightweight CLI querying tool for instant command-line filtering experiments.

### 3. Interactive Web Dashboard & Real Auto-Applier (`104/104_job_search/`)
- **Real-Time Search Bar**: Top-level instant full-text search across job titles, company names, job descriptions, and skills within the filtered dataset.
- **Multi-Browser Playwright Engine**: Supports executing automated applications using your preferred browser:
  - Brave Browser (`brave-browser`)
  - Google Chrome (`google-chrome`)
  - Microsoft Edge (`microsoft-edge`)
  - Mozilla Firefox (`firefox`)
- **Clear Dropdown Pagination**: Selectbox navigation displaying the exact total page count and job range, with 10 postings per page.
- **Configurable Batch Apply Quota**: Set your desired sequential daily limit (e.g. 20~50 jobs/day) with randomized human delays (10~16 seconds) between submissions.
- **State Persistence**: Application statuses (`unprocessed`, `shortlisted`, `applied`, `skipped`) are stored in `104/104_job_search/data/user_pipeline.json`. Applied jobs are excluded from the unprocessed view so you can seamlessly resume the next day without re-applying.

---

## 📖 How to Customize Crawl Categories & Keywords

Users can easily customize what jobs to crawl without writing complex code. There are two primary workflows:

### Method A: Customize Category List for Batch Crawling (`crawl_listings.py`)

1. **Find Job Category Codes**:
   Open `104/104_scrappers/data/job_categories.json` (the complete official 104 taxonomy tree). Search for your target role keywords (e.g. `演算法`, `行銷`, `財務`, `硬體`, `前端`, `專案經理`).
   Each entry contains:
   - `"no"`: The category code (e.g. `"2007001012"`)
   - `"des"`: The category name (e.g. `"演算法開發工程師"`)

2. **Paste into `target_categories.json`**:
   Open `104/104_scrappers/data/target_categories.json` and adjust the list to include only the roles you want to crawl:
   ```json
   [
     {
       "code": "2007001012",
       "name": "演算法開發工程師",
       "parent_name": "軟體/工程類人員"
     },
     {
       "code": "2007001001",
       "name": "軟體工程師",
       "parent_name": "軟體/工程類人員"
     }
   ]
   ```
   *(Note: The crawler only requires `"code"` to fetch jobs; `"name"` and `"parent_name"` are used for clear console logging.)*

3. **Run Batch Crawler**:
   ```bash
   python 104/104_scrappers/crawl_listings.py
   ```

### Method B: On-Demand Keyword or Category Search (`scraper.py`)

If you want to quickly crawl jobs by specific keywords (e.g. "Python", "FastAPI", "Quantitative Research") instead of categories, open `104/104_scrappers/scraper.py` and modify the bottom execution block:

```python
if __name__ == "__main__":
    scraper = Job104Scraper()

    # Option 1: Crawl by keywords
    keywords = ["機器學習", "Python 後端", "量化交易"]
    for kw in keywords:
        scraper.crawl_query(keyword=kw, max_pages=3, fetch_details=False)

    # Option 2: Crawl by category code directly
    # scraper.crawl_query(category_code="2007001012", max_pages=5)
```

Run:
```bash
python 104/104_scrappers/scraper.py
```

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
# Crawls listings across the configured target categories
python 104/104_scrappers/crawl_listings.py
```

### 3. Launch the Streamlit Web Application

```bash
streamlit run 104/104_job_search/app.py
```

Access the interactive dashboard in your browser at `http://localhost:8501`.

---

## 🔒 Privacy, Security & Screenshots

This repository maintains strict anonymity and privacy in `.gitignore`:
- **Local Browser Sessions**: Persistent cookies and session data (`104/104_job_search/browser_data/`) are never tracked.
- **Scraped Raw Databases**: Raw data dumps (`104/104_scrappers/data/*.jsonl`, `*.db`) are excluded from Git.
- **Application History**: User pipelines, application timestamps, and custom cover letter overrides (`104/104_job_search/data/user_pipeline.json`, `104/104_job_search/data/default_cv.json`) remain strictly local.
- **Proof-of-Application Screenshots (`104/104_job_search/screenshots/`)**:
  - When an automated job application is submitted, the system captures an instant screenshot of 104's "Application Submitted" confirmation modal.
  - The screenshot path is saved to `user_pipeline.json` as an audit trail for the applicant to verify when and how each job was submitted.
  - Screenshots are strictly local and ignored by Git; users can safely delete them anytime to reclaim disk space.
- **Zero Plaintext Credentials**: Authentication runs through local persistent browser profiles without storing plaintext account passwords.

---

## ⚖️ Disclaimer

This repository is developed for personal career intelligence, research, and educational purposes only. Users are responsible for complying with the Terms of Service and acceptable use policies of target platforms. The author assumes no liability for any misuse or service disruption.
