# Project Agent Guide

## Overview

`opclash_cli` is a Python 3.11 command-line tool for remote OpenClash management.
The codebase is intentionally small and command-oriented:

- `opclash_cli/main.py`: CLI entrypoint and argument routing
- `opclash_cli/commands/`: user-facing command handlers
- `opclash_cli/adapters/`: integration layers for controller and LuCI RPC
- `opclash_cli/local_config.py`: local config persistence and lookup
- `opclash_cli/output.py`: structured CLI output helpers
- `tests/`: command and behavior coverage
- `skills/opclash_cli_skill/SKILL.md`: project-specific skill instructions

## Working Rules

- Prefer small, command-scoped changes over broad refactors.
- Keep CLI behavior explicit and stable; avoid hidden side effects.
- Preserve structured output shapes unless the task explicitly requires a breaking change.
- Add or update tests when changing command behavior, parsing, or output contracts.
- When touching remote-control actions like `switch`, `reload`, or `restart`, keep audit and reason fields intact.
- When editing docs, prefer coherent section rewrites over patch-style append-only changes.

## Local Commands

Install and run:

```bash
python3 -m pip install -e .
python3 -m pytest
python3 -m opclash_cli.main --help
python3 -m opclash_cli.main init check
```

If the editable install is not needed, direct module execution is preferred during development.

## Change Guidelines

- For new CLI capabilities, wire arguments in `opclash_cli/main.py` first, then implement command behavior in the matching module under `opclash_cli/commands/`.
- Keep adapter logic out of the CLI entrypoint.
- Prefer simple return dictionaries from command functions so `output.py` remains the single place responsible for final emission.
- Match existing naming patterns such as `service status`, `nodes switch`, and `sub add`.

## Testing Expectations

- Run `python3 -m pytest` after meaningful code changes.
- Add focused tests in `tests/` for any new command branch or changed behavior.
- If a command writes audit metadata, verify both result data and audit fields.

## Git Workflow

- Default branch is `main`.
- Use `type(scope): summary`.
- Prefer a small type set: `feat`, `fix`, `refactor`, `test`, `docs`.
- Keep each commit focused on one user-visible or business-meaningful change.
- Prefer summaries that describe what changed in behavior or capability, not just which files or code paths were edited.
- Prefer a small scope set centered on command domains: `init`, `nodes`, `subscription`, `service`, `doctor`, `repo`.
- Fold config, adapter, output, and test-only changes back into the command domain they actually serve.
- Prefer concise Chinese summaries by default unless the repository later standardizes on English.
- Good examples:
  - `feat(nodes): 新增节点组查询入口`
  - `fix(service): 修复重启结果缺少审计信息`
  - `test(subscription): 补齐配置切换命令覆盖`
- Before pushing, confirm the worktree is clean except for intended changes.

## Installed Skill

The Codex skill `git-commit-governance` is installed in the environment at `/root/.codex/skills/git-commit-governance`.
Use it when generating commit messages, judging commit scope, or defining project-specific commit rules.

Repository-local commit rules are documented in `docs/git-commit提交说明.md` and `skills/opclash_cli-git-commit-rules/SKILL.md`.
