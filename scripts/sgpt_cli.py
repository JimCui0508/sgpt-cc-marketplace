#!/usr/bin/env python3
"""SGPT full CLI for Claude Code plugin — wraps goal_policy; observability only."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path


def _plugin_root() -> Path:
    env = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[1]


def find_repo() -> Path | None:
    if os.environ.get("SGPT_REPO"):
        p = Path(os.environ["SGPT_REPO"]).expanduser().resolve()
        if (p / "src" / "goal_policy").is_dir():
            return p
    # marketplace installLocation → parent is repo
    km = Path.home() / ".claude" / "plugins" / "known_marketplaces.json"
    if km.exists():
        try:
            data = json.loads(km.read_text())
            gmp = data.get("goal-mode-policy-plugins") or {}
            loc = gmp.get("installLocation") or (gmp.get("source") or {}).get("path")
            if loc:
                cand = Path(loc).resolve()
                # plugins/ → repo; or already repo
                for p in (cand.parent, cand):
                    if (p / "src" / "goal_policy").is_dir():
                        return p
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    # walk from cwd / plugin
    starts = [Path.cwd()]
    try:
        import subprocess

        top = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        if top:
            starts.insert(0, Path(top))
    except Exception:
        pass
    starts.append(_plugin_root())
    starts.append(_plugin_root().parent.parent)
    for s in starts:
        cur = s.resolve()
        for _ in range(6):
            if (cur / "src" / "goal_policy").is_dir():
                return cur
            if cur.parent == cur:
                break
            cur = cur.parent
    return None


def ensure_goal_policy():
    repo = find_repo()
    if not repo:
        print(
            "ERROR: cannot find goal-mode-policy repo (need src/goal_policy).\n"
            "Set SGPT_REPO=/path/to/goal-mode-policy or run from the repo checkout.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    src = str(repo / "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    os.environ.setdefault("SGPT_REPO", str(repo))
    return repo


def cmd_help(_args=None) -> int:
    print(
        """SGPT — Stop-Gate Process Tracing (full Claude Code plugin)

Not a model improver. Observability protocol only.
Paper channel table (0/41→20/41→41/41) is observational on one GPT-stack pack.

Commands (CLI):
  sgpt help              this text
  sgpt status [debug]    STOP.txt + debug Stop-hook scan (C3 hints)
  sgpt clause [dir]      independent clause check (wraps independent_evid_full_ok)
  sgpt receipts          harvest EVENT_CHAINS from product_runs (wraps sgpt_receipts)
  sgpt taxonomy          harvest taxonomy (wraps sgpt_taxonomy)
  sgpt c1|c2|c3          channel ladder guidance (+ parse debug for c3)
  sgpt intervene …       Intervention A: doc / aggregate / run (identical Condition)
  sgpt channel-table     print CHANNEL_RECOVERY summary if present
  sgpt condition         print byte-identical GOAL_EVIDENCE + arm ops

Slash commands in Claude Code:
  /sgpt  /sgpt-set  /sgpt-check  /sgpt-clause  /sgpt-receipts
  /sgpt-c1  /sgpt-c2  /sgpt-c3  /sgpt-intervene

