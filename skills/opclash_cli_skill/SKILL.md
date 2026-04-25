---

## name: opclash_cli_skill

description: Use when operating OpenClash with opclash_cli, including router-local subscription/service management and remote Clash Controller node operations.
skill_version: 0.3.1
updated_at: 2026-04-25

# opclash_cli_skill

## Overview

Use this skill to operate OpenClash safely through `opclash_cli`.

Primary rule: run `opclash_cli init check` before any business command, then decide what is allowed from the JSON result.

Model assumptions for v0.3.1:

- Config stores only Clash Controller URL/secret.
- `nodes` commands can run from remote machines when the controller is reachable.
- System-level commands (`sub`, `service`, UCI/path-based config and log operations) must run on the OpenWrt router as root with `uci` available.

## Required preflight

Run this first:

```bash
opclash_cli init check
```

Read the JSON output:

- Continue with `nodes` commands only when `ok: true` and `data.controller_ok: true`.
- Continue with `sub` or `service` commands only when `ok: true` and `data.router_local_ok: true`.
- If `ok: false`, stop and report `error.code`, `error.message`, and safe `error.details`.
- If `router_local_ok: false`, do not retry `sub` or `service` from the same host; ask the user to run on the router.

Do not continue with switch, reload, restart, add, remove, rename, enable, disable, or update commands after a failed preflight.

## Command order

Use fixed flows and inspect JSON after every command.

- Subscription discovery: `init check` -> `sub list` -> `sub current` -> `sub configs`
- Subscription usage: `init check` -> `sub list` -> `sub usage --name <name>`
- Subscription update: `init check` -> `sub list` -> `sub update --name <name> --dry-run` -> `sub update --name <name> --yes`
- Config switch: `init check` -> `sub current` -> `sub configs` -> `sub switch --config <path> --dry-run` -> `sub switch --config <path> --yes` -> `sub current`
- Node flow: `init check` -> `nodes groups` -> `nodes group --name <group>` -> `nodes switch --group <group> --target <target> --dry-run` -> `nodes switch --group <group> --target <target> --yes` -> `nodes group --name <group>`
- Service diagnosis: `init check` -> `service status` -> `service logs` -> `doctor config`
- Local CLI diagnosis: `init check` -> `doctor network` -> `doctor runtime` -> `doctor config` -> `doctor logs --limit 20`

For `sub update`, also inspect `data.summary.overall_status`, `data.firewall.status`, and `data.suggested_commands`.

## Mutation rule

- Always prefer `--dry-run` before mutations when the command supports it.
- Use `--yes` for real mutations in non-interactive agent runs.
- Never invent config paths, subscription names, group names, or node names. Discover them first with read commands.
- Do not expose controller secrets or full subscription URLs in the final answer.
- Do not run `service restart` when `service reload` is enough for the user's goal.
- After `nodes switch`, rerun `nodes group --name ...` to confirm active node state.
- After `sub switch`, rerun `sub current` and `service status`.
- After `sub update`, inspect failed/skipped items and follow `suggested_commands` only if they are read-only.
- After `service reload` or `service restart`, rerun `service status`.

Mutation commands:

```bash
opclash_cli init
opclash_cli nodes switch
opclash_cli sub add
opclash_cli sub remove
opclash_cli sub enable
opclash_cli sub disable
opclash_cli sub rename
opclash_cli sub update
opclash_cli sub switch
opclash_cli service reload
opclash_cli service restart
```

## Quick commands

```bash
opclash_cli init check
opclash_cli sub list
opclash_cli sub current
opclash_cli sub configs
opclash_cli sub usage --name <subscription_name>
opclash_cli nodes group --name <group_name>
opclash_cli nodes speedtest --group <group_name> --limit 10
opclash_cli service status
opclash_cli service logs
opclash_cli doctor network
opclash_cli doctor config
opclash_cli doctor logs --limit 20
```

## JSON handling

All normal command output is JSON. Treat it as the source of truth.

Success shape:

```json
{
  "ok": true,
  "command": "sub current",
  "data": {}
}
```

Failure shape:

```json
{
  "ok": false,
  "command": "service status",
  "error": {
    "code": "LOCAL_ROUTER_REQUIRED",
    "message": "This command must be run locally on the router.",
    "details": {}
  }
}
```

Decision rules:

- If `ok` is false, stop the current action chain unless the next command is a safe read-only diagnostic.
- `LOCAL_ROUTER_REQUIRED`: ask the user to run the command on the OpenWrt router; do not keep retrying locally.
- `CONTROLLER_URL_MISSING` or `CONTROLLER_URL_INVALID`: guide the user to run `opclash_cli init --controller-url <url> --controller-secret <secret>`.
- `SUBSCRIPTION_NOT_FOUND`, `CONFIG_NOT_FOUND`, `GROUP_NOT_FOUND`, `NODE_NOT_FOUND`: run the matching list/detail command before suggesting a corrected value.
- `CONFIRM_ABORTED`: report that the user cancelled; do not retry with `--yes` unless explicitly asked.

## Common mistakes

- Running switch commands before `init check`
- Running `sub`/`service` system commands from a non-router host
- Using old `subscription` commands instead of v0.3 `sub`
- Assuming `service logs` accepts `--tail`; use `service logs` and inspect the returned tail
- Treating a command as successful without checking JSON `ok`
- Performing mutation without post-action verification

