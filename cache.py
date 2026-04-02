"""待提交任务缓存模块。"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta


def load_cache(path: str) -> dict:
    """读取缓存文件，不存在或解析失败返回空字典。"""
    if not os.path.exists(path):
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cache(cache: dict, path: str) -> None:
    """保存缓存到 JSON 文件。"""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


def filter_new(homeworks: list[dict], cache: dict) -> list[dict]:
    """筛选需要通知的任务：新任务或截止时间发生变化。"""
    to_notify: list[dict] = []

    for hw in homeworks:
        if hw.get("is_submitted"):
            continue
        key = f"hw_{hw.get('homework_id')}"
        end_time = hw.get("end_time")
        if isinstance(end_time, datetime):
            end_time_iso = end_time.isoformat()
        else:
            end_time_iso = str(end_time)

        old = cache.get(key)
        if not old:
            to_notify.append(hw)
            continue

        if old.get("end_time") != end_time_iso:
            to_notify.append(hw)

    return to_notify


def update_cache(cache: dict, homeworks: list[dict]) -> dict:
    """更新缓存并清理过期数据。"""
    now = datetime.now()

    for hw in homeworks:
        key = f"hw_{hw.get('homework_id')}"
        end_time = hw.get("end_time")
        if isinstance(end_time, datetime):
            end_time_iso = end_time.isoformat()
        else:
            end_time_iso = str(end_time)

        cache[key] = {
            "title": str(hw.get("title") or ""),
            "end_time": end_time_iso,
            "notified_at": now.isoformat(),
            "type": int(hw.get("type") or 1),
        }

    expire_before = now - timedelta(days=7)
    remove_keys: list[str] = []

    for key, value in cache.items():
        try:
            end_dt = datetime.fromisoformat(str(value.get("end_time")))
            if end_dt < expire_before:
                remove_keys.append(key)
        except Exception:
            remove_keys.append(key)

    for key in remove_keys:
        cache.pop(key, None)

    return cache
