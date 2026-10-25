"""
104 登入授權工具
引導使用者在專屬的 Brave 自動化環境中完成一次性登入，並永久保存登入狀態。
"""

import os
import time
import logging
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("104_Login")

from applier import Job104Applier, BROWSER_DATA_DIR, SCREENSHOTS_DIR

def run_login(browser_name: str = "Brave"):
    print("\n" + "=" * 65)
    print(f"🚀 正在啟動專屬 {browser_name} 瀏覽器登入視窗...")
    print("👉 請在彈出的視窗中完成 104 登入（帳密 / Google / Line 登入均可）")
    print("💡 僅需登入這一次，登入態將永久保存在本地，後續投遞不再需要手動登入！")
    print("=" * 65 + "\n")

    with Job104Applier(headless=False, browser_name=browser_name) as applier:
        page = applier.get_or_create_page()
        page.goto("https://signin.104.com.tw/", wait_until="domcontentloaded")
        
        # 輪詢檢測登入狀態 (最多等待 5 分鐘)
        max_wait = 300
        start = time.time()
        logged_in = False

        while time.time() - start < max_wait:
            time.sleep(2)
            # 若登入過程彈出新分頁，收斂為單一分頁
            page = applier.get_or_create_page()
            cur_url = page.url
            # 若 URL 離開 signin 進入 104 其它頁面，表示登入完成
            if "signin.104.com.tw" not in cur_url and "104.com.tw" in cur_url:
                logged_in = True
                break
            # 或檢查頁面是否已經沒有 signin 的特定元素
            try:
                if not page.locator("input[type='password'], text='登入/註冊'").first.is_visible():
                    logged_in = True
                    break
            except Exception:
                pass

        if logged_in:
            time.sleep(2)
            print("\n" + "=" * 65)
            print("🎉 恭喜！偵測到 104 登入成功！")
            print(f"💾 登入狀態已安全永久保存於 {BROWSER_DATA_DIR}")
            print("=" * 65 + "\n")
            
            # 導向目標測試職缺確認登入態
            print("🔍 正在確認職缺頁面登入態 (924qj)...")
            page.goto("https://www.104.com.tw/job/924qj", wait_until="domcontentloaded")
            time.sleep(3)
            os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
            verify_shot = os.path.join(SCREENSHOTS_DIR, "logged_in_verified.png")
            page.screenshot(path=verify_shot)
            print(f"📸 已截圖驗證檔: {verify_shot}")
            time.sleep(2)
        else:
            print("❌ 等待逾時，請重新執行本工具。")

if __name__ == "__main__":
    run_login()
