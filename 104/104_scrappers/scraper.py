"""
104 人力銀行職缺爬蟲模組 (生產級強化版)
功能特色：
1. 【IP 防封機制】：動態隨機擾動延遲 (Jitter)、批次冷卻 (Cooldown)、429/403 指數退避重試
2. 【結構化多關鍵字檢索】：支援依自訂關鍵字清單、職務類別代碼、地區批次輪詢
3. 【智慧斷點去重】：自動載入已存在的 job_id，遇到重複立即跳過，節省網路資源
4. 【串流 JSONL 寫入】：一筆一寫入，避免程式崩潰或強制關閉時遺失資料
"""

import os
import json
import time
import random
import logging
from datetime import datetime
from typing import Dict, List, Optional, Set
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("104_Scraper")

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT_FILE = os.path.join(CURRENT_DIR, "data", "jobs_104.jsonl")

# 真實瀏覽器 User-Agent 輪替池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
]


class Job104Scraper:
    def __init__(self, output_file: str = DEFAULT_OUTPUT_FILE, proxy: Optional[str] = None):
        self.output_file = output_file
        self.proxy = proxy
        self.session = requests.Session()
        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

        self.existing_records: Dict[str, Dict] = self._load_existing_records()
        self.existing_job_ids: Set[str] = set(self.existing_records.keys())
        self.seen_job_ids: Set[str] = set()
        self.dirty: bool = False
        self.detail_call_count = 0  # 記錄連續請求次數，用於批次冷卻

    def _get_headers(self, referer: str = "https://www.104.com.tw/jobs/search/") -> Dict[str, str]:
        """產生貼近真人瀏覽器的請求標頭"""
        return {
            "User-Agent": random.choice(USER_AGENTS),
            "Referer": referer,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
            "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def _load_existing_records(self) -> Dict[str, Dict]:
        """載入已儲存的職缺紀錄 (job_id -> record)，用於比對 appear_date 與智慧更新"""
        records: Dict[str, Dict] = {}
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            jid = record.get("job_id")
                            if jid:
                                records[jid] = record
                logger.info(f"成功載入本地庫存 {len(records)} 筆職缺（支援 job_id + appear_date 增量比對）。")
            except Exception as e:
                logger.warning(f"讀取既有檔案失敗，將建立新檔：{e}")
        return records

    def _safe_request(self, url: str, referer: str, max_retries: int = 3) -> Optional[requests.Response]:
        """
        核心防封請求器：
        1. 捕獲 429 / 403 異常並自動退避休眠
        2. 指數退避 (Exponential Backoff)
        """
        for attempt in range(1, max_retries + 1):
            try:
                headers = self._get_headers(referer=referer)
                resp = self.session.get(url, headers=headers, timeout=15)

                if resp.status_code == 200:
                    return resp
                elif resp.status_code in (429, 403):
                    # 遇到速率限制或安全攔截，觸發緊急冷卻
                    sleep_time = attempt * 45 + random.uniform(10, 20)
                    logger.warning(
                        f"⚠️ 觸發反爬機制 (HTTP {resp.status_code})！"
                        f"將進行第 {attempt}/{max_retries} 次退避冷卻，休眠 {sleep_time:.1f} 秒..."
                    )
                    time.sleep(sleep_time)
                elif resp.status_code == 404:
                    return None
                else:
                    logger.warning(f"請求回應異常 (HTTP {resp.status_code}) URL: {url}")
                    time.sleep(3)

            except requests.exceptions.RequestException as e:
                logger.warning(f"網路連線異常 (第 {attempt} 次): {e}")
                time.sleep(5 * attempt)

        logger.error(f"❌ 達到最大重試次數，放棄該請求：{url}")
        return None

    def fetch_job_detail(self, job_id: str) -> Optional[Dict]:
        """抓取單一職缺的詳細內容，並執行批次冷卻保護"""
        self.detail_call_count += 1

        # 【IP防護機制 1】：批次休息冷卻
        # 每連續請求 20~25 次內頁，強制暫停 10~18 秒，模擬使用者停下閱讀
        if self.detail_call_count % random.randint(20, 25) == 0:
            pause_time = random.uniform(10.0, 18.0)
            logger.info(f"☕ 已連續抓取 {self.detail_call_count} 筆詳細內容，啟動保護冷卻，暫停 {pause_time:.1f} 秒...")
            time.sleep(pause_time)

        # 【IP防護機制 2】：日常隨機擾動延遲 (Jitter)
        time.sleep(random.uniform(1.8, 3.5))

        url = f"https://www.104.com.tw/job/ajax/content/{job_id}"
        referer = f"https://www.104.com.tw/job/{job_id}"
        resp = self._safe_request(url, referer=referer)
        if resp and resp.status_code == 200:
            try:
                return resp.json().get("data", {})
            except Exception:
                return None
        return None

    def parse_job_record(self, search_item: Dict, detail_data: Optional[Dict]) -> Dict:
        """整合職缺階層結構"""
        link = search_item.get("link", {}).get("job", "")
        job_id = link.split("/job/")[1].split("?")[0] if "/job/" in link else search_item.get("jobNo", "")
        clean_url = f"https:{link}" if link.startswith("//") else f"https://www.104.com.tw/job/{job_id}"

        header = detail_data.get("header", {}) if detail_data else {}
        job_detail = detail_data.get("jobDetail", {}) if detail_data else {}
        condition = detail_data.get("condition", {}) if detail_data else {}
        contact = detail_data.get("contact", {}) if detail_data else {}

        categories = []
        if job_detail.get("jobCategory"):
            categories = [c.get("description", "") for c in job_detail.get("jobCategory", []) if c.get("description")]
        elif search_item.get("jobCat"):
            categories = [str(cat) for cat in search_item.get("jobCat", [])]

        specialties = [s.get("description", "") for s in condition.get("specialty", []) if s.get("description")]
        skills = [s.get("description", "") for s in condition.get("skill", []) if s.get("description")]

        return {
            "job_id": job_id,
            "url": clean_url,
            "crawled_at": datetime.now().isoformat(),
            "company": {
                "id": search_item.get("custNo", ""),
                "name": header.get("custName") or search_item.get("custName", ""),
                "industry": search_item.get("coIndustryDesc", ""),
                "employee_count": search_item.get("employeeCount", None),
            },
            "location": {
                "region": search_item.get("jobAddrNoDesc", ""),
                "address": job_detail.get("addressDetail") or search_item.get("jobAddress", ""),
                "lat": search_item.get("lat"),
                "lon": search_item.get("lon"),
            },
            "job": {
                "title": header.get("jobName") or search_item.get("jobName", ""),
                "categories": categories,
                "description": job_detail.get("jobDescription") or search_item.get("description", ""),
                "salary": {
                    "desc": search_item.get("salaryDesc", ""),
                    "low": search_item.get("salaryLow", 0),
                    "high": search_item.get("salaryHigh", 0),
                    "type": job_detail.get("salaryType", ""),
                },
                "requirements": {
                    "work_exp": condition.get("workExp") or search_item.get("period", ""),
                    "education": condition.get("edu") or search_item.get("optionEdu", ""),
                    "majors": condition.get("major", []),
                    "specialties": specialties,
                    "skills": skills,
                    "other": condition.get("other", ""),
                },
                "contact": {
                    "hr_name": contact.get("hrName"),
                    "email": contact.get("email"),
                    "phone": contact.get("phone"),
                    "other": contact.get("other"),
                }
            },
            "pipeline": {
                "appear_date": search_item.get("appearDate", ""),
                "apply_count": search_item.get("applyCnt", 0),
                "application_status": "unprocessed",
                "applied_at": None,
                "note": ""
            }
        }

    def save_record(self, record: Dict):
        """以 JSONL 模式即時追加一筆新資料"""
        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
        jid = record["job_id"]
        self.existing_records[jid] = record
        self.existing_job_ids.add(jid)

    def flush_records(self):
        """若記憶體中有舊職缺因 appear_date 變更而被更新，以 Atomic Write 安全覆寫回 JSONL"""
        if not self.dirty:
            return
        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)
        tmp_file = f"{self.output_file}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            for rec in self.existing_records.values():
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        os.replace(tmp_file, self.output_file)
        self.dirty = False

    def prune_unseen_jobs(self) -> int:
        """
        在全量掃描（未指定 isnew 且未中斷）完成後，清除已從 104 下架關閉的舊職缺
        :return: 被清除的下架職缺數量
        """
        if not self.seen_job_ids:
            return 0
        closed_ids = [jid for jid in list(self.existing_records.keys()) if jid not in self.seen_job_ids]
        if not closed_ids:
            return 0
        for jid in closed_ids:
            del self.existing_records[jid]
        self.existing_job_ids = set(self.existing_records.keys())
        self.dirty = True
        self.flush_records()
        logger.info(f"🧹 已從本地資料庫清除 {len(closed_ids)} 筆已下架/關閉的舊職缺。")
        return len(closed_ids)

    def crawl_query(
        self,
        keyword: Optional[str] = None,
        jobcat: Optional[str] = None,
        area: Optional[str] = None,
        isnew: Optional[int] = None,
        max_pages: int = 150,
        fetch_details: bool = True
    ) -> Dict[str, int]:
        """
        執行單一條件查詢與爬取
        :param keyword: 搜尋關鍵字 (例如: 'Python')
        :param jobcat: 104 職務類別代碼 (例如: '2007000000' 為軟體/工程類)
        :param area: 地區代碼 (例如: '6001001000' 台北市)
        :param isnew: 最新更新日過濾 (0=本日最新, 3=3日內, 7=1週內, 14=2週內, 30=1個月內, None=不限)
        :param max_pages: 最大爬取頁數 (104 API 最大限制為 150 頁)
        :param fetch_details: 是否深入抓取第二層內頁詳細資訊
        :return: {"added": 新增筆數, "updated": 更新筆數, "skipped": 略過筆數}
        """
        query_desc = (
            f"關鍵字='{keyword or ''}', 類別='{jobcat or ''}', "
            f"地區='{area or ''}', isnew={isnew if isnew is not None else '不限'}"
        )
        logger.info(f"🚀 開始檢索條件：{query_desc}，預計抓取至多 {max_pages} 頁")

        new_count = 0
        updated_count = 0
        skipped_count = 0

        for page in range(1, max_pages + 1):
            params = ["mode=s"]
            if keyword:
                params.append(f"keyword={keyword}")
            if jobcat:
                params.append(f"jobcat={jobcat}")
            if area:
                params.append(f"area={area}")
            if isnew is not None:
                params.append(f"isnew={isnew}")
            params.append(f"page={page}")

            search_url = f"https://www.104.com.tw/jobs/search/api/jobs?{'&'.join(params)}"
            resp = self._safe_request(search_url, referer="https://www.104.com.tw/jobs/search/")

            if not resp or resp.status_code != 200:
                logger.warning(f"第 {page} 頁無法獲取資料，終止此條件檢索。")
                break

            data = resp.json().get("data", [])
            if not data:
                logger.info(f"第 {page} 頁已無更多職缺，該條件檢索完畢。")
                break

            logger.info(f"--- 正在處理第 {page} 頁（本頁 {len(data)} 筆）---")
            for idx, item in enumerate(data, 1):
                link = item.get("link", {}).get("job", "")
                job_id = link.split("/job/")[1].split("?")[0] if "/job/" in link else item.get("jobNo", "")
                if not job_id:
                    continue

                self.seen_job_ids.add(job_id)
                cust_name = item.get("custName", "")
                job_name = item.get("jobName", "")
                new_appear_date = str(item.get("appearDate", ""))

                # 交叉比對 job_id 與 appear_date
                if job_id in self.existing_records:
                    old_rec = self.existing_records[job_id]
                    old_appear_date = str(old_rec.get("pipeline", {}).get("appear_date", ""))
                    if not new_appear_date or new_appear_date == old_appear_date:
                        # appear_date 相同，代表職缺內容未變動，直接跳過不浪費資源
                        skipped_count += 1
                        continue

                    # appear_date 不同（職缺有更新）：才視設定呼叫第二層並更新紀錄
                    detail_data = None
                    if fetch_details:
                        detail_data = self.fetch_job_detail(job_id)

                    updated_rec = self.parse_job_record(item, detail_data)
                    # 若未抓取第二層 detail_data，保留舊紀錄中已有的第二層細部欄位
                    if not detail_data:
                        old_job = old_rec.get("job", {})
                        old_req = old_job.get("requirements", {})
                        new_req = updated_rec["job"]["requirements"]
                        for k in ("majors", "specialties", "skills", "other"):
                            if not new_req.get(k) and old_req.get(k):
                                new_req[k] = old_req[k]
                        if old_job.get("contact"):
                            updated_rec["job"]["contact"] = old_job["contact"]

                    self.existing_records[job_id] = updated_rec
                    self.dirty = True
                    updated_count += 1
                    logger.info(
                        f"[{idx}/{len(data)}] 🔄 更新 ({old_appear_date} -> {new_appear_date})："
                        f"{cust_name} - {job_name} ({job_id})"
                    )
                else:
                    # 全新職缺
                    detail_data = None
                    if fetch_details:
                        detail_data = self.fetch_job_detail(job_id)

                    record = self.parse_job_record(item, detail_data)
                    self.save_record(record)
                    new_count += 1
                    logger.info(f"[{idx}/{len(data)}] ✨ 新增 ({new_appear_date})：{cust_name} - {job_name} ({job_id})")

            # 翻頁之間的間隔
            time.sleep(random.uniform(2.5, 4.5))

        # 若本類別有更新舊職缺，安全寫回磁碟
        self.flush_records()

        logger.info(
            f"條件 [{query_desc}] 完成：新增 {new_count} 筆、更新 {updated_count} 筆、跳過未變動 {skipped_count} 筆。"
        )
        return {"added": new_count, "updated": updated_count, "skipped": skipped_count}


if __name__ == "__main__":
    scraper = Job104Scraper(output_file=DEFAULT_OUTPUT_FILE)

    # 範例：可設定一組關鍵字輪詢檢索
    target_keywords = [
        "Python",
        "後端工程師",
        "資料工程師",
        "資料分析師"
    ]

    for kw in target_keywords:
        scraper.crawl_query(keyword=kw, max_pages=2, fetch_details=True)
