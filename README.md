```text
 /\_/\\
( o.o )  opclash_cli
 > ^ <
```

> 🧭 AI-native OpenClash 远程管理命令行工具

`opclash_cli` 是一个面向 OpenClash 的 Python 3.11 CLI，聚焦远程管理、订阅切换、节点切换、服务控制与基础诊断。

## ✨ 特性

- 统一入口，覆盖 `init`、`nodes`、`subscription`、`service`、`doctor`
- 输出结构化 JSON，支持脚本集成与自动化调用
- 读写命令边界清晰，常用操作保持简洁直接
- 面向 AI Agent、终端脚本和日常运维场景

## 📦 安装

要求：

- Python `3.11+`
- 可访问 OpenClash Controller 与 LuCI RPC
- 使用虚拟环境

普通安装：

```bash
python3 -m pip install .
```

安装后可直接使用：

```bash
opclash_cli --help
```

开发安装：

```bash
python3 -m pip install -e .[dev]
```

或直接运行：

```bash
python3 -m opclash_cli.main --help
```

## 🚀 快速开始

1. 初始化本地连接配置

```bash
python3 -m opclash_cli.main init \
  --controller-url http://127.0.0.1:9090 \
  --controller-secret your-secret \
  --luci-url http://192.168.1.1/cgi-bin/luci \
  --luci-username root \
  --luci-password your-password
```

2. 检查后端连通性

```bash
opclash_cli init check
```

3. 查看节点组

```bash
opclash_cli nodes groups
```

4. 切换订阅配置

```bash
opclash_cli subscription switch \
  --config /etc/openclash/config/example.yaml
```

## ⚡ 常用子命令

- `opclash_cli init check`
- `opclash_cli nodes groups`
- `opclash_cli nodes speedtest --group HK --limit 10`
- `opclash_cli subscription list`
- `opclash_cli subscription update --name west2`
- `opclash_cli subscription switch --config /etc/openclash/config/example.yaml`
- `opclash_cli service restart --yes`
- `opclash_cli doctor logs --limit 20`

## 🛠️ 命令一览

| 领域 | 子命令 | 用途 | 常见示例 |
| --- | --- | --- | --- |
| 初始化 | `init` | 写入或检查本地连接配置 | `opclash_cli init check` |
| 节点 | `nodes groups` | 查看所有节点组 | `opclash_cli nodes groups` |
| 节点 | `nodes group` | 查看指定组详情 | `opclash_cli nodes group --name HK` |
| 节点 | `nodes switch` | 切换组内节点 | `opclash_cli nodes switch --group Apple --target DIRECT` |
| 节点 | `nodes speedtest` | 调用 Clash 自带测速并排序 | `opclash_cli nodes speedtest --group HK --limit 10` |
| 订阅 | `subscription list` | 查看订阅列表 | `opclash_cli subscription list` |
| 订阅 | `subscription add` | 新增订阅源 | `opclash_cli subscription add --name west2 --url https://example/sub` |
| 订阅 | `subscription enable/disable` | 控制订阅是否参与更新 | `opclash_cli subscription enable --name west2` |
| 订阅 | `subscription rename` | 调整订阅显示名 | `opclash_cli subscription rename --name west2 --to west2-main` |
| 订阅 | `subscription remove` | 删除订阅并写入本地归档 | `opclash_cli subscription remove --name west2` |
| 订阅 | `subscription update` | 更新订阅 | `opclash_cli subscription update --name west2` |
| 订阅 | `subscription switch` | 切换远端配置文件 | `opclash_cli subscription switch --config /etc/openclash/config/example.yaml` |
| 服务 | `service status` | 查看 OpenClash 服务状态 | `opclash_cli service status` |
| 服务 | `service reload/restart` | 重载或重启服务 | `opclash_cli service restart --yes` |
| 诊断 | `doctor` | 执行基础诊断与日志查看 | `opclash_cli doctor logs --limit 20` |
| 通用 | `version` / `completion` | 查看版本或生成补全脚本 | `opclash_cli completion bash` |

## ⚙️ 配置

本地配置文件默认写入：

```text
~/.config/opclash_cli/config.toml
```

支持通过环境变量覆盖：

```bash
export OPENCLASH_CLI_CONFIG=/path/to/config.toml
```

部署顺序：

1. 安装 CLI
2. 执行 `opclash_cli init ...` 写入连接配置
3. 执行 `opclash_cli init check` 验证 Controller 与 LuCI RPC
4. 再执行 `nodes`、`subscription`、`service` 等操作命令

说明：

- `subscription switch --config` 需要传入远端 OpenClash 主机上的完整配置路径
- `subscription enable/disable` 只影响该订阅是否参与更新，不直接切换当前运行配置
- 支持同时启用多个订阅；OpenClash 当前生效的配置仍由 `subscription current` / `subscription switch` 决定
- `service logs` 读取的是远端 `/tmp/openclash.log`
- `doctor logs` 读取的是本地 CLI 操作日志

## 🔐 安全与审计设计

- 本地凭据默认写入 `~/.config/opclash_cli/config.toml`，支持 `OPENCLASH_CLI_CONFIG` 覆盖
- 修改类命令支持交互确认、`--yes` 与 `--dry-run`
- CLI 统一输出 JSON，用于审计、脚本消费与自动化记录
- 本地操作日志只记录初始化与修改类动作
- 删除订阅时写入本地归档，用于回溯与恢复

## 📄 输出

命令默认输出结构化 JSON，例如：

```json
{
  "ok": true,
  "command": "init check",
  "timestamp": "2026-04-22T13:42:34.065661Z",
  "data": {
    "controller_ok": true,
    "luci_ok": true
  },
  "warnings": [],
  "audit": null,
  "error": null
}
```

## 📝 日志

- 操作日志：`~/.local/state/opclash_cli/operations.jsonl`
- 删除归档：`~/.local/state/opclash_cli/subscription-archive.jsonl`
- 环境变量：`OPENCLASH_CLI_LOG`、`OPENCLASH_CLI_SUBSCRIPTION_ARCHIVE`
- 查看日志：`opclash_cli doctor logs --limit 20`

## 📚 文档

- [变更记录](./CHANGELOG.md)
- [贡献指南](./CONTRIBUTING.md)
- [安全说明](./SECURITY.md)
- [许可证](./LICENSE)

## 🏷️ 版本与补全

- 版本：`opclash_cli version` 或 `opclash_cli --version`
- 补全：`opclash_cli completion bash` / `opclash_cli completion zsh`

## 🧪 开发

```bash
python3 -m pytest
python3 -m opclash_cli.main --help
```

## 📜 许可

许可证：`MIT`
