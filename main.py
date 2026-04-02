"""智慧树作业提醒主流程。"""

from __future__ import annotations

import argparse
import time
from datetime import datetime

import os

import requests
import schedule

import auth
import cache as cache_module
import config
import crawler
import notifier


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def run_check() -> None:
    try:
        print(f"[{_now_text()}] 开始本轮检查...")

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            }
        )

        cookie_loaded = auth.load_cookie(session, config.COOKIE_FILE)
        if not cookie_loaded or not auth.verify_login(session):
            print("Cookie 无效或不存在，启动微信扫码登录流程...")
            session = auth.wechat_login(
                cookie_path=config.COOKIE_FILE,
                app_token=config.WXPUSHER_APP_TOKEN,
                uid=config.WXPUSHER_UID,
                timeout=config.QRCODE_TIMEOUT_SECONDS,
            )
            if session is None:
                print("扫码超时，本轮结束")
                return

        uuid = auth.get_uuid(session)
        if not uuid:
            notifier.push_error("无法获取用户 uuid，请检查登录状态", config.WXPUSHER_APP_TOKEN, config.WXPUSHER_UID)
            return

        homeworks = crawler.get_all_homeworks(session, uuid)
        print(f"获取到 {len(homeworks)} 项待提交任务")

        cache = cache_module.load_cache(config.CACHE_FILE)
        to_notify = cache_module.filter_new(homeworks, cache)
        print(f"其中 {len(to_notify)} 项需要推送")

        unfinished = [hw for hw in homeworks if not bool(hw.get("is_submitted"))]

        if to_notify:
            notifier.push_homework_list(
                unfinished,
                config.WXPUSHER_APP_TOKEN,
                config.WXPUSHER_UID,
                has_new=True,
                new_count=len(to_notify),
            )
        else:
            notifier.push_homework_list(
                unfinished,
                config.WXPUSHER_APP_TOKEN,
                config.WXPUSHER_UID,
                has_new=False,
                new_count=0,
            )

        updated = cache_module.update_cache(cache, homeworks)
        cache_module.save_cache(updated, config.CACHE_FILE)

        print(f"[{_now_text()}] 本轮检查完成")

    except Exception:
        import traceback

        error_msg = traceback.format_exc()
        print(error_msg)
        notifier.push_error(error_msg[:500], config.WXPUSHER_APP_TOKEN, config.WXPUSHER_UID)


def main() -> None:
    parser = argparse.ArgumentParser(description="智慧树作业提醒脚本")
    parser.add_argument("--once", action="store_true", help="只执行一次后退出")
    parser.add_argument("--force-login", action="store_true", help="强制触发扫码登录流程")
    args = parser.parse_args()

    if args.force_login and os.path.exists(config.COOKIE_FILE):
        os.remove(config.COOKIE_FILE)

    run_check()
    if args.once:
        return

    schedule.every(config.CHECK_INTERVAL_HOURS).hours.do(run_check)
    print(f"定时任务已启动，每 {config.CHECK_INTERVAL_HOURS} 小时执行一次。")

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
