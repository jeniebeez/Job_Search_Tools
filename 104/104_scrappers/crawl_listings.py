"""
104 職缺全量列表高速採集與同步更新器 (crawl_listings.py)
說明：
1. 依據 104/104_scrappers/data/target_categories.json 的 46 個細項職業類別掃描職缺清單
2. 核心三大自動同步功能（預設直接執行，無須額外參數）：
   - 【舊有職缺的比對與更新】：交叉比對 (job_id, appear_date)，僅當 appear_date 改變時才更新內容 (Upsert)；未變動者直接跳過不浪費資源
   - 【已關閉職缺的刪除】：自動大掃除，將已從 104 下架關閉的舊職缺從 jobs_104.jsonl 與 user_pipeline.json 暫存中徹底刪除（若重新開放則自動還原）
   - 【嶄新職缺的新增】：自動將新上架的 job_id 寫入 jobs_104.jsonl
3. 選用參數：支援 --is-new <int> (0, 3, 7, 14, 30) 讓使用者選擇僅檢視/抓取最近 N 天內更新的職缺清單
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


def sync_closed_jobs_with_pipeline(scraper: Job104Scraper, pipeline_file: str = DEFAULT_PIPELINE) -> Dict[str, int]:
    """
    處理先前在投遞時因「職缺已關閉」被打入 skipped 的職缺：
    1. 若該職缺在最新一輪爬蟲中重新出現 (jid in scraper.seen_job_ids)：從 skipped 移除，還原為未處理。
    2. 若該職缺未重新出現（確實已關閉）：直接從 jobs_104.jsonl 剔除該職缺，並一併清除 user_pipeline.json 中的暫存 skipped 紀錄。
    """
    if not os.path.exists(pipeline_file):
        return {"restored": 0, "purged": 0}
    try:
        with open(pipeline_file, "r", encoding="utf-8") as f:
            pipeline = json.load(f)
        restored = 0
        purged = 0
        pipeline_changed = False

        for jid in list(pipeline.keys()):
            info = pipeline.get(jid, {})
            if info.get("status") == "skipped" and "職缺已關閉" in str(info.get("note", "")):
                if jid in scraper.seen_job_ids:
                    del pipeline[jid]
                    restored += 1
                    pipeline_changed = True
                else:
                    if jid in scraper.existing_records:
                        del scraper.existing_records[jid]
                        scraper.existing_job_ids.discard(jid)
                        scraper.dirty = True
                        purged += 1
                    del pipeline[jid]
                    pipeline_changed = True

        if scraper.dirty:
            scraper.flush_records()
        if pipeline_changed:
            with open(pipeline_file, "w", encoding="utf-8") as f:
                json.dump(pipeline, f, ensure_ascii=False, indent=2)
        if purged > 0:
            logger.info(f"🗑️ 已將 {purged} 筆投遞時確認「已關閉」的職缺從 jobs_104.jsonl 與暫存清單中徹底剔除！")
        if restored > 0:
            logger.info(f"♻️ 偵測到 {restored} 筆先前關閉的職缺重新開放，已自動從 skipped 還原為未處理！")
        return {"restored": restored, "purged": purged}
    except Exception as e:
        logger.warning(f"同步 user_pipeline.json 已關閉職缺時發生例外：{e}")
        return {"restored": 0, "purged": 0}


def run_batch_crawl(
    targets_file: str = DEFAULT_TARGETS,
    output_file: str = DEFAULT_OUTPUT,
    max_pages_per_cat: int = 100,
    is_new: Optional[int] = 7,
    fetch_details: bool = False
):
    if not os.path.exists(targets_file):
        logger.error(f"找不到目標類別清單：{targets_file}")
        return

    with open(targets_file, "r", encoding="utf-8") as f:
        targets: List[Dict] = json.load(f)

    scraper = Job104Scraper(output_file=output_file)
    mode_label = f"🔄 三合一高速同步更新模式 (isnew={is_new} 天內 + appear_date 比對 + 已關閉職缺大掃除)"
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
                isnew=is_new,
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

            # 每個類別結束時輕量休息 1.0 ~ 2.0 秒
            time.sleep(random.uniform(1.0, 2.0))

        except KeyboardInterrupt:
            logger.warning("⚠️ 收到使用者中斷指令 (Ctrl+C)，安全儲存並停止中...")
            scraper.flush_records()
            completed_all = False
            break
        except Exception as e:
            logger.error(f"❌ 採集類別 [{cat_name}] 時發生非預期錯誤: {e}，跳至下一類別繼續。")
            completed_all = False
            time.sleep(5)

    # 同步處理先前因「職缺已關閉」被打入 skipped 的項目（未重開者從 jobs_104.jsonl 剔除，重開者還原）
    pipeline_sync = sync_closed_jobs_with_pipeline(scraper)
    pruned = pipeline_sync["purged"]

    # 若 46 個類別完整跑完無中斷，自動執行下架職缺大掃除 (Pruning)
    if completed_all:
        pruned += scraper.prune_unseen_jobs(isnew_days=is_new)

    total_time_min = (time.time() - start_time) / 60
    logger.info(
        f"\n🏁 同步更新完成！總耗時: {total_time_min:.1f} 分鐘 | "
        f"本次新增: {total_added} 筆、更新: {total_updated} 筆、跳過未變動: {total_skipped} 筆、"
        f"刪除已關閉: {pruned} 筆 | 最終職缺庫存: {len(scraper.existing_job_ids)} 筆"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="104 職缺列表高速採集與同步更新工具")
    parser.add_argument(
        "--is-new",
        "--isnew",
        dest="is_new",
        type=int,
        default=7,
        choices=[0, 3, 7, 14, 30],
        help="抓取最近 N 天內更新的職缺清單並執行三合一更新與大掃除 (0=本日, 3=3日內, 7=1週內[預設], 14=2週內, 30=1個月內)"
    )
    parser.add_argument(
        "--fetch-details",
        action="store_true",
        help="選用：針對『全新職缺』或『appear_date 有變更的職缺』額外請求第二層內頁 API"
    )
    args = parser.parse_args()

    run_batch_crawl(
        is_new=args.is_new,
        fetch_details=args.fetch_details
    )
