# Job Search Tools (`Job_Search_Tools`)

A production-grade, extensible recruitment intelligence, job scraping, multi-dimensional filtering, and automated application workflow platform.

`Job_Search_Tools` is engineered as a modular multi-platform suite designed to support major international and regional job portals (including **104 Job Bank**, and architected for future expansion to platforms such as **Indeed**, **LinkedIn**, **JobStreet**, and **CakeResume**). Each supported platform maintains dedicated submodules for raw scraping (`*_scrappers`) and analytical querying, dashboard management, and automated application dispatching (`*_job_search`).

---

## 📁 Repository Structure

```text
Job_Search_Tools/
├── .gitignore                  # Global gitignore (excludes data, venv, browser sessions, and personal PII)
├── .vscode/                    # Workspace editor settings
├── README.md                   # Project documentation
│
├── 104/                        # Platform 1: 104 Job Bank Suite (Active)
│   ├── 104_scrappers/          # 104 Web Scrapers & Taxonomy Data
│   │   ├── crawl_listings.py   # High-speed batch listing collector across targeted categories
│   │   ├── scraper.py          # Core 104 REST API scraper with anti-ban protections
│   │   └── data/               # Scraper data store (JSONL, SQLite, target taxonomy)
│   │       ├── target_categories.json # Selected categories to crawl (customizable)
│   │       ├── job_categories.json    # Complete 104 official category taxonomy tree
│   │       └── jobs_104.jsonl         # Scraped raw jobs stream (local / gitignored)
│   │
│   └── 104_job_search/         # 104 Interactive Dashboard, Querying & Auto-Applier
│       ├── app.py              # Streamlit interactive dashboard & batch application hub
│       ├── applier.py          # Core Playwright browser automation module for real 104 application
│       ├── login_tool.py       # One-time browser authorization and session persistence helper
│       ├── db_sync.py          # SQLite synchronization and UPSERT engine
│       ├── query_filter.py     # CLI-based multi-criteria filtering demo
│       ├── browser_data/       # Persistent browser profile & login cookies (local / gitignored)
│       ├── screenshots/        # Proof-of-application & verification screenshots (local / gitignored)
│       └── data/               # User state & configuration (strictly local / gitignored)
│           ├── filter_rules.json      # Negative noise filtering rules
│           ├── default_cv.json        # Custom cover letter templates (optional override)
│           └── user_pipeline.json     # Application progress and interaction history
│
├── indeed/                     # Platform 2: Indeed Suite (Planned)
│   ├── indeed_scrappers/
│   └── indeed_job_search/
│
├── linkedin/                   # Platform 3: LinkedIn Suite (Planned)
│   ├── linkedin_scrappers/
│   └── linkedin_job_search/
│
└── jobstreet/                  # Platform 4: JobStreet Suite (Planned)
    ├── jobstreet_scrappers/
    └── jobstreet_job_search/
```

---

## 🛠️ General Environment Setup

