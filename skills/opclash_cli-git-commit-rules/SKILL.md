---
name: opclash_cli-git-commit-rules
description: Use this skill when the opclash_cli project needs repository-specific commit scope, summary language, and commit boundary guidance.
---

# opclash_cli Git Commit Rules

## Role

- This skill records commit facts and special constraints for the `opclash_cli` repository.
- Follow repository docs and `AGENT.md` if they are updated later.

## Project facts

- Allowed scopes: `init`, `nodes`, `subscription`, `service`, `doctor`, `repo`
- Preferred types: `feat`, `fix`, `refactor`, `test`, `docs`
- Preference overrides:
  - `summary_language`: `zh`
  - `body_style`: `medium`
  - `split_bias`: `medium`
- Avoided scopes: `config`, `adapter`, `output`, `tests`, `docs`, `misc`, `ui`, `backend`, `api`, `cli-backend`, mixed multi-domain scopes such as `nodes-service`
- Special constraints:
  - Use `type(scope): summary`
  - Prefer only these types: `feat`, `fix`, `refactor`, `test`, `docs`
  - Prefer summaries that describe behavior or capability changes in the CLI
  - Keep one commit focused on one command area or one coherent repository change
  - Changes to command behavior, output contract, or audit fields should usually include tests
  - Release, versioning, or packaging changes should prefer separate commits
  - Do not use `chore`, `build`, or `ci` unless the repository later adds an explicit need for them

## Scope guidance

- Use command-domain scopes for user-facing behavior:
  - `init`, `nodes`, `subscription`, `service`, `doctor`
- Collapse support-layer changes back into the command domain they serve:
  - config changes for initialization or local setup usually use `init`
  - adapter changes usually use the command domain they unblock, such as `nodes` or `service`
  - output changes use the command domain whose result shape changed
  - test-only changes also use the command domain they cover
- Use `repo` only for repository-wide tooling, ignore rules, project docs, or cross-command conventions

## Examples

- `feat(nodes): 新增节点组查询入口`
- `fix(service): 修复重启结果缺少审计信息`
- `refactor(init): 收敛本地配置读取与写入逻辑`
- `test(subscription): 补齐配置切换命令覆盖`
- `docs(repo): 补充项目级提交规范`
