"""
104 智能求職情報與真實自動投遞系統 (Streamlit Web App)
啟動方式：
    streamlit run 104/104_job_search/app.py

功能特點：
1. 支援多種瀏覽器 (Brave, Chrome, Edge, Firefox) 執行真實 Playwright 自動投遞
2. 頂部即時全文檢索框 + 側邊欄結構化多維度篩選器（經歷、薪資、地區、雜訊排除、技能標籤）
3. 頁碼下拉選單 (Selectbox) 精確指示總頁數與資料範圍，每頁固定最多 10 筆
4. 狀態完全持久化（104/104_job_search/data/user_pipeline.json），自動排除已投遞職缺，每天啟動皆可無縫延續進度
5. 支援單筆即時投遞與跨頁循序批次投遞，自帶隨機延遲節流機制
"""

import os
import re
import sys
import json
import time
import random
from datetime import datetime
from typing import Dict, List, Set, Tuple
import streamlit as st

# 頁面配置
st.set_page_config(
    page_title="104 智能求職情報與投遞助手",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 智慧動態路徑解析（相容專案根目錄、104 目錄或 104_job_search 目錄啟動）
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PARENT_104_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))

JSONL_PATH = os.path.join(PARENT_104_DIR, "104_scrappers", "data", "jobs_104.jsonl")
RULES_PATH = os.path.join(BASE_DIR, "data", "filter_rules.json")
PIPELINE_PATH = os.path.join(BASE_DIR, "data", "user_pipeline.json")
DEFAULT_CV_FILE = os.path.join(BASE_DIR, "data", "default_cv.json")

# 預設自薦信模板
DEFAULT_COVER_LETTERS = {
    "軟體開發 / 後端工程師": (
        "您好，我是軟體開發工程師。\n"
        "過去具備系統開發與維運經驗，精通 Python、API 設計與資料庫操作。\n"
        "在 104 上看見貴公司招募的職缺，工作內容與我的技術棧非常契合，希望能爭取面試機會，謝謝！"
    ),
    "AI / 資料工程師": (
        "您好，我是 AI / 資料工程師。\n"
        "專注於機器學習模型開發、LLM 應用落地與資料管線 (ETL) 建立，熟悉 Python 與現代 AI 開發架構。\n"
        "非常看好貴團隊的產品發展，渴望將我的技術投入貴公司的研發之中，附件為我的履歷，謝謝！"
    ),
    "專案管理 / 產品經理 (PM)": (
        "您好，我是專案/產品管理師。\n"
        "擅長跨部門溝通協調、敏捷開發進度管理與需求梳理，具備專案推進經驗。\n"
        "對於貴公司的產品領域非常感興趣，渴望運用我的專案管理專長為團隊貢獻，附件為我的履歷，謝謝！"
    ),
    "通用版 (客製化自由編輯)": (
        "您好，我對貴公司開出的職缺非常感興趣，工作要求與我的專長相符，期待有機會與您進一步交流，謝謝！"
    )
}

# 若本地存在使用者自定義的自薦信檔，優先載入；若不存在則自動初始化預設模板檔供使用者自訂 (已於 gitignore 忽略)
if os.path.exists(DEFAULT_CV_FILE):
    try:
        with open(DEFAULT_CV_FILE, "r", encoding="utf-8") as f:
            user_templates = json.load(f)
            if isinstance(user_templates, dict) and user_templates:
                DEFAULT_COVER_LETTERS = user_templates
    except Exception:
        pass
