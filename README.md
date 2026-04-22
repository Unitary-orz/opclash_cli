# opclash_cli

> 🧭 AI-native OpenClash 远程管理命令行工具

`opclash_cli` 是一个面向 OpenClash 的 Python 3.11 CLI，聚焦远程管理、订阅切换、节点切换、服务控制与基础诊断。

## ✨ 特性

- 统一入口，覆盖 `init`、`nodes`、`subscription`、`service`、`doctor`
- 输出结构化 JSON，便于脚本集成与自动化调用
- 读写命令边界清晰，常用操作保持简洁直接
- 适合 AI Agent、终端脚本和日常运维场景

## 📦 安装

要求：

- Python `3.11+`
- 可访问的 OpenClash Controller 与 LuCI RPC
- 建议使用虚拟环境

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

## 🛠️ 命令概览

```text
init
nodes
subscription
service
doctor
```

常用子命令：

- `init show`：查看本地配置
- `init check`：检查 Controller 与 LuCI RPC
- `nodes groups`：列出节点组
- `nodes group --name <group>`：查看指定节点组
- `nodes providers`：列出 provider
- `nodes switch --group <group> --target <node>`：切换节点
- `nodes speedtest [--group <group>] [--limit <n>]`：调用 Clash 自带测速并按延迟排序
- `subscription list`：列出订阅
- `subscription current`：查看当前配置
- `subscription configs`：列出配置文件
- `subscription add --name <name> --url <url>`：新增订阅
- `subscription update --name <name>`：更新订阅
- `subscription switch --config <file>`：切换配置
- `service status | reload | restart | logs`：服务状态与控制
- `doctor network | runtime | config | logs`：基础诊断与本地操作日志

## ⚙️ 配置与部署

本地配置文件默认写入：

```text
~/.config/opclash_cli/config.toml
```

也可以通过环境变量覆盖：

```bash
export OPENCLASH_CLI_CONFIG=/path/to/config.toml
```

建议部署顺序：

1. 安装 CLI
2. 执行 `opclash_cli init ...` 写入连接配置
3. 执行 `opclash_cli init check` 验证 Controller 与 LuCI RPC
4. 再执行 `nodes`、`subscription`、`service` 等操作命令

说明：

- `subscription switch --config` 需要传入远端 OpenClash 主机上的完整配置路径
- `service logs` 读取的是远端 `/tmp/openclash.log`
- `doctor logs` 读取的是本地 CLI 操作日志

## 📄 输出格式

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

## 🧪 开发

运行测试：

```bash
python3 -m pytest
```

查看帮助：

```bash
python3 -m opclash_cli.main --help
```

## 📝 日志

CLI 现在会在本地追加记录操作日志，默认路径：

```text
~/.local/state/opclash_cli/operations.jsonl
```

可通过环境变量覆盖：

```bash
export OPENCLASH_CLI_LOG=/path/to/operations.jsonl
```

每条日志为一行 JSON，包含：

- `timestamp`
- `command`
- `ok`
- `warnings`
- `audit`
- `error`
- `data`

默认只记录两类操作：

- 初始化相关：`init`、`init check`
- 修改相关：`nodes switch`、`subscription add/update/switch`、`service reload/restart`

查看本地操作日志：

```bash
opclash_cli doctor logs --limit 20
```

节点测速示例：

```bash
opclash_cli nodes speedtest --group Apple --limit 10
```

## 📚 文档

- [变更记录](./CHANGELOG.md)
- [贡献指南](./CONTRIBUTING.md)
- [许可证](./LICENSE)

## 🗺️ 版本

- `v0.1.0`：首个正式定义版本，完成核心 CLI 骨架与基础命令集

## 📜 许可

本项目采用 `MIT` 许可证。
