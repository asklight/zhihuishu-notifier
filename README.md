# zhihuishu-notifier

智慧树待提交任务提醒脚本（Python）。

核心能力：
- 自动检查“待提交任务”（作业/考试）
- 微信扫码登录（登录态持久化）
- 使用 WxPusher 推送提醒
- 本地缓存去重，避免重复提醒
- 定时巡检（`schedule`）

---

## 1. 功能概览

本项目用于定时检查智慧树待提交任务，并通过 WxPusher 推送到微信。

主要特性：
- Cookie 优先复用：减少重复登录
- Cookie 失效后自动触发扫码流程
- 扫码成功后保存 Cookie 到本地文件
- 自动去重：已缓存且截止时间未变化不会重复算“新任务”
- 推送策略：
  - 有新增时：推送“新增数量 + 当前未完成总数 + 未完成列表”
  - 无新增时：推送“无新增 + 当前未完成列表”
- 详情接口异常（如 404）时自动降级，不中断主流程

---

## 2. 项目结构

- main.py：主流程入口与定时调度
- auth.py：登录、Cookie 持久化、登录态校验
- crawler.py：待提交列表爬取与标准化
- cache.py：缓存读写、筛选新增、清理历史
- notifier.py：WxPusher 推送封装
- config.py：项目配置
- requirements.txt：依赖清单
- test.py：WxPusher 测试脚本
- data/cookie.json：登录 Cookie 存储
- data/homework_cache.json：作业缓存

---

## 3. 运行环境

建议：
- Python 3.10+
- Windows / Linux（Linux 需可用 Chrome/Chromium）

依赖：见 requirements.txt

---

## 4. 安装与初始化

### 4.1 创建虚拟环境（推荐）

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux/macOS：

```bash
python -m venv .venv
source .venv/bin/activate
```

### 4.2 安装依赖

```bash
pip install -r requirements.txt
```

---

## 5. 配置说明（config.py）

请先编辑 config.py：

- `WXPUSHER_APP_TOKEN`：你的应用 Token
- `WXPUSHER_UID`：接收者 UID
- `CHECK_INTERVAL_HOURS`：定时检查间隔（小时）
- `QRCODE_TIMEOUT_SECONDS`：扫码等待超时（秒）
- `HEADLESS`：是否无头模式
  - 本地调试建议 `False`
  - 服务器建议 `True`

数据文件路径：
- `COOKIE_FILE = "data/cookie.json"`
- `CACHE_FILE = "data/homework_cache.json"`

> 安全建议：不要把真实 Token 提交到公开仓库。

---

## 6. 如何运行

### 6.1 正常运行（启动后会定时执行）

```bash
python main.py
```

### 6.2 只执行一次（调试）

```bash
python main.py --once
```

### 6.3 强制重新登录（忽略旧 Cookie）

```bash
python main.py --force-login
```

---

## 7. 推送逻辑（当前实现）

每轮任务流程：
1. 读取本地 Cookie
2. 校验登录态
3. 失效则扫码登录并保存 Cookie
4. 拉取待提交任务列表
5. 通过缓存判断新增任务（新 ID 或截止时间变化）
6. 推送消息
7. 更新缓存

推送内容规则：
- 若有新增：
  - 标题显示“本次新增 X 项；当前未完成共 Y 项”
  - 正文仍展示全部未完成任务
- 若无新增：
  - 显示“本次无新增作业（截止时间无变化）”
  - 正文展示全部未完成任务

---

## 8. 常见日志与解释

### 8.1 `详情/状态接口 404`

示例：
- `homeworkDirGet2 ... 404`
- `homework/Info ... 404`

含义：
- 通常不是登录失败
- 是该任务在详情接口不可用或路由不匹配
- 程序会自动降级为“仅使用列表数据”，主流程继续

### 8.2 `获取到 N 项待提交任务，其中 0 项需要推送`

含义：
- 缓存中已存在这些任务，且截止时间没有变化
- 属于正常行为

### 8.3 扫码成功但超时

如果出现：
- 浏览器看起来已登录，但脚本判断超时

建议：
- 保持 `HEADLESS=False` 先本地调试
- 确认能进入在线学习页面（onlinestuh5）
- 检查 data/cookie.json 是否写入

---

## 9. 服务器部署建议

### 9.1 上传哪些文件

建议上传：
- main.py / auth.py / crawler.py / cache.py / notifier.py / config.py
- requirements.txt
- data/cookie.json（可选，首次可为空 `{}`）
- data/homework_cache.json（可保留历史，避免重复推送）

不要上传：
- `.venv`/`venv`
- `__pycache__`
- IDE 配置目录
- 临时截图

### 9.2 Linux 建议

- 安装 Chrome/Chromium
- `HEADLESS=True`
- 若首次登录需扫码，建议先在可见环境完成并保存 Cookie

### 9.3 进程守护

可使用：
- systemd
- supervisor
- pm2（运行 Python 也可）

---

## 10. 本地测试

### 10.1 测试 WxPusher

```bash
python test.py
```

### 10.2 清空缓存，强制观察“新增推送”

将 data/homework_cache.json 改为：

```json
{}
```

然后运行：

```bash
python main.py --once
```

---

## 11. 风险与注意事项

- 站点登录策略可能变化，扫码流程属于平台侧行为
- 请合理设置检查频率，避免过高频访问
- 妥善保管 Token/Cookie，不要公开泄露

---

## 12. 许可证
MIT License

Copyright (c) <YEAR> <COPYRIGHT HOLDER>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
MIT

---

## 13. 维护建议

后续可优化方向：
- 将 config.py 改为环境变量加载（更安全）
- 增加结构化日志（如 `logging` + 文件轮转）
- 增加 Dockerfile 与 systemd 示例
- 增加接口可用性探测与自动降级策略配置
