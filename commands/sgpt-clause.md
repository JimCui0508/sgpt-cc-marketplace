---
description: Independent clause check (metric_ok vs full_condition_ok)
argument-hint: [workspace-dir]
allowed-tools: [Bash, Read, Glob]
---

# /sgpt-clause

```bash
ROOT="${CLAUDE_PLUGIN_ROOT:-$(git rev-parse --show-toplevel)/plugins/sgpt-cc}"
WS="${ARGUMENTS:-.}"
bash "$ROOT/scripts/sgpt" clause $WS
```

Explain: `full_condition_ok` is external truth for GOAL_EVIDENCE-style goals; never call Met from stream success alone when `full_condition_ok=false`.
