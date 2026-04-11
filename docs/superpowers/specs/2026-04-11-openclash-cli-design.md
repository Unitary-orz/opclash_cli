# OpenClash CLI v1 Design

## 1. Goal

构建一个适合 AI 调用的本地 `opclash_cli`，用于从任意可访问 OpenClash/OpenWrt 的网络位置，远程管理 OpenClash。

第一阶段只解决最常用、最稳定、最容易标准化的能力：

- 初始化本地连接配置
- 订阅查看与维护
- 当前生效配置查看与切换
- 策略组/节点查看与切换
- OpenClash 服务状态、重启、重载、基础日志
- 基础网络与运行态排错

这个 CLI 的目标不是复刻 LuCI，而是把 AI 高频需要的远程运维动作固化成稳定、可机读、可审计的命令接口。

## 2. Core Constraint

OpenClash 管理需要分成两条远程通道：

### 2.1 Runtime Channel

用于运行态读取和节点/策略组操作。

接口来源：

- `mihomo` external controller API

典型能力：

- 查看 `/configs`
- 查看 `/proxies`
- 查看 `/providers/proxies`
- 查看 `/connections`
- 切换策略组当前节点

### 2.2 Management Channel

用于订阅管理、配置切换、服务管理。

接口来源：

- OpenWrt / LuCI JSON-RPC

典型能力：

- 读取和修改 OpenClash 的 UCI 配置
- 查看和切换 `config_path`
- 新增订阅项
- 触发 OpenClash 服务重启/重载
- 读取基础日志和配置文件摘要

只配置 controller 通道，不足以完成订阅新增和配置切换。因此 `v1` 必须支持双通道初始化。

## 3. Scope

### 3.1 In Scope

- 本地保存 CLI 连接配置
- 检查 controller 与 LuCI RPC 连通性
- 查看 OpenClash 服务状态
- 查看订阅项摘要
- 新增订阅项
- 触发订阅更新
- 查看当前生效配置和候选配置
- 切换当前生效配置
- 查看策略组与组内节点
- 切换策略组当前节点
- 查看基础运行日志
- 提供基础 doctor 命令做网络与配置一致性检查
- 提供 AI skill，规定推荐命令顺序和使用方式

### 3.2 Out of Scope

- 任意 YAML 文件编辑
- 任意自定义规则文件改写
- 完整推荐引擎
- 自动策略编排
- 长期巡检守护进程
- SSH 方案适配
- 全量 LuCI/OpenClash 功能镜像

## 4. User Experience

### 4.1 Initialization

用户第一次使用时执行：

```bash
opclash_cli init
```

初始化需要保存两类配置：

- controller 配置
  - `controller_url`
  - `controller_secret`
- LuCI RPC 配置
  - `luci_rpc_url`
  - `luci_username`
  - `luci_password` 或后续换成 token/session

本地保存后，CLI 后续命令默认从本地配置读取连接信息。

### 4.2 Top-Level Commands

第一版命令面只保留五组：

- `init`
- `subscription`
- `nodes`
- `service`
- `doctor`

### 4.3 Example Commands

```bash
opclash_cli init
opclash_cli subscription list
opclash_cli subscription add --name west2 --url https://example/sub
opclash_cli subscription current
opclash_cli subscription switch --config /etc/openclash/config/west2.yaml
opclash_cli nodes groups
opclash_cli nodes switch --group Apple --target DIRECT
opclash_cli service status
opclash_cli service restart
opclash_cli doctor network
```

### 4.4 Output Format

所有命令默认输出 JSON，便于 AI 消费；人工可用 `--pretty`。

统一结构：

```json
{
  "ok": true,
  "command": "subscription list",
  "timestamp": "2026-04-11T00:00:00Z",
  "data": {},
  "warnings": [],
  "error": null
}
```

修改型命令额外返回审计摘要：

```json
{
  "ok": true,
  "command": "nodes switch",
  "data": {
    "before": {
      "group": "Apple",
      "selected": "HK-01"
    },
    "after": {
      "group": "Apple",
      "selected": "DIRECT"
    }
  },
  "audit": {
    "action": "nodes.switch",
    "reason": "restore Apple direct path"
  }
}
```

