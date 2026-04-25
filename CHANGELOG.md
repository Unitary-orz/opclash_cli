# Changelog

## [v0.3.0] - 2026-04-25

### ⚠️ 行为变更

- `**init` 只写 Controller**：本地配置仅持久化 Clash Controller 的 URL 与 secret，不再保存跨机 LuCI / management 账号或 HTTPS 远程管理参数
- **本机限定系统类命令**：订阅 CRUD、服务控制、`sub switch` 等依赖 OpenWrt UCI 与路由器路径的操作，须在路由器上以 **root** 执行且环境可用 `uci`；在非本机执行会得到明确错误指引
- **远端保留 controller-only**：在 PC / CI 等环境仍可通过 Controller 使用 `nodes` 查看、测速与切换节点

### ✨ Added

- **子命令更名**：`subscription` 更名为 `sub`
- `**sub usage`**：基于订阅响应头查询用量、配额与到期信息
- **订阅管理补齐**：`sub remove`、`enable`、`disable`、`rename` 等
- **删除订阅归档**：删除时写入 `~/.local/state/opclash_cli/subscription-archive.jsonl`

### ♻️ Refactor

- **适配层收敛**：OpenWrt 侧统一走本机 UCI / shell 后端；移除「通过 HTTPS 调用远端 LuCI JSON-RPC」的配置与实现，`luci_rpc` 大幅精简

### 🐛 Fixed

- **订阅更新**：修复订阅更新后防火墙规则丢失的问题

### 🛠 Improved

- `init check` 等指标对齐本机/远端模型（如 `router_local_ok`、`router_local_backend`）
- README、命令帮助与 Agent CLI skill 等文档更新
- 本地操作日志覆盖订阅修改类命令

## [v0.2.0] - 2026-04-22

### ✨ Added

- 核心命令域：`init`、`nodes`、`subscription`、`service`、`doctor`
- 本地操作日志：`~/.local/state/opclash_cli/operations.jsonl`
- 本地日志查看：`opclash_cli doctor logs`
- 节点测速：`opclash_cli nodes speedtest`
- 版本与补全命令：`version`、`--version`、`completion bash|zsh`
- 品牌标识：README 与版本输出加入轻量猫咪字标
- 支持文档：新增 `SUPPORT.md`、`SECURITY.md`

### 🛠 Improved

- 修复标准 `pip install .` 下的打包发现问题
- 兼容 Clash 节点切换接口 `204 No Content` 响应
- 修改类命令支持交互确认、`--yes` 与 `--dry-run`
- 本地日志只记录初始化与修改类操作，输出更干净
- README 安装、部署、日志与命令说明更完整

### 📚 Docs

- README 增加子命令表格速览
- 项目文案收紧为更轻量的工具风格
- 许可证、贡献说明、支持说明与安全说明齐备

