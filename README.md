```text
 /\_/\\
( o.o )  opclash_cli
 > ^ <
```

> 🧭 面向 OpenClash 的本机管理与 Controller 远程控制 CLI

`opclash_cli` 是一个 Python 3.11 命令行工具，用于在路由器本机管理 OpenClash，并在其他机器上远程控制 Clash Controller，覆盖订阅、节点、服务和基础诊断。

## ✨ 特性

- 本机管理优先：订阅、服务、配置、日志等系统级操作要求在路由器本机执行
- 远程控制明确：在其他机器上默认只使用 controller 执行节点查看、测速和切换
- 订阅管理完整：支持新增、启停、更新、重命名、删除与本地归档
- 节点切换更稳妥：可先查看节点组与测速结果，再执行切换
- 服务与诊断闭环：重载或重启后可立即复核状态，并查看网络、配置、日志信息
- 结构化输出友好：默认 JSON，便于脚本、CI 和 AI Agent 直接消费
- 安全与审计可控：凭据本地保存，修改类操作支持确认与 `--dry-run`

## 🖥️ 本机与远程环境

配置文件里**只会**保存 OpenClash Controller（URL 与 secret），用于连接 Clash 外部控制接口。能不能改路由器上的订阅、服务或 UCI，取决于你是否在**路由器本机**执行命令，而不是否多写一套远程管理 URL。

**本机环境**：在已安装 OpenClash 的 OpenWrt 上、以 **root** 运行 CLI，且系统 `PATH` 中能调用 `uci`。此时 `init check` 会报告 `router_local_ok: true`，`sub`、`service`、`sub switch` 等依赖本机 OpenWrt 与文件路径的命令可用；Controller 既可以是 `127.0.0.1:9090`，也可以指向同一台路由器的对外地址。

**远程环境**：在 PC、服务器或 CI 上运行，仅能通过已保存的 Controller 访问远端 Clash。**`nodes` 系列**（查看组、测速、切换节点）一般可直接使用。任何需要读写本机 UCI、调用 OpenWrt 服务或访问路由器文件路径的命令会失败，并提示到路由器上执行；**不再提供**通过配置文件保存 LuCI HTTPS 账号、在异地完成全量订阅/服务管理的模式。

## 📦 安装

要求：

- Python `3.11+`
- 可访问 OpenClash Controller

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

## 🧩 Skill 安装

```bash
mkdir -p ~/.codex/skills
cp -r ./skills/opclash_cli_skill ~/.codex/skills/
```

## 🚀 快速开始

1. 初始化连接配置

无论是否在路由器本机，`init` 现在只写入 controller 配置：

```bash
python3 -m opclash_cli.main init \
  --controller-url http://192.168.1.1:9090 \
  --controller-secret your-secret
```

2. 检查 controller 和本机执行条件

```bash
opclash_cli init check
```

3. 查看节点组

```bash
opclash_cli nodes groups
```

4. 在路由器本机切换订阅配置

```bash
opclash_cli sub switch \
  --config /etc/openclash/config/example.yaml
```

## 🛠️ 命令一览


| 领域  | 子命令                      | 用途                | 常见示例                                                                 |
| --- | ------------------------ | ----------------- | -------------------------------------------------------------------- |
| 初始化 | `init`                   | 写入或检查本地连接配置       | `opclash_cli init check`                                             |
| 节点  | `nodes groups`           | 查看所有节点组           | `opclash_cli nodes groups`                                           |
| 节点  | `nodes group`            | 查看指定组详情           | `opclash_cli nodes group --name HK`                                  |
| 节点  | `nodes switch`           | 切换组内节点            | `opclash_cli nodes switch --group Apple --target DIRECT`             |
| 节点  | `nodes speedtest`        | 调用 Clash 自带测速并排序  | `opclash_cli nodes speedtest --group HK --limit 10`                  |
| 订阅  | `sub list`               | 查看订阅列表            | `opclash_cli sub list`                                               |
| 订阅  | `sub add`                | 新增订阅源             | `opclash_cli sub add --name west2 --url https://example/sub`         |
| 订阅  | `sub enable/disable`     | 控制订阅是否参与更新        | `opclash_cli sub enable --name west2`                                |
| 订阅  | `sub rename`             | 调整订阅显示名           | `opclash_cli sub rename --name west2 --to west2-main`                |
| 订阅  | `sub remove`             | 删除订阅并写入本地归档       | `opclash_cli sub remove --name west2`                                |
| 订阅  | `sub update`             | 更新订阅              | `opclash_cli sub update --name west2`                                |
| 订阅  | `sub switch`             | 切换远端配置文件          | `opclash_cli sub switch --config /etc/openclash/config/example.yaml` |
| 服务  | `service status`         | 查看 OpenClash 服务状态 | `opclash_cli service status`                                         |
| 服务  | `service reload/restart` | 重载或重启服务           | `opclash_cli service restart --yes`                                  |
| 服务  | `service logs`           | 查看 OpenClash 服务日志   | `opclash_cli service logs --tail 100`                                |
| 诊断  | `doctor`                 | 执行基础诊断与日志查看       | `opclash_cli doctor logs --limit 20`                                 |
| 通用  | `version` / `completion` | 查看版本或生成补全脚本       | `opclash_cli completion bash`                                        |


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
3. 执行 `opclash_cli init check` 验证 controller 与本机执行条件
4. 再执行 `nodes`、`sub`、`service` 等操作命令

说明：

- 首次使用若未执行 `init` 写入 controller，`nodes` 等 controller 命令会因 URL 缺失而失败
- `sub switch --config` 需要传入远端 OpenClash 主机上的完整配置路径
- `sub enable/disable` 只影响该订阅是否参与更新，不直接切换当前运行配置
- 支持同时启用多个订阅；OpenClash 当前生效的配置仍由 `sub current` / `sub switch` 决定
- 订阅、服务、UCI、配置文件和日志等系统级命令必须在路由器本机执行
- 非本机执行这些命令时，CLI 会直接提示切换到路由器本机
- `service logs` 读取的是本机 `/tmp/openclash.log`
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
    "router_local_ok": true,
    "router_local_backend": "local"
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

## 🧪 开发

```bash
python3 -m pytest
python3 -m opclash_cli.main --help
```

## 📜 许可

许可证：`MIT`