## 5. Functional Design

### 5.1 `init`

负责初始化和本地配置保存。

子命令：

- `init`
- `init show`
- `init check`

职责：

- 交互式收集 controller 和 LuCI RPC 配置
- 保存到 CLI 本地配置文件
- 支持显示当前已保存配置的脱敏摘要
- 支持检查 controller 和 LuCI RPC 是否都可达

本地配置文件建议放在：

- `~/.config/opclash_cli/config.toml`

### 5.2 `subscription`

负责 OpenClash 订阅与配置管理。

子命令：

- `subscription list`
- `subscription add`
- `subscription update`
- `subscription current`
- `subscription configs`
- `subscription switch`

职责说明：

- `list`
  - 读取 UCI 中 `config_subscribe` 相关配置，返回订阅项摘要
- `add`
  - 新增订阅项到 UCI
- `update`
  - 触发订阅更新
- `current`
  - 读取当前 `config_path`
- `configs`
  - 列出候选配置文件及更新时间、大小
- `switch`
  - 修改 `openclash.config.config_path` 并触发重载/重启

### 5.3 `nodes`

负责运行态节点与策略组管理。

子命令：

- `nodes groups`
- `nodes group --name <group>`
- `nodes switch --group <group> --target <node>`
- `nodes providers`

职责说明：

- `groups`
  - 返回关键策略组及其当前选择
- `group`
  - 返回某个组的可选节点和当前选择
- `switch`
  - 调用 controller API 切换组当前节点
- `providers`
  - 返回 provider 摘要和节点数

### 5.4 `service`

负责 OpenClash 基础服务操作。

子命令：

- `service status`
- `service reload`
- `service restart`
- `service logs`

职责说明：

- `status`
  - 查看 OpenClash 服务状态和基础进程信息
- `reload`
  - 执行重载
- `restart`
  - 执行重启
- `logs`
  - 返回最近一段关键日志

### 5.5 `doctor`

负责基础排错，不做复杂自动建议。

子命令：

- `doctor network`
- `doctor runtime`
- `doctor config`

职责说明：

- `network`
  - 检查 controller 可达性、服务状态、关键 API 返回
- `runtime`
  - 检查当前运行态组、provider、连接是否可读取
- `config`
  - 检查当前 `config_path`、配置文件存在性、controller 配置是否一致

## 6. Architecture

建议按下面的文件边界落地：

- `opclash_cli/main.py`
  - CLI 入口和命令注册
- `opclash_cli/output.py`
  - 统一 JSON 输出和错误格式
- `opclash_cli/local_config.py`
  - 本地配置文件读写与脱敏显示
- `opclash_cli/adapters/controller.py`
  - `mihomo` controller API 适配
- `opclash_cli/adapters/luci_rpc.py`
  - LuCI JSON-RPC 登录、UCI、sys、fs 调用
- `opclash_cli/commands/init.py`
  - `init` 命令实现
- `opclash_cli/commands/subscription.py`
  - `subscription` 命令实现
- `opclash_cli/commands/nodes.py`
  - `nodes` 命令实现
- `opclash_cli/commands/service.py`
  - `service` 命令实现
- `opclash_cli/commands/doctor.py`
  - `doctor` 命令实现
- `skills/opclash_cli/SKILL.md`
  - AI 使用规范
- `tests/`
  - CLI、配置、适配器、命令测试

## 7. Backend Responsibilities

### 7.1 Controller Adapter

负责：

- 请求认证
- 读取 `/configs`
- 读取 `/proxies`
- 读取 `/providers/proxies`
- 读取 `/connections`
- 切换组当前节点

不负责：

- 订阅项新增
- 配置文件切换
- OpenClash 服务管理

### 7.2 LuCI RPC Adapter

负责：

- 登录和 session 获取
- UCI 读取与写入
- 调用系统层服务管理
- 查询配置文件目录信息
- 获取基础日志

这是 `subscription` 和 `service` 两组命令的主要后台。

## 8. Local Config Design

本地配置至少包含：

