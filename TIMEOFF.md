# 上传 + 投稿中心：v1.0.15 本地验证交接

## 当前状态

v1.0.14 已经公开，但客户截图证明其完整包根启动器仍不能可靠触发更新：根 `Start.cmd` 把绝对路径传给 `UpdateAgent.exe`，该更新器会静默跳过更新，继而旧的 `app\Start-App.cmd` 仍尝试启动不存在的 `API_Posting_2.exe`。

**v1.0.15 已完成本地构建和验证，尚未上传 OSS、尚未切换清单、尚未更新下载网站。** 先完成本文件列出的本地验收；只有全绿后，才按“发布顺序”上传。不得覆盖或删除任何既有版本、配置、日志、数据、客户目录或回滚目录。

## 本次源码修复

- `API投稿2.0\version.json` 更新为 `1.0.15`；应用启动器仍只启动 `上传投稿中心.exe`。
- 新增 `release\Start.cmd` 作为完整包根启动器模板。它固定到安装根目录，并以相对路径调用：

  ```bat
  pushd "%ROOT%" || exit /b 1
  "updater\UpdateAgent.exe" --silent --check "updater\updater-config.json"
  call "app\Start-App.cmd"
  popd
  ```

- `release_safety.py` 现在拒绝缺少上述固定工作目录、相对更新器参数及 `popd` 的根启动器；测试覆盖了此前的绝对路径错误。
- 新增 `build_release_candidate.py`，从已审计的干净基线构建不可覆盖的候选包，并在生成后执行发布安全校验。

## 已完成的本地证据

- 实测旧 1.0.13 副本：从任意工作目录、向更新器传绝对路径时保持在 1.0.13；切到安装根目录并使用相对 `updater\...` 参数后，升级为 1.0.14，且 `Start-App.cmd` 更新为 `上传投稿中心.exe`。
- v1.0.15 根启动器在隔离目录、从工作区发起时，实际工作目录被切换到该安装根目录（无 GUI、无真实上传或投稿）。
- v1.0.15 候选包已通过 `release_safety.py`；其根 `Start.cmd`、`app\version.json` 与 `app\Start-App.cmd` 已逐项检查。
- 业务运行条件仍是 Windows 10/11 64 位和**正式版 Google Chrome**；不需要 Playwright 自带浏览器，也不要运行 GUI 做发布验证。

## v1.0.15 候选载荷

目录：

```text
C:\Users\Administrator\Documents\ChatGPT\更新 2\release-candidates\shangchuan-tougao-1.0.15\upload-payload-1.0.15
```

| 文件 | SHA-256 | OSS 目标键 |
| --- | --- | --- |
| `app.zip` | `1edf2eb3a3e5186f67a01867ad7ce06c1fffc40417050ee86c88c0ff69c3f4c9` | `updates/shang-chuan-tou-gao-zhong-xin/1.0.15/app.zip` |
| `shang-chuan-tou-gao-zhong-xin-1.0.15.zip` | `a8aaf6563e3463dd2dab249e9e936738a4531a1fbbc7b2083e772a8e3551df86` | `packages/shang-chuan-tou-gao-zhong-xin-1.0.15.zip` |
| `latest.json` | `dbca8ebf5131ce6826267c19d2e2639876c5d21ff6ee69d2fd64e2c2cf81be9d` | 两个清单位置（见下） |
| `latest.js` | `4579d533f39d1d0b3909b387adfd050209904dc8620787f2582e491c56e242e6` | `updates/shang-chuan-tou-gao-zhong-xin/latest.js` |

## 发布顺序（仅在本地全绿后）

1. 上传两个不可变 ZIP，不上传清单：

   ```text
   app.zip -> updates/shang-chuan-tou-gao-zhong-xin/1.0.15/app.zip
   shang-chuan-tou-gao-zhong-xin-1.0.15.zip -> packages/shang-chuan-tou-gao-zhong-xin-1.0.15.zip
   ```

2. 从公网 HTTPS 下载两个 ZIP，核对以上 SHA-256；任一不符立即停止。
3. 仅在 ZIP 均一致后，最后上传同一份 `latest.json` 到：

   ```text
   updates/shang-chuan-tou-gao-zhong-xin/1.0.0/latest.json
   updates/shang-chuan-tou-gao-zhong-xin/latest.json
   ```

   然后上传 `latest.js` 到 `updates/shang-chuan-tou-gao-zhong-xin/latest.js`。
4. 带随机参数读回两份 JSON、`latest.js` 和下载站，确认均为 1.0.15。
5. 下载站仓库 `C:\Users\Administrator\Documents\ChatGPT\更新 2\software-download-center` 仅更新版本文字和完整包 URL，提交推送后再从公开页面验收。

## 数据边界

不得读取、提交、上传、清空或覆盖：`共享飞书设置.json`、`个人数据\`、`API投稿2.0\config\`、`API投稿2.0\data\`、`API投稿2.0\logs\`、`自动上传\个人数据\`、任何客户安装目录、`app.previous`、视频、队列、浏览器资料、Token 或阿里云凭据。OSS 登录只能由用户本人完成；不得读取或代填密码、验证码、Cookie、AccessKey。