else:
    try:
        os.makedirs(os.path.dirname(DEFAULT_CV_FILE), exist_ok=True)
        with open(DEFAULT_CV_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_COVER_LETTERS, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

# 104 經歷代碼映射表
WORK_EXP_MAP = {
    0: "不拘",
    1: "1年以下",
    2: "1年以上",
    3: "2年以上",
    4: "3年以上",
    5: "4年以上",
    6: "5年以上",
    7: "6年以上",
    8: "7年以上",
    9: "8年以上",
    10: "9年以上",
    11: "10年以上"
}


def parse_work_exp(val) -> str:
    """將 104 的數值代碼或文字統一轉為可讀中文字串"""
    if val is None or val == "":
        return "不拘"
    if isinstance(val, int) and val in WORK_EXP_MAP:
        return WORK_EXP_MAP[val]
    if str(val).isdigit() and int(val) in WORK_EXP_MAP:
        return WORK_EXP_MAP[int(val)]
    return str(val)


def exp_matches(val, selected: List[str]) -> bool:
    """比對工作經歷是否符合選取條件"""
    if not selected:
        return True
    s = parse_work_exp(val)
    if "不拘" in selected and s == "不拘":
        return True
    if "1年以下" in selected and s in ("不拘", "1年以下"):
        return True
    if "1~3年" in selected and s in ("1年以上", "2年以上", "3年以上"):
        return True
    if "3~5年" in selected and s in ("3年以上", "4年以上", "5年以上"):
        return True
    if "5年以上" in selected and s in ("5年以上", "6年以上", "7年以上", "8年以上", "9年以上", "10年以上"):
        return True
    return False


def load_pipeline() -> Dict[str, Dict]:
    if os.path.exists(PIPELINE_PATH):
        try:
            with open(PIPELINE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_pipeline(pipeline: Dict[str, Dict]):
    with open(PIPELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(pipeline, f, ensure_ascii=False, indent=2)


def load_filter_rules() -> tuple[Dict[str, List[str]], Dict[str, List[str]]]:
    noise_rules = {}
    positive_rules = {}
    if os.path.exists(RULES_PATH):
        try:
            with open(RULES_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                noise_rules = data.get("noise_categories", {})
                positive_rules = data.get("positive_focus_keywords", {})
        except Exception:
            pass
    return noise_rules, positive_rules


@st.cache_data(ttl=15)
def load_raw_jobs() -> List[Dict]:
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
noise_rules, _ = load_filter_rules()

# ==========================================
# 側邊欄：瀏覽器與投遞設定、自薦信、結構化篩選器
# ==========================================
with st.sidebar:
    st.header("⚙️ 自動化投遞設定")

    browser_choice = st.selectbox(
        "🌐 選擇執行瀏覽器 (Chromium / Gecko)",
        options=["Brave", "Chrome", "Edge", "Firefox"],
        index=0,
        help="指定用於自動登入與投遞的瀏覽器引擎。各瀏覽器擁有獨立安全的本地 Session"
    )

    apply_mode = st.radio(
        "投遞動作執行模式",
        options=["🚀 真實自動投遞 (Playwright 送出至 104)", "📝 本地模擬記錄 (僅更新狀態，不發送 104)"],
        index=0,
        help="「真實自動投遞」將調用本地瀏覽器自動完成 104 官方投遞；「本地模擬記錄」僅更新本機追蹤看板"
    )

    official_resume_name = st.text_input(
        "104 官方指定履歷名稱",
        value="CV",
        help="對應您在 104 會員後台建立的履歷名稱（例如: CV、軟體版履歷等）"
    )

    enable_batch_limit = st.checkbox(
        "自訂單次批次投遞筆數（未勾選＝無上限，全數投遞）",
        value=False,
        help="預設不設上限，一鍵投遞當前篩選出的所有未投遞職缺；勾選後可自訂任意筆數（無 100 筆限制）"
    )
    if enable_batch_limit:
        batch_apply_limit = st.number_input(
            "🎯 單次批次投遞筆數",
            min_value=1,
            value=100,
            step=10,
            help="可輸入任意數量，無上限限制"
        )
    else:
        batch_apply_limit = None

    cooldown_min, cooldown_max = st.slider(
        "⏱️ 投遞間隔秒數 (隨機擾動節流)",
        min_value=5,
        max_value=30,
        value=(10, 16),
        help="每筆投遞之間的等待秒數，模擬真人節奏以確保帳號安全"
    )

    if st.button("🔑 檢查 / 開啟 104 登入視窗", use_container_width=True):
        with st.spinner(f"正在開啟 {browser_choice} 瀏覽器檢查登入狀態..."):
            try:
                sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
                from applier import Job104Applier
                with Job104Applier(headless=False, browser_name=browser_choice) as applier:
                    page = applier.get_or_create_page()
                    if applier.check_is_logged_in(page):
                        st.success(f"✅ {browser_choice} 目前處於登入有效狀態！")
                    else:
                        st.warning("⚠️ 尚未登入，已為您導向登入頁面，請在視窗中登入...")
                        applier.ensure_logged_in(page, timeout_seconds=90)
            except Exception as e:
                st.error(f"開啟瀏覽器時發生錯誤: {e}")

    st.divider()

    st.header("📝 自我推薦信 (Cover Letter)")
    with st.expander("ℹ️ 自薦信用途說明", expanded=False):
        st.markdown(
            "在 104 點選「我要應徵」時，系統最上方的核心區塊即為**「自我推薦信」**。"
            "客製化推薦信能大幅提升 HR 開信率與面試邀約！"
        )

    template_choice = st.selectbox(
        "選擇自薦信模板",
        list(DEFAULT_COVER_LETTERS.keys())
    )

    if "cover_letter_text" not in st.session_state or st.session_state.get("last_template") != template_choice:
        st.session_state.cover_letter_text = DEFAULT_COVER_LETTERS[template_choice]
        st.session_state.last_template = template_choice

    active_cover_letter = st.text_area(
        "編輯自薦信內容（投遞時將填入 104 自我推薦區塊）",
        value=st.session_state.cover_letter_text,
        height=130
    )

    cv_col1, cv_col2 = st.columns([1.2, 1])
    with cv_col1:
        if st.button("💾 儲存此模板修改", use_container_width=True, help="將修改後的內容永久保存，下次啟動自動載入此內容"):
            DEFAULT_COVER_LETTERS[template_choice] = active_cover_letter
            try:
                os.makedirs(os.path.dirname(DEFAULT_CV_FILE), exist_ok=True)
                with open(DEFAULT_CV_FILE, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_COVER_LETTERS, f, ensure_ascii=False, indent=2)
                st.session_state.cover_letter_text = active_cover_letter
                st.success(f"✅ 已永久儲存「{template_choice}」！下次開啟直接生效。")
            except Exception as e:
                st.error(f"儲存失敗: {e}")

    with cv_col2:
        with st.popover("➕ 另存為新模板", use_container_width=True):
            new_tpl_name = st.text_input("新模板名稱", placeholder="例如: 量化研究員專用自薦信")
            if st.button("確認新增", type="primary", use_container_width=True):
                if new_tpl_name.strip():
                    DEFAULT_COVER_LETTERS[new_tpl_name.strip()] = active_cover_letter
                    try:
                        os.makedirs(os.path.dirname(DEFAULT_CV_FILE), exist_ok=True)
                        with open(DEFAULT_CV_FILE, "w", encoding="utf-8") as f:
                            json.dump(DEFAULT_COVER_LETTERS, f, ensure_ascii=False, indent=2)
                        st.session_state.cover_letter_text = active_cover_letter
                        st.session_state.last_template = new_tpl_name.strip()
                        st.success(f"✅ 成功新增模板「{new_tpl_name.strip()}」！")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"新增失敗: {e}")
                else:
                    st.warning("請先輸入新模板名稱！")

    st.divider()

    st.header("🔍 結構化條件篩選器")

    with st.expander("🛡️ 雜訊與底層排除設定", expanded=True):
        exclude_hardware = st.checkbox("排除硬體/韌體/電子底層 (IC/Firmware/嵌入式/單晶片等)", value=True)
        exclude_annotator = st.checkbox("排除假 AI / 標註員 (標註/審核/兼職工讀)", value=True)
        exclude_service_noise = st.checkbox("排除非辦公室雜訊 (保全/清潔/電銷/餐飲等)", value=True)

    region_options = ["台北市", "新北市", "桃園市", "新竹市", "新竹縣", "台中市", "遠端工作"]
    selected_regions = st.multiselect(
        "工作地區 (預設雙北、桃園、遠端)",
        options=region_options,
        default=["台北市", "新北市", "桃園市", "遠端工作"]
    )

    min_salary = st.number_input("最低薪資門檻 (NT$)", min_value=30000, max_value=200000, value=45000, step=5000)
    include_negotiable = st.checkbox("包含「待遇面議 (經常性薪資達4萬以上)」", value=True)

    exp_options = ["不拘", "1年以下", "1~3年", "3~5年", "5年以上"]
    selected_exps = st.multiselect(
        "工作經歷要求 (預設不拘、1~3年)",
        options=exp_options,
        default=["不拘", "1年以下", "1~3年"]
    )

    tag_filter_input = st.text_input(
        "🏷️ 技能標籤 / 關鍵字過濾",
        placeholder="例如: Python, RAG, PyTorch (多個可用逗號分隔)",
        help="僅保留職務內容或標籤中含有此類技術關鍵字的職缺"
    )

    status_filter = st.radio(
        "職缺處理狀態",
        options=["全部未處理 (Unprocessed)", "⭐ 已收藏候選 (Shortlisted)", "🚀 已投遞 (Applied)", "❌ 已略過 (Skipped)"],
        index=0,
        help="預設僅顯示「全部未處理」。已投遞的職缺會自動移出，下次開啟可無縫延續昨日進度"
    )

# ==========================================
# 資料過濾核心運算 (篩選管線)
# ==========================================
filtered_jobs = []

tag_kws = [k.strip().lower() for k in tag_filter_input.replace("，", ",").split(",") if k.strip()]

_KW_PATTERNS = {
    k: re.compile(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])")
    for k in tag_kws if k.isascii()
}


def match_keyword(kw: str, text: str, pattern_cache: dict = _KW_PATTERNS) -> bool:
    """純英文關鍵字採用單字邊界比對（避免 RAG 誤判 storage、AI 誤判 email/maintain），中英混合或中文採用子字串比對"""
    if kw.isascii():
        pat = pattern_cache.get(kw)
        if pat is None:
            pat = re.compile(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])")
            pattern_cache[kw] = pat
        return bool(pat.search(text))
    return kw in text


for item in raw_jobs:
    job_id = item.get("job_id")
    current_status = st.session_state.pipeline.get(job_id, {}).get("status", "unprocessed")

    # 1. 狀態過濾
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
    title_lower = title.lower()
    categories = " ".join(job.get("categories", []))
    desc = str(job.get("description", ""))
    full_text = f"{title} {categories}".lower()
    full_content = f"{title} {categories} {desc}".lower()

    # 2. 雜訊與底層排除 (Negative Filtering)
    if exclude_service_noise:
        service_categories = ["保險與金融電銷", "直銷與傳銷", "保全與樓管", "清潔與勞力", "餐飲門市服務", "美容與養生"]
        is_trash = False
        for cname in service_categories:
            for kw in noise_rules.get(cname, []):
                if kw.lower() in full_text:
                    is_trash = True
                    break
            if is_trash:
                break
        if is_trash:
            continue

    if exclude_hardware:
        hw_kws = noise_rules.get("硬體韌體與電子底層", []) + noise_rules.get("高門檻純底層與無關領域", [])
        if any(kw.lower() in full_text or kw.lower() in desc.lower() for kw in hw_kws):
            continue

    if exclude_annotator:
        ann_kws = noise_rules.get("假AI與資料標註", [])
        if any(kw.lower() in full_text for kw in ann_kws):
            continue

    # 3. 地區比對
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

    # 4. 薪資比對 (支援面議 low=0, high=0 與文字判斷)
    salary = job.get("salary", {})
    s_desc = str(salary.get("desc", ""))
    low = salary.get("low", 0) or 0
    high = salary.get("high", 0) or 0
    is_negotiable = ("面議" in s_desc) or (low == 0 and high == 0 and not s_desc)

    if is_negotiable:
        if not include_negotiable:
            continue
    elif high > 0 and high < min_salary:
        continue
    elif low > 0 and low < min_salary and high == 0:
        continue

    # 5. 經歷比對 (精準支援 104 代碼 0~11)
    req = job.get("requirements", {})
    raw_exp = req.get("work_exp")
    if not exp_matches(raw_exp, selected_exps):
        continue

    # 6. 標籤 / 技能關鍵字篩選 (含單字邊界精準比對與契合度計分)
    if tag_kws:
        matched_kws = [k for k in tag_kws if match_keyword(k, full_content)]
        if not matched_kws:
            continue
        title_hits = sum(1 for k in tag_kws if match_keyword(k, title_lower))
        item = dict(item)
        item["_matched_kws"] = matched_kws
        item["_title_hits"] = title_hits
        item["_kw_hits"] = len(matched_kws)

    filtered_jobs.append(item)

# 若有設定技能關鍵字，自動依「職稱命中數 + 總關鍵字命中數」由高至低排序，將最精準的極品職缺排在最前面
if tag_kws:
    filtered_jobs.sort(key=lambda x: (x.get("_title_hits", 0), x.get("_kw_hits", 0)), reverse=True)

# ==========================================
# 主畫面最頂部：即時檢索框 (Search Bar)
# ==========================================
st.markdown("### 💼 104 智能求職情報與自動投遞系統")

s_col1, s_col2 = st.columns([3.2, 1.3])
with s_col1:
    search_query = st.text_input(
        "🔍 即時檢索職缺（支援逗號分隔多個關鍵字，英文自動啟用單字邊界防誤判）",
        placeholder="例如輸入: LLM, RAG, Agent, 生成式, GenAI 或 AI, 演算法...",
        label_visibility="visible"
    )
with s_col2:
    search_scope = st.radio(
        "🎯 頂部檢索框比對範圍",
        options=["🎯 僅職稱與公司名 (精準鎖定)", "📄 全文檢索 (含工作內容)"],
        index=0,
        help="預設僅比對「職稱」與「公司名稱」，避免工作內容提到 AI 工具或 email 就被誤納入"
    )

# 二次檢索
if search_query.strip():
    sq_kws = [k.strip().lower() for k in search_query.replace("，", ",").split(",") if k.strip()]
    final_jobs = []
    title_only_mode = search_scope.startswith("🎯")
    for it in filtered_jobs:
        c_name = str(it.get("company", {}).get("name", "")).lower()
        j_title = str(it.get("job", {}).get("title", "")).lower()
        if title_only_mode:
            target_text = f"{j_title} {c_name}"
        else:
            j_desc = str(it.get("job", {}).get("description", "")).lower()
            j_loc = str(it.get("location", {}).get("region", "")).lower()
            target_text = f"{j_title} {c_name} {j_desc} {j_loc}"
        if any(match_keyword(sq, target_text) for sq in sq_kws):
            final_jobs.append(it)
else:
    final_jobs = filtered_jobs

# ==========================================
# 主畫面：情報統計 KPI 與操作列
# ==========================================
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("📦 背景採集總量", f"{len(raw_jobs):,} 筆")
with col2:
    st.metric("🎯 篩選後職缺", f"{len(final_jobs):,} 筆")
with col3:
    shortlisted_cnt = sum(1 for v in st.session_state.pipeline.values() if v.get("status") == "shortlisted")
    st.metric("⭐ 已加入收藏候選", f"{shortlisted_cnt:,} 筆")
with col4:
    applied_cnt = sum(1 for v in st.session_state.pipeline.values() if v.get("status") == "applied")
    st.metric("🚀 已投遞履歷", f"{applied_cnt:,} 筆")

st.divider()

# ==========================================
# 分頁控制 (Selectbox 每頁最多 10 個職缺)
# ==========================================
PAGE_SIZE = 10
total_pages = max(1, (len(final_jobs) + PAGE_SIZE - 1) // PAGE_SIZE)

col_title, col_page = st.columns([2.5, 1.5])
with col_title:
    st.subheader(f"📋 職缺清單 (符合條件共 {len(final_jobs):,} 筆，每頁顯示 10 筆)")

with col_page:
    page_options = [
        f"第 {p} 頁 (共 {total_pages} 頁，顯示第 {(p - 1) * PAGE_SIZE + 1} ~ {min(p * PAGE_SIZE, len(final_jobs))} 筆)"
        for p in range(1, total_pages + 1)
    ]
    selected_page_str = st.selectbox(
        "📄 切換瀏覽頁碼",
        options=page_options,
        index=0,
        label_visibility="collapsed"
    )
    current_page = page_options.index(selected_page_str) + 1

start_idx = (current_page - 1) * PAGE_SIZE
end_idx = min(start_idx + PAGE_SIZE, len(final_jobs))
page_jobs = final_jobs[start_idx:end_idx]

# ==========================================
# 批次自動投遞操作區 (跨頁全體未處理職缺)
# ==========================================
all_unapplied_candidates = [
    item for item in final_jobs
    if st.session_state.pipeline.get(item.get("job_id"), {}).get("status") != "applied"
]
target_batch_jobs = all_unapplied_candidates[:batch_apply_limit] if batch_apply_limit else all_unapplied_candidates

if all_unapplied_candidates or shortlisted_cnt > 0:
    action_box = st.container(border=True)
    with action_box:
        b_col1, b_col2, b_col3 = st.columns([2.2, 1.4, 1.4])
        with b_col1:
            st.markdown(
                f"⚡ **智慧批量投遞操作**  \n"
                f"<span style='color: #888; font-size: 0.9em;'>當前篩選結果共有 **{len(all_unapplied_candidates):,}** 筆未投遞職缺（每完成 1 筆即自動存檔，隨時中斷皆不影響進度）。</span>",
                unsafe_allow_html=True
            )
        with b_col2:
            if target_batch_jobs:
                btn_label = f"🚀 依序投遞全部 {len(target_batch_jobs)} 筆" if not batch_apply_limit else f"🚀 依序投遞前 {len(target_batch_jobs)} 筆"
                if st.button(
                    btn_label,
                    type="primary",
                    use_container_width=True,
                    help=f"自動循序投遞 {len(target_batch_jobs)} 筆職缺（每筆隨機間隔 {cooldown_min}~{cooldown_max} 秒）"
                ):
                    if apply_mode.startswith("🚀"):
                        st.info(f"🤖 啟動循序真實投遞：共 {len(target_batch_jobs)} 筆，間隔 {cooldown_min}~{cooldown_max} 秒節流中...")
                        progress_bar = st.progress(0.0)
                        status_placeholder = st.empty()

                        sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
                        from applier import Job104Applier

                        with Job104Applier(headless=False, browser_name=browser_choice) as applier:
                            for idx, j_item in enumerate(target_batch_jobs):
                                j_id = j_item.get("job_id")
                                j_info = j_item.get("job", {})
                                c_info = j_item.get("company", {})
                                status_placeholder.markdown(f"**正在投遞 [{idx+1}/{len(target_batch_jobs)}]**：`{j_info.get('title')}` ({c_info.get('name')})...")

                                res = applier.apply_to_job(
                                    job_id=j_id,
                                    cover_letter=active_cover_letter,
                                    resume_name=official_resume_name or "CV",
                                    submit=True
                                )
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                if res.get("success"):
                                    st.session_state.pipeline[j_id] = {
                                        "status": "applied",
                                        "applied_at": res.get("applied_at") or now_str,
                                        "cover_letter": active_cover_letter,
                                        "resume_file": f"104 官方履歷 ({official_resume_name})",
                                        "screenshot": res.get("screenshot")
                                    }
                                    save_pipeline(st.session_state.pipeline)
                                elif res.get("needs_manual"):
                                    st.session_state.pipeline[j_id] = {
                                        "status": "shortlisted",
                                        "time": now_str,
                                        "note": "⚠️ 含公司必填提問（需手動補填送出）",
                                        "screenshot": res.get("screenshot")
                                    }
                                    save_pipeline(st.session_state.pipeline)
                                elif res.get("closed"):
                                    st.session_state.pipeline[j_id] = {
                                        "status": "skipped",
                                        "time": now_str,
                                        "note": "❌ 職缺已關閉或結束徵才"
                                    }
                                    save_pipeline(st.session_state.pipeline)

                                progress_bar.progress((idx + 1) / len(target_batch_jobs))
                                if idx < len(target_batch_jobs) - 1:
                                    if res.get("closed"):
                                        time.sleep(1.5)
                                    else:
                                        sleep_secs = random.uniform(cooldown_min, cooldown_max)
                                        time.sleep(sleep_secs)

                        status_placeholder.success(f"🎉 已完成 {len(target_batch_jobs)} 筆職缺的自動投遞處理！")
                        time.sleep(2)
                        st.rerun()
                    else:
                        for j_item in target_batch_jobs:
                            j_id = j_item.get("job_id")
                            st.session_state.pipeline[j_id] = {
                                "status": "applied",
                                "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "cover_letter": active_cover_letter,
                                "resume_file": f"104 官方履歷 ({official_resume_name})"
                            }
                        save_pipeline(st.session_state.pipeline)
                        st.success(f"🎉 已成功將前 {len(target_batch_jobs)} 筆標記為已投遞！")
                        time.sleep(1.5)
                        st.rerun()

        with b_col3:
            if shortlisted_cnt > 0:
                if st.button(f"⭐ 投遞所有收藏 ({shortlisted_cnt} 筆)", type="secondary", use_container_width=True):
                    shortlisted_items = [
                        item for item in raw_jobs
                        if st.session_state.pipeline.get(item.get("job_id"), {}).get("status") == "shortlisted"
                    ]
                    if apply_mode.startswith("🚀"):
                        st.info(f"🤖 啟動收藏職缺投遞：共 {len(shortlisted_items)} 筆...")
                        progress_bar = st.progress(0.0)
                        status_placeholder = st.empty()

                        sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
                        from applier import Job104Applier

                        with Job104Applier(headless=False, browser_name=browser_choice) as applier:
                            for idx, j_item in enumerate(shortlisted_items):
                                j_id = j_item.get("job_id")
                                j_info = j_item.get("job", {})
                                c_info = j_item.get("company", {})
                                status_placeholder.markdown(f"**正在投遞收藏 [{idx+1}/{len(shortlisted_items)}]**：`{j_info.get('title')}` ({c_info.get('name')})...")

                                res = applier.apply_to_job(
                                    job_id=j_id,
                                    cover_letter=active_cover_letter,
                                    resume_name=official_resume_name or "CV",
                                    submit=True
                                )
                                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                if res.get("success"):
                                    st.session_state.pipeline[j_id] = {
                                        "status": "applied",
                                        "applied_at": res.get("applied_at") or now_str,
                                        "cover_letter": active_cover_letter,
                                        "resume_file": f"104 官方履歷 ({official_resume_name})",
                                        "screenshot": res.get("screenshot")
                                    }
                                    save_pipeline(st.session_state.pipeline)
                                elif res.get("closed"):
                                    st.session_state.pipeline[j_id] = {
                                        "status": "skipped",
                                        "time": now_str,
                                        "note": "❌ 職缺已關閉或結束徵才"
                                    }
                                    save_pipeline(st.session_state.pipeline)

                                progress_bar.progress((idx + 1) / len(shortlisted_items))
                                if idx < len(shortlisted_items) - 1:
                                    sleep_secs = random.uniform(cooldown_min, cooldown_max)
                                    time.sleep(sleep_secs)

                        status_placeholder.success(f"🎉 收藏的 {len(shortlisted_items)} 筆職缺已處理完畢！")
                        time.sleep(2)
                        st.rerun()
                    else:
                        for j_item in shortlisted_items:
                            j_id = j_item.get("job_id")
                            st.session_state.pipeline[j_id] = {
                                "status": "applied",
                                "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "cover_letter": active_cover_letter,
                                "resume_file": f"104 官方履歷 ({official_resume_name})"
                            }
                        save_pipeline(st.session_state.pipeline)
                        st.success(f"🎉 已將收藏的 {len(shortlisted_items)} 筆標記為已投遞！")
                        time.sleep(1.5)
                        st.rerun()

# ==========================================
# 職缺卡片渲染 (每頁最多 10 筆)
# ==========================================
if not page_jobs:
    st.info("💡 目前沒有符合條件的職缺，請嘗試放寬篩選條件或清空搜尋關鍵字。")
else:
    for job_item in page_jobs:
        jid = job_item.get("job_id")
        j = job_item.get("job", {})
        comp = job_item.get("company", {})
        loc = job_item.get("location", {})
        sal = j.get("salary", {})
        req = j.get("requirements", {})
        url = job_item.get("url")

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

                # 徽章解析
                badges = []
                s_low = sal.get("low", 0)
                s_high = sal.get("high", 0)
                s_text = sal.get("desc", "")

                if s_text:
                    badges.append(f"💰 `{s_text}`")
                elif s_low > 0 or s_high > 0:
                    if s_high > 0 and s_high < 9999999:
                        badges.append(f"💰 `月薪 {s_low:,} ~ {s_high:,}元`")
                    else:
                        badges.append(f"💰 `月薪 {s_low:,}元以上`")
                else:
                    badges.append("💰 `待遇面議 (經常性薪資4萬以上)`")

                badges.append(f"⏳ `{parse_work_exp(req.get('work_exp'))}`")

                edu_val = req.get("education")
                edu_str = "學歷不拘"
                if isinstance(edu_val, list) and edu_val:
                    edu_map = {1: "高中", 2: "專科", 3: "專科", 4: "大學", 5: "碩士", 6: "博士"}
                    edu_names = [edu_map.get(x, "") for x in edu_val if x in edu_map]
                    if edu_names:
                        edu_str = "、".join(set(edu_names))
                elif isinstance(edu_val, str) and edu_val:
                    edu_str = edu_val
                badges.append(f"🎓 `{edu_str}`")

                matched_kws_list = job_item.get("_matched_kws", [])
                if matched_kws_list:
                    badges.append(f"🔥 `命中 {len(matched_kws_list)} 項: {', '.join(matched_kws_list)}`")

                pipeline_note = st.session_state.pipeline.get(jid, {}).get("note")
                if pipeline_note:
                    badges.append(f"📌 `{pipeline_note}`")

                st.markdown(" ".join(badges))

            with action_btns:
                st.write("")
                if current_status == "applied":
                    st.success("✅ 已投遞履歷")
                    applied_time = st.session_state.pipeline.get(jid, {}).get("applied_at", "")
                    applied_res = st.session_state.pipeline.get(jid, {}).get("resume_file", "")
                    st.caption(f"投遞時間: {applied_time}")
                    if applied_res:
                        st.caption(f"官方履歷: {applied_res}")
                    if st.button("🔄 重新標記為未處理", key=f"revert_{jid}", use_container_width=True):
                        del st.session_state.pipeline[jid]
                        save_pipeline(st.session_state.pipeline)
                        st.rerun()
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
                        if apply_mode.startswith("🚀"):
                            with st.spinner(f"🤖 正在調用 {browser_choice} 自動投遞引擎送出至 104..."):
                                try:
                                    sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
                                    from applier import Job104Applier
                                    with Job104Applier(headless=False, browser_name=browser_choice) as applier:
                                        res = applier.apply_to_job(
                                            job_id=jid,
                                            cover_letter=active_cover_letter,
                                            resume_name=official_resume_name or "CV",
                                            submit=True
                                        )
                                        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                        if res.get("success"):
                                            st.session_state.pipeline[jid] = {
                                                "status": "applied",
                                                "applied_at": res.get("applied_at") or now_str,
                                                "cover_letter": active_cover_letter,
                                                "resume_file": f"104 官方履歷 ({official_resume_name})",
                                                "screenshot": res.get("screenshot")
                                            }
                                            save_pipeline(st.session_state.pipeline)
                                            st.success(f"🎉 投遞成功！已送出至 104：{j.get('title')}")
                                            time.sleep(1.5)
                                            st.rerun()
                                        elif res.get("needs_manual"):
                                            st.session_state.pipeline[jid] = {
                                                "status": "shortlisted",
                                                "time": now_str,
                                                "note": "⚠️ 含公司必填提問（需手動補填送出）",
                                                "screenshot": res.get("screenshot")
                                            }
                                            save_pipeline(st.session_state.pipeline)
                                            st.warning(f"⚠️ 含有公司必填提問，已轉入『⭐ 已收藏候選』供手動補填：{j.get('title')}")
                                            time.sleep(1.5)
                                            st.rerun()
                                        elif res.get("closed"):
                                            st.session_state.pipeline[jid] = {
                                                "status": "skipped",
                                                "time": now_str,
                                                "note": "❌ 職缺已關閉或結束徵才"
                                            }
                                            save_pipeline(st.session_state.pipeline)
                                            st.warning(f"❌ 該職缺已關閉，已自動移入『❌ 已略過』：{j.get('title')}")
                                            time.sleep(1.5)
                                            st.rerun()
                                        else:
                                            st.error(f"❌ 投遞未能完成: {res.get('message')}")
                                except Exception as e:
                                    st.error(f"❌ 執行自動投遞時發生異常: {e}")
                        else:
                            st.session_state.pipeline[jid] = {
                                "status": "applied",
                                "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "cover_letter": active_cover_letter,
                                "resume_file": f"104 官方履歷 ({official_resume_name})"
                            }
                            save_pipeline(st.session_state.pipeline)
                            st.toast(f"已記錄投遞：{j.get('title')} ({comp.get('name')})")
                            st.rerun()

            # 展開工作內容
            with st.expander("📖 查看職缺工作內容與詳細資訊"):
                desc_text = j.get("description", "無詳細工作內容")
                st.text(desc_text)
                st.caption(f"104 職缺原始代碼: {jid} | 資料採集時間: {job_item.get('crawled_at')}")
