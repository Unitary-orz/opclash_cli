---
name: opclash_cli_skill
description: Use when operating OpenClash with this repository CLI, with router-local system operations and remote controller reads/switches.
skill_version: 0.3.0
updated_at: 2026-04-25
---

# opclash_cli_skill

## Overview

Use this skill to keep OpenClash operations predictable and auditable.
Primary rule: run `opclash_cli init check` before any business command.

Model assumptions for v0.3.0:

- Config stores only controller URL/secret.
- `nodes` commands work from remote machines when controller is reachable.
- System-level operations (`sub` CRUD/switch, `service`, UCI/path-based tasks) must run on the router locally with root and `uci` available.

## Required preflight

Run this first:

```bash
opclash_cli init check
```

If preflight fails, do not continue with switch/reload/restart commands.

## Command order

Use fixed flows:

- Subscription flow: `init check` -> `sub list` -> `sub current` -> `sub configs`
- Node flow: `init check` -> `nodes groups` -> `nodes group --name ...`
- Service/Network diagnosis: `init check` -> `service status` -> `doctor network` -> `doctor config`

## Mutation rule

- Prefer `--dry-run` before high-impact mutations.
- After `nodes switch`, rerun `nodes group --name ...` to confirm active node state.
- After `sub switch`, rerun `sub current` and `service status`.
- After `service reload` or `service restart`, rerun `service status`.

## Quick commands

```bash
opclash_cli sub current
opclash_cli nodes group --name <group_name>
opclash_cli service status
opclash_cli doctor network
opclash_cli doctor config
```

## Common mistakes

- Running switch commands before `init check`
- Running `sub`/`service` system commands from a non-router host
- Performing mutation without post-action verification

