# 上传 + 投稿中心：完整交接（暂停点）

## 当前目标

本项目是 `E:\自动化\上传+投稿` 下的本地隔离版“上传 + 投稿中心”，在一个窗口中整合 API 投稿和视频上传。

本次交接的状态是：**先暂停，不继续修改程序、不构建、不发布、不执行真实投稿/上传。** 下一会话先按“下一步”核对环境与 Git，再等待用户给出新的明确需求。

绝不修改以下两个原始程序目录：

- `E:\自动化\api投稿2.0`
- `E:\自动化\自动上传\程序`

源码远程仓库：`https://github.com/nmrsz645-bit/shangchuanXtougao.git`，分支 `main`。接手时必须重新执行 `git pull --ff-only`、`git status --short` 与 `git log -1 --oneline` 核对实时状态；不以本文中的历史提交号代替实时状态。

## 下一步：第一条可直接执行的操作

在已有项目目录的 PowerShell 中执行以下命令；它只读取 Git 与交接状态，不启动业务程序：

```powershell
Set-Location 'E:\自动化\上传+投稿'
git pull --ff-only
git status --short
git log -1 --oneline
Get-Content .\README.md
Get-Content .\AGENTS.md
Get-Content .\TIMEOFF.md
Get-Content .\requirements-dev.txt
```

若新电脑还没有源码，先执行：

```powershell
Set-Location 'E:\自动化'
git clone https://github.com/nmrsz645-bit/shangchuanXtougao.git 上传+投稿
```

首次在新电脑运行离线测试前，使用 Python 3.12 或更高版本按 `README.md` 创建 `.venv` 后只需执行一次：

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

## 已完成并验证的内容

- 已完成单窗口整合入口：`投稿中心.py` 加载飞书设置、API 投稿和视频上传；`启动投稿中心.vbs` 可隐藏命令行启动，`.bat` 保留兼容入口。
- 共享飞书设置仍保留 App ID、Secret、投稿表格链接和黏贴表格链接的配置入口；两模块共用 `共享飞书设置.json`。
- 7×24 基础能力已实现：单实例锁、Windows 启动/异常退出重启、可选自动启动任务，以及每天 00:00（或错过后补做）检查并启动已停止任务。
- 投稿方案“自动代理”按每个方案独立运行：每天先使用 40；方案内所有项目当天均达 40 后切换为 83；次日回到 40；关闭时保留当时 40/83。
- 已新增 API 投稿“当前小程序 App ID（留空使用旧规则）”设置。它保存在本机 `API投稿2.0\config\settings.json`；同一电脑的投稿项目共用该值。填写时同时影响模板匹配、两种既有程序链接格式和生成的 `sslocal` 链接；留空继续原规则。
- 本次源码验证已通过：发布安全 7 项、根目录 9 项、API 投稿 67 项、视频上传 62 项，共 145 项；`compileall` 通过。新增的完整流程测试全程使用临时 SQLite 与模拟飞书/巨量接口，不会真实投稿或上传。
- 新电脑源码初始化已补齐 `requirements-dev.txt` 与虚拟环境命令；实际视频上传必须安装正式版 Google Chrome，不能把 Playwright 自带 Chromium 当作替代品。GitHub Actions 的 `.github/workflows/offline-tests.yml` 会在每次推送和拉取请求时自动运行离线测试与语法检查。
- 源码入口 `启动投稿中心.vbs` 会优先使用项目 `.venv`；首次启用每日守护或跨日首次启动，会立即补做一次“停止则重启”检查，之后每 10 秒检查日期是否变化。
- Git 已包含源码、测试和交接文档：`6aabf98` 提交 App ID 功能与初版交接，`2d46cc7` 提交离线流程测试、私有数据保护测试、README、AGENTS 与本交接文件。
- “上传 + 投稿中心”线上正式版本已发布为 **1.0.2**。更新包：`https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com/updates/shang-chuan-tou-gao-zhong-xin/1.0.2/app.zip`，SHA-256：`95C284D9380935B7A935632C0A62C94F7C05BC7FA92432E8CC2509187D3DBE82`。完整包：`https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com/packages/shang-chuan-tou-gao-zhong-xin-1.0.2.zip`，SHA-256：`1F764A1CBD7E7079F084A5EA7A7FE739313D546538AAA787F85E1A971F914434`。
- 1.0.2 发布已完成旧 1.0.0 客户端隔离升级验证：生成 `app.previous`，11 项受保护数据逐字节不变，更新包递归检查为 1,209 个程序文件且不含用户数据、配置、日志或队列；主清单、旧客户端兼容清单和两个下载目录均已公网回读为 1.0.2。

## 未完成事项

- 当前没有获授权的功能修改。接手者不要自行继续开发；先等待用户的新需求。
- 尚未在“全新电脑 + 新的用户配置”上完成真实飞书授权、巨量接口、Chrome 登录、Playwright 和 7×24 计划任务的端到端验收。Git 不包含这些私有运行状态。
- 现有自动化测试为离线回归测试；真实巨量创建单元、飞书读写、Chrome 上传和线上升级不应由测试直接触发。
- 若某台旧 1.0.1 安装包缺少安装根目录 `Start.cmd`，它不会自动检查更新；必须先单独修复启动/更新入口，不能通过直接运行 `app\上传投稿中心.exe` 来验证在线更新。

