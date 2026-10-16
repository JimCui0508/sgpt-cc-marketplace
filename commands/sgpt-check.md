---
description: After stop — status, independent clause check, and an appended receipt
allowed-tools: [Read, Bash, Glob, Grep]
---

# /sgpt-check — full post-stop recovery

Same pieces the Stop hook runs when `.sgpt/goal.json` exists: `sgpt status`, `sgpt clause`, a receipt sketch, then one appended line in `.sgpt/receipts.jsonl`.

```bash
ROOT="${CLAUDE_PLUGIN_ROOT}"
[ -z "$ROOT" ] && ROOT="$(git rev-parse --show-toplevel 2>/dev/null)/plugins/sgpt-cc"
bash "$ROOT/scripts/sgpt" check .
```

Then tell the user:

1. **Verdict** (`Met` / `NotYet` / `Impossible`) and the appended **receipt id**.
2. **C2**: send bare product `/goal` → `Goal active` (retain) vs `No goal set` (cleared Met|Imp). The plugin does not send `/goal`.
3. Summarize `full_condition_ok` vs session success. Met requires `full_condition_ok`. Do not call Met from stream success.
4. If Met vs Impossible is unclear → **C3**: `claude --debug-file /tmp/sgpt-debug.jsonl --debug hooks` then `/sgpt-c3`. `--debug-file` is still product-owned.
5. Honesty: SGPT observes; fixture≠Web; no wrong-Met claim from soft heuristics alone. Impossible is not auto-continued. Live Intervention A is not part of this command.
