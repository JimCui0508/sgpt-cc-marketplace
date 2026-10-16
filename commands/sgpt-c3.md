---
description: C3 debug hooks — parse Stop-hook ok/impossible
argument-hint: [debug-file]
allowed-tools: [Bash, Read]
---

```bash
ROOT="${CLAUDE_PLUGIN_ROOT:-$(git rev-parse --show-toplevel)/plugins/sgpt-cc}"
bash "$ROOT/scripts/sgpt" c3 ${ARGUMENTS}
```

If no debug file: show exact launch line `claude --debug-file /tmp/sgpt-debug.jsonl --debug hooks`.
