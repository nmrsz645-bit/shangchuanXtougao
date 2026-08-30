# 上传 + 投稿中心：交接说明

## 当前目标

维护并继续开发 `E:\自动化\上传+投稿` 中的**本地隔离版**“上传 + 投稿中心”。它把 API 投稿和视频上传放进同一个桌面窗口；不得修改下列两个原程序目录：

- `E:\自动化\api投稿2.0`
- `E:\自动化\自动上传\程序`

当前已完成一项本地验证过的投稿兼容性改动：可在 API 投稿的“授权”页面填写一台电脑共用的“当前小程序 App ID”。该值会用于匹配巨量项目模板和投稿请求；留空时保持原有两种程序链接的 App ID 规则。用户已完成本地实际测试并确认可用，更新程序任务已获授权按既有安全流程处理在线更新；在其交付完整验证结果前，不得自行宣称线上发布完成。

## 下一步：第一条可直接执行的操作

在**下一台电脑**的 PowerShell 中，克隆已交接的源码，然后先阅读本文件和检查 Git 状态；不要立刻运行真实投稿、上传或在线更新：

```powershell
Set-Location 'E:\自动化'
git clone https://github.com/nmrsz645-bit/shangchuanXtougao.git 上传+投稿
Set-Location 'E:\自动化\上传+投稿'
Get-Content .\TIMEOFF.md
git status --short
```

指定远程仓库：`https://github.com/nmrsz645-bit/shangchuanXtougao.git`。

截至本次交接配置：项目根目录已初始化为 Git 仓库，分支为 `main`，远程 `origin` 已指向上述地址。受保护数据不在 Git 内；接手前应再次运行 `git status --short` 和 `git log -1 --oneline`，不要把本文件内的历史提交号当作实时状态。

## 已完成并验证过的内容

以下是此前已完成的功能与当时的验证记录；换电脑、重建环境或再次发布前必须重新运行相关验证，不能把历史结果当作当前机器的实时结果。

- 整合桌面入口：`投稿中心.py` 同时加载 API 投稿和视频上传模块；`启动投稿中心.vbs` 可隐藏命令行窗口启动，`.bat` 为兼容入口。
- 共享飞书设置：`共享飞书设置.json` 供两个模块共同使用，UI 仍保留飞书 App ID 和 Secret 的配置入口。
- 7×24 基础保障：本地单实例锁、Windows 启动/异常退出重启、可选自动启动两个任务，以及每天 00:00 检查并启动已停止任务（错过 00:00 后启动/唤醒也会补做检查）。
- 投稿方案“自动代理”：按**每个方案**独立工作；勾选后每日先用 40，方案内每个项目当天已占用都达到 40 时统一改为 83；次日回到 40。关闭后保留当时的 40/83。新增项目遵循该方案当日阶段。
- 自动代理的历史验证：根目录测试 4 项、API 投稿 63 项、视频上传 62 项，共 129 项通过；`compileall`、Tk 窗口冒烟启动、冻结 EXE 启动冒烟均已在当时环境通过。
- 本次小程序 App ID 功能：授权页新增“当前小程序 App ID（留空使用旧规则）”输入框，保存在既有 `API投稿2.0\\config\\settings.json` 的设置中；同机项目共用该值。程序链接中的启动页、参数、书籍链接生成逻辑没有改变。设置为空时，仍按原有两种链接格式选择旧 App ID。
- 本次源码验证：API 投稿测试 `65 passed`、根目录测试 `4 passed`、`python -m compileall -q API投稿2.0\\app` 通过；本地候选 EXE 启动烟测通过，用户已完成实际本地投稿测试并确认正常。
- 本地测试候选包：`候选发布-20260829-小程序AppID-本地测试\\上传投稿中心\\上传投稿中心.exe`，SHA-256 为 `07ED06FFF2A684CAA7C2B32E56D71D6D267BB9EBD30314BA705197C2F819B99B`。它仅作本次经测试的程序候选来源；其中的运行配置/数据仍属私有数据，不能提交 Git。
- 本地发布版曾以仅替换 `上传投稿中心.exe` 和 `_internal` 的方式安全更新；当时确认 1,163 个运行文件一致，用户数据未变，并保留了 `program.previous-20260819222728` 回滚副本。
- 曾完成 1.0.1 在线更新发布和旧客户端隔离升级验证；若后续涉及在线更新，必须重新读取公开清单、下载包哈希、隔离升级和数据保留结果后才能声明成功。

## 未完成事项

- 在线更新任务已收到正式发布通知，但本文件不把“已通知”视为“已上线”。接手者必须取得其回报的线上版本、公开包/清单哈希、隔离旧客户端升级、受保护数据保留和 `app.previous` 回滚证据后，才能通知其他用户更新。
- 尚未在一台全新电脑验证 Python/Playwright/Chrome、飞书授权、巨量接口、浏览器登录资料或 7×24 计划任务。这些都需要真实的本地用户配置，不能在没有授权的情况下伪造或上传。
- 尚未在新电脑验证 Python/Playwright/Chrome、飞书授权、巨量接口、浏览器登录资料或 7×24 计划任务。这些都需要真实的本地用户配置，不能在没有授权的情况下伪造或上传。
- 当前没有待修复的已确认代码故障。截图中出现过 `The read operation timed out`（外部读取超时）和 `no_task`（暂无任务）；它们不是已确认的程序崩溃。若复现，先保存运行日志和时间点，再做只读网络/API 检查。

