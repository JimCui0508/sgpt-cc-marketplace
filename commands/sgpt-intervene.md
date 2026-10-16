---
description: Intervention A — identical /goal Condition; print/omit/fake_low
argument-hint: [doc|aggregate|run|condition]
allowed-tools: [Bash, Read]
---

# /sgpt-intervene

```bash
ROOT="${CLAUDE_PLUGIN_ROOT:-$(git rev-parse --show-toplevel)/plugins/sgpt-cc}"
MODE="${ARGUMENTS:-doc}"
case "$MODE" in
  condition|ops) bash "$ROOT/scripts/sgpt" condition ;;
  aggregate) bash "$ROOT/scripts/sgpt" intervene aggregate ;;
  run*) echo "Live runs are expensive. Prefer: bash $ROOT/scripts/sgpt intervene doc"; bash "$ROOT/scripts/sgpt" intervene doc ;;
  *) bash "$ROOT/scripts/sgpt" intervene doc --show-ops ;;
esac
```

Stress: Condition identical; arm ops via append-system-prompt only; print→Met, omit/fake_low→NotYet on paper pack (6/6); not a model improver.
