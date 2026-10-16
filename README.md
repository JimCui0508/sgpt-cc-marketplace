# sgpt-cc — SGPT 完整实现（Claude Code 插件）

**给奶奶也能看懂的说明**

Agent 说「干完了」，不等于目标真达成。有的是达成了（Met），有的是还没到（NotYet），有的是根本做不到（Impossible）。默认日志常常只写「停了」。

**SGPT**（Stop-Gate Process Tracing）就是一套把停工原因看清楚的办法：

1. **独立条款核查** — 对照磁盘/stdout 看条件是否真满足  
2. **收据链** — Goal-set → Stop 反馈 → STOP.txt  
3. **通道阶梯 C1→C2→C3** — 默认流 → 再发一次 `/goal` → 打开 debug  
4. **Intervention A** — 同一条 Condition 下改证据打印（print/omit/fake_low），看闸门会不会翻  

**它不会让模型变聪明**，只帮你看清退出。论文数字（0/41→20/41→41/41）是某一套 GPT 转发语料上的观测，不是万能保证。

---

## 一分钟安装

**本机仓库（推荐开发机）**

```bash
claude plugin marketplace add /Users/didi/Projects/goal-mode-policy/plugins
claude plugin install sgpt-cc@goal-mode-policy-plugins
```

若已装过 0.1.0 MVP：

```bash
claude plugin update sgpt-cc@goal-mode-policy-plugins
# 或卸载再装：
# claude plugin uninstall sgpt-cc@goal-mode-policy-plugins
# claude plugin install sgpt-cc@goal-mode-policy-plugins
```

**公开安装（GitHub marketplace）**

```bash
claude plugin marketplace add JimCui0508/sgpt-cc-marketplace
claude plugin install sgpt-cc@sgpt-cc-marketplace
```

Anthropic 目录（claude.ai/directory/manage）另需付费账号与审核；`claude-plugins-official` 不接受自助投稿。

**仅当前会话**

```bash
claude --plugin-dir /Users/didi/Projects/goal-mode-policy/plugins/sgpt-cc
```

需要跑条款/收据 harvest 时，保证能找到仓库：

```bash
export SGPT_REPO=/Users/didi/Projects/goal-mode-policy
```

---

## 命令一览

| 命令 | 作用 |
|------|------|
| `/sgpt` | 总览 / 把参数转给 CLI |
| `/sgpt-set` | 写成可核查目标，写入 `.sgpt/goal.json`（仍要你自己发产品 `/goal`） |
| `/sgpt-check` | 停后：status + clause + 追加收据 |
| `/sgpt-clause` | 独立条款核查 |
| `/sgpt-receipts` | 收据链 |
| `/sgpt-c1` `/sgpt-c2` `/sgpt-c3` | 通道阶梯（手动） |
| `/sgpt-intervene` | Intervention A 说明/聚合（手动；`run` 要 `--i-mean-it`） |
| `/sgpt-auto` | 钩子开没开、环境变量、最近一条收据 |

