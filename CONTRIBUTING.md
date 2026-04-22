# Contributing

感谢关注 `opclash_cli`。贡献流程保持简单直接。

## 开发环境

- Python `3.11+`
- 推荐使用虚拟环境

安装：

```bash
python3 -m pip install -e .[dev]
```

## 提交流程

1. 保持改动聚焦，一个提交只做一件事
2. 优先补充或更新相关测试
3. 运行：

```bash
python3 -m pytest
```

4. 提交信息建议使用：

```text
type(scope): summary
```

示例：

```text
docs(readme): 精简项目首页并补齐标准文档
fix(service): 修复重启结果缺少审计信息
```

## 约定

- 保持 CLI 行为显式、稳定
- 输出结构尽量兼容既有脚本
- 新增参数应优先保持高频命令简洁

## 文档改动

文档应尽量：

- 简洁
- 准确
- 可直接复制执行

## License

By contributing, you agree that your contributions are licensed under the `MIT` License.
