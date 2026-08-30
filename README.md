# 上传 + 投稿中心（本地版）

双击 `启动投稿中心.vbs`，可在不显示命令行窗口的情况下启动程序。`启动投稿中心.bat` 保留为兼容入口。

- `API投稿2.0`：从飞书领取投稿任务，通过巨量 API 创建投稿单元。
- `自动上传`：扫描视频、浏览器上传巨量素材库，并按需回写飞书。

API 投稿的“授权”页可填写一台电脑共用的“当前小程序 App ID”。留空时继续按旧的两种程序链接格式选择 App ID。

本项目是两个原程序的本地副本。原程序目录没有被修改。

## 新电脑接手源码

普通用户请下载已打包的完整程序；以下步骤只供开发/维护电脑使用。需要 Windows、Git 和 Python 3.12 或更新版本。

```powershell
Set-Location 'E:\自动化'
git clone https://github.com/nmrsz645-bit/shangchuanXtougao.git 上传+投稿
Set-Location '.\上传+投稿'

python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
```

实际视频上传必须安装正式版 Google Chrome；程序会直接启动它，**不需要**下载 Playwright 自带的 Chromium。

源码目录中的 `启动投稿中心.vbs` 会优先使用 `.venv` 的 Python；完成以上安装后可直接双击启动。若 `.venv` 不存在，才回退使用系统 `pythonw.exe`。

新电脑必须重新填写飞书/巨量授权并登录 Chrome；不要把另一台电脑的 `共享飞书设置.json`、`个人数据`、`API投稿2.0\config/data/logs` 或 Chrome 数据提交到 Git。

## 本地数据规则

- API 投稿运行后会在 `API投稿2.0\config`、`API投稿2.0\data`、`API投稿2.0\logs` 保存本机数据。
- 自动上传运行后会在 `自动上传\个人数据` 保存设置、Chrome 登录资料、队列、统计和日志。
- 这些目录不属于源代码，后续本地打包或更新时必须保留，且不上传云端。

除上述本机小程序 App ID 配置外，两个模块保留原有业务逻辑。

## 离线自动化测试

```powershell
Set-Location 'E:\自动化\上传+投稿'
.\.venv\Scripts\python -m pytest test_center_startup.py test_daily_restart.py test_shared_feishu.py test_handoff_safety.py test_release_safety.py -q

$env:PYTHONPATH = 'E:\自动化\上传+投稿\API投稿2.0\app'
.\.venv\Scripts\python -m pytest API投稿2.0\tests -q

Set-Location 'E:\自动化\上传+投稿\自动上传'
..\.venv\Scripts\python -m pytest -q
```

测试使用模拟的飞书和巨量接口，不会真实投稿、上传、打开 Chrome 或触发在线更新。更新器实际升级后的数据保留，仍须由更新程序在隔离环境中验证。

发布前还应对**干净的候选更新包**运行离线检查，避免缺少版本文件、根启动入口没有更新检查，或用户数据误被打包：

```powershell
python release_safety.py --app-zip <app.zip> --manifest <latest.json> --start-script <Start.cmd> --version <版本号>
```

该检查只针对将要上传的干净候选目录；不要对客户已安装目录运行，客户目录中的个人数据本来就必须保留。
