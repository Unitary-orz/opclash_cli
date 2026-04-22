# Changelog

项目的重要变更记录在这里。

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
