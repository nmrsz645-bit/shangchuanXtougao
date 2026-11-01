# Codex 维护交接：上传 + 投稿中心 1.0.17

## 先读与版本边界

- 用户操作先读 README.md；维护先读本文件和 AGENTS.md，再打开任务涉及的模块。
- 跨电脑安装、实际构建命令、两处正式 JSON、OSS key、网站卡片/catalog、验收与回滚统一维护在 [docs/RELEASE-GUIDE.md](https://github.com/nmrsz645-bit/shangchuanXtougao/blob/main/docs/RELEASE-GUIDE.md)；生产操作须另有对应授权。
- 产品版本来自 `API投稿2.0/version.json`，当前为 **1.0.17**；上传子模块 pyproject 的 0.1.0 是内部包版本，不能据此判断产品版本。
- 仓库：`https://github.com/nmrsz645-bit/shangchuanXtougao`，正式分支 `main`。
- 上传完成/IAA 修复源码基线：`a0ada8ea1a6637aad4c98febd713addc53683380`。
- 2026-10-31 GitHub 维护发行仍为 1.0.17：清空新用户预填账号、完善构建和文档；准确发行提交由不可变 `v1.0.17` 标签与包内 `BUILD-INFO.json.sourceCommit` 给出。
- 不把此维护发行误称为 OSS 自动更新版本的新发布。OSS 2026-10-28 包和清单没有被本轮替换，二者字节/散列不同。

<a id="new-codex"></a>

## 另一台电脑的 Codex 从这里接手

2026-11-01 文档交接：目标是让另一台 Windows 电脑取得可维护源码、构建入口和发布方法；这次不发布新程序，不迁移真实任务或登录态。新电脑路径自选，以当地 `git rev-parse --show-toplevel` 为准，不依赖原电脑盘符或聊天历史。

1. 按 [RELEASE-GUIDE 第0—2节](https://github.com/nmrsz645-bit/shangchuanXtougao/blob/main/docs/RELEASE-GUIDE.md) 取得 main；已有目录先看 Git 状态/远端，不覆盖、重置或重复克隆。
2. 阅读本文件、AGENTS.md、发布指南；按下方模块表进入源码，不把历史备份分支当正式开发源。
3. 核对 Windows/Python/Chrome/依赖，复用合格的本机环境，缺少时在新目录创建虚拟环境；按接手任务需要运行明确的离线测试，不覆盖已有环境。旧电脑的通过记录不能代替新电脑验收。
4. 核对源码启动器、整合版 spec、组包脚本与更新器依赖；GUI 会读取保存的自动任务，先确认无真实配置。真实上传/投稿/写表、数据迁移、程序发布分别按用户当次授权执行。
5. 报告源码绝对路径、完整 HEAD/分支/远端、改动、解释器、已做验证与缺项，再按用户指定任务继续；不能仅凭下载成功或文档齐全声称真实业务已跑通。

| 需要接手的成果 | 获取位置与用途 |
| --- | --- |
| 当前维护源码、测试、构建脚本与最新文档 | 本仓库 `main`；接手时重新核对远端 HEAD。此次文档交接前基准为 `a142a7347115f71cd4a9d87e6da46214355a6148`。 |
| 可运行的 GitHub 完整包、源码快照、构建信息、验收及散列 | [v1.0.17 Release](https://github.com/nmrsz645-bit/shangchuanXtougao/releases/tag/v1.0.17)；标签提交 `6071b4f6a640e3b27b78e302cff6a33fbeb57e6d`。维护构建需 clone，不能只拿无 .git 的源码 ZIP。 |
| 历史发布/隔离升级/包内代码审计辅助脚本 | [backup/existing-safe-20261031](https://github.com/nmrsz645-bit/shangchuanXtougao/tree/c5ccaa2d4c0a805a50aa4b4879133fb114e9b819/backups/existing-safe-20261031)，提交 `c5ccaa2d4c0a805a50aa4b4879133fb114e9b819`；有 README、MANIFEST 和 SHA256，不在 main，也不是新增产品功能。 |
| 客户端实际接收的程序更新 | OSS 两份正式 JSON 指向的包，详见发布指南；GitHub 维护包不会自动进入该通道。 |

## 用途与架构

Tkinter 整合壳嵌入两个 Python 模块。飞书共享配置由壳写入，各模块保留自己的任务状态。
API 模块通过 urllib 调用飞书/千川接口；上传模块用 Playwright 控制正式版 Google Chrome。
本机持久数据与源码分离。没有服务端数据库或必须复制的私人配置，干净克隆可以安装依赖并离线测试。

素材准备链路：`app.py → service.py::TaskService.preview/execute`。预览按视频 stem 精确匹配复制表；执行会移动符合处理条件的文件，并为匹配项追加飞书，不直接启动浏览器上传。

自动上传另行启动：`app.py → automation.py → uploader.py`，成功/失败通过 app 回调写 `tracking.py`。上传 100% 后仍需面板“确定”、可能出现的 IAA“确认”和入库核验；IAA 只在零选中/非半选状态点唯一确认并等待关闭。平台回执按内容 MD5、大小和目标账号关联素材 ID，再到该账号核验；改名后的重复内容可能复用旧素材 ID，不能只用新文件名搜索结果判失败。**`automation.py` 会删除已核验成功的目标视频，前序源文件已移动，程序不会另留原片副本；真实运行前应按用户授权保留独立媒体备份。**

API 编排链路：`desktop_app.py → worker.py → run_once.py`；`run_once.py` 使用 `queue_service.py/feishu_queue.py` 领取任务，`posting_service.py` 解析/选择素材，`qianchuan_client.py` 查询项目与创建投稿，`feishu_client.py/storage.py` 回写和保存状态。素材上传、API 投稿、软件发布是三条不同流程，授权和故障证据分别核对。

| 路径 | 作用/修改入口 |
| --- | --- |
| `投稿中心.py` | 主界面、版本读取、共享设置与启动/重启协调；冻结后以 EXE 同级目录为 ROOT。 |
| `start_center.py`、`启动投稿中心.vbs/.bat` | 源码开发启动入口。 |
| `shared_feishu.py`、`center_startup.py`、`daily_restart.py` | 共享设置、Windows 开机启动和每日检查。 |
| `API投稿2.0/app/desktop_posting/desktop_app.py` | 授权、项目、方案与运行状态界面。 |
| 同目录 `settings.py`、`storage.py` | 本地 JSON 配置、SQLite `data/state.db` 及状态表。 |
| `feishu_queue.py`、`feishu_client.py` | 飞书表头、领取、回写和接口。 |
| `run_once.py`、`queue_service.py` | API 核心业务编排、项目/素材选择、创建投稿，以及任务领取复核/失败释放；定位单次投稿行为先读这里。 |
| `qianchuan_client.py`、`posting_service.py`、`worker.py` | 授权刷新、接口投稿、工作循环与失败恢复。 |
| `自动上传/src/video_feishu/config.py`、`app.py` | 上传配置、keyring、界面协调与自动循环。 |
| `service.py`、`feishu.py`、`video_ops.py` | 扫描匹配、读取复制表、移动与写表。 |
| `uploader.py` | 浏览器上传、进度/结果识别、可选 IAA 确认、平台回执及素材核验。 |
| `automation.py`、`tracking.py` | 上传任务调度、队列、账本与每日统计。 |
| `上传投稿中心.spec` | 完整整合版 PyInstaller 入口。 |
| `release/Start.cmd`、`API投稿2.0/Start-App.cmd` | 发行包根更新入口与 app 层 ASCII 启动器。 |
| `release/build_github_package.py`、`release_safety.py` | 新构建组包与数据/入口/版本校验。 |

## 环境与依赖

- 已有构建环境为 Windows x64、Python **3.13.15**；程序依赖 Tkinter、sqlite3、urllib 标准库。
- Playwright **1.62.0**、keyring **25.7.0**、pytest **8.4.2**、PyInstaller **6.22.2**、setuptools **84.0.0**。
- `requirements-build-windows.txt` 固定以上直接构建依赖并引用 `requirements-dev.txt`；后者安装上传模块 editable 及测试依赖。它不是所有传递依赖的完整 lockfile。
- Python 项目要求至少 3.12；本发行包包含 python313.dll，重建本版使用 3.13 x64。正式版 Google Chrome 是外部运行依赖，不运行浏览器下载命令。
- 更新器 `UpdateAgent.exe` 是既有外部二进制依赖，SHA256 `68721ebefcdebbe7b4133424d9e432bcfa0372f7a015ecf54d5aeeb5a6493316`。**本仓库不包含其源码**；不要声称可以从本仓库重新编译更新器。所有本项目 Python 产品源码、测试、spec 与启动器已纳入 Git。

## 开发启动与验证

在干净、无业务配置的维护目录执行：

```powershell
git clone https://github.com/nmrsz645-bit/shangchuanXtougao.git
Set-Location shangchuanXtougao
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build-windows.txt
.\.venv\Scripts\python.exe -B -m pytest -q -p no:cacheprovider test_center_startup.py test_daily_restart.py test_shared_feishu.py test_handoff_safety.py test_release_safety.py test_github_package.py API投稿2.0/tests 自动上传/tests
.\.venv\Scripts\python.exe -B run_api_tests.py
```

开发 GUI：`.\.venv\Scripts\python.exe 投稿中心.py`；它会加载已有设置，只有确认隔离/无自动任务或取得授权后才能启动。
CI `.github/workflows/offline-tests.yml` 运行 Windows/Ubuntu Python 3.13 离线测试；push 仅触发测试，不部署 OSS、下载站或真实业务。
显式列出测试路径可避免递归收集本机保留的候选源码副本。2026-10-31 Windows 本地完整回归为 **304 passed in 21.50s**。构建、CI、审查与公网回读结果另见 GitHub Release 验收说明，不把旧记录当作未来修改后的通过证据。

## 安全配置模板与数据位置

`examples/shared-feishu.example.json` 对应壳的 `共享飞书设置.json`；`api-settings.example.json` 对应 API 的 `config/settings.json`；`upload-settings.example.json` 对应上传模块 `个人数据/settings.json`。
示例为空值，不含账号、token 或可用 Secret。用户通过 GUI 保存实际配置，不自动复制示例覆盖已有文件。
飞书凭证由自己的企业自建应用取得；千川凭证/回调由自己的开放平台应用及本人授权取得；表格链接、小程序 App ID、素材库广告账号均由各自后台核对。具体步骤见 README“首次配置”。
不得伪造授权回调，不提交回调链接、tokens.json、真实 .env 或浏览器 Cookie。上传 Secret 使用 keyring；壳/API 还会保存本机 JSON 凭证，应限制访问。
源码数据：根共享设置、`API投稿2.0/config,data,logs`、`自动上传/个人数据`；冻结程序数据位于 `app/` 对应目录，上传默认 `app/个人数据`。`AUTO_UPLOAD_DATA_DIR` 只重定向上传模块。
这些都是用户数据：不清空、不打包、不读其凭证做发布验证。修改/迁移前保护原文件、SQLite 及 WAL/SHM、媒体、队列、浏览器资料和回滚目录。

## 完整 Windows 构建

只使用全新输出目录，不能对用户安装运行。先从本项目已验证完整包取得 `updater/UpdateAgent.exe`，上述散列不符则停止；不要从未知来源下载同名 EXE。

```powershell
$python = Join-Path $PWD '.venv\Scripts\python.exe'
& $python -m PyInstaller --clean --noconfirm --distpath '候选发布-local/dist' --workpath '候选发布-local/build' '上传投稿中心.spec'
& $python -B -m release.build_github_package --app-dist '候选发布-local/dist/上传投稿中心' --updater '依赖包/updater/UpdateAgent.exe' --destination '候选发布-local/assembled' --source-commit (git rev-parse HEAD)
```

`--destination` 必须不存在；脚本不覆盖已存在候选。输出完整 ZIP、供离线审计的 app ZIP、干净 package 目录。完整包携带 README、HANDOFF、示例和 BUILD-INFO。
脚本先验证准确 HEAD、冻结模块与已提交源码完全一致（仅忽略代码文件名），并核对同级 `build/上传投稿中心/COLLECT-00.toc` 的全部冻结文件散列，再组包。不要移动 dist 离开配套 build 目录后组包。
脚本固定更新器散列，递归检查 runtime 数据，写产品版本/启动器并核对归档布局；README/HANDOFF 不含本地历史聊天。
`build_release_candidate.py` 是旧“已有基线组包”工具，**不会重新编译 EXE**；不能只给旧包改版本号宣称完成新构建。
`API投稿2.0/scripts/build_exe.ps1` 只构建旧独立 API 工具，也不是整合版构建入口。
新程序包发布前应比较冻结模块与源码，检查依赖、归档全部文件及敏感数据，实际验证来源提交。

## 发布与更新方法

本节是概要；可执行参数与本产品对象以 [RELEASE-GUIDE](https://github.com/nmrsz645-bit/shangchuanXtougao/blob/main/docs/RELEASE-GUIDE.md) 为统一入口。GitHub 1.0.17 标签仍固定在程序发行提交，后续纯文档提交不会重新发布程序。

1. 核对 Git status、远端分支及现有 Release；不覆盖他人变更、旧 tag 或旧资产。
2. 当前源码与全部可达 Git 历史做凭证扫描；扫描日志脱敏。检查本地路径、用户数据、测试资料，不把未命中等同于绝对无风险。
3. 完整离线回归、全新构建、包内白名单和散列检查、独立审查；修复阻断后再提交。
4. 只暂存授权文件，正常 push；等待 Offline tests。固定 tag 到准确 commit。
5. GitHub Release 传独立命名完整包、README、HANDOFF、BUILD-INFO 与 SHA256SUMS；下载回读核对 SHA256 和包内版本/提交。
6. GitHub 发布完成后，客户端仍走原 OSS 地址；要让用户收到新程序，须按发布指南第5节另做经授权的 OSS 发布和旧版升级验收。本次交接仅更新文档，未执行任何程序发布。

既有 root Start.cmd 使用相对配置参数，先 `pushd` 到安装根目录，再同步运行更新器；绝对配置参数曾导致静默跳过更新。
线上旧更新器固定读取 `updates/shang-chuan-tou-gao-zhong-xin/1.0.0/latest.json`；该目录名不是当前产品版本。
未来经授权切换 OSS 时必须先不可变 ZIP 和公网 SHA256，再 HTTPS 候选隔离升级/数据保留，再两处正式 JSON 与 latest.js，最后下载站与旧版正式升级核验。
更新器只接受 HTTPS。保持原数据和回滚目录，不用实际客户安装验证。不得把 HTTP 200、已 push、网站文字或本地包视为完整发布成功。

## 已完成、已知问题和后续入口

- 1.0.17 已修复上传面板快速 100% 状态识别、平台确认回执、重命名重复素材核验、可选 IAA 真实容器识别和 EXE 同级版本优先读取。
- IAA 仅在出现时、零选中/非半选状态点击唯一确认，等待弹窗关闭；不操作 checkbox，查询期间继续检查延迟弹窗。
- 既往三条独立自制素材真实上传已核验成功，但没有触发 IAA。IAA 验证来自实际网站组件的离线集成，**线上完整弹窗路径仍未现场验证**；勿宣称每种线上情况都成功。
- 飞书复制表重复“书名”表头仍取第一列，去空格后可能误取日期；文件名精确匹配，见 `feishu.py::source_rows_by_last_book`。当前只记录限制，不擅改业务表。
- 平台回执信息部分仅在内存，进程在成功记录前中断可能重试重复内容；需要持久化回执/幂等改进时从 uploader 与 automation/tracking 的边界入手。
- 混合成功/失败批次回执采用保守策略，尚无线上混合批完整验收；不要只延长超时或无限重试掩盖问题。
- Git 历史扫描未发现凭证；历史旧源码包含过默认业务账号地址（不是认证 Secret），本轮从当前源码和新包移除，不强推重写历史。
- 未执行本轮真实投稿、飞书写入或真实上传。下一次线上验证需明确目标账号、隔离素材和授权，保留可审计结果，不能启动用户真实自动队列试错。
- 新电脑可公开取得的验收证据为 Release 的 [VERIFICATION.json](https://github.com/nmrsz645-bit/shangchuanXtougao/releases/download/v1.0.17/VERIFICATION.json)：记录 2026-10-31 的 304 项离线测试、构建与隔离 GUI；不是新电脑或新改动的验收结果。历史备份脚本的本机依赖路径已替换为占位路径，须先读其说明；HTTP 回环实验不是正式升级验收方法。
