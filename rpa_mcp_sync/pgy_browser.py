from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import requests

from .config_store import ROOT

CDP_URL = "http://127.0.0.1:9222/json/version"
PGY_KOL_URL = "https://pgy.xiaohongshu.com/solar/pre-trade/note/kol"


def browser_status() -> dict[str, Any]:
    try:
        response = requests.get(CDP_URL, timeout=2)
        if response.ok:
            payload = response.json()
            return {
                "connected": True,
                "message": "已连接 Chrome 调试端口",
                "webSocketDebuggerUrl": payload.get("webSocketDebuggerUrl"),
                "browser": payload.get("Browser"),
            }
    except requests.RequestException:
        pass
    return {
        "connected": False,
        "message": "未检测到 Chrome 调试端口，请先启动调试浏览器并登录蒲公英",
        "start_command": 'Start-Process "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=D:\\第三事业部\\runtime\\chrome-pgy-profile"',
    }


def start_browser() -> dict[str, Any]:
    status = browser_status()
    if status["connected"]:
        return status
    chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
    if not chrome.exists():
        return {"connected": False, "message": "未找到 Chrome，请手动用调试端口启动浏览器"}
    profile = ROOT / "runtime" / "chrome-pgy-profile"
    profile.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            str(chrome),
            "--remote-debugging-port=9222",
            f"--user-data-dir={profile}",
            PGY_KOL_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return {**browser_status(), "message": "已尝试启动独立 Chrome，请在打开的页面登录蒲公英"}


def collect_visible_list() -> dict[str, Any]:
    if not browser_status()["connected"]:
        return {"ok": False, "message": "未连接 Chrome 调试端口"}
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {"ok": False, "message": "当前环境未安装 Playwright，无法执行真实页面采集"}

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            pages = context.pages
            page = next((item for item in pages if "pgy.xiaohongshu.com" in item.url), pages[0] if pages else context.new_page())
            if "pgy.xiaohongshu.com" not in page.url:
                page.goto(PGY_KOL_URL, wait_until="domcontentloaded", timeout=30000)
            if "/solar/pre-trade/note/kol" not in page.url:
                return {"ok": False, "message": "请先打开蒲公英博主广场 / 找博主页面", "current_url": page.url}
            page.wait_for_timeout(1500)
            login_hint = page.locator("text=登录").first
            if login_hint.count() and "login" in page.url.lower():
                return {"ok": False, "message": "蒲公英尚未登录，请在打开的 Chrome 页面完成登录", "current_url": page.url}
            rows = page.locator(".blogger-list_list .d-new-table tbody tr")
            count = rows.count()
            if count == 0:
                return {
                    "ok": False,
                    "message": "未识别到博主列表，请确认已登录并停留在博主广场列表页",
                    "current_url": page.url,
                }
            creators: list[dict[str, Any]] = []
            for index in range(min(count, 20)):
                row = rows.nth(index)
                text = row.inner_text(timeout=3000)
                profile = row.locator(".profile").first
                nickname = text.splitlines()[0].strip() if text else f"蒲公英达人{index + 1}"
                pgy_url = page.url
                if profile.count():
                    label = profile.inner_text(timeout=1000).strip()
                    nickname = label or nickname
                    href = profile.get_attribute("href")
                    if href:
                        pgy_url = href if href.startswith("http") else f"https://pgy.xiaohongshu.com{href}"
                creators.append(
                    {
                        "source": "pgy",
                        "nickname": nickname,
                        "pgy_url": pgy_url,
                        "raw_payload": {"text": text},
                    }
                )
            return {"ok": True, "creators": creators, "current_url": page.url}
    except Exception as error:
        return {"ok": False, "message": f"蒲公英采集失败：{error}"}
