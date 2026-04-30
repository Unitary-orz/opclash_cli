---
name: opclash-patrol
description: Use when operating OpenClash with opclash_cli for routine patrol, deciding whether recent failures are node-level or subscription-level, and choosing safe node or backup-config switches with follow-up verification.
---

# Opclash Patrol

## Overview

- Use this skill for patrol and incident handling, not for generic subscription editing.
- Keep the flow light: diagnose -> choose candidate -> switch -> recheck.
- Treat `opclash_cli` JSON output as the source of truth.

## Start Here

Run these first:

```bash
opclash_cli init check
opclash_cli doctor availability --since 30m
```

Read `data.summary.status`:

- `healthy`: summarize and stop
- `observe`: summarize recent instability, but do not switch automatically
- `switch-node`: follow the node flow
- `fallback-subscription`: follow the subscription flow

## Node Flow

When `doctor availability` points to a node or group problem:

1. Inspect the suggested group:

```bash
opclash_cli nodes group --name <group>
```

2. Measure good candidates:

```bash
opclash_cli nodes speedtest --group <group> --limit 5
```

3. Prefer candidates that satisfy both:
- not flagged as unavailable by `doctor availability`
- lower delay than other remaining healthy choices

4. Switch carefully:

```bash
opclash_cli nodes switch --group <group> --target <target> --dry-run
opclash_cli nodes switch --group <group> --target <target> --yes
```

5. Recheck:

```bash
opclash_cli doctor availability --since 10m
```

Do not choose by latency alone.

## Subscription Flow

When `doctor availability` points to subscription-level failure:

- Do not blind switch subscriptions.
- Prefer explicit backup configs that are pre-agreed or user-provided.

Inspect current and available configs:

```bash
opclash_cli sub current
opclash_cli sub configs
```

If a backup config needs a minimal gate before switching, prefer checking whether it can refresh cleanly:

```bash
opclash_cli sub update --config <path> --dry-run
```

If the user wants a stronger check, or patrol policy allows it, run the real update before switching.

Switch carefully:

```bash
opclash_cli sub switch --config <path> --dry-run
opclash_cli sub switch --config <path> --yes
```

Then recheck:

```bash
opclash_cli doctor availability --since 10m
```

If the backup config still returns `fallback-subscription`, stop guessing and report that manual backup subscription selection is needed.

## Output Style

- Lead with what is broken: node, group, chain, or subscription.
- Then say what action you took.
- End with whether the recheck recovered service.

## Avoid

- switching nodes by latency only
- blindly switching to an unknown backup config
- claiming recovery without a recheck
