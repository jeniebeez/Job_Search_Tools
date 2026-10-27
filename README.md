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
- **Smart 3-in-1 Synchronization (`appear_date` Upsert + Closed Job Pruning + New Job Insertion)**:
  - Stores job objects in `104/104_scrappers/data/jobs_104.jsonl`.
  - Running `crawl_listings.py` by default performs a full synchronization across all target categories:
    1. **Existing Jobs Comparison & Update**: Cross-checks `(job_id, appear_date)` in memory—if `appear_date` is unchanged, the record is skipped immediately without wasting resources; if `appear_date` has changed, the record is updated in-place (`Upsert`).
    2. **Closed Jobs Deletion (Set-Difference Pruning)**: Computes the set difference (`existing_records - seen_job_ids`) after traversing all target categories to automatically delete delisted/closed postings directly from `jobs_104.jsonl` (without needing prior application attempts), while also cleaning up or restoring any `"職缺已關閉"` entries in `user_pipeline.json`.
    3. **Brand-New Jobs Insertion**: Appends newly posted `job_id`s into `jobs_104.jsonl`.
  - Optionally accepts `--is-new <int>` (`0`, `3`, `7`, `14`, `30`) to quickly fetch only postings updated within the last `N` days.

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
- **Uncapped / Configurable Batch Apply**: Defaults to unlimited sequential application across all matching unapplied postings (with an optional toggle to set a custom batch count), protected by randomized human delays (10~16 seconds) between submissions.
- **State Persistence & Smart Auto-Routing**: Application statuses (`unprocessed`, `shortlisted`, `applied`, `skipped`) are persisted in `104/104_job_search/data/user_pipeline.json` immediately after each job is processed.

#### D. Search & Keyword Filtering Syntax Guide (`app.py`)
The Streamlit dashboard provides a two-stage keyword filtering and relevance-ranking mechanism that combines **OR (Union)** and **AND (Intersection)** logic:
1. **Sidebar "🏷️ 技能標籤 / 關鍵字過濾" (Full-Content `OR` Filter + Auto-Relevance Sorting)**:
   - **Searches Full Content**: Matches against `Job Title + Job Categories + Full Job Description`.
   - **Comma Delimiters (`,` or `，`) & Optional Whitespace**: Supports both half-width (`,`) and full-width (`，`) commas. Spaces around commas are automatically stripped via `.strip()`, so `Python, RAG, PyTorch`, `Python,RAG,PyTorch`, and `Python，RAG，PyTorch` behave identically.
   - **English Word-Boundary Protection**: Pure ASCII keywords (such as `AI`, `RAG`, `LLM`) automatically enforce regex word boundaries `(?<![a-z0-9])...(?![a-z0-9])` so `RAG` never false-matches English words like `storage` or `average`, and `AI` never false-matches `email` or `maintain`.
   - **Automatic Relevance Sorting (`🔥 命中 N 項`)**: Whenever sidebar skill keywords are active, matching jobs are automatically sorted from highest to lowest by `(1) Title Keyword Hits` and `(2) Total Keyword Hits`, placing the most relevant roles at Page 1 and displaying a `🔥 命中 N 項` badge on each card.
   - *Note*: Watch out for spaces **inside** a multi-word keyword — e.g., `生成式AI` vs. `生成式 AI` are matched as literal substrings, so including both (`生成式AI, 生成式 AI`) ensures maximum recall.
2. **Top "🔍 即時檢索職缺" Search Bar (Role / Title `AND` Refinement)**:
   - Supports comma-separated multi-keywords and provides a scope toggle:
     - **`🎯 僅職稱與公司名 (精準鎖定)` (Default)**: Matches **only** the job title and company name. Ideal for filtering by role titles (e.g., `工程師, Engineer, Developer, 演算法, 研究`) without overlapping with your sidebar technical keywords.
     - **`📄 全文檢索 (含工作內容)`**: Searches across title, company name, full description, and region.

