"""
104 智能求職儀表板與自動投遞系統 (Streamlit Web App)
啟動方式：
    streamlit run 104/app.py
功能特點：
1. 即時讀取 104/jobs_104.jsonl 龐大資料庫（動態連動背景爬蟲）
2. 內建客製化求職漏斗：雙北/桃園/遠端、薪資>=45k/面議、經歷1~3年、自動雜訊排除
3. 左側履歷與自薦信管理中心：模板切換、文字即時編輯
4. 卡片式職缺瀏覽：一鍵收藏 (Shortlist)、略過 (Skip)、模擬履歷投遞 (Apply)
5. 投遞狀態持久化保存：記錄於 104/user_pipeline.json，重整不消失
"""

import os
import json
from datetime import datetime
from typing import Dict, List, Set
import streamlit as st
import pandas as pd

# 頁面配置
st.set_page_config(
    page_title="104 智能求職情報與投遞助手",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

JSONL_PATH = "104/jobs_104.jsonl"
RULES_PATH = "104/filter_rules.json"
PIPELINE_PATH = "104/user_pipeline.json"

# 預設自薦信模板
DEFAULT_COVER_LETTERS = {
    "軟體開發 / 後端工程師": (
        "您好，我是軟體開發工程師。\n"
        "過去具備 1~3 年的系統開發與維運經驗，精通 Python、API 設計與資料庫操作。\n"
        "在 104 上看見貴公司招募的職缺，工作內容與我的技術棧非常契合，希望能爭取面試機會，謝謝！"
    ),
    "專案管理 / 產品經理 (PM)": (
        "您好，我是專案/產品管理師。\n"
        "擅長跨部門溝通協調、敏捷開發進度管理與需求梳理，具備 1~3 年專案推進經驗。\n"
        "對於貴公司的產品領域非常感興趣，渴望運用我的專案管理專長為團隊貢獻，附件為我的履歷，謝謝！"
    ),
    "通用版 (客製化自由編輯)": (
        "您好，我對貴公司開出的職缺非常感興趣，附件為我的詳細個人履歷，期待有機會與您進一步交流，謝謝！"
    )
}


def load_pipeline() -> Dict[str, Dict]:
    """載入使用者標記的狀態 (收藏/已投遞/略過)"""
    if os.path.exists(PIPELINE_PATH):
        try:
            with open(PIPELINE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_pipeline(pipeline: Dict[str, Dict]):
    """持久化保存使用者狀態"""
    with open(PIPELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(pipeline, f, ensure_ascii=False, indent=2)


def load_noise_rules() -> Dict[str, List[str]]:
    """載入雜訊關鍵字規則"""
    if os.path.exists(RULES_PATH):
        try:
            with open(RULES_PATH, "r", encoding="utf-8") as f:
                return json.load(f).get("noise_categories", {})
        except Exception:
            return {}
    return {}


@st.cache_data(ttl=15)
def load_raw_jobs() -> List[Dict]:
    """快取讀取 JSONL（每 15 秒自動刷新最新爬取的職缺）"""
    jobs = []
    if not os.path.exists(JSONL_PATH):
        return []
    with open(JSONL_PATH, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    jobs.append(json.loads(line))
                except Exception:
                    continue
    return jobs


# 初始化 Session State
if "pipeline" not in st.session_state:
    st.session_state.pipeline = load_pipeline()

raw_jobs = load_raw_jobs()
noise_rules = load_noise_rules()

# ==========================================
# 側邊欄：履歷、自薦信與多維度篩選器
# ==========================================
with st.sidebar:
    st.header("📄 履歷與自薦信管理")

    uploaded_resume = st.file_uploader("上傳個人履歷 PDF", type=["pdf"])
    if uploaded_resume:
        st.success(f"已掛載履歷：{uploaded_resume.name}")

    st.subheader("📝 自薦信 (Cover Letter) 模板")
    template_choice = st.selectbox(
        "選擇模板類型",
        list(DEFAULT_COVER_LETTERS.keys())
    )

    if "cover_letter_text" not in st.session_state or st.session_state.get("last_template") != template_choice:
        st.session_state.cover_letter_text = DEFAULT_COVER_LETTERS[template_choice]
        st.session_state.last_template = template_choice

    active_cover_letter = st.text_area(
        "編輯自薦信內容（投遞時將自動附帶）",
        value=st.session_state.cover_letter_text,
        height=140
    )

    st.divider()

    st.header("🔍 多維度篩選過濾器")

    # 1. 雜訊過濾
    enable_noise_filter = st.checkbox("自動排除非辦公室雜訊 (保全/清潔/電銷等)", value=True)

    # 2. 地區篩選
    region_options = ["台北市", "新北市", "桃園市", "新竹市", "新竹縣", "台中市", "遠端工作"]
    selected_regions = st.multiselect(
        "工作地區 (預設雙北、桃園、遠端)",
        options=region_options,
        default=["台北市", "新北市", "桃園市", "遠端工作"]
    )

    # 3. 薪資門檻
    min_salary = st.number_input("最低薪資門檻 (NT$)", min_value=30000, max_value=200000, value=45000, step=5000)
    include_negotiable = st.checkbox("包含「待遇面議 (經常性薪資達4萬以上)」", value=True)

    # 4. 經歷篩選
    exp_options = ["不拘", "1年以下", "1~3年", "3~5年", "5年以上"]
    selected_exps = st.multiselect(
        "工作經歷要求 (預設不拘、1~3年)",
        options=exp_options,
        default=["不拘", "1年以下", "1~3年"]
    )

    # 5. 關鍵字搜尋
    search_keyword = st.text_input("即時關鍵字過濾 (職稱、公司、技術標籤)", placeholder="例如: Python, 專案, AWS")

    # 6. 狀態篩選
    status_filter = st.radio(
        "職缺處理狀態",
        options=["全部未處理 (Unprocessed)", "⭐ 已收藏候選 (Shortlisted)", "🚀 已投遞 (Applied)", "❌ 已略過 (Skipped)"],
        index=0
    )

# ==========================================
# 資料過濾核心運算 (Rough Filter Engine)
# ==========================================
focused_jobs = []

for item in raw_jobs:
    job_id = item.get("job_id")
    current_status = st.session_state.pipeline.get(job_id, {}).get("status", "unprocessed")

    # 狀態過濾
    if "全部未處理" in status_filter and current_status != "unprocessed":
        continue
    elif "已收藏候選" in status_filter and current_status != "shortlisted":
        continue
    elif "已投遞" in status_filter and current_status != "applied":
        continue
    elif "已略過" in status_filter and current_status != "skipped":
        continue

    job = item.get("job", {})
    title = str(job.get("title", ""))
    categories = " ".join(job.get("categories", []))
    desc = str(job.get("description", ""))
    full_text = f"{title} {categories}".lower()

    # 1. 雜訊排除
    if enable_noise_filter:
        is_trash = False
        for cname, kws in noise_rules.items():
            for kw in kws:
                if kw.lower() in full_text:
                    is_trash = True
                    break
            if is_trash:
                break
        if is_trash:
            continue

    # 2. 地區比對
    location = item.get("location", {})
    region = str(location.get("region", ""))
    is_remote = "遠端" in desc or "在家工作" in desc or "remote" in desc.lower()

    region_matched = False
    if "遠端工作" in selected_regions and is_remote:
        region_matched = True
    for r in selected_regions:
        if r != "遠端工作" and r in region:
            region_matched = True
            break
    if selected_regions and not region_matched:
        continue

    # 3. 薪資比對
    salary = job.get("salary", {})
    s_desc = str(salary.get("desc", ""))
    low = salary.get("low", 0) or 0
    high = salary.get("high", 0) or 0

    if "面議" in s_desc:
        if not include_negotiable:
            continue
    elif high > 0 and high < min_salary:
        continue
    elif low > 0 and low < min_salary and high == 0:
        continue

    # 4. 經歷比對
    req = job.get("requirements", {})
    work_exp = str(req.get("work_exp", ""))

    if selected_exps:
        exp_matched = False
        if "不拘" in selected_exps and ("不拘" in work_exp or not work_exp):
            exp_matched = True
        if "1年以下" in selected_exps and ("1年以下" in work_exp or "1年" in work_exp):
            exp_matched = True
        if "1~3年" in selected_exps and any(x in work_exp for x in ["1年", "2年", "3年", "1~3"]):
            exp_matched = True
        if "3~5年" in selected_exps and any(x in work_exp for x in ["3年", "4年", "5年", "3~5"]):
            exp_matched = True
        if "5年以上" in selected_exps and any(x in work_exp for x in ["5年", "6年", "7年", "8年", "10年"]):
            exp_matched = True

        # 如果使用者只勾選 1~3 年，主動排除 5 年以上
        if "5年以上" not in selected_exps and any(x in work_exp for x in ["5年", "6年", "7年", "8年", "10年"]):
            exp_matched = False

        if not exp_matched:
            continue

    # 5. 關鍵字搜尋
    if search_keyword:
        kw = search_keyword.lower()
        company_name = str(item.get("company", {}).get("name", "")).lower()
        if kw not in title.lower() and kw not in company_name and kw not in full_text and kw not in desc.lower():
            continue

    focused_jobs.append(item)

# ==========================================
# 主畫面：情報統計、批次投遞與職缺卡片
# ==========================================
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 背景爬取總量", f"{len(raw_jobs):,} 筆")
with col2:
    st.metric("🎯 篩選後精華職缺", f"{len(focused_jobs):,} 筆")
with col3:
    shortlisted_cnt = sum(1 for v in st.session_state.pipeline.values() if v.get("status") == "shortlisted")
    st.metric("⭐ 已加入收藏候選", f"{shortlisted_cnt:,} 筆")
with col4:
    applied_cnt = sum(1 for v in st.session_state.pipeline.values() if v.get("status") == "applied")
    st.metric("🚀 已投遞履歷", f"{applied_cnt:,} 筆")

st.divider()

# 批次操作區
top_action_col1, top_action_col2 = st.columns([3, 1])
with top_action_col1:
    st.subheader(f"📋 職缺清單 (目前顯示 {len(focused_jobs)} 筆)")
with top_action_col2:
    if shortlisted_cnt > 0 and st.button(f"⚡ 一鍵投遞所有收藏 ({shortlisted_cnt} 筆)", type="primary"):
        for jid, info in list(st.session_state.pipeline.items()):
            if info.get("status") == "shortlisted":
                st.session_state.pipeline[jid] = {
                    "status": "applied",
                    "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "cover_letter": active_cover_letter
                }
        save_pipeline(st.session_state.pipeline)
        st.success(f"🎉 已成功模擬批次投遞 {shortlisted_cnt} 筆職缺！")
        st.rerun()

# 職缺分頁渲染 (每頁顯示 20 筆)
PAGE_SIZE = 20
total_pages = max(1, (len(focused_jobs) + PAGE_SIZE - 1) // PAGE_SIZE)
current_page = st.number_input("目前頁碼", min_value=1, max_value=total_pages, value=1, step=1)

start_idx = (current_page - 1) * PAGE_SIZE
end_idx = start_idx + PAGE_SIZE
page_jobs = focused_jobs[start_idx:end_idx]

for job_item in page_jobs:
    jid = job_item.get("job_id")
    url = job_item.get("url")
    comp = job_item.get("company", {})
    loc = job_item.get("location", {})
    j = job_item.get("job", {})
    sal = j.get("salary", {})
    req = j.get("requirements", {})

    current_status = st.session_state.pipeline.get(jid, {}).get("status", "unprocessed")

    # 卡片容器
    with st.container(border=True):
        card_header, action_btns = st.columns([3.8, 1.2])

        with card_header:
            st.markdown(f"### [{j.get('title')}]({url})")
            st.markdown(
                f"🏢 **{comp.get('name')}** | 🏷️ 產業：{comp.get('industry', '未提供')} | "
                f"📍 **{loc.get('region')}**"
            )

            # 標籤列
            badges = []
            salary_desc = sal.get("desc") or "面議"
            badges.append(f"💰 `{salary_desc}`")
            badges.append(f"🎓 `{req.get('education', '學歷不拘')}`")
            badges.append(f"⏳ `{req.get('work_exp', '經歷不拘')}`")

            categories_str = ", ".join(j.get("categories", []))
            if categories_str:
                badges.append(f"📌 `{categories_str}`")

            st.markdown(" ".join(badges))

        with action_btns:
            st.write("")
            if current_status == "applied":
                st.success("✅ 已投遞履歷")
                applied_time = st.session_state.pipeline.get(jid, {}).get("applied_at", "")
                st.caption(f"投遞時間: {applied_time}")
            else:
                btn_col1, btn_col2 = st.columns(2)
                with btn_col1:
                    if current_status == "shortlisted":
                        if st.button("⭐ 取消", key=f"unshort_{jid}"):
                            del st.session_state.pipeline[jid]
                            save_pipeline(st.session_state.pipeline)
                            st.rerun()
                    else:
                        if st.button("⭐ 收藏", key=f"short_{jid}"):
                            st.session_state.pipeline[jid] = {"status": "shortlisted", "time": datetime.now().isoformat()}
                            save_pipeline(st.session_state.pipeline)
                            st.rerun()

                with btn_col2:
                    if st.button("❌ 略過", key=f"skip_{jid}"):
                        st.session_state.pipeline[jid] = {"status": "skipped", "time": datetime.now().isoformat()}
                        save_pipeline(st.session_state.pipeline)
                        st.rerun()

                if st.button("🚀 立即投遞", key=f"apply_{jid}", type="primary", use_container_width=True):
                    st.session_state.pipeline[jid] = {
                        "status": "applied",
                        "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "cover_letter": active_cover_letter
                    }
                    save_pipeline(st.session_state.pipeline)
                    st.toast(f"已成功記錄並模擬投遞：{j.get('title')} ({comp.get('name')})")
                    st.rerun()

        # 展開工作內容
        with st.expander("📖 查看職缺工作內容與詳細資訊"):
            desc_text = j.get("description", "無詳細工作內容")
            st.text(desc_text)
            st.caption(f"104 職缺原始代碼: {jid} | 資料採集時間: {job_item.get('crawled_at')}")
