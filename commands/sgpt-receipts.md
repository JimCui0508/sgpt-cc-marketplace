---
description: Receipt chain — Goal-set · Stop feedback · STOP.txt (wraps sgpt_receipts)
argument-hint: [--show-only] [debug-file]
allowed-tools: [Bash, Read]
---

# /sgpt-receipts

```bash
ROOT="${CLAUDE_PLUGIN_ROOT:-$(git rev-parse --show-toplevel)/plugins/sgpt-cc}"
if echo "$ARGUMENTS" | grep -q show-only; then
  FILE=$(echo "$ARGUMENTS" | awk '{for(i=1;i<=NF;i++) if($i!~/^--/) {print $i; exit}}')
  bash "$ROOT/scripts/sgpt" receipts --show-only --file "${FILE:-/tmp/sgpt-debug.jsonl}"
else
  bash "$ROOT/scripts/sgpt" receipts
fi
```

Summarize chain: Goal-set → Stop-hook feedback → session end → STOP.txt. Harvest writes EVENT_CHAINS when repo present.
