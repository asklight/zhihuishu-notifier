"""智慧树 Cookie 持久化与微信扫码登录模块。"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from requests.cookies import create_cookie
from DrissionPage import ChromiumOptions, ChromiumPage

import config
import notifier


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}
CDP_GET_ALL_COOKIES = "Network.getAllCookies"


def save_cookie(session: requests.Session, path: str) -> None:
    """保存 session cookies 到 JSON 文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(session.cookies.get_dict(), f, indent=2, ensure_ascii=False)


def load_cookie(session: requests.Session, path: str) -> bool:
    """加载 JSON cookies 到 session，成功返回 True。"""
    if not os.path.exists(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict) or not data:
                return False
            session.cookies.update(data)
            return True
    except Exception:
        return False


def _utc_iso_now() -> str:
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def verify_login(session: requests.Session) -> bool:
    """校验当前 session 是否有效。"""
    try:
        uuid = get_uuid(session)
        if not uuid:
            return False

        resp = session.get(
            config.HOMEWORK_LIST_URL,
            params={"uuid": uuid, "date": _utc_iso_now()},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("status") == "200" and data.get("rt") is not None
    except Exception:
        return False


def get_uuid(session: requests.Session) -> Optional[str]:
    """获取用户 uuid（rt.username）。"""
    try:
        ts = int(time.time() * 1000)
        resp = session.get(config.VERIFY_URL, params={"dateFormate": ts}, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        rt = data.get("rt") or {}
        username = rt.get("username")
        if username:
            return username
    except Exception:
        pass

    try:
        for key in session.cookies.keys():
            if isinstance(key, str) and key.startswith("exitRecod_"):
                value = key.replace("exitRecod_", "", 1).strip()
                if value:
                    return value
    except Exception:
        pass

    return None


def _fill_credentials(page: ChromiumPage) -> None:
    if config.ZHS_USERNAME:
        try:
            page.ele(
                'xpath://input[contains(@placeholder,"账号") or contains(@placeholder,"手机号") or contains(@placeholder,"用户名")]'
            ).input(config.ZHS_USERNAME)
        except Exception:
            pass

    if config.ZHS_PASSWORD:
        try:
            page.ele('xpath://input[contains(@type,"password") or contains(@placeholder,"密码")]').input(
                config.ZHS_PASSWORD
            )
        except Exception:
            pass


def _click_wechat_login(page: ChromiumPage) -> bool:
    wechat_selectors = [
        'xpath://a[contains(@class,"wechat") or contains(text(),"微信")]',
        'xpath://div[contains(@class,"wechat") or contains(text(),"微信")]',
        'xpath://span[contains(text(),"微信")]',
    ]
    for selector in wechat_selectors:
        try:
            page.ele(selector).click()
            return True
        except Exception:
            continue
    return False


def _capture_qrcode(page: ChromiumPage, qrcode_path: str) -> None:
    qrcode_ele = None
    start = time.time()
    while time.time() - start < 10:
        try:
            qrcode_ele = page.ele('xpath://div[contains(@class,"qrcode") or contains(@class,"wxLogin")]')
        except Exception:
            qrcode_ele = None

        if qrcode_ele:
            break
        time.sleep(0.5)

    if qrcode_ele:
        try:
            time.sleep(1)
            qrcode_ele.get_screenshot(path=qrcode_path)
            return
        except Exception:
            pass

    page.get_screenshot(path=qrcode_path)


def _collect_cookies_from_raw(raw) -> dict[str, str]:
    cookies: dict[str, str] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and item.get("name"):
                cookies[item["name"]] = str(item.get("value") or "")
    elif isinstance(raw, dict):
        for k, v in raw.items():
            cookies[str(k)] = str(v)
    return cookies


def _collect_cookies_from_page(page: ChromiumPage) -> dict[str, str]:
    try:
        try:
            raw = page.cookies(all_domains=True)
        except TypeError:
            raw = page.cookies()
        cookies = _collect_cookies_from_raw(raw)

        try:
            runner = getattr(page, "run_cdp", None) or getattr(page, "_run_cdp", None)
            if runner:
                data = runner(CDP_GET_ALL_COOKIES)
                for item in data.get("cookies", []):
                    if item.get("name"):
                        cookies[item["name"]] = str(item.get("value") or "")
        except Exception:
            pass

        return cookies
    except Exception:
        return {}


def _get_tabs(page: ChromiumPage):
    try:
        tabs = getattr(page, "tabs", None)
        if callable(tabs):
            return tabs()
        return tabs
    except Exception:
        return None


def _apply_cdp_cookies(session: requests.Session, page: ChromiumPage) -> None:
    try:
        runner = getattr(page, "run_cdp", None) or getattr(page, "_run_cdp", None)
        if not runner:
            return
        data = runner(CDP_GET_ALL_COOKIES)
        for item in data.get("cookies", []):
            name = item.get("name")
            value = item.get("value")
            domain = item.get("domain")
            path = item.get("path") or "/"
            if not name:
                continue
            try:
                cookie = create_cookie(
                    name=name,
                    value=value,
                    domain=domain,
                    path=path,
                    secure=bool(item.get("secure")),
                )
                session.cookies.set_cookie(cookie)
            except Exception:
                continue
    except Exception:
        return


def _build_session_from_page(page: ChromiumPage) -> Optional[requests.Session]:
    try:
        cookies = _collect_cookies_from_page(page)
        tabs = _get_tabs(page)
        if tabs:
            for tab in tabs:
                cookies.update(_collect_cookies_from_page(tab))

        if not cookies:
            return None

        session = requests.Session()
        session.headers.update(DEFAULT_HEADERS)
        session.cookies.update(cookies)
        _apply_cdp_cookies(session, page)
        return session
    except Exception:
        return None


def _try_valid_session(page: ChromiumPage, cookie_path: str, app_token: str, uid: str) -> Optional[requests.Session]:
    session = _build_session_from_page(page)
    if not session:
        return None

    if verify_login(session):
        save_cookie(session, cookie_path)
        notifier.push_login_success(app_token, uid)
        return session

    cookie_keys = set(session.cookies.keys())
    if cookie_keys.intersection({"GSSESSIONID", "SESSION", "JSESSIONID", "CASTGC"}):
        save_cookie(session, cookie_path)
        notifier.push_login_success(app_token, uid)
        return session

    return None


def _try_fallback_session(page: ChromiumPage, cookie_path: str, app_token: str, uid: str) -> Optional[requests.Session]:
    session = _build_session_from_page(page)
    if not session:
        return None

    cookie_keys = set(session.cookies.keys())
    if cookie_keys:
        save_cookie(session, cookie_path)
        notifier.push_login_success(app_token, uid)
        return session

    return None


def _try_any_session(page: ChromiumPage, cookie_path: str, app_token: str, uid: str) -> Optional[requests.Session]:
    session = _try_valid_session(page, cookie_path, app_token, uid)
    if session:
        return session
    return _try_fallback_session(page, cookie_path, app_token, uid)


def _login_progressed(page: ChromiumPage) -> bool:
    selector = (
        'xpath://div[contains(@class,"scan") or contains(@class,"success") '
        'or contains(text(),"扫码成功") or contains(text(),"已扫描") or contains(text(),"已登录")]'
    )
    try:
        if "passport.zhihuishu.com" not in page.url:
            return True

        tabs = _get_tabs(page)
        if tabs:
            for tab in tabs:
                try:
                    if "passport.zhihuishu.com" not in tab.url:
                        return True
                except Exception:
                    continue

        return bool(page.ele(selector, timeout=1))
    except Exception:
        return False


def _goto_online_home(page: ChromiumPage) -> None:
    try:
        link_selectors = [
            'xpath://a[contains(text(),"我的学堂") or contains(@href,"onlinestuh5")]',
            'xpath://span[contains(text(),"我的学堂")]',
            'xpath://div[contains(text(),"我的学堂")]',
        ]
        for selector in link_selectors:
            try:
                page.ele(selector, timeout=2).click()
                time.sleep(2)
                return
            except Exception:
                continue
    except Exception:
        pass

    try:
        page.get(config.ONLINE_HOME_URL)
        time.sleep(2)
    except Exception:
        pass


def _sync_domains(page: ChromiumPage) -> bool:
    try:
        _goto_online_home(page)
        page.get(config.ONLINE_HOME_URL)
        time.sleep(2)
        page.get("https://www.zhihuishu.com")
        time.sleep(1)
        page.get("https://hike-examstu.zhihuishu.com")
        time.sleep(1)
        page.get("https://onlineservice.zhihuishu.com")
        time.sleep(2)
        return True
    except Exception:
        return False


def _browser_verify(page: ChromiumPage) -> bool:
    try:
        ts = int(time.time() * 1000)
        page.get(f"{config.VERIFY_URL}?dateFormate={ts}")
        time.sleep(1)
        text = ""
        try:
            text = page.html or ""
        except Exception:
            text = ""
        data = json.loads(text) if text.strip().startswith("{") else None
        if isinstance(data, dict) and data.get("status") == "200":
            return True
        return False
    except Exception:
        return False


def _handle_progress(
    page: ChromiumPage,
    cookie_path: str,
    app_token: str,
    uid: str,
    synced: bool,
    snapshotted: bool,
) -> tuple[Optional[requests.Session], bool, bool]:
    if not synced:
        synced = _sync_domains(page) or synced

    if not snapshotted:
        _debug_snapshot(page, "progress", app_token, uid)
        snapshotted = True

    _browser_verify(page)

    session = _try_any_session(page, cookie_path, app_token, uid)
    return session, synced, snapshotted


def _wait_for_login(page: ChromiumPage, cookie_path: str, app_token: str, uid: str, timeout: int) -> Optional[requests.Session]:
    start = time.time()
    synced = False
    snapshotted = False
    last_sync_at = 0.0
    while time.time() - start < timeout:
        progressed = _login_progressed(page)
        should_sync = progressed or (time.time() - last_sync_at >= 8)

        if should_sync:
            session, synced, snapshotted = _handle_progress(
                page, cookie_path, app_token, uid, synced, snapshotted
            )
            last_sync_at = time.time()
            if session:
                return session

        session = _try_any_session(page, cookie_path, app_token, uid)
        if session:
            return session

        time.sleep(3)

    _debug_snapshot(page, "timeout", app_token, uid)
    _debug_cookie_state(page, "timeout", app_token, uid)
    notifier.push_login_timeout(app_token, uid)
    return None


def _show_qrcode(path: str) -> None:
    try:
        if os.name == "nt" and os.path.exists(path):
            os.startfile(path)
    except Exception:
        pass


def _debug_snapshot(page: ChromiumPage, label: str, app_token: str, uid: str) -> None:
    try:
        os.makedirs("data", exist_ok=True)
        path = os.path.join("data", f"debug_{label}.png")
        try:
            page.get_screenshot(path=path)
        except Exception:
            return

        title = ""
        url = ""
        try:
            url = page.url
        except Exception:
            url = ""
        try:
            title = page.title
        except Exception:
            try:
                title = page.run_js("document.title")
            except Exception:
                title = ""

        print(f"[DEBUG] 当前页面: title={title} url={url}")
        notifier.push_image(path, f"扫码状态截图\nTitle: {title}\nURL: {url}", app_token, uid)
    except Exception:
        pass


def _debug_cookie_state(page: ChromiumPage, label: str, app_token: str, uid: str) -> None:
    try:
        raw_list = []
        try:
            raw_list = page.cookies(all_domains=True)
        except TypeError:
            raw_list = page.cookies()

        names = []
        if isinstance(raw_list, list):
            names = [c.get("name") for c in raw_list if isinstance(c, dict) and c.get("name")]

        cdp_names = []
        try:
            runner = getattr(page, "run_cdp", None) or getattr(page, "_run_cdp", None)
            if runner:
                data = runner(CDP_GET_ALL_COOKIES)
                cdp_names = [c.get("name") for c in data.get("cookies", []) if c.get("name")]
        except Exception:
            cdp_names = []

        summary = (
            f"Cookie 调试({label})\n"
            f"page.cookies: {len(names)}\n"
            f"cdp.cookies: {len(cdp_names)}\n"
            f"names: {', '.join(names[:20])}\n"
            f"cdp: {', '.join(cdp_names[:20])}"
        )
        print("[DEBUG]", summary)
        notifier.push_text("Cookie 调试", summary, app_token, uid)
    except Exception:
        pass


def wechat_login(
    cookie_path: str,
    app_token: str,
    uid: str,
    timeout: int = 120,
) -> Optional[requests.Session]:
    """通过微信扫码登录并持久化 Cookie。"""
    page = None
    try:
        co = ChromiumOptions()
        co.headless(bool(getattr(config, "HEADLESS", True)))
        co.set_argument("--no-sandbox")
        co.set_argument("--disable-gpu")
        co.set_argument("--disable-dev-shm-usage")

        page = ChromiumPage(addr_or_opts=co)
        page.get(config.LOGIN_URL)
        time.sleep(2)

        _fill_credentials(page)

        if not _click_wechat_login(page):
            notifier.push_error("未找到微信登录入口，请检查登录页结构或手动登录。", app_token, uid)
            return None

        time.sleep(2)

        qrcode_path = "data/qrcode.png"
        _capture_qrcode(page, qrcode_path)
        _show_qrcode(qrcode_path)

        notifier.push_qrcode(qrcode_path, app_token, uid)

        return _wait_for_login(page, cookie_path, app_token, uid, timeout)
    finally:
        if page is not None:
            try:
                page.quit()
            except Exception:
                pass
