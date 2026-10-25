"""
104 JSONL 到 SQLite 資料庫同步模組 (db_sync.py)
說明：
1. 本腳本僅在需要將已爬好的 JSONL 檔案同步入 SQLite 時執行。
2. 會自動載入 104/filter_rules.json 的自訂雜訊關鍵字，為每筆職缺打上 is_noise 與 noise_category 標籤。
3. 採用 UPSERT 機制，已存在的職缺會更新資訊，但保留使用者的投遞狀態（如已投遞 applied）。
"""

import os
import json
import sqlite3
import logging
from typing import Dict, List, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DB_Sync")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_104_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

DEFAULT_JSONL = os.path.join(PARENT_104_DIR, "104_scrappers", "data", "jobs_104.jsonl")
DEFAULT_DB = os.path.join(BASE_DIR, "data", "jobs.db")
DEFAULT_RULES = os.path.join(BASE_DIR, "data", "filter_rules.json")


def load_filter_rules(rules_path: str = DEFAULT_RULES) -> Dict[str, List[str]]:
    """讀取雜訊過濾規則設定檔"""
    if not os.path.exists(rules_path):
        logger.warning(f"找不到過濾規則檔 {rules_path}，將不進行雜訊自動標記。")
        return {}
    with open(rules_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("noise_categories", {})


def classify_noise(job_record: Dict, rules: Dict[str, List[str]]) -> Tuple[int, str]:
    """依據職缺標題與分類判定是否為雜訊"""
    title = job_record.get("job", {}).get("title", "")
    categories = " ".join(job_record.get("job", {}).get("categories", []))
    target_text = f"{title} {categories}".lower()

    for category_name, keywords in rules.items():
        for kw in keywords:
            if kw.lower() in target_text:
                return 1, category_name  # is_noise=1, category
    return 0, ""


def init_db(db_path: str = DEFAULT_DB) -> sqlite3.Connection:
    """初始化 SQLite 資料表與索引"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        company_name TEXT,
        company_industry TEXT,
        job_title TEXT,
        region TEXT,
        address TEXT,
        salary_low INTEGER,
        salary_high INTEGER,
        salary_desc TEXT,
        work_exp TEXT,
        education TEXT,
        is_noise INTEGER DEFAULT 0,
        noise_category TEXT,
        application_status TEXT DEFAULT 'unprocessed',
        applied_at TIMESTAMP,
        crawled_at TEXT,
        url TEXT,
        raw_data JSON
    )
    """)

    # 建立索引以確保檢索系統的高速查詢
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_region ON jobs(region)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_salary_low ON jobs(salary_low)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_is_noise ON jobs(is_noise)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON jobs(application_status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_company ON jobs(company_name)")

    conn.commit()
    return conn


def sync_jsonl_to_sqlite(
    jsonl_path: str = DEFAULT_JSONL,
    db_path: str = DEFAULT_DB,
    rules_path: str = DEFAULT_RULES
):
    """執行同步：從 JSONL 讀取並寫入 SQLite"""
    if not os.path.exists(jsonl_path):
        logger.error(f"找不到 JSONL 檔案：{jsonl_path}，請先執行爬蟲。")
        return

    rules = load_filter_rules(rules_path)
    conn = init_db(db_path)
    cursor = conn.cursor()

    total_synced = 0
    noise_count = 0

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            item = json.loads(line)
            job_id = item.get("job_id")
            if not job_id:
                continue

            company = item.get("company", {})
            location = item.get("location", {})
            job = item.get("job", {})
            salary = job.get("salary", {})
            req = job.get("requirements", {})
            pipe = item.get("pipeline", {})

            is_noise, noise_category = classify_noise(item, rules)
            if is_noise:
                noise_count += 1

            cursor.execute("""
            INSERT INTO jobs (
                job_id, company_name, company_industry, job_title,
                region, address, salary_low, salary_high, salary_desc,
                work_exp, education, is_noise, noise_category,
                application_status, applied_at, crawled_at, url, raw_data
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id) DO UPDATE SET
                company_name=excluded.company_name,
                job_title=excluded.job_title,
                region=excluded.region,
                salary_low=excluded.salary_low,
                salary_high=excluded.salary_high,
                is_noise=excluded.is_noise,
                noise_category=excluded.noise_category,
                raw_data=excluded.raw_data
            """, (
                job_id,
                company.get("name"),
                company.get("industry"),
                job.get("title"),
                location.get("region"),
                location.get("address"),
                salary.get("low", 0),
                salary.get("high", 0),
                salary.get("desc"),
                req.get("work_exp"),
                req.get("education"),
                is_noise,
                noise_category,
                pipe.get("application_status", "unprocessed"),
                pipe.get("applied_at"),
                item.get("crawled_at"),
                item.get("url"),
                json.dumps(item, ensure_ascii=False)
            ))
            total_synced += 1

    conn.commit()
    conn.close()
    logger.info(f"🎉 同步完成！共匯入/更新 {total_synced} 筆職缺（其中標記為雜訊者共 {noise_count} 筆）。")


if __name__ == "__main__":
    sync_jsonl_to_sqlite()