#### E. Job Pipeline Status Definitions (`unprocessed`, `shortlisted`, `applied`, `skipped`)
Every job tracked in `104/104_job_search/data/user_pipeline.json` belongs to one of four lifecycle states, selectable in the sidebar under **"職缺處理狀態"**:

| Status | UI Label | Meaning & How Jobs Enter This State |
| :--- | :--- | :--- |
| **`unprocessed`** | **全部未處理 (Unprocessed)** | **Default state** for all newly scraped postings that have not yet been applied to, bookmarked, or skipped. |
| **`shortlisted`** | **⭐ 已收藏候選 (Shortlisted)** | **1. Manual Bookmark / Auto-Routed Mandatory Questionnaire (`⚠️ 含公司必填提問`)**: Jobs you manually starred, or jobs where a company requires custom mandatory questionnaire answers (`此為必填問題`) that blocked automated batch submission.<br>**2. Dedicated Semi-Automated Workflow**: Batch auto-apply buttons (`依序投遞` / `投遞所有收藏`) are intentionally hidden in this view. Clicking **`🚀 立即投遞`** on a shortlisted card opens the browser, selects your resume, **pre-fills your cover letter, and pauses on the application modal** so you can type in the company's custom questions and submit manually (automatically detecting `應徵成功` once you submit, or you can click **`✅ 已投遞`** on the card to archive it directly). |
| **`applied`** | **🚀 已投遞 (Applied)** | **Verified or Manually Archived Submissions**: Jobs where the Playwright engine verified 104's official `應徵成功` (`/job/apply/done`) confirmation screen, or jobs you manually marked via the **`✅ 已投遞`** button on a card. Automatically hidden from the `Unprocessed` queue so you never double-apply. |
| **`skipped`** | **❌ 已略過 (Skipped)** | **1. Manual Skip**: Jobs you manually dismissed via the `❌ 略過` button.<br>**2. Auto-Routed (Closed / Expired Job `❌ 職缺已關閉`)**: During automated application, if 104 indicates the position is closed or no longer accepting applications (`結束徵才 / 職缺已關閉`), the engine immediately aborts within 1 second and **automatically moves the job to `skipped`** with a `📌 ❌ 職缺已關閉或結束徵才` badge so future batch runs never waste time reopening it. |

---

### 2. Cover Letter Management & Persistence (`default_cv.json`)

When applying on 104, a tailored cover letter (自我推薦信) dramatically increases recruiter response rates and interview conversions.

#### How It Works:
1. **Auto-Initialization on First Run**:
   When any user launches the dashboard (`streamlit run 104/104_job_search/app.py`) for the first time, the system automatically checks if `104/104_job_search/data/default_cv.json` exists. If missing, it **automatically creates it** pre-populated with standard starter templates (Backend, AI/Data, PM, and General).
2. **Two Ways to Customize & Persist**:
   - **Method A: Directly in the Streamlit Web UI (Recommended)**:
     - Select any template from the dropdown in the left sidebar.
     - Edit the text directly in the "編輯自薦信內容" text area.
     - Click **"💾 儲存此模板修改"** to permanently save your changes into `default_cv.json`.
     - Click **"➕ 另存為新模板"** to create and save a new custom template under a custom title (e.g. "量化研究員專用信").
     - On all subsequent launches, Streamlit automatically loads your saved templates.
   - **Method B: Edit `default_cv.json` in Your Editor**:
     - You can also directly open `104/104_job_search/data/default_cv.json` in VS Code or any text editor and manage your template dictionary in JSON format.
3. **Strict Privacy Protection**:
   - `default_cv.json` is strictly ignored by `.gitignore`. Your candidate name, contact info, personal portfolio links, and cover letters will **never be committed or pushed to GitHub**, guaranteeing 100% personal data privacy.

---

### 3. How to Customize Crawl Categories & Keywords (104)

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
    # scraper.crawl_query(jobcat="2007001012", max_pages=5)