Still needs Claude product /goal for the real gate.
C3 needs you to start with --debug-file … --debug hooks.
"""
    )
    repo = find_repo()
    print(f"repo: {repo or '(not found — set SGPT_REPO)'}")
    print(f"plugin: {_plugin_root()}")
    return 0


def cmd_status(args) -> int:
    # Delegate to bash helper for parity with MVP, then enrich
    script = _plugin_root() / "scripts" / "sgpt-status"
    debug = args.debug_file or os.environ.get("SGPT_DEBUG_FILE") or ""
    env = os.environ.copy()
    if debug:
        env["SGPT_DEBUG_FILE"] = debug
    import subprocess

    if script.exists():
        cmd = ["bash", str(script)]
        if debug:
            cmd.append(debug)
        r = subprocess.run(cmd, env=env)
        return r.returncode
    print("sgpt-status missing", file=sys.stderr)
    return 1


def _snapshot_workspace(ws: Path) -> dict:
    snap: dict = {}
    for name in (
        "STOP.txt",
        "SCORE.txt",
        "KEEP_MARK.txt",
        "metrics.json",
        "feature_config.json",
        "history.jsonl",
        "decision_log.jsonl",
        "TASK.txt",
    ):
        p = ws / name
        if p.exists():
            snap[name] = p.read_text(errors="replace")[:4000]
    # Prefer goal_policy SCORE_PY compare when available
    score_py = ws / "score.py"
    if score_py.exists():
        try:
            ensure_goal_policy()
            from goal_policy import goal_interp_recsys as rs

            snap["score_py_unchanged"] = score_py.read_text() == rs.SCORE_PY
        except SystemExit:
            snap["score_py_unchanged"] = None
        except Exception as e:
            snap["score_py_unchanged"] = None
            snap["score_py_compare_error"] = str(e)[:200]
    else:
        snap["score_py_unchanged"] = False
    return snap


def cmd_clause(args) -> int:
    ws = Path(args.workspace or ".").resolve()
    stdout_path = Path(args.stdout).resolve() if args.stdout else None
    stdout = ""
    if stdout_path and stdout_path.exists():
        stdout = stdout_path.read_text(errors="replace")
    else:
        # common local artifacts
        for cand in (
            ws / "stdout.txt",
            ws / "session.stdout.txt",
            Path("/tmp/sgpt-debug.jsonl"),
        ):
            if cand.exists() and cand.suffix in (".txt", ".jsonl", ".log"):
                # only use .txt as stdout for AUC tool_result parse
                if cand.suffix == ".txt":
                    stdout = cand.read_text(errors="replace")
                    stdout_path = cand
                    break

    files = _snapshot_workspace(ws)
    repo = find_repo()
    out: dict = {
        "workspace": str(ws),
        "stdout_file": str(stdout_path) if stdout_path else None,
        "honesty": "observability only; fixture≠Web; no wrong-Met claim",
    }

    # Generic markers always
    stop = files.get("STOP.txt") or ""
    out["stop"] = {
        "exists": bool(stop.strip()),
        "GOAL_NOT_MET": "GOAL_NOT_MET" in stop,
        "silent_done": "silent_done" in stop.lower(),
        "prefix": stop[:200].replace("\n", "\\n"),
    }
    metrics = {}
    try:
        metrics = json.loads(files.get("metrics.json") or "{}")
    except json.JSONDecodeError:
        metrics = {}
    out["metrics_json_auc"] = metrics.get("auc")

    if repo:
        ensure_goal_policy()
        from goal_policy import goal_interp_recsys as rs

        indep = rs.independent_evid_full_ok(stdout, files)
        out["independent"] = indep
        out["metric_ok_note"] = (
            "metric_ok≈AUC alone; full_condition_ok needs score.py tool AUC≥0.75 "
            "+ score.py unchanged + STOP.txt (Intervention A definition)."
        )
        print(json.dumps(out, indent=2, ensure_ascii=False))
        print()
        print(
            f"full_condition_ok={indep.get('full_condition_ok')}  "
            f"auc_ge_0_75={indep.get('auc_ge_0_75')}  "
            f"score_py_unchanged={indep.get('score_py_unchanged')}  "
            f"stop_exists={indep.get('stop_exists')}"
        )
        if indep.get("full_condition_ok"):
            print("hint: independent clauses PASS under GOAL_EVIDENCE definition — still confirm C2/C3 exit class.")
        else:
            print("hint: independent clauses FAIL or incomplete — do not call Met from session success alone.")
    else:
        out["independent"] = None
        out["error"] = "goal_policy not found; generic STOP/metrics only"
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 2
    return 0


def _local_parse_events(text: str) -> dict:
    """Minimal receipt parse when goal_policy is unavailable."""
    events = []
    stop_fb = []
    achieved = False
    goal_set = bool(re.search(r"Goal set:", text or ""))
    result_subtype = None
    for line in (text or "").splitlines():
        if "Stop hook feedback" in line:
            stop_fb.append(line.strip()[:400])
        if line.strip().startswith("{"):
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            if o.get("type") == "user":
                content = o.get("message", {}).get("content")
                parts = content if isinstance(content, list) else []
                for c in parts:
                    if isinstance(c, dict):
                        tt = c.get("text") or ""
                        if tt.startswith("Stop hook feedback"):
                            stop_fb.append(tt[:400])
            if o.get("type") == "result":
                result_subtype = o.get("subtype")
                res = o.get("result") or ""
                if "Goal achieved" in res:
                    achieved = True
    return {
        "goal_set": goal_set,
        "stop_fb": stop_fb,
        "achieved": achieved,
        "result_subtype": result_subtype,
    }


def cmd_receipts(args) -> int:
    if args.show_only:
        path = Path(args.file or "/tmp/sgpt-debug.jsonl")
        text = path.read_text(errors="replace") if path.exists() else ""
        stop_path = Path(args.stop or "./STOP.txt")
        stop = stop_path.read_text(errors="replace") if stop_path.exists() else ""
        parsed = None
        repo = find_repo()
        if repo:
            try:
                ensure_goal_policy()
                from goal_policy import sgpt_receipts

                parsed = sgpt_receipts._parse_events(path.name, text)
            except Exception:
                parsed = None
        if parsed is None:
            parsed = _local_parse_events(text)
        print("=== receipt chain (local file) ===")
        print(f"file: {path} exists={path.exists()}")
        print(f"goal_set: {parsed.get('goal_set')}")
        nfb = len(parsed.get("stop_fb") or [])
        print(f"n_stop_hook_feedbacks: {nfb}")
        for i, fb in enumerate((parsed.get("stop_fb") or [])[:5]):
            print(f"  stop_fb[{i}]: {str(fb)[:160].replace(chr(10), ' ')}")
        print(f"goal_achieved_marker: {parsed.get('achieved')}")
        print(f"result_subtype: {parsed.get('result_subtype')}")
        print(f"STOP.txt exists={stop_path.exists()} prefix={stop[:120]!r}")
        print("chain sketch: Goal-set → Stop-hook feedback(s) → session end → STOP.txt")
        return 0

    repo = ensure_goal_policy()
    from goal_policy import sgpt_receipts

    out = sgpt_receipts.build()
    print(f"wrote EVENT_CHAINS under {sgpt_receipts.OUT_JSON}")
    # compact summary
    chains = out.get("chains") or out.get("runs") or []
    if isinstance(out, dict):
        keys = [k for k in out if k != "chains"]
        print(json.dumps({k: out[k] for k in keys if not isinstance(out[k], list)}, indent=2, default=str)[:2000])
    print(f"repo={repo}")
    return 0


def cmd_taxonomy(args) -> int:
    ensure_goal_policy()
    from goal_policy import sgpt_taxonomy

    out = sgpt_taxonomy.harvest()
    print(f"wrote {sgpt_taxonomy.OUT} n={out.get('n')} anomalies={out.get('anomaly_counts')}")
    return 0


def cmd_c1(_args) -> int:
    print(
        """=== C1 stream-only ===
