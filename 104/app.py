"""
104 智能求職儀表板與自動投遞系統 (Streamlit Web App)
啟動方式：
    streamlit run 104/app.py
功能特點：
1. 修正 104 列表 API 代碼解析（經歷代碼 0~11、薪資面議 0/0 識別），精確篩選數萬筆職缺
2. 【永久履歷庫】：支援本地持久化儲存多份 PDF 履歷，隨時切換指定投遞的履歷版本
3. 【自薦信管理】：對應 104 官方應徵彈窗的「自我推薦信」區塊，支援自由編輯與模板切換
4. 卡片式職缺瀏覽：顯示直觀中文字標籤、一鍵收藏、略過、記錄投遞
5. 投遞狀態持久化：寫入 104/user_pipeline.json，重整完全不丟失
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
RESUME_DIR = "104/resumes"

os.makedirs(RESUME_DIR, exist_ok=True)

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
        "您好，我對貴公司開出的職缺非常感興趣，工作要求與我的專長相符，附件為我的詳細個人履歷，期待有機會與您進一步交流，謝謝！"
    )
}

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


def list_saved_resumes() -> List[str]:
    """取得永久履歷庫中的所有 PDF 檔案"""
    if not os.path.exists(RESUME_DIR):
        return []
    files = [f for f in os.listdir(RESUME_DIR) if f.lower().endswith(".pdf")]
    return sorted(files)


# 初始化 Session State
if "pipeline" not in st.session_state:
    st.session_state.pipeline = load_pipeline()

raw_jobs = load_raw_jobs()
noise_rules, positive_rules = load_filter_rules()

# ==========================================
# 側邊欄：多履歷庫、自薦信與多維度篩選器
# ==========================================
with st.sidebar:
    st.header("📂 永久履歷庫管理")

    # 上傳並儲存新履歷至本地持久化目錄
    uploaded_file = st.file_uploader("上傳新履歷 PDF（永久保存於履歷庫）", type=["pdf"])
    if uploaded_file is not None:
        save_path = os.path.join(RESUME_DIR, uploaded_file.name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        st.success(f"已成功加入履歷庫：{uploaded_file.name}")
        st.rerun()

    saved_resumes = list_saved_resumes()
    selected_resume = None

    if saved_resumes:
        selected_resume = st.selectbox(
            "選擇當前投遞履歷版本",
            options=saved_resumes,
            help="投遞時將以此份 PDF 作為附件"
        )
        st.info(f"當前掛載：**{selected_resume}**")

        # 履歷管理小工具
        col_res1, col_res2 = st.columns(2)
        with col_res1:
            resume_filepath = os.path.join(RESUME_DIR, selected_resume)
            with open(resume_filepath, "rb") as rf:
                st.download_button(
                    label="📥 下載預覽",
                    data=rf.read(),
                    file_name=selected_resume,
                    mime="application/pdf",
                    use_container_width=True
                )
        with col_res2:
            if st.button("🗑️ 刪除此履歷", use_container_width=True):
                os.remove(os.path.join(RESUME_DIR, selected_resume))
                st.rerun()
    else:
        st.caption("目前履歷庫尚無檔案，請先上傳 PDF 履歷。")

    st.divider()

    st.header("📝 自我推薦信 (Cover Letter)")
    with st.expander("ℹ️ 自薦信用途說明", expanded=False):
        st.markdown(
            "**這是什麼？**\n"
            "在 104 點選「我要應徵」時，系統最上方的核心區塊就是**「自我推薦信」**。"
            "HR 打開應徵通知時第一眼看到的就是這段內容，客製化自薦信能大幅提高開信率與面試邀約！"
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

    st.divider()

    st.header("🎯 專屬 AI / LLM 戰略速篩")
    ai_track = st.selectbox(
        "選擇高勝率戰略賽道",
        options=[
            "全部職缺 (不限賽道)",
            "🔥 LLM / 生成式 AI 核心 (RAG, Agent, Prompt, Vector DB)",
            "⚡ Python AI 應用與管線 (FastAPI, 爬蟲, 自動化)",
            "💼 AI 解決方案與技術顧問 (顧問, POC, 專案導入)"
        ],
        index=0,
        help="直接鎖定當前市場急需、不考白板題刷題的即戰力職缺！"
    )

    st.header("🔍 多維度篩選過濾器")

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

    search_keyword = st.text_input("即時關鍵字搜尋 (職稱、公司、技能)", placeholder="例如: Python, 專案, AWS")

    status_filter = st.radio(
        "職缺處理狀態",
        options=["全部未處理 (Unprocessed)", "⭐ 已收藏候選 (Shortlisted)", "🚀 已投遞 (Applied)", "❌ 已略過 (Skipped)"],
        index=0
    )

# ==========================================
# 資料過濾核心運算 (Rough Filter Engine - 精準修正版)
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
    full_search_text = f"{title} {categories} {desc}".lower()

    # 1. 雜訊與底層排除 (Negative Filtering)
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

    # 2. 戰略賽道正向篩選 (Positive Track Filtering)
    if ai_track != "全部職缺 (不限賽道)":
        target_kws = []
        if "LLM / 生成式 AI 核心" in ai_track:
            target_kws = positive_rules.get("LLM & 生成式AI 核心", [])
        elif "Python AI 應用" in ai_track:
            target_kws = positive_rules.get("AI 應用與資料管線", [])
        elif "AI 解決方案" in ai_track:
            target_kws = positive_rules.get("AI 解決方案與技術顧問", [])

        if target_kws and not any(kw.lower() in full_search_text for kw in target_kws):
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

    # 3. 薪資比對 (支援面議 low=0, high=0 與文字判斷)
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

    # 4. 經歷比對 (精準支援 104 代碼 0~11)
    req = job.get("requirements", {})
    raw_exp = req.get("work_exp")
    if not exp_matches(raw_exp, selected_exps):
        continue

    # 5. 關鍵字比對
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
    st.subheader(f"📋 職缺清單 (符合條件共 {len(focused_jobs):,} 筆)")
with top_action_col2:
    if shortlisted_cnt > 0 and st.button(f"⚡ 一鍵投遞所有收藏 ({shortlisted_cnt} 筆)", type="primary"):
        for jid, info in list(st.session_state.pipeline.items()):
            if info.get("status") == "shortlisted":
                st.session_state.pipeline[jid] = {
                    "status": "applied",
                    "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "cover_letter": active_cover_letter,
                    "resume_file": selected_resume or "預設履歷"
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

            st.markdown(" ".join(badges))

        with action_btns:
            st.write("")
            if current_status == "applied":
                st.success("✅ 已投遞履歷")
                applied_time = st.session_state.pipeline.get(jid, {}).get("applied_at", "")
                applied_res = st.session_state.pipeline.get(jid, {}).get("resume_file", "")
                st.caption(f"投遞時間: {applied_time}")
                if applied_res:
                    st.caption(f"附件履歷: {applied_res}")
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

                resume_tag = f"（使用：{selected_resume}）" if selected_resume else ""
                if st.button(f"🚀 立即投遞", key=f"apply_{jid}", type="primary", use_container_width=True):
                    st.session_state.pipeline[jid] = {
                        "status": "applied",
                        "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "cover_letter": active_cover_letter,
                        "resume_file": selected_resume or "預設履歷"
                    }
                    save_pipeline(st.session_state.pipeline)
                    st.toast(f"已記錄投遞：{j.get('title')} ({comp.get('name')})")
                    st.rerun()

        # 展開工作內容
        with st.expander("📖 查看職缺工作內容與詳細資訊"):
            desc_text = j.get("description", "無詳細工作內容")
            st.text(desc_text)
            st.caption(f"104 職缺原始代碼: {jid} | 資料採集時間: {job_item.get('crawled_at')}")
