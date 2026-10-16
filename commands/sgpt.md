---
description: SGPT full help — Stop-Gate Process Tracing (clause/receipts/C1–C3/Intervention A)
argument-hint: [help|status|clause|receipts|c1|c2|c3|intervene|condition|channel-table]
allowed-tools: [Read, Bash, Glob, Grep]
---

# /sgpt — unified SGPT entry

User args: `$ARGUMENTS`

## Run the full CLI

```bash
ROOT="${CLAUDE_PLUGIN_ROOT}"
[ -z "$ROOT" ] && ROOT="$(git rev-parse --show-toplevel 2>/dev/null)/plugins/sgpt-cc"
ARGS="${ARGUMENTS:-help}"
bash "$ROOT/scripts/sgpt" $ARGS
```

If args empty, print overview in Chinese (unless user wrote English):

**SGPT** = 停工时看清退出类（Met / NotYet / Impossible / retain）。不是模型改进器。

| 子命令 | 作用 |
|--------|------|
| `status` | STOP.txt + debug 扫描 |
| `clause` | 独立条款核查（`independent_evid_full_ok`） |
| `check` | status + clause + 追加一条本地收据 |
| `set --text` | 写入 `.sgpt/goal.json`（不发送产品 `/goal`） |
| `auto` | 钩子是否开启、环境变量、最近收据 |
| `receipts` | 收据链 harvest / 本地解析 |
| `c1` `c2` `c3` | 通道阶梯 |
| `condition` | 打印 Intervention A 相同 Condition |
| `intervene doc\|aggregate\|run` | Intervention A |
| `channel-table` | 论文 C1→C2→C3 表 |

Slash 别名：`/sgpt-set` `/sgpt-check` `/sgpt-clause` `/sgpt-receipts` `/sgpt-c1` `/sgpt-c2` `/sgpt-c3` `/sgpt-intervene` `/sgpt-auto`

诚实边界：真正 `/goal` 闸门仍是 Claude Code 产品；C3 需 `--debug-file`；论文数字是观测语料。钩子只在写过目标文件后做条款核查和收据，不自动跑 C1–C3，也不跑 Intervention A。
