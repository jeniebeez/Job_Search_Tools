"""
104 職缺全量列表高速採集器 (crawl_listings.py)
說明：
1. 依據 104/target_categories.json 的 46 個細項職業類別，全台無死角掃描職缺清單
2. 僅採集搜尋列表資料（含公司、職稱、地區、薪資、經歷、學歷、標籤），不深入內頁，速度極快
3. 具備隨機延遲 (2.0 ~ 3.5s)、每 30 頁冷卻休息、429/403 退避機制與記憶體去重
4. 採集完畢後，可用於快速粗篩，再針對精選職缺深入抓取內頁詳細內文
"""

import os
import sys
import json
import time
import random
import logging
from pathlib import Path
from typing import List, Dict

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from scraper import Job104Scraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Crawl_Listings")


def run_batch_crawl(
    targets_file: str = "104/target_categories.json",
    output_file: str = "104/jobs_104.jsonl",
    max_pages_per_cat: int = 100
):
    if not os.path.exists(targets_file):
        logger.error(f"找不到目標類別清單：{targets_file}")
        return

    with open(targets_file, "r", encoding="utf-8") as f:
        targets: List[Dict] = json.load(f)

    scraper = Job104Scraper(output_file=output_file)
    logger.info(f"🎯 準備執行「方案一：全量列表採集」，共計 {len(targets)} 個細項職業類別")
    logger.info(f"📦 目前本地已有庫存職缺：{len(scraper.existing_job_ids)} 筆")

    total_categories = len(targets)
    start_time = time.time()

    for idx, cat in enumerate(targets, 1):
        cat_code = cat.get("code")
        cat_name = cat.get("name")
        parent_name = cat.get("parent_name")

        logger.info(f"\n=======================================================")
        logger.info(f"[{idx}/{total_categories}] 正在採集：{parent_name} -> {cat_name} ({cat_code})")
        logger.info(f"=======================================================")

        try:
            # 採集列表模式：fetch_details=False (極速且安全)
            added = scraper.crawl_query(
                jobcat=cat_code,
                max_pages=max_pages_per_cat,
                fetch_details=False
            )
            elapsed_min = (time.time() - start_time) / 60
            logger.info(
                f"✅ [{cat_name}] 完成！新增 {added} 筆，"
                f"目前總庫存：{len(scraper.existing_job_ids)} 筆 (已耗時 {elapsed_min:.1f} 分鐘)"
            )

            # 每個類別結束時適度休息
            time.sleep(random.uniform(3.0, 5.0))

        except KeyboardInterrupt:
            logger.warning("⚠️ 收到使用者中斷指令 (Ctrl+C)，安全停止中...")
            break
        except Exception as e:
            logger.error(f"❌ 採集類別 [{cat_name}] 時發生非預期錯誤: {e}，跳至下一類別繼續。")
            time.sleep(5)

    total_time_min = (time.time() - start_time) / 60
    logger.info(f"\n🏁 方案一採集任務全部完成！總耗時: {total_time_min:.1f} 分鐘，總職缺庫存: {len(scraper.existing_job_ids)} 筆")


if __name__ == "__main__":
    run_batch_crawl()