This project uses [`uv`](https://github.com/astral-sh/uv) for fast, isolated Python virtual environments and dependency management.

### 1. Clone & Setup Environment

```bash
# Clone the repository
git clone https://github.com/jeniebeez/Job_Search_Tools.git
cd Job_Search_Tools

# Create virtual environment with Python 3.12 (managed by uv)
uv venv --python 3.12
source .venv/bin/activate

# Install dependencies & Playwright browser drivers
uv pip install requests pandas openpyxl beautifulsoup4 streamlit playwright
playwright install chromium
```

---

## 💼 Platform Guide: 104 Job Bank (`104/`)

104 Job Bank is Taiwan's largest job portal. This suite provides end-to-end coverage: high-efficiency taxonomy-based API crawling, intelligent negative filtering, an interactive Streamlit UI, and real automated application submissions via Playwright.

### 1. Key Submodules & Architecture

#### A. High-Efficiency API Scraper (`104/104_scrappers/`)
- **Direct REST API Interface**: Directly interfaces with 104's internal JSON API endpoints, bypassing browser rendering overhead for rapid listing collection.
- **Taxonomy Traversal**: Traverses configured job categories (by default: Software Engineering, AI/Machine Learning, Cloud/DevOps, and Technical PM) to achieve 100% full-market coverage without hitting 104's 100-page query ceiling.
- **Anti-Ban Protections**:
  - Dynamic randomized jitter delays (2.5s ~ 4.5s).
  - Periodic batch cooldown pauses.
  - Exponential backoff retry handler on HTTP 429 / 403 status codes.
  - User-Agent header rotation matching genuine modern browsers.
- **Stream-Friendly Storage**: Sequentially appends job objects to `104/104_scrappers/data/jobs_104.jsonl`, enabling instant deduplication via `job_id` and recovery from interruptions.

#### B. Intelligent Filtering & Database Sync (`104/104_job_search/`)
- **Negative Noise Elimination**: Automatically filters out irrelevant postings (security guards, custodial labor, telemarketing, direct sales, low-level hardware/firmware, and fake AI data annotation gigs) using customizable keywords in `104/104_job_search/data/filter_rules.json`.
- **Salary Normalization**: Distinguishes numeric pay brackets from legal "Negotiable (> NT$40,000)" postings.
- **Experience Mapping**: Translates 104 internal integer codes (`0` to `11`) into human-readable brackets (Entry-level, 1~3 years, 3~5 years, etc.).
- **Query & DB Sync Engines**:
  - `db_sync.py`: Synchronizes JSONL data into an indexed SQLite database (`jobs.db`) with UPSERT logic, auto-tagging noise classifications.
  - `query_filter.py`: Lightweight CLI tool for quick multi-criteria terminal experiments.

#### C. Interactive Dashboard & Playwright Auto-Applier (`104/104_job_search/`)
- **Top Real-Time Search Bar**: Instant full-text search across job titles, company names, job descriptions, and skills within the filtered dataset.
- **Multi-Browser Playwright Engine**: Supports executing automated applications using your preferred browser:
  - Brave Browser (`brave-browser`)
  - Google Chrome (`google-chrome`)
  - Microsoft Edge (`microsoft-edge`)
  - Mozilla Firefox (`firefox`)
- **Clear Dropdown Pagination**: Selectbox navigation displaying the exact total page count and job range, with 10 postings per page.
- **Configurable Batch Apply Quota**: Set your desired sequential daily limit (e.g. 20~50 jobs/day) with randomized human delays (10~16 seconds) between submissions.
- **State Persistence**: Application statuses (`unprocessed`, `shortlisted`, `applied`, `skipped`) are stored in `104/104_job_search/data/user_pipeline.json`. Applied jobs are automatically excluded from the unprocessed view so you can seamlessly resume the next day without re-applying.

---

### 2. How to Customize Crawl Categories & Keywords (104)

Users can easily customize what jobs to crawl without writing complex code:

#### Method A: Customize Category List for Batch Crawling (`crawl_listings.py`)

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
   *(Note: The crawler only requires `"code"` to fetch jobs; `"name"` and `"parent_name"` are used for console logging.)*

3. **Run Batch Crawler**:
   ```bash
   python 104/104_scrappers/crawl_listings.py
   ```

#### Method B: On-Demand Keyword or Category Search (`scraper.py`)

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

### 3. Launching 104 Tools

```bash
# 1. (Optional) Run one-time browser login authorization helper
python 104/104_job_search/login_tool.py

# 2. (Optional) Run batch listings crawler
python 104/104_scrappers/crawl_listings.py

# 3. Launch the Streamlit interactive dashboard & auto-applier
streamlit run 104/104_job_search/app.py
```

Access the dashboard in your browser at `http://localhost:8501`.

---

## 🌐 Planned Platforms & Extensibility

`Job_Search_Tools` follows a uniform architectural blueprint across all target platforms:
* `<platform>/<platform>_scrappers/`: Platform-specific API or HTML parsers, pagination handlers, anti-bot bypasses, and category taxonomy files.
* `<platform>/<platform>_job_search/`: Filtering pipelines, normalization engines, Streamlit UI dashboards, and Playwright automated submission scripts.

Upcoming platform modules:
- **Indeed (`indeed/`)**: Aggregated international job listings, salary distribution estimates, and automated dispatching.
- **LinkedIn (`linkedin/`)**: Professional network job intelligence, company headcount growth tracking, and Easy Apply automation.
- **JobStreet (`jobstreet/`)**: Southeast Asian regional tech and finance job market scraping and tracking.

---

## 🔒 Privacy, Security & Proof Screenshots

This repository maintains strict anonymity and privacy in `.gitignore`:
- **Local Browser Sessions (`browser_data/`)**: Persistent cookies, tokens, and browser profiles are stored exclusively on your local machine and never committed to Git.
- **Scraped Raw Databases (`*.jsonl`, `*.db`)**: Raw data dumps are excluded from version control.
- **Application History & Custom Templates (`data/user_pipeline.json`, `data/default_cv.json`)**: Application timestamps, cover letter drafts, and personal notes remain strictly local.
- **Proof-of-Application Screenshots (`screenshots/`)**:
  - When an automated job application is submitted, the system captures an instant screenshot of the platform's confirmation modal.
  - The screenshot path is saved to `user_pipeline.json` as an audit trail for the applicant to verify when and how each job was submitted.
  - Screenshots are strictly local and ignored by Git; users can safely delete them anytime to reclaim disk space.
- **Zero Plaintext Credentials**: Authentication runs through local persistent browser profiles without storing plaintext account passwords.

---

## ⚖️ Disclaimer

This repository is developed for personal career intelligence, research, and educational purposes only. Users are responsible for complying with the Terms of Service and acceptable use policies of target platforms. The author assumes no liability for any misuse or service disruption.
