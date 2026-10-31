# 新 Windows 电脑接手、程序更新与网站发布指南

核对日期：2026-10-31。产品当前版本 **1.0.17**；本次仅补文档，下面涉及生产上传、Release 和网站的步骤均为**未来另获对应授权后的操作说明，本阶段没有执行**。
`git push` 源码不等于给客户端推送更新，也不等于发布网站。

## 1. 仓库、分支与版本关系

```powershell
git clone --branch main https://github.com/nmrsz645-bit/shangchuanXtougao.git
Set-Location shangchuanXtougao
git status --short
git log -1 --format='%H %s'
git ls-remote origin refs/heads/main refs/tags/v1.0.17
```

- `main` 是本项目维护分支；当前正式 GitHub Release 是 [v1.0.17](https://github.com/nmrsz645-bit/shangchuanXtougao/releases/tag/v1.0.17)，程序构建提交为 `6071b4f6a640e3b27b78e302cff6a33fbeb57e6d`。其后 main 的纯文档提交不代表程序升级。
- 要复现这份已发布程序，在干净克隆中 `git switch --detach v1.0.17`；要继续修改，在 main 上新建自己的 `codex/` 分支，先检查/保留其他改动。
- 没有预设的独立客户端测试通道；候选包只能放全新本地目录、独立版本化 HTTPS 候选清单，并在隔离安装副本验证。不得用正式两处 JSON 作试验。
- GitHub 维护发行和 2026-10-28 OSS 发行都叫 1.0.17，但不是同一 ZIP。GitHub 包补齐文档并清空新用户预填账号；不应覆盖或假装升级原 OSS 同版本包。
- Release 内 README/HANDOFF 是该次发行快照；新接手说明以 main 的本指南为准，不替换已发布附件或重打旧标签来追平文档。
- 本仓库唯一活动工作流 `.github/workflows/offline-tests.yml` 在 push / pull_request 时运行离线测试，权限 contents:read，无生产上传/部署；本仓库 Pages 未启用，仓库 webhooks 为0。按本次核实的这些触发条件，普通文档推送 main 不会改客户端、OSS 或下载站；未来操作前仍要重新检查。

## 2. 新电脑安装与本地数据边界

普通用户：完整解压 GitHub/OSS 完整包，安装正式版 Google Chrome，从包根 **Start.cmd** 启动；不需要另装 Python。直接启动 app 内 EXE 会绕过检查更新。
开发电脑：Windows 10/11 x64、Git、Python **3.13.15 x64**。本次直接依赖固定为 Playwright 1.62.0、keyring 25.7.0、pytest 8.4.2、PyInstaller 6.22.2、setuptools 84.0.0。

```powershell
py -3.13 -m venv .venv
$python = Join-Path $PWD '.venv\Scripts\python.exe'
& $python -m pip install -r requirements-build-windows.txt
& $python -B -m pytest -q -p no:cacheprovider test_center_startup.py test_daily_restart.py test_shared_feishu.py test_handoff_safety.py test_release_safety.py test_github_package.py API投稿2.0/tests 自动上传/tests
```

显式测试路径避免递归收集保留的候选源码副本。`requirements-build-windows.txt` 引用 `requirements-dev.txt`，不是完整传递依赖 lockfile；不要混用系统 Python 3.10。
开发 GUI：`& $python 投稿中心.py`，或源码 `启动投稿中心.vbs/.bat`。先确认无真实自动任务授权/配置，开发启动也可能运行已保存的自动任务。

| 内容 | 新电脑处理 |
| --- | --- |
| Git 跟踪源码、README、HANDOFF、examples、测试、spec | 重新 clone；不要把旧电脑整盘目录当源码分发。 |
| `.venv`、build、dist、候选/验收目录 | 不迁移为运行依赖；在新机重建，旧证据可留原机备查。 |
| 根 `共享飞书设置.json`；API 的 `config`、`data/state.db`、`logs` | 含凭证或业务状态，不提交/打包/自动搬运。需续跑时先停任务并完整备份 SQLite/WAL/SHM，另行授权设计迁移，不能覆盖新机已有状态。 |
| 源码 `自动上传/个人数据`；冻结程序 `app/个人数据` | 含上传配置、队列、账本、日志和 Chrome 资料，不作为公共交接资料。`AUTO_UPLOAD_DATA_DIR` 只重定向上传模块。 |
| keyring/Windows 凭据、DPAPI、Chrome 登录态、Cookie、tokens.json | 不可分发；跨电脑不保证可解密，每台电脑重新授权和本人登录。 |
| 视频、任务目录及回滚副本 | 原样保护。授权迁移媒体后重新选择新路径；不因路径变化删队列、媒体或 app.previous。 |

安全空模板是 `examples/shared-feishu.example.json`、`api-settings.example.json`、`upload-settings.example.json`；通过界面保存真实配置，不直接用模板覆盖已有配置。

## 3. 版本、更新器依赖与完整构建

真实产品版本字段：**`API投稿2.0/version.json` 的 `version`**。冻结程序优先读 app 同级 version.json，再回退该源码位置；上传子包 pyproject 的 0.1.0 不是产品版本。
下一次真实程序升级才修改产品版本，连同对应源码、测试、文档提交；本轮不改 1.0.17。不能为了发文档升版本，也不能覆盖已有版本的 ZIP/tag。

更新器是外部 .NET CLR 程序，当前 26,624 字节，SHA256：
`68721ebefcdebbe7b4133424d9e432bcfa0372f7a015ecf54d5aeeb5a6493316`。
其原工程尚未找到，不能承诺从源码构建这个组件，也不能用同名 Python/C# 程序替代。

新机可从本项目固定 Release 取得依赖；以下是下载，不是安装迁移或生产上传：

```powershell
gh release download v1.0.17 --repo nmrsz645-bit/shangchuanXtougao --pattern '*github-windows-x64.zip' --pattern SHA256SUMS.txt --dir '候选发布-dependency'
Get-FileHash -Algorithm SHA256 '候选发布-dependency/shang-chuan-tou-gao-zhong-xin-1.0.17-github-windows-x64.zip'
Expand-Archive -LiteralPath '候选发布-dependency/shang-chuan-tou-gao-zhong-xin-1.0.17-github-windows-x64.zip' -DestinationPath '候选发布-dependency/unpacked'
Get-FileHash -Algorithm SHA256 '候选发布-dependency/unpacked/updater/UpdateAgent.exe'
```

固定 GitHub 完整包 SHA256 为 `0e35caa792b3f185bcd065dece81ada617328d4e4de74d6348500b8d0f977e56`；依赖散列必须与上文一致。下载目录必须全新，不用 clobber/Force 覆盖旧文件。
在已提交源码、全新 `$job` 输出目录中构建（本阶段未执行）：

```powershell
$job = '候选发布-next'
$commit = git rev-parse HEAD
& $python -m PyInstaller --clean --noconfirm --distpath "$job/dist" --workpath "$job/build" '上传投稿中心.spec'
& $python -B -m release.build_github_package --app-dist "$job/dist/上传投稿中心" --updater '候选发布-dependency/unpacked/updater/UpdateAgent.exe' --destination "$job/assembled" --source-commit $commit
```

保留同级 dist/build：组包核验 HEAD、已提交本地模块、冻结代码和 `build/上传投稿中心/COLLECT-00.toc` 全部文件散列。输出 `assembled/package`、`app-audit-only.zip`、`*-github-windows-x64.zip`。
组包拒绝已有 destination、未列入示例、未提交发行资产和运行数据。维护构建需 Git 工作副本；源码 ZIP 不含 .git，不能代替来源校验用的 clone。

## 4. 应用层更新包、完整 OSS 包与清单

本项目没有二进制差分更新；所谓“增量包”实际是整个 **app 层 ZIP**，不含外层 updater。完整 ZIP 包含 app、updater、根 Start.cmd。
`build_release_candidate.py` 的 `--base-root/--destination/--version` 只复制已有基线、改版本并组包，不编译 EXE，且 notes 固定为旧 CMD 修复说明；不要把旧基线直接冒充新构建。它还会重写 version.json，复用带 BUILD-INFO 的基线时必须重新核验内层记录，不能直接照抄。

以下**本地内联组包片段**复用现有 `build_release_candidate.py` 的散列/ZIP helpers 和 `release_safety.py`，保持上一步新构建 app 不变；不是仓库内不存在的“自动上传脚本”，也不上传任何对象：

```powershell
@'
from pathlib import Path
import json, sys
from build_release_candidate import sha256, zip_directory
from release_safety import REQUIRED_APP_FILES, validate_release
base, out = Path(sys.argv[1]), Path(sys.argv[2])
if out.exists(): raise FileExistsError(out)
out.mkdir(parents=True)
version = json.loads((base/'app/version.json').read_text('utf-8'))['version']
info = json.loads((base/'BUILD-INFO.json').read_text('utf-8'))
assert info['productVersion'] == version
assert all(sha256(base/'app'/n) == h for n,h in info['requiredFileSha256'].items())
oss = 'https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com'
product = 'shang-chuan-tou-gao-zhong-xin'
zip_directory(base/'app', out/'app.zip')
manifest = {'version':version, 'url':f'{oss}/updates/{product}/{version}/app.zip',
    'sha256':sha256(out/'app.zip'), 'notes':'',
    'files':{n:sha256(base/'app'/n) for n in REQUIRED_APP_FILES}}
(out/'latest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n','utf-8')
full = f'{product}-{version}.zip'
zip_directory(base, out/full)
site = {'version':version,'fullPackageUrl':f'{oss}/packages/{full}'}
(out/'latest.js').write_text('window.SHANG_CHUAN_TOU_GAO_ZHONG_XIN_LATEST = Object.freeze('+json.dumps(site)+');\n','utf-8')
validate_release(out/'app.zip',out/'latest.json',base/'Start.cmd',version)
(out/'SHA256SUMS.txt').write_text(''.join(sha256(p)+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.is_file()),'ascii')
'@ | & $python - "$job/assembled/package" "$job/oss-payload"
& $python -B release_safety.py --app-zip "$job/oss-payload/app.zip" --manifest "$job/oss-payload/latest.json" --start-script "$job/assembled/package/Start.cmd" --version (Get-Content 'API投稿2.0/version.json' -Raw | ConvertFrom-Json).version
```

发布前填写清单 notes 的真实变更说明，再重新生成相应清单散列并校验；不得沿用示例说明。SHA256SUMS 不应包含自己的递归散列。
修改 notes 后可只在本地重新生成校验清单（本阶段未执行）：

```powershell
Get-ChildItem -LiteralPath "$job/oss-payload" -File | Where-Object Name -ne 'SHA256SUMS.txt' | Sort-Object Name | ForEach-Object { '{0}  {1}' -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(), $_.Name } | Set-Content -LiteralPath "$job/oss-payload/SHA256SUMS.txt" -Encoding ascii
```

对全新候选检查 ZIP CRC/布局、完整包全部文件、私有数据/凭证、BUILD-INFO 与提交、清单四个必需文件散列。工具只检查其明确覆盖的项，不替代人工全包审查。

## 5. 客户端实际机制与 OSS 精确对象

根 `release/Start.cmd` 在安装根目录同步调用：
`updater\UpdateAgent.exe --silent --check updater\updater-config.json`，随后调用 `app\Start-App.cmd`。参数使用相对配置路径；不要改回曾静默失效的绝对参数。
本机 `updater-config.json` 字段为 appId、manifestUrl、appRoot、versionFile、preservePaths、requiredFiles；appRoot=`..\app`，versionFile=`version.json`，preservePaths=`["*"]`。
当前更新检查是启动器发起的静默检查，不是运行中弹窗推送，也没有在本阶段新增用户确认流程。

Bucket **luotuoruanjiangengx**，地域华北2（北京），外网 HTTPS 基址 `https://luotuoruanjiangengx.oss-cn-beijing.aliyuncs.com`：

| Object key | 用途/字段 |
| --- | --- |
| `updates/shang-chuan-tou-gao-zhong-xin/<新版本>/app.zip` | 不可变应用层更新包。 |
| `packages/shang-chuan-tou-gao-zhong-xin-<新版本>.zip` | 不可变新用户完整包。 |
| `updates/shang-chuan-tou-gao-zhong-xin/<新版本>/latest.json` | 发布前需另建的 HTTPS 候选清单；只让隔离副本读取，不是正常客户端入口。 |
| **`updates/shang-chuan-tou-gao-zhong-xin/1.0.0/latest.json`** | **旧客户端固定入口，目录 1.0.0 不是当前版本，必须保护并更新同一地址。** |
| `updates/shang-chuan-tou-gao-zhong-xin/latest.json` | 另一正式 JSON；历史发布要求与旧入口字节一致。不能只改这一份便称旧客户端已收到更新。 |
| `updates/shang-chuan-tou-gao-zhong-xin/latest.js` | 网站卡片元数据，不是客户端 JSON。 |

两份 JSON 均含 version、url（HTTPS app.zip）、sha256（app ZIP）、notes、files。files 至少覆盖 `version.json`、`上传投稿中心.exe`、`Start-App.cmd`、`_internal/python313.dll`；值均为相应文件 SHA256。
2026-10-31 两份正式 JSON 实际均为 1.0.17，JSON 文件本身的 SHA256=`f11b5d890a8773c00f4155e90b15a56f7028bab4bb23cc5b9a3fb9a1e4c1cdd6`（64位，不是 app.zip 散列），指向 2026-10-28 OSS 构建，不是 GitHub 同版本维护包。

未来获生产授权后的**手工发布顺序**（仓库没有已验证的 OSS 自动上传脚本）：

1. 备份当前两份正式 JSON、latest.js、网站本卡静态字段和相应版本散列；保留旧 ZIP 与可恢复安装副本。
2. OSS 控制台确认 bucket；先上传新版本 app.zip 和标准命名完整 ZIP 到表中不可变 key，不覆盖旧版本。ACL 沿用原受控设置，不扩大 Bucket 权限。
3. 公网完整下载两包并验 SHA256/CRC/版本/布局；任何不符停止。
4. 上传版本化候选 latest.json，在干净旧版**隔离副本**仅修改副本 manifestUrl 为该 HTTPS 地址；从副本根目录运行原更新器相对配置命令，验证升级和合成数据保留，不启动真实任务。
5. 候选通过后，最后将同一 latest.json 分别上传到顶层和 **1.0.0/** 两处；再上传 latest.js。两处字节/目标包/散列必须一致。
6. 更新网站静态兜底卡片，由网站维护会话按下一节授权执行；之后按第7节验收旧固定地址和公网页面。

## 6. 网站卡片与历史 catalog：不要混用

网站仓库 [nmrsz645-bit/software-download-center](https://github.com/nmrsz645-bit/software-download-center)，文件 `index.html`；域名 `https://download.luotuoqiluotuozhaoma.com/`。
实际 Pages 配置是 legacy、**main 分支根目录 /**；网站 main 推送会部署。当前协作由“更新”维护会话写网站 `docs-cross-pc-handoff` 文档分支，本项目会话不写网站仓库或生产 main。
共享步骤见 [网站接手](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#website)、[catalog 规则](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#catalog)、[客户端发布顺序](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#client-update)。本项目对象如下，不能只看通用链接：

| 映射 | 本项目实际值 |
| --- | --- |
| 静态版本元素 | `id="shangchuan-version"`；文字 `当前版本：v<版本> · Windows 64 位 · 国内直连`。 |
| 静态完整包链接 | `id="shangchuan-download"` 的 href 与按钮版本文字；当前指向 OSS 标准完整包 1.0.17。 |
| 运行时脚本 | 旧 OSS 基址下 `updates/shang-chuan-tou-gao-zhong-xin/latest.js`。 |
| JS 对象 | `window.SHANG_CHUAN_TOU_GAO_ZHONG_XIN_LATEST`；version、fullPackageUrl，后者必须为 HTTPS 完整包 URL。 |
| 应用函数 | `applyDownload('shangchuan-version','shangchuan-download',对象,'国内下载完整包')` 更新文字和链接；脚本失败保留静态兜底。 |

网站更新要同时核对静态两元素和运行时 latest.js，不能只改显示版本、只更新静态 href 或把 app.zip 当完整下载包。默认应先让新包可下载并校验，再动清单/JS/网站；不要批量替换其他卡片。
本项目没有仓库内生效的 catalog 生成/上传脚本，也不读取矩阵专属站内清单。实际存在的历史外部对象为同一旧 OSS bucket 的 **`catalog.json`** 和 **`downloads/catalog.json`**；二者根对象的 apps 数组均有 `id="shang-chuan-tou-gao-zhong-xin"` 条目，字段 name、description、version、visible、downloadUrl。
本次其历史记录仍为 1.0.2、相对路径 `packages/shang-chuan-tou-gao-zhong-xin-1.0.2.zip`，但当前网站 index **不加载这两份 catalog**，不是本卡当前发布入口。不要依据这份旧记录回退网站或擅改全站 catalog；若另有旧消费者，先核实其实际读取方并另获授权。

## 7. 验收、回滚与 GitHub 发布边界

最低验收：从公网下载 ZIP 验 SHA256 与 CRC；核对 app/version.json、BUILD-INFO 来源提交、EXE/启动器/依赖和文档；读回两处正式 JSON 及 latest.js；核对公网页面静态和运行时版本/完整包 URL；在独立旧安装副本以**原配置**升级，验证配置/队列/日志/浏览器资料合成标记保留。
隔离更新命令需在隔离安装根目录运行：`.\updater\UpdateAgent.exe --silent --check updater\updater-config.json`；这里只说明调用形式，本阶段未执行。
测试样本使用合成数据，不能对客户安装、实际 Chrome 登录态或真实任务做发布试验。完整包启动检查可在无凭证副本完成；真实上传/投稿另需授权。
更新器接受 HTTPS；HTTP 回环不能替代该实际更新路径。程序版本相同或回退到低版本时，旧客户端不会被当作升级处理，不能靠把清单 version 改小实现已升级用户降级。

回滚时先停止新发布入口：恢复事先保存的两份正式 JSON、latest.js 和本站本卡静态字段一致性，只在对应生产回滚授权下执行；保留新旧不可变 ZIP。已升级客户端需正常停任务、备份数据后，按验证过的独立 app.previous/旧完整包手工恢复并核对状态，不删除运行数据、不强杀任务。系统已有恢复逻辑并不证明任意数据迁移可自动回滚。
共享 [验收与回滚](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#verify-rollback) 还列出证据要求。

未来发布新 GitHub 版本时，先确认目标标签不存在、代码/文档/测试已提交且 CI 通过，再使用正常新 Release 流程：

```powershell
git status --short
git diff --cached --check
git push origin main
# 仅在真实新版本、对应发布授权及资产审查齐备后：
# gh release create v<新版本> --repo nmrsz645-bit/shangchuanXtougao --target <完整commit> --title '真实新版本' --notes-file <已审查说明文件> <已审查资产路径>
```

不覆盖已有 v1.0.17/tag/附件，不强推。发布后匿名下载每个附件验哈希，并确认 Release 非草稿/标签指向准确提交；成功发送或本地组包不是发布成功。GitHub Release 本身不激活本项目 OSS 客户端清单或网站。

## 8. 凭据、权限与仍然缺少的证据

- Git/GitHub CLI：用自己的 Git Credential Manager / `gh auth login` 登录获授权账号；仓库保持现有 public 权限。需要源码推送与 Release 附件写权限，不扩展到无关仓库/组织，不把 PAT/SSH 私钥放入命令、示例或 ZIP。
- OSS：由有本 bucket/产品 prefix 权限的操作者本人登录控制台；短期 STS 如有需要应由管理员针对该范围另行授予。本项目没有 OSS 凭据配置字段、环境变量读取或自动上传器，不索要/硬编码长期密钥，不因接手扩大权限。
- 业务配置字段：共享 `app_id`、`secret`、`task_sheet_url`、`copy_sheet_url`；API `qianchuan_app_id`、`qianchuan_secret`、`configured_advertiser_ids`、`mini_program_app_id`；上传 `material_url`、`source_dir`、`destination_dir`。飞书企业自建应用、自己的巨量开放平台应用/正式回调、小程序后台、本人目标素材账号分别提供对应值，详见 README“首次配置”及 examples。本人配置并授权，不能分发真实共享设置、回调、token、个人资料、内部聊天或浏览器资料。
- 更多权限边界见共享 [credentials](https://github.com/nmrsz645-bit/software-download-center/blob/docs-cross-pc-handoff/docs/PUBLISHING.md#credentials)。公开文档只记录本产品和必要的公共下载站对象。
- 缺口逐项保留：外部 .NET UpdateAgent 的确切原工程/源码/构建测试未找到；Windows CLR4 系列环境及正式版 Chrome 是运行依赖，裸新系统安装组合未穷尽验证；没有自动 OSS 上传脚本/统一网站 catalog 管线；线上 IAA 弹窗未现场触发验收；跨电脑真实业务数据迁移和升级后复杂状态回滚没有通用自动保证。
- 本阶段只校验文档、路径、参数与线上只读对象；不重建程序、不修改版本、包、Release/tag、OSS 或网站。本指南中的生产步骤未执行。
