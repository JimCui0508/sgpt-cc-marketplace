---
name: sgpt
description: This skill should be used when the user asks about SGPT, Stop-Gate Process Tracing, Claude Code /goal exit class, Met vs NotYet vs Impossible, C1/C2/C3 channels, post-/goal status, debug hooks, receipt chains, independent clause checks, Intervention A print/omit/fake_low, or whether a stopped goal session really met its condition. Full observability protocol — not a model improver.
version: 1.1.0
---

# SGPT skill (full)

## Purpose

Guide operators through the **full SGPT protocol**:
1. Independent clause check (`full_condition_ok` / `independent_evid_full_ok`)
2. Receipt chain (Goal-set · Stop-hook feedback · STOP.txt)
3. Channel ladder C1 → C2 → C3
4. Intervention A under **byte-identical** `/goal` Condition

Do **not** claim this improves model quality. Fixture ≠ Web. No wrong-Met claims from soft heuristics when debug shows legal Impossible.

## Prefer commands / CLI

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" help
bash "${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" clause .
bash "${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" check .
bash "${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" auto
bash "${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" receipts --show-only
bash "${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" c1|c2|c3
bash "${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" intervene doc
```

Slash: `/sgpt` `/sgpt-set` `/sgpt-check` `/sgpt-clause` `/sgpt-receipts` `/sgpt-c1` `/sgpt-c2` `/sgpt-c3` `/sgpt-intervene` `/sgpt-auto`

## Hooks (after `/sgpt-set`)

SessionStart and Stop run only when `.sgpt/goal.json` (or `.sgpt/clauses.json` / `.sgpt/goal.txt`) exists. Stop reuses `sgpt clause` + a receipt append. Default does **not** exit 2. `SGPT_AUTO_CONTINUE=1` may block Stop on **NotYet** only, up to `SGPT_AUTO_CONTINUE_MAX` (default 2). `SGPT_AUTO_LAB=1` only notes that C1–C3 and intervene exist. `SGPT_HOOKS=0`, `SGPT_AUTO=0`, or `disableAllHooks` silences hooks.

## Still product-manual

- Real `/goal` gate = Claude Code product (hooks do not send it)
- C3 requires `--debug-file` + `--debug hooks` at session start (hooks do not start that)
- Live Intervention A runs need repo + proxy and `--i-mean-it` (hooks never call `fake_low` / `intervene`)

## Repo

Set `SGPT_REPO` if not discoverable. Harvest: `taxonomy` / `receipts` / `channel-table`.
