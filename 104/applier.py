"""
104 人力銀行 Playwright 自動投遞核心模組
使用本地 Brave 瀏覽器引擎，具備真人人性化操作、持久化 Session 與反爬蟲風控規避機制。
"""

import os
import sys
import time
import random
import logging
from datetime import datetime
from typing import Dict, Optional, Tuple
from playwright.sync_api import sync_playwright, Page, BrowserContext

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("104_Applier")

BROWSER_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "browser_data"))
SCREENSHOTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "screenshots"))
BRAVE_EXEC_PATH = "/usr/bin/brave-browser"

os.makedirs(BROWSER_DATA_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)


class Job104Applier:
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.context: Optional[BrowserContext] = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def start(self):
        """啟動 Brave 瀏覽器並加載獨立持久化使用者設定檔"""
        self.playwright = sync_playwright().start()
        logger.info(f"啟動 Brave 瀏覽器引擎 (Profile: {BROWSER_DATA_DIR})")
        
        self.context = self.playwright.chromium.launch_persistent_context(
            user_data_dir=BROWSER_DATA_DIR,
            executable_path=BRAVE_EXEC_PATH,
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ],
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
            locale="zh-TW",
            viewport={"width": 1366, "height": 850}
        )

    def close(self):
        """安全關閉瀏覽器實例"""
        if self.context:
            try:
                self.context.close()
            except Exception:
                pass
            self.context = None
        if self.playwright:
            try:
                self.playwright.stop()
            except Exception:
                pass
            self.playwright = None

    def get_or_create_page(self) -> Page:
        if self.context.pages:
            return self.context.pages[0]
        return self.context.new_page()

    def check_is_logged_in(self, page: Page) -> bool:
        """檢驗是否已登入 104"""
        try:
            page.goto("https://www.104.com.tw/", wait_until="domcontentloaded")
            time.sleep(2)
            # 若頁面頂部存在「登入/註冊」按鈕，代表尚未登入
            login_btn = page.locator("text='登入/註冊'").first
            if login_btn.is_visible():
                return False
            return True
        except Exception as e:
            logger.warning(f"檢查登入狀態失敗: {e}")
            return False

    def ensure_logged_in(self, page: Page, timeout_seconds: int = 180) -> bool:
        """若尚未登入，引導並等待使用者在彈出的 Brave 視窗中完成登入"""
        if self.check_is_logged_in(page):
            logger.info("✅ 104 帳號處於登入有效狀態！")
            return True

        logger.info("⚠️ 偵測到 104 帳號尚未登入，正在導向登入入口...")
        page.goto("https://signin.104.com.tw/", wait_until="domcontentloaded")
        
        print("\n" + "=" * 60)
        print("🔔 請在彈出的 Brave 瀏覽器視窗中完成 104 登入")
        print("💡（完成後此 Profile 會永久保存登入態，未來投遞無需再次登入）")
        print("=" * 60 + "\n")

        start_time = time.time()
        while time.time() - start_time < timeout_seconds:
            time.sleep(2)
            cur_url = page.url
            # 當離開 signin 頁面並回到 104 主域時，代表登入成功
            if "signin.104.com.tw" not in cur_url and "104.com.tw" in cur_url:
                time.sleep(3)
                logger.info("🎉 登入成功！已安全記錄 Session Cookies。")
                return True
            # 或者檢查登入/註冊按鈕是否消失
            try:
                login_btn = page.locator("text='登入/註冊'").first
                if not login_btn.is_visible() and "104.com.tw" in cur_url:
                    logger.info("🎉 登入成功！")
                    return True
            except Exception:
                pass

        logger.error("❌ 登入逾時，未能完成授權。")
        return False

    def apply_to_job(
        self,
        job_id: str,
        cover_letter: str,
        resume_name: str = "CV",
        submit: bool = True
    ) -> Dict:
        """
        對指定職缺進行完整投遞：
        1. 導航至該職缺頁面
        2. 點擊「應徵」按鈕喚出彈窗
        3. 下拉選取指定履歷 (如 CV)
        4. 填入自我推薦信
        5. 截圖存查
        6. 點擊「確認送出」
        """
        page = self.get_or_create_page()
        job_url = f"https://www.104.com.tw/job/{job_id}"
        logger.info(f"正在導航至職缺頁面: {job_url}")

        page.goto(job_url, wait_until="domcontentloaded")
        # 擬人化停頓 2.5 ~ 4.0 秒
        time.sleep(random.uniform(2.5, 4.0))

        # 檢測「應徵」按鈕
        apply_btn = page.locator("text='應徵'").first
        if not apply_btn.is_visible():
            # 嘗試搜尋包含「我要應徵」或 button/a 標籤
            candidates = page.locator("button:has-text('應徵'), div:has-text('應徵'), span:has-text('應徵')").all()
            if candidates:
                apply_btn = candidates[0]

        if not apply_btn.is_visible():
            err_msg = f"找不到職缺 {job_id} 的應徵按鈕，可能職缺已關閉或已下架"
            logger.error(err_msg)
            page.screenshot(path=os.path.join(SCREENSHOTS_DIR, f"err_no_btn_{job_id}.png"))
            return {"success": False, "message": err_msg}

        logger.info("點擊「應徵」按鈕...")
        apply_btn.click()
        time.sleep(random.uniform(2.0, 3.5))

        # 檢查是否觸發了未登入跳轉
        if "signin.104.com.tw" in page.url:
            logger.warning("未登入，正在等待登入...")
            if not self.ensure_logged_in(page):
                return {"success": False, "message": "未完成登入，無法投遞"}
            # 重新回到該職缺頁
            page.goto(job_url, wait_until="domcontentloaded")
            time.sleep(2.5)
            page.locator("text='應徵'").first.click()
            time.sleep(2.5)

        # 等待應徵彈窗出現 (特徵: 自我推薦信 textarea.form-control)
        try:
            page.wait_for_selector("textarea.form-control", timeout=10000)
        except Exception:
            # 檢查是否有其他彈窗提示（例如：您已經應徵過此職缺）
            body_text = page.inner_text("body")
            if "您已應徵過此職缺" in body_text or "已應徵" in body_text:
                logger.warning(f"職缺 {job_id} 先前已應徵過")
                return {"success": True, "already_applied": True, "message": "此職缺先前已應徵過"}
            err_msg = "等待應徵彈窗逾時"
            logger.error(err_msg)
            return {"success": False, "message": err_msg}

        # 1. 處理履歷選擇下拉選單 (.select-resume vue-multiselect)
        try:
            resume_box = page.locator(".select-resume").first
            if resume_box.is_visible() and resume_name:
                cur_resume = resume_box.inner_text().strip()
                if resume_name not in cur_resume:
                    logger.info(f"切換履歷為: {resume_name}")
                    resume_box.click()
                    time.sleep(1.0)
                    opt = page.locator(f".multiselect__option:has-text('{resume_name}')").first
                    if opt.is_visible():
                        opt.click()
                        time.sleep(0.8)
                else:
                    logger.info(f"目前已預設選中履歷: {cur_resume}")
        except Exception as e:
            logger.warning(f"履歷選擇時提示: {e}")

        # 2. 填寫自我推薦信 (Cover Letter)
        textarea = page.locator("textarea.form-control").first
        if textarea.is_visible():
            logger.info("正在填寫客製化自我推薦信...")
            textarea.click()
            # 清空並填入
            textarea.fill("")
            time.sleep(0.5)
            textarea.fill(cover_letter)
            time.sleep(random.uniform(1.5, 2.5))
        else:
            logger.error("未找到推薦信輸入框！")
            return {"success": False, "message": "找不到推薦信文字框"}

        # 3. 填寫完成後的截圖存查
        shot_path_before = os.path.join(SCREENSHOTS_DIR, f"ready_to_submit_{job_id}.png")
        page.screenshot(path=shot_path_before)
        logger.info(f"📸 已截取確認送出前畫面存查: {shot_path_before}")

        if not submit:
            logger.info("【測試預覽模式】：未點擊「確認送出」，欄位驗證成功！")
            return {
                "success": True,
                "test_mode": True,
                "screenshot": shot_path_before,
                "message": "測試驗證成功：已成功開啟彈窗、選定履歷並填入自薦信（未點擊送出）"
            }

        # 4. 點擊「確認送出」按鈕
        submit_btn = page.locator("button.submit-btn:has-text('確認送出')").first
        if not submit_btn.is_visible():
            submit_btn = page.locator("button:has-text('確認送出')").first

        if not submit_btn.is_visible():
            err_msg = "找不到「確認送出」按鈕！"
            logger.error(err_msg)
            return {"success": False, "message": err_msg}

        logger.info("🚀 正在點擊「確認送出」按鈕進行正式投遞...")
        submit_btn.click()

        # 等待送出完成
        time.sleep(4.0)
        shot_path_after = os.path.join(SCREENSHOTS_DIR, f"after_submit_{job_id}.png")
        page.screenshot(path=shot_path_after)
        logger.info(f"📸 已截取送出後確認畫面存查: {shot_path_after}")

        return {
            "success": True,
            "applied_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "screenshot": shot_path_after,
            "message": "🎉 已成功將履歷與自薦信正式送出至 104！"
        }