## 关键文件与路径

| 用途 | 路径 |
| --- | --- |
| 集成程序根目录 | `E:\自动化\上传+投稿` |
| 集成入口和 7×24 调度 | `投稿中心.py`、`center_startup.py`、`daily_restart.py`、`start_center.py` |
| 隐藏黑框启动入口 | `启动投稿中心.vbs` |
| 共享飞书设置实现 | `shared_feishu.py` |
| 投稿桌面 UI 与小程序 App ID 输入 | `API投稿2.0\app\desktop_posting\desktop_app.py` |
| 小程序 App ID 规则与链接生成 | `API投稿2.0\app\desktop_posting\microapp_link.py` |
| 模板筛选和投稿请求体 | `API投稿2.0\app\desktop_posting\qianchuan_client.py`、`run_once.py` |
| API 投稿设置持久化 | `API投稿2.0\app\desktop_posting\settings.py` |
| 投稿 SQLite 存储 | `API投稿2.0\app\desktop_posting\storage.py` |
| API 投稿测试 | `API投稿2.0\tests\` |
| 视频上传源码与测试 | `自动上传\src\video_feishu\`、`自动上传\tests\` |
| 视频上传依赖声明 | `自动上传\pyproject.toml` |
| 正式本地发布版 | `发布版\上传投稿中心\上传投稿中心.exe` |
| 回滚副本 | `发布版\上传投稿中心\program.previous-20260819143406`、`program.previous-20260819222728` |
| 历史候选/验收/构建目录 | `候选发布-*`、`验收-*`、`build-*`；仅作历史证据，不能作为新的发布源 |

## 运行与验证命令

不要在没有用户授权时启动真实投稿、上传、浏览器自动化或在线更新。以下是源码级的测试命令；需先在新电脑安装与项目匹配的 Python 和依赖，并在项目根目录执行：

```powershell
Set-Location 'E:\自动化\上传+投稿'

# 根目录的集成启动与共享设置测试
python -m pytest test_center_startup.py test_daily_restart.py test_shared_feishu.py -q

# API 投稿模块测试（必须让 app 包可被导入）
$env:PYTHONPATH = 'E:\自动化\上传+投稿\API投稿2.0\app'
python -m pytest API投稿2.0\tests -q

# API 投稿源码语法检查（不触发真实业务）
python -m compileall -q API投稿2.0\app

# 视频上传模块测试：先按 pyproject.toml 安装其 dev 依赖
Set-Location 'E:\自动化\上传+投稿\自动上传'
python -m pytest -q

# 仅做语法编译检查，不执行实际业务
Set-Location 'E:\自动化\上传+投稿'
python -m compileall 投稿中心.py center_startup.py daily_restart.py shared_feishu.py API投稿2.0\app 自动上传\src
```

本地运行请双击 `E:\自动化\上传+投稿\启动投稿中心.vbs`。视频自动上传需要本机安装 Google Chrome 并由用户完成登录；冻结 EXE 不包含 Chrome。

## 严禁误动、误传或误提交的数据

以下内容是每台电脑的私有运行数据；**不得提交 Git、上传 GitHub、打进在线更新包、清空、覆盖或拿旧副本替换**：

- `共享飞书设置.json`（含飞书凭据）
- `个人数据\`
- `API投稿2.0\config\`
- `API投稿2.0\data\`，尤其 `state.db` 及其 `-wal` / `-shm`
- `API投稿2.0\logs\`
- `自动上传\个人数据\`（Chrome 登录资料、Token、队列、统计、日志等）
- `发布版\上传投稿中心\个人数据\`
- `发布版\上传投稿中心\API投稿2.0\` 下的运行配置与数据
- 所有 `program.previous-*` 回滚副本
- 用户新增的文件、视频源文件、上传队列、失败重试记录和浏览器配置

在线更新时只能替换程序文件（EXE 和经审计的 `_internal`）；先做独立临时目录校验、受保护数据哈希比对、生成新的 `app.previous`，失败必须回滚。只有公开下载包、清单和哈希均可读，且隔离旧客户端真实升级通过后，才可切换线上 `latest.json` / `catalog.json`。

## 接手前的最小检查清单

1. 阅读本文件、`README.md`、`AGENTS.md`，并先确认当前提交、Git 状态和远程地址均与本文件一致。
2. 在新电脑执行上方第一步；确认 `git status --short` 无输出、`git remote -v` 指向指定仓库，并核对本文件的描述。
3. 新电脑必须由用户自行填写飞书配置、完成 Chrome 登录；不要从 Git 或聊天记录恢复 Secret、Token、Cookie。
4. 对任何新功能先运行相关单元测试，再进行不触发真实投稿/上传的 UI 冒烟验证；涉及发布时按受保护数据、回滚和隔离升级流程完整验证。
