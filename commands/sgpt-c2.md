---
description: C2 post-/goal status check (Goal active vs No goal set)
allowed-tools: [Bash]
---

```bash
bash "${CLAUDE_PLUGIN_ROOT:-$(git rev-parse --show-toplevel)/plugins/sgpt-cc}/scripts/sgpt" c2
```

Remind user to send bare product `/goal` now. Interpret Goal active vs No goal set. Met vs Impossible still needs C3.
