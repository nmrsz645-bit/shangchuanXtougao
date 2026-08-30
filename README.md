# 上传 + 投稿中心（本地版）

双击 `启动投稿中心.vbs`，可在不显示命令行窗口的情况下启动程序。`启动投稿中心.bat` 保留为兼容入口。

- `API投稿2.0`：从飞书领取投稿任务，通过巨量 API 创建投稿单元。
- `自动上传`：扫描视频、浏览器上传巨量素材库，并按需回写飞书。

API 投稿的“授权”页可填写一台电脑共用的“当前小程序 App ID”。留空时继续按旧的两种程序链接格式选择 App ID。

本项目是两个原程序的本地副本。原程序目录没有被修改。

## 本地数据规则

- API 投稿运行后会在 `API投稿2.0\config`、`API投稿2.0\data`、`API投稿2.0\logs` 保存本机数据。
- 自动上传运行后会在 `自动上传\个人数据` 保存设置、Chrome 登录资料、队列、统计和日志。
- 这些目录不属于源代码，后续本地打包或更新时必须保留，且不上传云端。

除上述本机小程序 App ID 配置外，两个模块保留原有业务逻辑。

## 离线自动化测试

```powershell
Set-Location 'E:\自动化\上传+投稿'
python -m pytest test_center_startup.py test_daily_restart.py test_shared_feishu.py test_handoff_safety.py -q

$env:PYTHONPATH = 'E:\自动化\上传+投稿\API投稿2.0\app'
python -m pytest API投稿2.0\tests -q
```

测试使用模拟的飞书和巨量接口，不会真实投稿、上传、打开 Chrome 或触发在线更新。更新器实际升级后的数据保留，仍须由更新程序在隔离环境中验证。
