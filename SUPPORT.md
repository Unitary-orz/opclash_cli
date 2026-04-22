# Support

建议先执行：

```bash
opclash_cli init check
opclash_cli doctor network
opclash_cli doctor config
```

### 1. 命令能连上但切换失败

先检查：

- Controller 地址和密钥是否正确
- 目标组或节点名是否真实存在
- 目标节点是否属于该组

推荐命令：

```bash
opclash_cli nodes group --name Apple
```

### 2. 配置切换失败

先确认：

- `--config` 传入的是远端完整路径
- 文件位于 `/etc/openclash/config` 或你指定的目录

推荐命令：

```bash
opclash_cli subscription configs
opclash_cli service logs
```

### 3. 服务异常

推荐顺序：

```bash
opclash_cli service status
opclash_cli doctor network
opclash_cli service logs
```

提交 issue 时建议附带：

- `opclash_cli version`
- 出错命令
- 返回的 JSON 错误信息
- 已执行过的排查命令
