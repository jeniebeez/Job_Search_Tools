"""
104 職缺檢索與過濾範例 (Filter System Demo)
展示如何快速對爬下來的 JSONL 資料進行多維度條件篩選，
支援：地區、薪資下限、要求技能、年資需求、投遞狀態過濾。
"""

import os
import json
from typing import List, Dict, Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_JSONL = os.path.join(BASE_DIR, "data", "jobs_104.jsonl")


def load_jobs(jsonl_path: str = DEFAULT_JSONL) -> List[Dict]:
    """讀取 JSONL 所有職缺資料"""
    jobs = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                jobs.append(json.loads(line))
    return jobs


def filter_jobs(
    jobs: List[Dict],
    region_keyword: Optional[str] = None,     # 地區 (例: "台北市", "信義區")
    min_salary: Optional[int] = None,         # 最低薪資門檻 (例: 50000)
    required_skills: Optional[List[str]] = None, # 必備技能 (例: ["Python", "FastAPI"])
    max_experience: Optional[str] = None,     # 年資 (例: "不拘", "1年")
    status: Optional[str] = None              # 投遞狀態 (例: "unprocessed")
) -> List[Dict]:
    """多維度篩選器"""
    results = []
    for item in jobs:
        loc = item.get("location", {})
        job = item.get("job", {})
        req = job.get("requirements", {})
        sal = job.get("salary", {})
        pipe = item.get("pipeline", {})

        # 1. 地區篩選
        if region_keyword and region_keyword not in loc.get("region", ""):
            continue

        # 2. 薪資篩選 (以職缺提供的 low 或 high 判斷)
        if min_salary is not None:
            job_low = sal.get("low", 0)
            job_high = sal.get("high", 0)
            if job_high > 0 and job_high < min_salary:
                continue
            if job_low > 0 and job_low < min_salary:
                continue

        # 3. 技能篩選 (比對 specialties 或 skills 或 description)
        if required_skills:
            all_skill_text = " ".join(
                req.get("specialties", []) +
                req.get("skills", []) +
                [job.get("description", "")]
            ).lower()

            match = all(s.lower() in all_skill_text for s in required_skills)
            if not match:
                continue

        # 4. 年資篩選
        if max_experience and max_experience not in req.get("work_exp", ""):
            continue

        # 5. 投遞狀態篩選
        if status and pipe.get("application_status") != status:
            continue

        results.append(item)
    return results


if __name__ == "__main__":
    jobs = load_jobs()
    print(f"目前資料庫中共有 {len(jobs)} 筆職缺")

    # 範例：篩選「台北市」、要求「Python」且尚未投遞 (unprocessed) 的職缺
    filtered = filter_jobs(
        jobs,
        region_keyword="台北市",
        required_skills=["Python"],
        status="unprocessed"
    )

    print(f"\n🔍 符合篩選條件的職缺共有 {len(filtered)} 筆：\n")
    for idx, item in enumerate(filtered[:5], 1):
        print(f"[{idx}] {item['company']['name']} - {item['job']['title']}")
        print(f"    地區: {item['location']['region']} | 薪資: {item['job']['salary']['desc']}")
        print(f"    年資: {item['job']['requirements']['work_exp']} | 學歷: {item['job']['requirements']['education']}")
        print(f"    擅長工具: {', '.join(item['job']['requirements']['specialties'])}")
        print(f"    投遞狀態: {item['pipeline']['application_status']}")
        print(f"    連結: {item['url']}")
        print("-" * 60)