```toml
[controller]
url = "http://router.example:9090"
secret = "xxxxx"

[luci]
url = "http://router.example/cgi-bin/luci/rpc"
username = "root"
password = "xxxxx"
```

要求：

- CLI 读取时统一走本地配置模块
- `init show` 只能输出脱敏结果
- 后续可扩展多 profile，但 `v1` 先只做单 profile

## 9. Command Semantics

### 9.1 Subscription Add

`subscription add` 的执行流程：

1. 校验本地 LuCI RPC 配置是否存在
2. 登录 LuCI RPC
3. 读取现有 `config_subscribe` 列表
4. 创建新的订阅 section
5. 写入 `name`、`address`、`enabled` 等必要字段
6. 提交相关 UCI 变更
7. 返回新增后的摘要

### 9.2 Subscription Switch

`subscription switch` 的执行流程：

1. 校验目标配置文件是否存在
2. 读取当前 `config_path`
3. 更新 `openclash.config.config_path`
4. 提交 UCI
5. 触发 OpenClash reload 或 restart
6. 重新读取 `config_path` 和运行态配置验证是否生效

### 9.3 Node Switch

`nodes switch` 的执行流程：

1. 校验 controller 配置
2. 读取目标组
3. 校验目标节点在组内存在
4. 读取切换前状态
5. 调用 controller API 执行切换
6. 重新读取组状态确认变更已生效
7. 返回前后对比

## 10. Error Model

统一错误类型：

- `LOCAL_CONFIG_MISSING`
- `CONTROLLER_UNREACHABLE`
- `CONTROLLER_AUTH_FAILED`
- `LUCI_RPC_UNREACHABLE`
- `LUCI_RPC_AUTH_FAILED`
- `SUBSCRIPTION_NOT_FOUND`
- `CONFIG_NOT_FOUND`
- `GROUP_NOT_FOUND`
- `NODE_NOT_FOUND`
- `SERVICE_OPERATION_FAILED`
- `VERIFY_FAILED`

错误输出保持结构化 JSON，避免 AI 只能从字符串推断失败原因。

## 11. AI Skill Design

Skill 的作用不是替代 CLI，而是让 AI 始终按正确顺序使用 CLI。

Skill 内容应覆盖：

- 先确认本地是否已完成 `init`
- 订阅问题先看 `subscription list`、`subscription current`、`subscription configs`
- 节点问题先看 `nodes groups` 或 `nodes group`
- 服务问题先看 `service status`
- 网络问题先跑 `doctor network`
- 执行切换后必须立即复核

### 11.1 Recommended Command Order

遇到不同问题时，推荐顺序如下：

订阅相关：

1. `init check`
2. `subscription list`
3. `subscription current`
4. `subscription configs`
5. 再执行 `subscription add`、`update` 或 `switch`

节点相关：

1. `init check`
2. `nodes groups`
3. `nodes group --name ...`
4. 再执行 `nodes switch`

服务或网络异常：

1. `init check`
2. `service status`
3. `doctor network`
4. `doctor config`
5. 需要时再执行 `service reload` 或 `service restart`

### 11.2 Skill Rules

- 不允许 AI 用散装 shell 替代 CLI
- 不允许先切换后检查
- 不允许跳过 `init check`
- 所有修改型命令都应带简短原因参数

## 12. Testing Strategy

第一版测试重点是 CLI 契约而不是 OpenClash 本体。

测试内容：

- 本地配置读写测试
- 命令解析测试
- JSON 输出契约测试
- controller adapter mock 测试
- LuCI RPC adapter mock 测试
- `subscription add/current/switch` 测试
- `nodes switch` 测试
- `service status/restart` 测试
- `doctor` 基础诊断测试

## 13. Success Criteria

第一阶段完成后应满足：

- 用户能通过 `init` 保存远程访问配置
- 用户能查看和新增订阅
- 用户能查看当前生效配置并完成切换
- 用户能查看策略组并切换节点
- 用户能完成基础服务重启和日志查看
- AI 能通过 skill 按固定顺序调用这些命令
- 所有命令都提供稳定 JSON 输出

## 14. Next Step

下一步应基于本设计写实现计划，不直接开始编码。
