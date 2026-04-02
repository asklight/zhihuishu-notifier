"""智慧树待提交任务爬取模块。"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

import config


PENDING_LIST_URL = config.HOMEWORK_LIST_URL
HOMEWORK_DETAIL_URL = config.HOMEWORK_DETAIL_URL
HOMEWORK_STATUS_URL = config.HOMEWORK_STATUS_URL


def _utc_iso_now() -> str:
    """返回 UTC ISO8601 时间字符串（带毫秒和 Z 后缀）。"""
    now = datetime.now(timezone.utc)
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def _ms_to_local_datetime(ms: int | float | None) -> datetime:
    """毫秒时间戳转本地时区 datetime（naive）。"""
    if ms is None:
        return datetime.fromtimestamp(0)
    return datetime.fromtimestamp(float(ms) / 1000)


def _clean_html_text(html: str) -> str:
    """HTML 转纯文本并截断。"""
    text = BeautifulSoup(html or "", "lxml").get_text(separator="\n").strip()
    return text[:300]


def _safe_get_json(session: requests.Session, url: str, params: dict, hint: str) -> dict | None:
    """统一 GET JSON 请求，失败打印告警并返回 None。"""
    try:
        resp = session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "200":
            print(f"[WARN] {hint} 接口返回非成功状态: {data.get('status')}")
            return None
        return data
    except Exception as exc:
        print(f"[WARN] {hint} 请求失败: {exc}")
        return None


def get_pending_list(session: requests.Session, uuid: str) -> list[dict]:
    """返回去重后的待提交作业列表，每项包含 id、title、courseId、courseName、type、endTime。"""
    data = _safe_get_json(
        session,
        PENDING_LIST_URL,
        params={"uuid": uuid, "date": _utc_iso_now()},
        hint="待提交列表",
    )
    if not data:
        return []

    items = data.get("rt") or []
    dedup: dict[tuple[int, int], dict] = {}

    for item in items:
        try:
            item_type = int(item.get("type", 0))
            item_id = int(item.get("id", 0))
        except Exception:
            continue

        if item_id <= 0 or item_type not in (1, 2):
            continue

        key = (item_type, item_id)
        if key in dedup:
            continue

        dedup[key] = {
            "id": item_id,
            "title": str(item.get("title") or "").strip(),
            "courseId": int(item.get("courseId") or 0),
            "courseName": str(item.get("courseName") or "").strip(),
            "type": item_type,
            "endTime": item.get("endTime"),
            "score": float(item.get("score") or 0.0),
        }

    return list(dedup.values())


def get_homework_detail(session: requests.Session, homework_id: int) -> dict | None:
    """获取单个作业详情，失败返回 None。"""
    data = _safe_get_json(
        session,
        HOMEWORK_DETAIL_URL,
        params={"homeworkId": homework_id},
        hint=f"作业详情(homeworkId={homework_id})",
    )
    if not data:
        return None

    rt = data.get("rt") or {}
    return {
        "content": _clean_html_text(str(rt.get("content") or "")),
        "score": float(rt.get("score") or 0.0),
        "createUserName": str(rt.get("createUserName") or "").strip(),
        "isDelay": int(rt.get("isDelay") or 0),
        "endTime": rt.get("endTime"),
    }


def get_homework_status(session: requests.Session, homework_id: int) -> dict | None:
    """获取单个作业提交状态，失败返回 None。"""
    data = _safe_get_json(
        session,
        HOMEWORK_STATUS_URL,
        params={"homeworkId": homework_id, "isDoHomework": 0},
        hint=f"作业状态(homeworkId={homework_id})",
    )
    if not data:
        return None

    rt = data.get("rt") or {}
    return {
        "isComplete": str(rt.get("isComplete") or "0"),
        "submitDate": rt.get("submitDate"),
    }


def _build_homework_item(item: dict, detail: dict, status: dict) -> dict:
    end_ms = detail.get("endTime") or item.get("endTime")
    return {
        "homework_id": int(item.get("id", 0)),
        "course_id": int(item.get("courseId") or 0),
        "course_name": str(item.get("courseName") or ""),
        "title": str(item.get("title") or ""),
        "content": str(detail.get("content") or ""),
        "end_time": _ms_to_local_datetime(end_ms),
        "score": float(detail.get("score") or 0.0),
        "teacher": str(detail.get("createUserName") or ""),
        "is_submitted": str(status.get("isComplete") or "0") == "1",
        "type": 1,
        "type_label": "作业",
    }


def _build_exam_item(item: dict) -> dict:
    return {
        "homework_id": int(item.get("id", 0)),
        "course_id": int(item.get("courseId") or 0),
        "course_name": str(item.get("courseName") or ""),
        "title": str(item.get("title") or ""),
        "content": "",
        "end_time": _ms_to_local_datetime(item.get("endTime")),
        "score": float(item.get("score") or 0.0),
        "teacher": "",
        "is_submitted": False,
        "type": 2,
        "type_label": "考试",
    }


def get_all_homeworks(session: requests.Session, uuid: str) -> list[dict]:
    """获取全部待提交任务并标准化输出。"""
    pending = get_pending_list(session, uuid)
    result: list[dict] = []

    for item in pending:
        homework_id = int(item.get("id", 0))
        item_type = int(item.get("type", 0))

        if item_type == 1:
            detail = get_homework_detail(session, homework_id)
            time.sleep(0.5)
            status = get_homework_status(session, homework_id)
            time.sleep(0.5)

            if not detail or not status:
                print(f"[WARN] 作业 homeworkId={homework_id} 详情或状态获取失败，使用列表数据降级")
                result.append(
                    {
                        "homework_id": homework_id,
                        "course_id": int(item.get("courseId") or 0),
                        "course_name": str(item.get("courseName") or ""),
                        "title": str(item.get("title") or ""),
                        "content": "",
                        "end_time": _ms_to_local_datetime(item.get("endTime")),
                        "score": float(item.get("score") or 0.0),
                        "teacher": "",
                        "is_submitted": False,
                        "type": 1,
                        "type_label": "作业",
                    }
                )
                continue

            result.append(_build_homework_item(item, detail, status))
        elif item_type == 2:
            result.append(_build_exam_item(item))
            time.sleep(0.5)

    return sorted(result, key=lambda x: x.get("end_time") or datetime.fromtimestamp(0))