## 下一位接手者的关键文件与路径

| 用途 | 路径 |
| --- | --- |
| 项目根目录 | `E:\自动化\上传+投稿` |
| 接手约定 | `AGENTS.md` |
| 使用说明 | `README.md` |
| 当前暂停点与交接 | `TIMEOFF.md` |
| 集成入口与 7×24 调度 | `投稿中心.py`、`center_startup.py`、`daily_restart.py`、`start_center.py` |
| 共享飞书设置实现 | `shared_feishu.py` |
| App ID 输入界面 | `API投稿2.0\app\desktop_posting\desktop_app.py` |
| App ID 规则与链接生成 | `API投稿2.0\app\desktop_posting\microapp_link.py` |
| 模板筛选/请求体/投稿执行 | `API投稿2.0\app\desktop_posting\qianchuan_client.py`、`run_once.py` |
| API 设置与状态数据库实现 | `API投稿2.0\app\desktop_posting\settings.py`、`storage.py` |
| API 离线完整流程测试 | `API投稿2.0\tests\test_run_once_integration.py` |
| 交接私有数据保护测试 | `test_handoff_safety.py` |
| 发布候选安全检查与测试 | `release_safety.py`、`test_release_safety.py` |
| GitHub 自动离线验证 | `.github\workflows\offline-tests.yml` |
| 视频上传源码与测试 | `自动上传\src\video_feishu\`、`自动上传\tests\` |
| 正式本地发布版 | `发布版\上传投稿中心\上传投稿中心.exe` |
| 本次本地测试候选（仅历史证据） | `候选发布-20260829-小程序AppID-本地测试\上传投稿中心\上传投稿中心.exe` |

## 运行与验证命令

未经用户明确授权，不运行真实投稿、真实上传、浏览器自动化、构建或在线更新。以下命令均为源码级离线验证：

```powershell
Set-Location 'E:\自动化\上传+投稿'

# 根目录集成、共享设置、Git 私有数据保护、发布候选安全检查
python -m pytest test_center_startup.py test_daily_restart.py test_shared_feishu.py test_handoff_safety.py test_release_safety.py -q

# API 投稿：让 app 包可导入，再运行全部离线测试
$env:PYTHONPATH = 'E:\自动化\上传+投稿\API投稿2.0\app'
python -m pytest API投稿2.0\tests -q

# 视频上传：离线测试
Set-Location 'E:\自动化\上传+投稿\自动上传'
python -m pytest -q

# 语法检查，不执行真实业务
Set-Location 'E:\自动化\上传+投稿'
python -m compileall -q API投稿2.0\app 自动上传\src 投稿中心.py center_startup.py daily_restart.py shared_feishu.py
```

## 已知问题与诊断边界

- `The read operation timed out` 是外部读取超时，不足以单独证明程序崩溃；复现时先保存日志与时间点，再进行只读网络/API 检查。
- `no_task` 表示当前没有可领取的任务，不是崩溃。
- `worker_error: invalid param` 通常来自飞书租户 Token/飞书设置，不应靠修改投稿逻辑猜测修复。
- `没有与该程序链接兼容的项目模板` 表示当前项目模板的 App ID 与投稿链接/已填写的本机 App ID 不一致，或模板不再可用；先检查授权页的 App ID 与巨量模板，勿直接改模板筛选逻辑。
- 线上更新包已经 1.0.2，但“服务器发布”不是对未运行客户端的主动通知；客户端需从安装根目录 `Start.cmd` 进入更新检查。
- 新电脑接手源码时先按 `README.md` 创建 `.venv`、安装 `requirements-dev.txt`（其中已包含 `自动上传[dev]`）；需要真实 Chrome 上传时安装正式版 Google Chrome。用户电脑运行打包程序不需要这些开发依赖。

## 严禁误动、误传、误提交的数据和配置

以下为每台电脑私有运行数据。**不得提交 Git、上传 GitHub、打进更新包、清空、覆盖或用旧副本替换：**

- `共享飞书设置.json`（飞书凭据和表格链接）
- `个人数据\`
- `API投稿2.0\config\`（含 Token 与本机 App ID）
- `API投稿2.0\data\`，尤其 `state.db` 与 `-wal` / `-shm`
- `API投稿2.0\logs\`
- `自动上传\个人数据\`（Chrome 登录资料、Token、队列、统计、日志）
- `发布版\上传投稿中心\个人数据\` 及其 `API投稿2.0` 下的运行配置、数据和日志
- 所有 `program.previous-*` 回滚副本
- 用户新增文件、视频源、上传队列、失败重试记录、浏览器配置与任何未列出的本机私有文件

涉及未来在线更新时，只能替换经审计的程序文件；必须先临时目录校验、比对受保护数据哈希、保留新的 `app.previous`，失败即回滚。没有完整的公网读回和隔离旧客户端升级证据，不得切换或宣称新版本完成。
