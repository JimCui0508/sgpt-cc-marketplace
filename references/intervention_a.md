# Intervention A (identical Condition)

`GOAL_EVIDENCE` (shared across print/omit/fake_low):

> python3 score.py was run and its stdout shows AUC of at least 0.75, score.py is unchanged, and STOP.txt exists.

Arm-specific worker ops travel **only** via `--append-system-prompt` (never inside `/goal` text).

Paper outcomes (attached body A): print → met 6/6; omit → not_yet 6/6; fake_low → not_yet 6/6.

```bash
sgpt condition
sgpt intervene doc
sgpt intervene aggregate   # if product_runs present
```

Live re-run: see repo `results/REPRO.md` — expensive; needs Claude Code + proxy. `sgpt intervene run` still refuses without `--i-mean-it`. Plugin hooks never call `fake_low` or `intervene`.
