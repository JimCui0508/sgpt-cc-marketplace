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
| `/sgpt-set` | 写可核查的 `/goal` |
| `/sgpt-check` | 停后：status + clause + C2/C3 提醒 |
| `/sgpt-clause` | 独立条款核查 |
| `/sgpt-receipts` | 收据链 |
| `/sgpt-c1` `/sgpt-c2` `/sgpt-c3` | 通道阶梯 |
| `/sgpt-intervene` | Intervention A 说明/聚合 |

CLI（同样功能）：

```bash
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" help
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" status
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" clause .
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" receipts --show-only
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" c2
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" c3 /tmp/sgpt-debug.jsonl
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" condition
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" intervene doc
"${CLAUDE_PLUGIN_ROOT}/scripts/sgpt" channel-table
```

---

## 最短操作路径

1. `/goal <可核查条件>`（产品命令，插件只提醒）  
2. 干活直到停  
3. **C2**：再发一次裸 `/goal` → `Goal active` / `No goal set`  
4. `/sgpt-check` 或 `sgpt clause`  
5. 要分清 Met vs Impossible：**C3**  
   `claude --debug-file /tmp/sgpt-debug.jsonl --debug hooks`  
6. 复现论文表：仓库内 `PYTHONPATH=src python3 -m goal_policy.…`（见 `results/REPRO.md`）

---

## 自动 vs 仍需手做

| 自动（插件） | 仍需你 / 产品 |
|--------------|----------------|
| 条款核查包装、收据解析、C1–C3 说明、Intervention A 文档与 aggregate | 真正的 `/goal` 闸门 |
| `sgpt status` 扫 STOP/debug | 用 `--debug-file` **启动**会话 |
| harvest taxonomy/receipts（有仓库时） | 现场 Intervention A 多 seed 跑（费钱，见 `intervene run`） |

---

## 发布状态

- **Anthropic 官方目录**（claude.ai/directory）：需公开 GitHub 仓 + 付费 claude.ai + 门户提交与审核；当前环境 GitHub 未连接，**未能代交**。  
- **自建 marketplace**：把本插件推到公开 GitHub（建议仓名 `sgpt-cc-marketplace`，根目录含 `.claude-plugin/marketplace.json` + 插件），他人即可：  
  `claude plugin marketplace add JimCui0508/sgpt-cc-marketplace`  
- **不能**自行写入 `claude-plugins-official`（需 Anthropic 伙伴渠道）。

---

## 布局

```
plugins/sgpt-cc/
  .claude-plugin/plugin.json   # v1.0.0
  README.md
  commands/                    # /sgpt* slash commands
  skills/sgpt/SKILL.md
  scripts/sgpt  sgpt_cli.py  sgpt-status
  references/{channels,intervention_a}.md
```

Marketplace：`plugins/.claude-plugin/marketplace.json`（name: `goal-mode-policy-plugins`）。
