# Web Scrapers Collection (`Web_Scrappers`)

A centralized collection and monorepo for production-grade web scrapers, data extraction pipelines, and automated workflow tools.

Each subproject in this repository focuses on a specific platform, implementing robust anti-blocking measures, stream-friendly data storage, and downstream integration tools (such as interactive dashboards, search filters, and automated dispatchers).

---

## 📁 Repository Structure

```text
Web_Scrappers/
├── .gitignore              # Global gitignore (excludes data, venv, and personal PII)
├── .vscode/                # Workspace editor settings
├── README.md               # Project documentation
│
└── 104/                    # Project 1: 104 Job Bank Scraper & Application Suite
    ├── app.py              # Streamlit interactive dashboard & application hub
    ├── applier.py          # Core Playwright browser automation module for real 104 application
    ├── login_tool.py       # One-time browser authorization and session persistence helper
    ├── crawl_listings.py   # High-speed batch listing collector across 46 categories
    ├── scraper.py          # Core 104 REST API scraper with anti-ban protections
    ├── db_sync.py          # Optional SQLite synchronization and UPSERT engine
    ├── query_filter.py     # CLI-based multi-criteria filtering demo
    ├── filter_rules.json   # Noise classification rules (hardware, annotators, service noise)
    ├── target_categories.json # Target job taxonomy configuration (46 subcategories)
    └── job_categories.json # Complete 104 official category taxonomy tree
```

---

## 🚀 Project 1: 104 Job Bank Intelligence & Application Suite

A full-stack job scraping, intelligent screening, and automated resume application workflow designed for the Taiwan tech job market (104 Job Bank).

### Key Features

1. **High-Efficiency API Crawler (`scraper.py`, `crawl_listings.py`)**
   - Directly interfaces with 104's internal REST API (bypassing heavy browser rendering).
   - **Systematic Taxonomy Traversal**: Queries 46 specific job subcategories (Software, AI/Data, Cloud/MIS, and Project Management) to achieve 100% full-coverage without hitting 104's 100-page limit.
   - **Anti-Ban Protection**:
     - Dynamic randomized delays (jitter: 2.5s ~ 4.5s).
     - Periodic batch cooldowns (pausing after bursts).
     - Exponential backoff retry handler on HTTP 429/403.
     - Realistic browser header rotation.
   - **Stream-Friendly JSONL Storage**: Zero data loss on interruption, supports incremental resume and in-memory deduplication (`job_id`).

2. **Multi-Dimensional Funnel Filtering Engine**
   - **Negative Noise Filtering**: Automatically eliminates non-office and low-relevance jobs (security guards, cleaners, telemarketers, raw hardware/firmware, low-level IC/embedded, data annotation) using customizable keyword rules in `filter_rules.json`.
   - **Salary & Negotiable Normalization**: Distinguishes between explicit numbers and legal "Negotiable (> NT$40,000)" markers.
   - **Experience Code Mapping**: Decodes 104's internal integer period codes (`0` to `11`) into readable experience brackets (Entry-level, 1~3 years, etc.).

3. **Interactive Streamlit Web Dashboard & Automation (`app.py`, `applier.py`)**
   - **Top Real-Time Search Bar**: Instant full-text search across titles, companies, locations, and technical keywords over filtered results.
   - **Multi-Browser Playwright Integration**: Supports executing automated applications via Brave, Google Chrome, Microsoft Edge, or Firefox.
   - **Dropdown Page Navigator**: Clear page selector showing total pages and job index range, with exactly 10 postings rendered per page.
   - **Cover Letter Manager**: Pre-configured customizable templates corresponding directly to 104's official application cover letter modal.
   - **Job Action Cards**:
     - `[⭐ Shortlist]`: Save to favorite candidates.
     - `[❌ Skip]`: Hide irrelevant postings.
     - `[🚀 Apply]`: Execute real Playwright browser submission to 104 or record local mock application.
     - `[⚡ Sequential Apply]`: Batch automated submission for current page postings with human-like cooldown delays.
   - **State Persistence**: User application statuses are saved to `104/user_pipeline.json` (unprocessed filter automatically excludes applied jobs to seamlessly resume daily).

---

## 🛠️ Environment Setup & Quick Start

This project uses [`uv`](https://github.com/astral-sh/uv) for fast, isolated Python environment and dependency management.

### 1. Clone & Setup Environment

```bash
# Clone the repository (replace <your-username> with your GitHub handle)
git clone https://github.com/<your-username>/Web_Scrappers.git
cd Web_Scrappers

# Create virtual environment with Python 3.12 (managed by uv)
uv venv --python 3.12
source .venv/bin/activate

# Install dependencies
uv pip install requests pandas openpyxl beautifulsoup4 streamlit
```

### 2. Run the Batch Crawler (Optional / On-demand)

```bash
# Crawls listings across the 46 configured target categories
python 104/crawl_listings.py
```

### 3. Launch the Streamlit Web Application

```bash
streamlit run 104/app.py
```

Access the dashboard at `http://localhost:8501`.

---

## 🔒 Privacy & Security

This repository is pre-configured with strict privacy protections in `.gitignore`:
- **Local Browser Sessions & Screenshots**: Browser session data (`104/browser_data/`) and verification screenshots (`104/screenshots/`) are strictly ignored.
- **Scraped Databases**: Raw data dumps (`*.jsonl`, `*.db`, `*.csv`) are excluded.
- **Application History**: User pipelines and custom notes (`104/user_pipeline.json`) are kept strictly local.
- **No Hardcoded Secrets**: Scrapers and appliers run locally without requiring stored plaintext account credentials.

---

## ⚖️ Disclaimer

This repository is developed for personal career intelligence, research, and educational purposes only. Users are responsible for complying with the Terms of Service and acceptable use policies of target platforms. The author assumes no liability for any misuse or service disruption.

