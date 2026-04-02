"""项目配置模块。"""


# WxPusher 配置
# 注册地址：https://wxpusher.zjiecode.com
# 登录后在"我的应用"中创建应用，获取 APP_TOKEN
# 在"关注"页面扫码关注后获取自己的 UID
WXPUSHER_APP_TOKEN = "AT_11111"
WXPUSHER_UID = "UID_11111"

# 定时检查间隔（小时）
CHECK_INTERVAL_HOURS = 0.1

# 扫码等待超时（秒），微信二维码有效期约 2-3 分钟，建议不超过 150
QRCODE_TIMEOUT_SECONDS = 120

# 是否无头模式（本地调试建议 False 以便屏幕扫码）
HEADLESS = False

# 数据文件路径
COOKIE_FILE = "data/cookie.json"
CACHE_FILE = "data/homework_cache.json"

# 智慧树接口（不要修改）
LOGIN_URL = "https://passport.zhihuishu.com/login"
VERIFY_URL = "https://hike-examstu.zhihuishu.com/zhsathome/getLoginUserInfo"
ONLINE_HOME_URL = "https://onlineweb.zhihuishu.com/onlinestuh5"
HOMEWORK_LIST_URL = "https://hike-examstu.zhihuishu.com/zhsathome/homework/findImportantReminderList"
HOMEWORK_DETAIL_URL = "https://onlineservice.zhihuishu.com/gateway/f/v1/student/homework/homeworkDirGet2"
HOMEWORK_STATUS_URL = "https://onlineservice.zhihuishu.com/gateway/f/v1/student/homework/Info"