```

Run:
```bash
python 104/104_scrappers/scraper.py
```

---

### 4. Execution Commands & Typical Workflows

Depending on your current task, use the following commands:

#### 🔹 Command 1: One-Time Browser Login Authorization (Optional)
```bash
python 104/104_job_search/login_tool.py
```
- **What it does**: Launches a dedicated browser window (Brave / Chrome) pointing to 104's sign-in page, allowing you to log in with your credentials or third-party auth (Google, LINE). The login cookies and tokens are permanently saved to `104/104_job_search/browser_data/`.
- **When to use**: Run once when setting up a fresh environment, or whenever your 104 session expires. *(Note: You can also trigger this directly inside the Streamlit UI sidebar via the "🔑 檢查 / 開啟 104 登入視窗" button).*

#### 🔹 Command 2: Batch Listings Scraper & Synchronizer (Data Ingestion & Full Cleanup)
```bash
# Default: Full 3-in-1 synchronization (updates changed jobs, adds new jobs, and deletes closed jobs)
python 104/104_scrappers/crawl_listings.py

# Optional: Only fetch postings updated within the last N days (0=today, 3=3 days, 7=1 week, 14=2 weeks, 30=1 month)
python 104/104_scrappers/crawl_listings.py --is-new 7
```
- **What it does**: Traverses all category codes defined in `104/104_scrappers/data/target_categories.json` via high-speed API endpoints and synchronizes active postings into `104/104_scrappers/data/jobs_104.jsonl`.
- **Core 3-in-1 Synchronization (Default Execution)**:
  1. **Existing Jobs Comparison & Update (`appear_date` Upsert)**: Compares `(job_id, appear_date)` against `jobs_104.jsonl`. If `appear_date` is identical, the job is skipped immediately to save resources; if `appear_date` has changed, its description, title, salary, and metadata are updated in place.
  2. **Closed Jobs Deletion (Set-Difference Pruning)**: Compares all existing records in `jobs_104.jsonl` against the active `job_id`s returned by 104 across all categories (`existing_records - seen_job_ids`), automatically deleting delisted/closed jobs directly from `jobs_104.jsonl` without requiring prior application attempts, while also cleaning up or restoring any `"職缺已關閉"` entries in `user_pipeline.json`.
  3. **Brand-New Jobs Insertion**: Appends newly posted `job_id`s directly into `jobs_104.jsonl`.
- **When to skip this command**:
  - If your local `jobs_104.jsonl` was recently updated and your goal is to filter jobs, draft cover letters, or apply to positions, **skip this command** and proceed directly to Command 3.

#### 🔹 Command 3: Launch Streamlit Analytics Dashboard & Auto-Applier (Daily Driver ⭐)
```bash
streamlit run 104/104_job_search/app.py
```
- **What it does**: Launches the local interactive web interface (accessible at `http://localhost:8501`).
- **Core Daily Workflow**:
  1. **Filter & Search**: Query positions using the top real-time search bar (with `🎯 僅職稱與公司名` or `📄 全文檢索` scope) and multi-dimensional sidebar filters (regions, salary thresholds, experience levels, noise elimination, and word-boundary skill keywords).
  2. **Review Candidates**: Browse matching postings sorted by keyword relevance (`🔥 命中 N 項`), 10 jobs per page, with direct 104 job links.
  3. **Select Cover Letter**: Choose or edit your tailored cover letter templates.
  4. **Dispatch Applications**: Click **"🚀 依序投遞全部 N 筆篩選職缺"** (or optionally enable a custom batch limit in the sidebar) to execute automated, jitter-throttled Playwright browser applications. For jobs routed to **⭐ 已收藏候選 (Shortlisted)** due to mandatory custom questions, click **"🚀 立即投遞"** on the card to open a pre-filled application window for manual answer completion, and click **"✅ 已投遞"** to archive.
  5. **Track Progress**: Completed applications (`applied`), custom-question candidates (`shortlisted`), and closed/dismissed jobs (`skipped`) are automatically saved to `104/104_job_search/data/user_pipeline.json` and excluded from the "Unprocessed" view for seamless next-day progress continuity.

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
