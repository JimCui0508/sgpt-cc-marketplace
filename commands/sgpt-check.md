---
description: After stop — C2 reminder, status, clause, receipts, C3 tips
allowed-tools: [Read, Bash, Glob, Grep]
---

# /sgpt-check — full post-stop recovery

```bash
ROOT="${CLAUDE_PLUGIN_ROOT}"
[ -z "$ROOT" ] && ROOT="$(git rev-parse --show-toplevel 2>/dev/null)/plugins/sgpt-cc"
bash "$ROOT/scripts/sgpt" status
bash "$ROOT/scripts/sgpt" clause .
# optional local receipt sketch if debug present:
bash "$ROOT/scripts/sgpt" receipts --show-only --file "${SGPT_DEBUG_FILE:-/tmp/sgpt-debug.jsonl}" || true
```

Then tell the user:

1. **C2**: send bare product `/goal` → `Goal active` (retain) vs `No goal set` (cleared Met|Imp).
2. Summarize `status` + `clause` (`full_condition_ok` vs session success).
3. If Met vs Impossible unclear → **C3**: `claude --debug-file /tmp/sgpt-debug.jsonl --debug hooks` then `/sgpt-c3`.
4. Honesty: SGPT observes; fixture≠Web; no wrong-Met claim from soft heuristics alone.
