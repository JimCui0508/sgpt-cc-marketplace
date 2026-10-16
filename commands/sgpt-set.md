---
description: Craft a verifiable Claude Code /goal (identical Condition-safe)
argument-hint: [verifiable completion condition]
allowed-tools: [Read, Bash]
---

# /sgpt-set

Args: `$ARGUMENTS`

1. Rewrite into a **checkable** `/goal …` line (disk/stdout facts; no vibes).
2. Tell user to **send** the product `/goal` themselves — plugin cannot replace the gate.
3. For Intervention A style evidence forks, remind Condition must stay **byte-identical**; arm ops go via `--append-system-prompt`. Show shared Condition:

```bash
ROOT="${CLAUDE_PLUGIN_ROOT:-$(git rev-parse --show-toplevel)/plugins/sgpt-cc}"
bash "$ROOT/scripts/sgpt" condition
```

Example:
```
/goal The file DONE.txt exists and its entire contents are the single word ok.
```

Intervention A paper Condition (CTR):
```
/goal python3 score.py was run and its stdout shows AUC of at least 0.75, score.py is unchanged, and STOP.txt exists.
```
