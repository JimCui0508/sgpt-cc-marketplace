---
description: Show SGPT hook automation status and how to set env flags
allowed-tools: [Bash, Read]
---

# /sgpt-auto

Show whether Stop / SessionStart hooks are armed, the recorded goal, the last receipt, and how to turn automation on or off.

```bash
ROOT="${CLAUDE_PLUGIN_ROOT}"
[ -z "$ROOT" ] && ROOT="$(git rev-parse --show-toplevel 2>/dev/null)/plugins/sgpt-cc"
bash "$ROOT/scripts/sgpt" auto
```

Explain the printed flags in the user's language:

| Flag | Effect |
|------|--------|
| `SGPT_HOOKS=0` or `SGPT_AUTO=0` | Hooks exit 0 immediately. No clause check, no receipt. |
| `disableAllHooks: true` | Claude Code turns **every** hook off (user, project, and plugin). |
| `SGPT_AUTO_CONTINUE=1` | Stop may `decision: block` only when the verdict is **NotYet**. |
| `SGPT_AUTO_CONTINUE_MAX` | How many NotYet blocks per session (default **2**). Met and Impossible never block. |
| `SGPT_AUTO_LAB=1` | One short note that `/sgpt-c1` `/sgpt-c2` `/sgpt-c3` `/sgpt-intervene` exist. Nothing is auto-run. |

Still manual, even when hooks are on:

- Product `/goal` (this plugin only stores `.sgpt/goal.json` via `/sgpt-set`)
- Starting a session with `--debug-file` / `--debug hooks`
- `/sgpt-c1`, `/sgpt-c2`, `/sgpt-c3`
- `/sgpt-intervene` — live `run` still needs `--i-mean-it`. Hooks never call `fake_low` or `intervene`.

Example (shell that launches `claude`):

```bash
export SGPT_AUTO_CONTINUE=1
export SGPT_AUTO_CONTINUE_MAX=2
export SGPT_AUTO_LAB=1
# turn automation off:
# export SGPT_HOOKS=0
```
