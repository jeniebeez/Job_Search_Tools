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

# 真實瀏覽器 User-Agent 輪替池
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
]


class Job104Scraper:
    def __init__(self, output_file: str = "104/jobs_104.jsonl", proxy: Optional[str] = None):
        self.output_file = output_file
        self.proxy = proxy
        self.session = requests.Session()
        if self.proxy:
            self.session.proxies = {"http": self.proxy, "https": self.proxy}

        self.existing_job_ids: Set[str] = self._load_existing_ids()
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

    def _load_existing_ids(self) -> Set[str]:
        """載入已儲存的 job_id，實現斷點續爬與去重"""
        ids = set()
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            record = json.loads(line)
                            if "job_id" in record:
                                ids.add(record["job_id"])
                logger.info(f"成功載入本地庫存 {len(ids)} 筆職缺，將自動跳過重複項目。")
            except Exception as e:
                logger.warning(f"讀取既有檔案失敗，將建立新檔：{e}")
        return ids

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
        """以 JSONL 模式即時追加一筆資料"""
        os.makedirs(os.path.dirname(self.output_file) or ".", exist_ok=True)
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
        self.existing_job_ids.add(record["job_id"])

    def crawl_query(
        self,
        keyword: Optional[str] = None,
        jobcat: Optional[str] = None,
        area: Optional[str] = None,
        max_pages: int = 150,
        fetch_details: bool = True
    ) -> int:
        """
        執行單一條件查詢與爬取
        :param keyword: 搜尋關鍵字 (例如: 'Python')
        :param jobcat: 104 職務類別代碼 (例如: '2007000000' 為軟體/工程類)
        :param area: 地區代碼 (例如: '6001001000' 台北市)
        :param max_pages: 最大爬取頁數 (104 API 最大限制為 150 頁)
        :param fetch_details: 是否深入抓取內頁詳細資訊
        """
        query_desc = f"關鍵字='{keyword or ''}', 類別='{jobcat or ''}', 地區='{area or ''}'"
        logger.info(f"🚀 開始檢索條件：{query_desc}，預計抓取至多 {max_pages} 頁")

        new_count = 0
        for page in range(1, max_pages + 1):
            params = ["mode=s"]
            if keyword:
                params.append(f"keyword={keyword}")
            if jobcat:
                params.append(f"jobcat={jobcat}")
            if area:
                params.append(f"area={area}")
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
                cust_name = item.get("custName", "")
                job_name = item.get("jobName", "")

                if job_id in self.existing_job_ids:
                    continue

                detail_data = None
                if fetch_details and job_id:
                    detail_data = self.fetch_job_detail(job_id)

                record = self.parse_job_record(item, detail_data)
                self.save_record(record)
                new_count += 1
                logger.info(f"[{idx}/{len(data)}] 寫入：{cust_name} - {job_name} ({job_id})")

            # 翻頁之間的間隔
            time.sleep(random.uniform(2.5, 4.5))

        logger.info(f"條件 [{query_desc}] 完成，本次新增 {new_count} 筆。")
        return new_count


if __name__ == "__main__":
    scraper = Job104Scraper(output_file="104/jobs_104.jsonl")

    # 範例：可設定一組關鍵字輪詢檢索
    target_keywords = [
        "Python",
        "後端工程師",
        "資料工程師",
        "資料分析師"
    ]

    for kw in target_keywords:
        scraper.crawl_query(keyword=kw, max_pages=2, fetch_details=True)
