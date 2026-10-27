"""
104 職缺全量列表高速採集器 (crawl_listings.py)
說明：
1. 依據 104/104_scrappers/data/target_categories.json 的 46 個細項職業類別掃描職缺清單
2. 預設啟用 isnew=7（僅抓取過去 7 天內更新的職缺），並交叉比對 (job_id, appear_date)：
   - 若 appear_date 相同（例如使用者在第 5 天提早更新，或同職缺跨類別重複出現）-> 直接跳過，不浪費資源
   - 若 appear_date 不同 -> 自動更新職缺內容 (Upsert)
   - 若為全新 job_id -> 自動新增寫入
3. 若曾在投遞時因「職缺已關閉」被打入 skipped 的職缺重新開放，自動從 user_pipeline.json 還原為未處理狀態
4. 支援 --full-sync 全量同步模式（不限更新日掃描全部頁數，並在完整跑完後自動清除已下架關閉的舊職缺）
"""

import os
import sys
import json
import time
import random
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Optional

CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from scraper import Job104Scraper

DEFAULT_TARGETS = str(CURRENT_DIR / "data" / "target_categories.json")
DEFAULT_OUTPUT = str(CURRENT_DIR / "data" / "jobs_104.jsonl")
DEFAULT_PIPELINE = str(CURRENT_DIR.parent / "104_job_search" / "data" / "user_pipeline.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Crawl_Listings")


def restore_reopened_closed_jobs(seen_job_ids: set, pipeline_file: str = DEFAULT_PIPELINE) -> int:
    """
    若某職缺先前在投遞時因「職缺已關閉」被打入 skipped，
    但在最新一輪爬蟲中重新出現在 104 活躍清單，自動將其從 skipped 移除（還原為未處理）。
    """
    if not seen_job_ids or not os.path.exists(pipeline_file):
        return 0
    try:
        with open(pipeline_file, "r", encoding="utf-8") as f:
            pipeline = json.load(f)
        restored = 0
        for jid in list(pipeline.keys()):
            info = pipeline.get(jid, {})
            if (
                jid in seen_job_ids
                and info.get("status") == "skipped"
                and "職缺已關閉" in str(info.get("note", ""))
            ):
                del pipeline[jid]
                restored += 1
        if restored > 0:
            with open(pipeline_file, "w", encoding="utf-8") as f:
                json.dump(pipeline, f, ensure_ascii=False, indent=2)
            logger.info(f"♻️ 偵測到 {restored} 筆先前關閉的職缺重新開放，已自動從 skipped 還原為未處理！")
        return restored
    except Exception as e:
        logger.warning(f"檢查 user_pipeline.json 時發生例外：{e}")
        return 0


def run_batch_crawl(
    targets_file: str = DEFAULT_TARGETS,
    output_file: str = DEFAULT_OUTPUT,
    max_pages_per_cat: int = 100,
    isnew: Optional[int] = 7,
    full_sync: bool = False,
    fetch_details: bool = False
):
    if not os.path.exists(targets_file):
        logger.error(f"找不到目標類別清單：{targets_file}")
        return

    with open(targets_file, "r", encoding="utf-8") as f:
        targets: List[Dict] = json.load(f)

    effective_isnew = None if full_sync else isnew
    scraper = Job104Scraper(output_file=output_file)
    mode_label = (
        "🧹 全量同步與下架清理模式 (--full-sync)"
        if full_sync
        else f"⚡ 週期增量更新模式 (isnew={effective_isnew} 天內 + appear_date 比對)"
    )
    logger.info(f"🎯 啟動「{mode_label}」，共計 {len(targets)} 個細項職業類別")
    logger.info(f"📦 目前本地已有庫存職缺：{len(scraper.existing_job_ids)} 筆")

    total_categories = len(targets)
    start_time = time.time()
    total_added = 0
    total_updated = 0
    total_skipped = 0
    completed_all = True

    for idx, cat in enumerate(targets, 1):
        cat_code = cat.get("code")
        cat_name = cat.get("name")
        parent_name = cat.get("parent_name")

        logger.info("\n=======================================================")
        logger.info(f"[{idx}/{total_categories}] 正在採集：{parent_name} -> {cat_name} ({cat_code})")
        logger.info("=======================================================")

        try:
            stats = scraper.crawl_query(
                jobcat=cat_code,
                isnew=effective_isnew,
                max_pages=max_pages_per_cat,
                fetch_details=fetch_details
            )
            added = stats["added"]
            updated = stats["updated"]
            skipped = stats["skipped"]
            total_added += added
            total_updated += updated
            total_skipped += skipped

            elapsed_min = (time.time() - start_time) / 60
            logger.info(
                f"✅ [{cat_name}] 完成！新增 {added} 筆、更新 {updated} 筆、跳過未變動 {skipped} 筆 | "
                f"目前總庫存：{len(scraper.existing_job_ids)} 筆 (已耗時 {elapsed_min:.1f} 分鐘)"
            )

            # 每個類別結束時適度休息
            time.sleep(random.uniform(3.0, 5.0))

        except KeyboardInterrupt:
            logger.warning("⚠️ 收到使用者中斷指令 (Ctrl+C)，安全儲存並停止中...")
            scraper.flush_records()
            completed_all = False
            break
        except Exception as e:
            logger.error(f"❌ 採集類別 [{cat_name}] 時發生非預期錯誤: {e}，跳至下一類別繼續。")
            completed_all = False
            time.sleep(5)

    # 還原重新開啟的「職缺已關閉」項目
    restore_reopened_closed_jobs(scraper.seen_job_ids)

    # 若為 --full-sync 且 46 個類別完整跑完無中斷，執行下架職缺清理 (Pruning)
    pruned = 0
    if full_sync and completed_all:
        pruned = scraper.prune_unseen_jobs()

    total_time_min = (time.time() - start_time) / 60
    logger.info(
        f"\n🏁 採集任務完成！總耗時: {total_time_min:.1f} 分鐘 | "
        f"本次新增: {total_added} 筆、更新: {total_updated} 筆、跳過未變動: {total_skipped} 筆"
        + (f"、清除已下架: {pruned} 筆" if full_sync else "")
        + f" | 最終職缺庫存: {len(scraper.existing_job_ids)} 筆"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="104 職缺列表高速採集與增量更新工具")
    parser.add_argument(
        "--isnew",
        type=int,
        default=7,
        choices=[0, 3, 7, 14, 30],
        help="僅抓取最近 N 天內更新的職缺 (0=本日, 3=3日內, 7=1週內[預設], 14=2週內, 30=1個月內)"
    )
    parser.add_argument(
        "--full-sync",
        action="store_true",
        help="全量掃描所有頁數（不限更新日），並在完整跑完後自動清除已從 104 下架關閉的舊職缺"
    )
    parser.add_argument(
        "--fetch-details",
        action="store_true",
        help="針對『全新職缺』或『appear_date 有變更的職缺』額外請求第二層內頁 API"
    )
    args = parser.parse_args()

    run_batch_crawl(
        isnew=args.isnew,
        full_sync=args.full_sync,
        fetch_details=args.fetch_details
    )
