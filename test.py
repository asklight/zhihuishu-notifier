"""WxPusher 测试脚本。"""

import config
import notifier


def main() -> None:
	ok = notifier.push_text(
		title="WxPusher 测试",
		content="如果看到这条消息，说明推送成功。",
		app_token=config.WXPUSHER_APP_TOKEN,
		uid=config.WXPUSHER_UID,
	)
	print("推送结果:", ok)


if __name__ == "__main__":
	main()