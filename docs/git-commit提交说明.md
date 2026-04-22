# git commit 提交说明

本文档用于统一 `opclash_cli` 仓库的提交信息写法，便于按命令域和功能域追踪变更。

## 1. 提交格式

统一使用：

`<type>(<scope>): <summary>`

示例：

- `feat(nodes): 新增节点组查询入口`
- `fix(service): 修复重启结果缺少审计信息`
- `test(subscription): 补齐配置切换命令覆盖`
- `docs(repo): 更新 CLI 提交流程说明`

当一次提交仍然只表达一个目标，但需要补充关键影响面时，可以使用简短 body：

- `feat(subscription): 新增配置切换结果输出`
  - `- 补充切换前后配置对比`
  - `- 补充结果字段，便于脚本消费`

## 2. type 建议

本项目收紧为以下 5 类常用 type：

- `feat`：新增功能或新增命令能力
- `fix`：修复用户可感知问题、行为错误或结果错误
- `refactor`：整理实现，但不改变预期外部行为
- `test`：纯测试补充或测试结构调整
- `docs`：纯文档变更

使用建议：

- 能归到 `feat`、`fix`、`refactor` 时，不要再用更泛的仓库类 type
- 仓库脚本、忽略规则、小型配置整理，默认归到 `docs(repo)` 或 `refactor(repo)`，除非后续项目明确需要单独放开 `chore`
- 暂不作为常规 type 使用：`chore`、`build`、`ci`、`revert`

## 3. scope 约束

本项目优先使用命令域、配置域或仓库域作为 scope。

推荐 scope：

- `init`
- `nodes`
- `subscription`
- `service`
- `doctor`
- `repo`

使用规则：

- 一次提交只保留 1 个 scope
- 优先表达“改动服务于哪个命令或功能域”
- 配置、适配层、输出结构和测试改动，优先归到它们实际服务的命令域
- 只有仓库级约定、脚本、忽略规则、项目文档这类跨命令域变动，才使用 `repo`

不推荐 scope：

- `config`
- `adapter`
- `output`
- `tests`
- `docs`
- `cli-backend`
- `misc`
- `fixes`
- `ui`
- `api-db`

这类 scope 要么过于泛化，要么拼接多个域，不利于查看历史。

## 4. summary 写法

- 默认使用中文 summary
- 优先描述功能点变化、用户可感知结果或明确的行为变化
- 可以保留“修复”“补齐”“统一”“收敛”等动作词，但必须说清具体功能点
- 避免只写“修复问题”“优化代码”“调整逻辑”
- 如果一个提交里混入多个独立故事，优先拆分，而不是在 summary 里并列罗列

推荐：

- `feat(nodes): 新增节点组查询入口`
- `fix(service): 修复重启结果缺少审计信息`
- `refactor(init): 收敛本地配置写入与展示逻辑`
- `test(doctor): 补齐运行环境检查覆盖`
- `docs(repo): 补充项目级提交规范`

不推荐：

- `fix bug`
- `update code`
- `调整一下命令`
- `优化代码`
- `feat(nodes): 修复切换并补测试并改输出`

## 5. 提交前检查

- 确认这次提交只表达一件清晰的事
- 确认工作区和暂存区没有混入无关文件
- 优先检查暂存改动的整体范围，再决定是否需要查看完整 diff
- 如果改动跨多个独立命令域，优先考虑拆分提交
- commit-only 任务默认不顺手改代码

常用检查命令：

- `git status --short`
- `git diff --cached --stat`
- `git diff --cached`

## 6. 特殊约束

- 不要使用 `--no-gpg-sign`
- 如果签名失败，应先处理签名问题，不要绕过
- 涉及发布、版本号、打包或仓库级流程的改动，优先单独提交
- 若修改命令行为或输出结构，应同步补测试

## 7. 项目偏好

- 项目名：`opclash_cli`
- `summary_language`：`zh`
- `body_style`：`medium`
- `split_bias`：`medium`

建议把提交历史写成“看标题就知道哪个命令域发生了什么变化”的风格。
