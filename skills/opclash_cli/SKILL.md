---
name: opclash_cli
description: Use the local opclash_cli in a fixed order for OpenClash remote management.
---

## Rule

Always run `opclash_cli init check` first.

## Command order

- Subscription work: `init check` -> `subscription list` -> `subscription current` -> `subscription configs`
- Node work: `init check` -> `nodes groups` -> `nodes group --name ...`
- Service or network issues: `init check` -> `service status` -> `doctor network` -> `doctor config`

## Mutation rule

- Every mutation command must include `--reason`
- After `nodes switch`, rerun `nodes group --name ...`
- After `subscription switch`, rerun `subscription current` and `service status`
- After `service reload` or `service restart`, rerun `service status`
