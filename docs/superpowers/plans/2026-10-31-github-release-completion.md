# 1.0.17 GitHub 补齐执行计划

> For agentic workers: 使用 executing-plans 连续执行，最终进行独立审查。

Goal: GitHub 同时提供 1.0.17 源码、Windows 完整包、README 和安全 HANDOFF。
Architecture: 保持产品版本；清空新用户预填业务账号，重新构建独立命名的 GitHub 维护发行。更新器作为固定散列校验的二进制依赖复用，不改 OSS。
Tech Stack: Windows x64、Python 3.13.15、PyInstaller 6.22.2、pytest、GitHub Releases。
Spec: 用户 2026-10-31 的 GitHub 补齐授权；仓库 nmrsz645-bit/shangchuanXtougao。

## Global Constraints

- 不改运行中的程序、用户配置、业务数据、浏览器资料、OSS、下载站或更新清单。
- 保护本地 TIMEOFF.md 原文；公开交接写 HANDOFF.md，TIMEOFF 发布安全索引。
- 不升级版本、不覆盖旧包、不强推、不修改仓库权限。
- push 只触发已有 Offline tests；已检查无生产部署工作流。

## Review Focus

- 包内不能带本机配置、账号、日志、浏览器资料或内部诊断聊天。
- Start.cmd 先从安装根目录调用更新器，再启动 app。
- GitHub 维护包与 2026-10-28 OSS 发行的差异必须公开说明。
- 打包必须真正编译源码，不能给旧 EXE 改版本。
- 版本、提交、源码、文档和散列必须可追溯。

## Tasks

- [x] 1. 核对 main、Release、工作流、历史提交，扫描凭证和业务标识。
- [x] 2. 新增默认账号留空/已有配置保留测试，观察失败，再清空默认值。
- [x] 3. 补 README、HANDOFF、安全示例、依赖与构建脚本，备份本地旧交接。
- [ ] 4. 离线全量测试；全新目录编译、白名单组包、扫描源码与包内文件。
- [ ] 5. 独立审查、修正阻断、精确暂存、正常提交推送、验证 CI。
- [ ] 6. 发布 v1.0.17 Release，上传独立命名 ZIP、文档与散列，公网回读。

## Execution ledger

- 初始 main: a0ada8ea1a6637aad4c98febd713addc53683380；唯一既有修改 TIMEOFF.md。
- Gitleaks 8.30.1: 28 commits，0 credential findings；业务账号默认值需移除。
- Ruling: 用户已授权端到端执行并要求不重复询问常规许可，按详细要求连续执行。
- Ruling: 只为安全发布清空硬编码账号，不改变已有配置或其他业务逻辑。

- 审查修复：递归敏感路径、准确HEAD/冻结模块/全部COLLECT文件散列、按钮实际流程；反例5失败后7通过。
- 全量明确测试路径：302 passed in 19.17s。裸递归曾收集本机保留审计副本引发重复模块，已在文档使用明确生产测试路径，不删任何副本。
- 全新整合版 PyInstaller 编译退出0，15.73秒；未启动真实业务。

- 独立复核最后一项资产旁路已解除：示例精确白名单、文档/版本/启动器读取准确提交；新增反例2失败后组包9项通过。
- 同版本旧更新器隔离实测退出0，1210文件散列均未变化，4个合成数据标记保留；不会把GitHub维护包回退至OSS旧构建。

- 最终明确路径完整回归：304 passed in 21.50s；独立审查无残留Critical/Important。
