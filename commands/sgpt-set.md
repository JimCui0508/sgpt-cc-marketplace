---
description: Craft a verifiable Claude Code /goal and record it for SGPT hooks
argument-hint: [verifiable completion condition]
allowed-tools: [Read, Bash]
---

# /sgpt-set

Args: `$ARGUMENTS`

1. If args are empty, ask for a checkable completion condition and stop. Do not write a goal file.
2. Rewrite the args into a **checkable** goal (disk or stdout facts; no vibes).
3. Persist that rewritten goal. This arms SessionStart/Stop hooks. It does **not** send product `/goal` and does **not** start a debug session:

```bash
ROOT="${CLAUDE_PLUGIN_ROOT:-$(git rev-parse --show-toplevel)/plugins/sgpt-cc}"
bash "$ROOT/scripts/sgpt" set --text "<rewritten checkable goal>"
```

4. Tell the user to **send** the product `/goal` themselves — the plugin cannot replace the gate.
5. For Intervention A style evidence forks, remind Condition must stay **byte-identical**; arm ops go via `--append-system-prompt`. If `SGPT_REPO` is available, show the shared Condition (`|| true` so a missing repo does not fail the set):

```bash
ROOT="${CLAUDE_PLUGIN_ROOT:-$(git rev-parse --show-toplevel)/plugins/sgpt-cc}"
bash "$ROOT/scripts/sgpt" condition || true
```

Example:
```
/goal The file DONE.txt exists and its entire contents are the single word ok.
```

Intervention A paper Condition (CTR):
```
/goal python3 score.py was run and its stdout shows AUC of at least 0.75, score.py is unchanged, and STOP.txt exists.
```

The automated Stop verdict uses `sgpt clause` (`independent_evid_full_ok` for that paper Condition). A custom sentence is stored and shown; it does not invent a second checker.
