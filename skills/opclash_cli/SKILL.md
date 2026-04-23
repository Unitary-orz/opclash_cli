---
name: opclash_cli
description: Use when operating OpenClash remotely with this repository CLI, especially for diagnosis, subscription switching, node switching, reload, or restart workflows that need ordered verification.
---

# opclash_cli

## Overview

Use this skill to keep remote operations predictable and auditable.
Primary rule: run `opclash_cli init check` before any business command.

## Required preflight

Run this first:

```bash
opclash_cli init check
```

If preflight fails, do not continue with switch/reload/restart commands.

## Command order

Use fixed flows:

- Subscription flow: `init check` -> `subscription list` -> `subscription current` -> `subscription configs`
- Node flow: `init check` -> `nodes groups` -> `nodes group --name ...`
- Service/Network diagnosis: `init check` -> `service status` -> `doctor network` -> `doctor config`

## Mutation rule

- Every mutation command must include `--reason`.
- After `nodes switch`, rerun `nodes group --name ...` to confirm active node state.
- After `subscription switch`, rerun `subscription current` and `service status`.
- After `service reload` or `service restart`, rerun `service status`.

## Quick commands

```bash
opclash_cli subscription current
opclash_cli nodes group --name <group_name>
opclash_cli service status
opclash_cli doctor network
opclash_cli doctor config
```

## Common mistakes

- Running switch commands before `init check`
- Forgetting `--reason` on mutation commands
- Performing mutation without post-action verification
