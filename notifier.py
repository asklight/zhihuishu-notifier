"""WxPusher 推送通知模块。"""

from __future__ import annotations

import base64
import io
from datetime import datetime
from pathlib import Path

from wxpusher import WxPusher
from PIL import Image


def _safe_send(content: str, app_token: str, uid: str, content_type: int) -> bool:
    try:
        resp = WxPusher.send_message(content, uids=[uid], token=app_token, content_type=content_type)
        if resp is not None:
            print("[INFO] WxPusher 返回:", resp)
        return True
    except Exception as exc:
        print(f"[ERROR] WxPusher 推送失败: {exc}")
        return False


def push_text(title: str, content: str, app_token: str, uid: str) -> bool:
    """推送 Markdown 文本消息。"""
    message = f"## {title}\n\n{content}" if title else content
    return _safe_send(message, app_token, uid, content_type=3)


def push_image(image_path: str, caption: str, app_token: str, uid: str) -> bool:
    """推送本地图片（HTML）。"""
    try:
        image_bytes = Path(image_path).read_bytes()

        def build_html(encoded: str) -> str:
            return (
                f"<p>{caption}</p>"
                f'<img src="data:image/jpeg;base64,{encoded}" style="max-width:280px"/>'
            )

        encoded = base64.b64encode(image_bytes).decode("utf-8")
        html = build_html(encoded)

        if len(html) > 38000:
            img = Image.open(io.BytesIO(image_bytes))
            max_width = 280
            if img.width > max_width:
                ratio = max_width / img.width
                img = img.resize((max_width, int(img.height * ratio)))

            for quality in (75, 60, 45):
                buffer = io.BytesIO()
                img.convert("RGB").save(buffer, format="JPEG", quality=quality, optimize=True)
                encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
                html = build_html(encoded)
                if len(html) <= 38000:
                    break

        if len(html) > 38000:
            return _safe_send(
                f"{caption}\n二维码图片过大，请改用本地弹窗或缩小截图范围。",
                app_token,
                uid,
                content_type=3,
            )

        return _safe_send(html, app_token, uid, content_type=2)
    except Exception as exc:
        print(f"[ERROR] 图片推送失败: {exc}")
        return False


def push_qrcode(image_path: str, app_token: str, uid: str) -> bool:
    """推送登录二维码。"""
    caption = "⚠️ 智慧树 Cookie 已失效，请在 2 分钟内用微信扫描以下二维码重新登录："
    return push_image(image_path, caption, app_token, uid)


def _deadline_icon(end_time: datetime, now: datetime) -> str:
    days = (end_time - now).total_seconds() / 86400
    if days <= 3:
        return "🔴"
    if days <= 7:
        return "🟡"
    return "🟢"


def _build_homework_header(has_new: bool, total: int, new_count: int = 0) -> list[str]:
    if has_new:
        return [
            "## 📚 智慧树作业提醒",
            f"本次新增 {new_count} 项；当前未完成共 {total} 项。",
            "",
            "---",
            "",
        ]

    return [
        "## 📚 智慧树作业提醒",
        "本次无新增作业（截止时间无变化）。",
        f"以下是仍未完成的作业，共 {total} 项：",
        "",
        "---",
        "",
    ]


def push_homework_list(
    homeworks: list[dict],
    app_token: str,
    uid: str,
    has_new: bool = True,
    new_count: int = 0,
) -> bool:
    """推送作业提醒列表（Markdown）。"""
    if not homeworks:
        return _safe_send("✅ 当前暂无待提交作业", app_token, uid, content_type=3)

    now = datetime.now()
    sorted_items = sorted(homeworks, key=lambda x: x.get("end_time") or datetime.fromtimestamp(0))

    lines = _build_homework_header(has_new, len(sorted_items), new_count=new_count)

    for hw in sorted_items:
        end_time = hw.get("end_time")
        if not isinstance(end_time, datetime):
            continue

        icon = _deadline_icon(end_time, now)
        title = str(hw.get("title") or "").strip()
        course_name = str(hw.get("course_name") or "").strip()
        end_text = end_time.strftime("%Y/%m/%d %H:%M")
        days_left = int((end_time - now).total_seconds() // 86400)

        lines.append(f"{icon} **{title}**")
        lines.append(f"📖 {course_name}")
        lines.append(f"⏰ 截止：{end_text}")

        if int(hw.get("type") or 1) == 1:
            content = str(hw.get("content") or "").strip()
            if content:
                lines.append(f"📝 {content[:100]}")

        lines.append(f"（距截止 {days_left} 天）")
        lines.append("")

    return _safe_send("\n".join(lines), app_token, uid, content_type=3)


def push_login_success(app_token: str, uid: str) -> bool:
    """推送登录成功通知。"""
    return _safe_send("✅ 智慧树微信扫码登录成功，即将为您检查作业列表...", app_token, uid, 3)


def push_login_timeout(app_token: str, uid: str) -> bool:
    """推送二维码超时通知。"""
    return _safe_send("⏱️ 二维码已超时，本轮登录取消。将在下次定时任务时重新尝试。", app_token, uid, 3)


def push_error(message: str, app_token: str, uid: str) -> bool:
    """推送异常通知。"""
    return _safe_send(f"❌ 智慧树通知脚本发生错误：\n{message}", app_token, uid, 3)
