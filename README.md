# opclash_cli

> 🧭 AI-native OpenClash 远程管理命令行工具

`opclash_cli` 是一个面向 OpenClash 的 Python 3.11 CLI，聚焦远程管理、订阅切换、节点切换、服务控制与基础诊断。

## ✨ 特性

- 统一入口，覆盖 `init`、`nodes`、`subscription`、`service`、`doctor`
- 输出结构化 JSON，便于脚本集成与自动化调用
- 读写命令边界清晰，常用操作保持简洁直接
- 适合 AI Agent、终端脚本和日常运维场景

## 📦 安装

```bash
python3 -m pip install -e .
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
python3 -m opclash_cli.main init check
```

3. 查看节点组

```bash
python3 -m opclash_cli.main nodes groups
```

4. 切换订阅配置

```bash
python3 -m opclash_cli.main subscription switch \
  --config example.yaml
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
- `subscription list`：列出订阅
- `subscription current`：查看当前配置
- `subscription configs`：列出配置文件
- `subscription add --name <name> --url <url>`：新增订阅
- `subscription update --name <name>`：更新订阅
- `subscription switch --config <file>`：切换配置
- `service status | reload | restart | logs`：服务状态与控制
- `doctor network | runtime | config`：基础诊断

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

安装开发依赖：

```bash
python3 -m pip install -e .[dev]
```

运行测试：

```bash
python3 -m pytest
```

查看帮助：

```bash
python3 -m opclash_cli.main --help
```

## 📚 文档

- [变更记录](./CHANGELOG.md)
- [贡献指南](./CONTRIBUTING.md)
- [许可证](./LICENSE)

## 🗺️ 版本

- `v0.1.0`：首个正式定义版本，完成核心 CLI 骨架与基础命令集

## 📜 许可

本项目采用 `MIT` 许可证。