Default Claude Code -p / chat stream.

What to look for: Goal achieved / Goal failed / session subtype.
On the paper pack: named exit class 0/41 — stream success ≠ goal class.

Operator: do NOT conclude Met from "session success" alone.
Next: /sgpt-c2 (bare /goal) or sgpt c2.
"""
    )
    return 0


def cmd_c2(_args) -> int:
    print(
        """=== C2 +post-/goal ===
After the run stops, YOU send the product slash command (no new condition):

  /goal

Read the reply:
  Goal active: …  → goal RETAINED (NotYet / keep / stop-with-retain)
  No goal set     → CLEARED — Met OR Impossible (C2 cannot split)

Paper pack: 20/41 named (all retained); cleared cases stay ambiguous.
Next for Met vs Impossible: sgpt c3 / start with --debug-file.
"""
    )
    return 0


def cmd_c3(args) -> int:
    print(
        """=== C3 +debug hooks ===
Start (or re-run) with:

  claude --debug-file /tmp/sgpt-debug.jsonl --debug hooks

Then parse Stop-hook JSON:
  ok:true          → Met (still confirm independent clauses)
  impossible:true  → Impossible clear
  ok:false + Goal active → retain

Paper pack: 41/41 named.
"""
    )
    debug = args.debug_file or os.environ.get("SGPT_DEBUG_FILE") or "/tmp/sgpt-debug.jsonl"
    p = Path(debug)
    if not p.exists():
        latest = Path.home() / ".claude" / "debug" / "latest"
        if latest.exists():
            p = latest
    if p.exists():
        text = p.read_bytes()[: int(os.environ.get("SGPT_STATUS_MAX_BYTES", "2000000"))].decode(
            "utf-8", errors="replace"
        )
        print(f"--- scanning {p} ---")
        print(f"Goal set spans: {len(re.findall(r'Goal set:', text))}")
        print(f"Goal active: {len(re.findall(r'Goal active:', text))}")
        print(f"No goal set: {len(re.findall(r'No goal set', text))}")
        n_ok_t = len(re.findall(r'"ok"\s*:\s*true', text))
        n_ok_f = len(re.findall(r'"ok"\s*:\s*false', text))
        n_imp = len(re.findall(r'"impossible"\s*:\s*true', text))
        print(f"ok:true: {n_ok_t}")
        print(f"ok:false: {n_ok_f}")
        print(f"impossible:true: {n_imp}")
    else:
        print(f"(no debug file yet at {debug}; create one with --debug-file)")
    return 0


def cmd_condition(_args) -> int:
    ensure_goal_policy()
    from goal_policy import goal_interp_intervene as iv

    print("=== Identical /goal Condition (Intervention A) ===")
    print(f"/goal {iv.GOAL_EVIDENCE}")
    print()
    print("Arm ops MUST go via --append-system-prompt (not inside Condition):")
    for v in ("print", "omit", "fake_low"):
        print(f"\n--- {v} ---")
        print(iv._evidence_worker_ops(v))
    print(
        "Honesty: Condition bytes identical across arms; only displayed evidence differs.\n"
        "Do not paste arm ops into /goal text (that re-confounds Claim-1)."
    )
    return 0


def cmd_intervene(args) -> int:
    repo = ensure_goal_policy()
    from goal_policy import goal_interp_intervene as iv

    mode = args.mode
    if mode == "doc" or mode is None:
        print("=== Intervention A (doc) ===")
        print("Shared Condition:", iv.GOAL_EVIDENCE)
        print("Variants: print → met 6/6; omit/fake_low → not_yet retained 6/6 (paper pack).")
        print("Module: python3 -m goal_policy.goal_interp_product_a")
        print("Also:   python3 -m goal_policy.goal_interp_intervene --cells evid_print,evid_omit,evid_fake_low")
        print(f"Repo: {repo}")
        print("See results/REPRO.md. Needs proxy + Claude Code; expensive.")
        if args.show_ops:
            cmd_condition(args)
        return 0

    if mode == "aggregate":
        # Prefer product_a_clean aggregate
        try:
            from goal_policy import goal_interp_product_a as pa

            print(json.dumps(pa._aggregate(), indent=2, default=str)[:8000])
        except Exception as e:
            print(f"product_a aggregate failed: {e}", file=sys.stderr)
            print(iv.render_report(iv.aggregate()))
        return 0

    if mode == "run":
        print(
            "WARNING: live Intervention A launches Claude Code runs (cost/time).\n"
            "Refusing automatic multi-seed launch from the plugin unless --i-mean-it.\n"
            "Recommended:\n"
            f"  cd {repo} && PYTHONPATH=src python3 -m goal_policy.goal_interp_product_a "
            "--seeds 0,1,2 --variants print,omit,fake_low\n"
            "Or intervene cells evid_print,evid_omit,evid_fake_low (see REPRO.md)."
        )
        if not args.i_mean_it:
            return 3
        from goal_policy import goal_interp_product_a as pa

        seeds = tuple(int(x) for x in (args.seeds or "0").split(",") if x.strip() != "")
        variants = tuple(x.strip() for x in (args.variants or "print").split(",") if x.strip())
        pa.run_batch(seeds=seeds, variants=variants, workers=1, force=bool(args.force))
        print(json.dumps(pa._aggregate(), indent=2, default=str)[:4000])
        return 0

    print(f"unknown intervene mode: {mode}", file=sys.stderr)
    return 1


def cmd_channel_table(_args) -> int:
    repo = find_repo()
    if not repo:
        print("repo not found", file=sys.stderr)
        return 2
    md = repo / "results" / "CHANNEL_RECOVERY.md"
    js = repo / "results" / "CHANNEL_RECOVERY.json"
    print("=== CHANNEL_RECOVERY (paper pack) ===")
    if md.exists():
        # print key table lines
        lines = md.read_text().splitlines()
        for i, line in enumerate(lines):
            if "overall" in line.lower() or line.startswith("| GT") or line.startswith("| correct") or line.startswith("| goal"):
                print(line)
            if "0/41" in line and "41/41" in line:
                print(line)
        print(f"\nfull: {md}")
    if js.exists():
        print(f"json: {js}")
    print("C1 0/41 → C2 20/41 → C3 41/41 (observational).")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="sgpt", description="SGPT full CLI")
    sub = ap.add_subparsers(dest="cmd")

    sub.add_parser("help", aliases=["h"])
    p_status = sub.add_parser("status")
    p_status.add_argument("debug_file", nargs="?", default=None)

    p_clause = sub.add_parser("clause", aliases=["check-clause", "indep"])
    p_clause.add_argument("workspace", nargs="?", default=".")
    p_clause.add_argument("--stdout", default=None)

    p_rec = sub.add_parser("receipts")
    p_rec.add_argument("--show-only", action="store_true")
    p_rec.add_argument("--file", default=None)
    p_rec.add_argument("--stop", default="./STOP.txt")

    sub.add_parser("taxonomy")
    sub.add_parser("c1")
    sub.add_parser("c2")
    p_c3 = sub.add_parser("c3")
    p_c3.add_argument("debug_file", nargs="?", default=None)

    sub.add_parser("condition", aliases=["goal-evidence"])

    p_iv = sub.add_parser("intervene", aliases=["int-a", "product-a"])
    p_iv.add_argument("mode", nargs="?", default="doc", choices=["doc", "aggregate", "run"])
    p_iv.add_argument("--show-ops", action="store_true")
    p_iv.add_argument("--seeds", default="0")
    p_iv.add_argument("--variants", default="print")
    p_iv.add_argument("--force", action="store_true")
    p_iv.add_argument("--i-mean-it", action="store_true")

    sub.add_parser("channel-table", aliases=["channels"])

    args = ap.parse_args(argv)
    cmd = args.cmd or "help"
    dispatch = {
        "help": cmd_help,
        "h": cmd_help,
        "status": cmd_status,
        "clause": cmd_clause,
        "check-clause": cmd_clause,
        "indep": cmd_clause,
        "receipts": cmd_receipts,
        "taxonomy": cmd_taxonomy,
        "c1": cmd_c1,
        "c2": cmd_c2,
        "c3": cmd_c3,
        "condition": cmd_condition,
        "goal-evidence": cmd_condition,
        "intervene": cmd_intervene,
        "int-a": cmd_intervene,
        "product-a": cmd_intervene,
        "channel-table": cmd_channel_table,
        "channels": cmd_channel_table,
    }
    fn = dispatch.get(cmd, cmd_help)
    return int(fn(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