CLI（同样功能）：

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" help
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" status
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" clause .
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" check .
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" set --text "DONE.txt exists and contains ok"
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" auto
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" receipts --show-only
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" c2
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" c3 /tmp/sgpt-debug.jsonl
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" condition
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" intervene doc
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" channel-table
```

---

## 最短操作路径

1. `/sgpt-set <可核查条件>` 写入 `.sgpt/goal.json`，然后你自己发产品 `/goal`（插件不代发）  
2. 干活直到停（Stop 钩子会自动 clause + 收据；也可手动 `/sgpt-check`）  
3. **C2**：再发一次裸 `/goal` → `Goal active` / `No goal set`  
4. 看收据判定，或再跑 `sgpt clause`  
5. 要分清 Met vs Impossible：**C3**  
   `claude --debug-file /tmp/sgpt-debug.jsonl --debug hooks`  
6. 复现论文表：仓库内 `PYTHONPATH=src python3 -m goal_policy.…`（见 `results/REPRO.md`）

---

## 自动 vs 仍需手做

装上插件后，钩子就注册了。**没有目标文件时它们直接退出，不打断日常会话。** 先 `/sgpt-set`（或 `sgpt set --text "…"`）写好目标，之后才自动核查。

| 自动（有 `.sgpt/goal.json` 之后） | 仍需你 / 产品 |
|----------------------------------|----------------|
| **SessionStart**：短上下文 = 当前目标 + 最近一条收据 | 真正的 `/goal` 闸门（插件不代发） |
| **Stop**：跑与 `/sgpt-check` 相同的 `status` + `clause`，并往 `.sgpt/receipts.jsonl` 追加收据；stdout 是 `hookEventName: Stop` 的 JSON，里面有 Met / NotYet / Impossible 和 receipt id | 用 `--debug-file … --debug hooks` **启动**会话（C3）。钩子不代开 debug |
| 默认 **不** exit 2、**不** `decision: block` | `SGPT_AUTO_CONTINUE=1` 时，仅 **NotYet**（不是 Met / Impossible）且计数低于 `SGPT_AUTO_CONTINUE_MAX`（默认 2）才 block，让 Claude 继续改未满足条款 |
| `SGPT_AUTO_LAB=1` 时，会话里**提一句** C1–C3 / intervene 命令还在 | `/sgpt-c1` `/sgpt-c2` `/sgpt-c3` `/sgpt-intervene` 仍是 slash/CLI。钩子不跑 `fake_low` / `intervene`；现场多 seed 要 `sgpt intervene run --i-mean-it` |

目标文件（cwd 或向上到 git 根目录）：`.sgpt/goal.json`（`/sgpt-set` 写这个），也认 `.sgpt/clauses.json`、`.sgpt/goal.txt`。可用 `SGPT_GOAL_FILE` 指到别的路径。

自动判定沿用现有 `sgpt clause`（有仓库时是 `independent_evid_full_ok`）：**只有 `full_condition_ok` 才是 Met**；debug 里已有的 `"impossible": true` 才是 Impossible；其余是 NotYet。不另写一套核查器。自定义英文目标会写进上下文，但不会被当成第二条判定规则。

当前 Claude Code 里，Stop 的 `additionalContext` 也可能被产品当成「继续这一轮」的反馈（和 `decision: block` 共用次数上限）。本插件默认仍只在 `SGPT_AUTO_CONTINUE=1` 且判定为 NotYet 时才设置 `decision: block`（exit 0，不 exit 2）。不想要任何钩子反馈时，用下面的关闭方式。

### 环境变量

在启动 `claude` 的 shell 里导出（钩子继承这个环境）：

```bash
export SGPT_AUTO_CONTINUE=1          # 仅 NotYet 时 block Stop
export SGPT_AUTO_CONTINUE_MAX=2      # 每个会话最多继续几次（默认 2）
export SGPT_AUTO_LAB=1               # 只提示 C1–C3 / intervene 存在，不自动执行
export SGPT_REPO=/path/to/goal-mode-policy   # 才能跑到 full_condition_ok
export SGPT_DEBUG_FILE=/tmp/sgpt-debug.jsonl # 你自己用 --debug-file 写出的文件

# 立刻关掉本插件钩子（exit 0，不核查、不写收据）：
export SGPT_HOOKS=0
# 或者
export SGPT_AUTO=0
```

循环计数写在 `${CLAUDE_PLUGIN_DATA}/auto-continue/<session>.json`；没有该变量时写在项目 `.sgpt/auto-continue/`。换一条目标或换一个 session 会重新计数。

### 怎么关掉

1. **只关 SGPT 钩子**：`SGPT_HOOKS=0` 或 `SGPT_AUTO=0`。
2. **关掉所有 Claude Code 钩子**：在用户或项目 settings 里设 `"disableAllHooks": true`，或单次启动：

```bash
claude --settings '{"disableAllHooks": true}'
```

`/sgpt-auto` 会打印当前开关、目标文件和最近收据。

建议把项目里的 `.sgpt/` 放进 `.gitignore`（目标、收据、计数都在这里），除非你想提交它们。

---

## 发布状态

- **Anthropic 官方目录**（claude.ai/directory）：需公开 GitHub 仓 + 付费 claude.ai + 门户提交与审核；当前环境 GitHub 未连接，**未能代交**。  
- **自建 marketplace**：把本插件推到公开 GitHub（建议仓名 `sgpt-cc-marketplace`，根目录含 `.claude-plugin/marketplace.json` + 插件），他人即可：  
  `claude plugin marketplace add JimCui0508/sgpt-cc-marketplace`  
- **不能**自行写入 `claude-plugins-official`（需 Anthropic 伙伴渠道）。

---

## 布局

```
plugins/sgpt-cc/   (this repo: plugin root = repository root)
  .claude-plugin/plugin.json   # v1.1.0
  .claude-plugin/marketplace.json
  README.md
  hooks/hooks.json             # SessionStart, Stop, opt-in lab note
  commands/                    # /sgpt* slash commands, including /sgpt-auto
  skills/sgpt/SKILL.md
  scripts/sgpt  sgpt_cli.py  sgpt-status
  references/{channels,intervention_a}.md
```

Marketplace：`plugins/.claude-plugin/marketplace.json`（name: `goal-mode-policy-plugins`）。
