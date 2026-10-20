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
    ├── crawl_listings.py   # High-speed batch listing collector across 46 categories
    ├── scraper.py          # Core 104 REST API scraper with anti-ban protections
    ├── db_sync.py          # Optional SQLite synchronization and UPSERT engine
    ├── query_filter.py     # CLI-based multi-criteria filtering demo
    ├── filter_rules.json   # Noise classification & AI track matching rules
    ├── target_categories.json # Target job taxonomy configuration (46 subcategories)
    ├── job_categories.json # Complete 104 official category taxonomy tree
    └── resumes/            # Local permanent resume library (.gitkeep tracked, PDFs ignored)
```

---

## 🚀 Project 1: 104 Job Bank Intelligence & Application Suite

A full-stack job scraping, intelligent screening, and resume application workflow designed for the Taiwan tech job market (104 Job Bank).

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

3. **Interactive Streamlit Web Dashboard (`app.py`)**
   - **Real-Time KPI Dashboard**: Displays live counts for total scraped jobs, filtered focused jobs, shortlisted jobs, and applied jobs.
   - **Permanent Resume Library (`104/resumes/`)**: Upload and store multiple PDF resume versions locally (e.g., AI/LLM version, Backend version, PM version) and switch between them dynamically.
   - **Cover Letter Manager**: Pre-configured customizable templates corresponding directly to 104's official application cover letter modal.
   - **Job Action Cards**:
     - `[⭐ Shortlist]`: Save to favorite candidates.
     - `[❌ Skip]`: Hide irrelevant postings.
     - `[🚀 Apply]`: Simulate / record job applications with timestamp and attached resume tag.
     - `[⚡ Batch Apply]`: One-click batch application for all shortlisted jobs.
   - **State Persistence**: User application statuses are saved to `104/user_pipeline.json` (persists across restarts).

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
- **Personal Resumes**: All PDF files inside `104/resumes/` are strictly ignored and will never be committed to git.
- **Scraped Databases**: Raw data dumps (`*.jsonl`, `*.db`, `*.csv`) are excluded.
- **Application History**: User pipelines and custom notes (`104/user_pipeline.json`) are kept strictly local.
- **No Hardcoded Secrets**: Scrapers use public anonymous REST endpoints without requiring stored plaintext account credentials.

---

## 🗺️ Roadmap

- [x] **104 Job Bank**: High-speed batch listing scraper & Streamlit interactive dashboard.
- [ ] **104 Job Bank**: Automated browser application runner (Playwright / Headless submission integration).
- [ ] **CakeResume Scraper**: Tech & startup talent portal scraper.
- [ ] **Yes123 Scraper**: Secondary job market comparison scraper.
- [ ] **Universal Unified Search**: Aggregated search interface querying across all scraped platforms.

---

## ⚖️ Disclaimer

This repository is developed for educational, personal career intelligence, and research purposes only. Please adhere to the `robots.txt`, Terms of Service, and ethical rate-limiting policies of target platforms when deploying crawlers.
