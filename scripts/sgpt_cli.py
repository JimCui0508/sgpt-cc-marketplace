#!/usr/bin/env python3
"""SGPT full CLI for Claude Code plugin — wraps goal_policy; observability only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import subprocess
import sys
from datetime import datetime, timezone
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
  sgpt check [dir]       status + clause + append a local receipt (same as /sgpt-check)
  sgpt set --text "…"    write .sgpt/goal.json (does not send product /goal)
  sgpt auto              hook status and env flags
  sgpt receipts          harvest EVENT_CHAINS from product_runs (wraps sgpt_receipts)
  sgpt taxonomy          harvest taxonomy (wraps sgpt_taxonomy)
  sgpt c1|c2|c3          channel ladder guidance (+ parse debug for c3)
  sgpt intervene …       Intervention A: doc / aggregate / run (identical Condition)
  sgpt channel-table     print CHANNEL_RECOVERY summary if present
  sgpt condition         print byte-identical GOAL_EVIDENCE + arm ops

Slash commands in Claude Code:
  /sgpt  /sgpt-set  /sgpt-check  /sgpt-clause  /sgpt-receipts
  /sgpt-c1  /sgpt-c2  /sgpt-c3  /sgpt-intervene  /sgpt-auto

Still needs Claude product /goal for the real gate.
C3 needs you to start with --debug-file … --debug hooks.
SessionStart/Stop checks run only after /sgpt-set writes .sgpt/goal.json.
SGPT_AUTO_LAB=1 only notes that C1–C3 remain manual.
They do not send /goal, start debug sessions, or run Intervention A.
Disable hooks: SGPT_HOOKS=0 or SGPT_AUTO=0, or Claude disableAllHooks.
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


def debug_marker_counts(text: str) -> dict:
    """Same Stop-hook markers sgpt c3 / sgpt-status already count."""
    text = text or ""
    return {
        "goal_set": len(re.findall(r"Goal set:", text)),
        "goal_active": len(re.findall(r"Goal active:", text)),
        "no_goal": len(re.findall(r"No goal set", text)),
        "ok_true": len(re.findall(r'"ok"\s*:\s*true', text)),
        "ok_false": len(re.findall(r'"ok"\s*:\s*false', text)),
        "impossible": len(re.findall(r'"impossible"\s*:\s*true', text)),
    }


def discover_debug_file() -> Path | None:
    if os.environ.get("SGPT_DEBUG_FILE"):
        return Path(os.environ["SGPT_DEBUG_FILE"]).expanduser()
    if os.environ.get("CLAUDE_DEBUG_FILE"):
        cand = Path(os.environ["CLAUDE_DEBUG_FILE"]).expanduser()
        if cand.exists():
            return cand
    for cand in (Path("/tmp/sgpt-debug.jsonl"), Path.home() / ".claude" / "debug" / "latest"):
        if cand.exists():
            return cand
    return None


def read_debug_markers(path: Path | None) -> dict:
    counts = {
        "ok_true": 0,
        "ok_false": 0,
        "impossible": 0,
        "goal_set": 0,
        "goal_active": 0,
        "no_goal": 0,
        "path": None,
    }
    if path is None or not path.is_file():
        return counts
    try:
        limit = int(os.environ.get("SGPT_STATUS_MAX_BYTES", "2000000") or "2000000")
    except ValueError:
        limit = 2_000_000
    text = path.read_bytes()[:limit].decode("utf-8", errors="replace")
    counts.update(debug_marker_counts(text))
    counts["path"] = str(path)
    return counts


def evaluate_clause(ws: Path, stdout: str | None = None) -> dict:
    """Independent clause check. Same facts as `sgpt clause` (not a second checker)."""
    ws = ws.resolve()
    stdout_path = Path(stdout).resolve() if stdout else None
    stdout_text = ""
    if stdout_path and stdout_path.exists():
        stdout_text = stdout_path.read_text(errors="replace")
    else:
        for cand in (
            ws / "stdout.txt",
            ws / "session.stdout.txt",
            Path("/tmp/sgpt-debug.jsonl"),
        ):
            if cand.exists() and cand.suffix in (".txt", ".jsonl", ".log"):
                if cand.suffix == ".txt":
                    stdout_text = cand.read_text(errors="replace")
                    stdout_path = cand
                    break

    files = _snapshot_workspace(ws)
    repo = find_repo()
    out: dict = {
        "workspace": str(ws),
        "stdout_file": str(stdout_path) if stdout_path else None,
        "honesty": "observability only; fixture≠Web; no wrong-Met claim",
    }
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

    if not repo:
        out["independent"] = None
        out["error"] = "goal_policy not found; generic STOP/metrics only"
        return out
    try:
        ensure_goal_policy()
        from goal_policy import goal_interp_recsys as rs

        indep = rs.independent_evid_full_ok(stdout_text, files)
        out["independent"] = indep
        out["metric_ok_note"] = (
            "metric_ok≈AUC alone; full_condition_ok needs score.py tool AUC≥0.75 "
            "+ score.py unchanged + STOP.txt (Intervention A definition)."
        )
    except SystemExit:
        out["independent"] = None
        out["error"] = "goal_policy not found; generic STOP/metrics only"
    except Exception as e:
        out["independent"] = None
        out["error"] = f"goal_policy clause check failed: {e}"[:300]
    return out


def print_clause_report(out: dict) -> None:
    print(json.dumps(out, indent=2, ensure_ascii=False))
    indep = out.get("independent")
    if not isinstance(indep, dict):
        return
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


def cmd_clause(args) -> int:
    ws = Path(args.workspace or ".").resolve()
    out = evaluate_clause(ws, args.stdout)
    print_clause_report(out)
    if not isinstance(out.get("independent"), dict):
        return 2
    return 0


def classify_verdict(clause: dict, markers: dict) -> str:
    """Met only from full_condition_ok. Impossible from the existing debug marker."""
    if int(markers.get("impossible") or 0) > 0:
        return "Impossible"
    indep = clause.get("independent")
    if isinstance(indep, dict) and indep.get("full_condition_ok") is True:
        return "Met"
    return "NotYet"


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


def _read_capped(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        limit = int(os.environ.get("SGPT_STATUS_MAX_BYTES", "2000000") or "2000000")
    except ValueError:
        limit = 2_000_000
    return path.read_bytes()[: max(0, limit)].decode("utf-8", errors="replace")


def local_receipt_view(debug_path: Path, stop_path: Path) -> dict:
    """Receipt sketch used by `sgpt receipts --show-only` and by Stop hooks."""
    text = _read_capped(debug_path)
    stop = stop_path.read_text(errors="replace") if stop_path.is_file() else ""
    parsed = None
    repo = find_repo()
    if repo and debug_path.is_file():
        try:
            ensure_goal_policy()
            from goal_policy import sgpt_receipts

            parsed = sgpt_receipts._parse_events(debug_path.name, text)
        except (Exception, SystemExit):
            parsed = None
    if parsed is None:
        parsed = _local_parse_events(text)
    return {
        "file": str(debug_path),
        "exists": debug_path.exists(),
        "goal_set": parsed.get("goal_set"),
        "stop_fb": list(parsed.get("stop_fb") or []),
        "n_stop_hook_feedbacks": len(parsed.get("stop_fb") or []),
        "goal_achieved_marker": parsed.get("achieved"),
        "result_subtype": parsed.get("result_subtype"),
        "stop_exists": stop_path.exists(),
        "stop_prefix": stop[:120],
    }


def cmd_receipts(args) -> int:
    if args.show_only:
        path = Path(args.file or "/tmp/sgpt-debug.jsonl")
        stop_path = Path(args.stop or "./STOP.txt")
        view = local_receipt_view(path, stop_path)
        print("=== receipt chain (local file) ===")
        print(f"file: {path} exists={path.exists()}")
        print(f"goal_set: {view.get('goal_set')}")
        print(f"n_stop_hook_feedbacks: {view.get('n_stop_hook_feedbacks')}")
        for i, fb in enumerate((view.get("stop_fb") or [])[:5]):
            print(f"  stop_fb[{i}]: {str(fb)[:160].replace(chr(10), ' ')}")
        print(f"goal_achieved_marker: {view.get('goal_achieved_marker')}")
        print(f"result_subtype: {view.get('result_subtype')}")
        prefix = view.get("stop_prefix") or ""
        print(f"STOP.txt exists={stop_path.exists()} prefix={prefix[:120]!r}")
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
        try:
            limit = int(os.environ.get("SGPT_STATUS_MAX_BYTES", "2000000") or "2000000")
        except ValueError:
            limit = 2_000_000
        text = p.read_bytes()[:limit].decode("utf-8", errors="replace")
        marks = debug_marker_counts(text)
        print(f"--- scanning {p} ---")
        print(f"Goal set spans: {marks['goal_set']}")
        print(f"Goal active: {marks['goal_active']}")
        print(f"No goal set: {marks['no_goal']}")
        print(f"ok:true: {marks['ok_true']}")
        print(f"ok:false: {marks['ok_false']}")
        print(f"impossible:true: {marks['impossible']}")
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


GOAL_FILENAMES = ("goal.json", "clauses.json", "goal.txt")

LAB_NOTE = (
    "SGPT lab helpers exist and stay manual: /sgpt-c1, /sgpt-c2, /sgpt-c3, "
    "/sgpt-intervene (CLI: sgpt c1|c2|c3 and sgpt intervene). "
    "This hook does not send product /goal, does not start a --debug-file session, "
    "and does not run Intervention A. Live fake_low/intervene still needs --i-mean-it."
)


def hooks_disabled() -> bool:
    return os.environ.get("SGPT_HOOKS") == "0" or os.environ.get("SGPT_AUTO") == "0"


def lab_enabled() -> bool:
    return os.environ.get("SGPT_AUTO_LAB") == "1"


def auto_continue_enabled() -> bool:
    return os.environ.get("SGPT_AUTO_CONTINUE") == "1"


def auto_continue_max() -> int:
    raw = os.environ.get("SGPT_AUTO_CONTINUE_MAX", "2")
    try:
        n = int(str(raw).strip())
    except (TypeError, ValueError):
        n = 2
    return max(0, n)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def new_receipt_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"rcpt-{stamp}-{secrets.token_hex(2)}"


def goal_fingerprint(goal: str) -> str:
    return hashlib.sha256(goal.encode("utf-8")).hexdigest()[:16]


def read_hook_input() -> dict:
    try:
        if sys.stdin.isatty():
            return {}
    except Exception:
        return {}
    raw = sys.stdin.read()
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def apply_hook_cwd(data: dict) -> None:
    cwd = data.get("cwd")
    if isinstance(cwd, str) and cwd:
        path = Path(cwd).expanduser()
        if path.is_dir():
            os.chdir(path)


def emit_hook(event: str, additional: str, decision: str | None = None, reason: str | None = None) -> None:
    payload: dict = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": additional,
        }
    }
    if decision:
        payload["decision"] = decision
        if reason:
            payload["reason"] = reason
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _search_roots() -> list[Path]:
    roots: list[Path] = []
    cwd = Path.cwd().resolve()
    roots.append(cwd)
    cur = cwd
    for _ in range(8):
        if cur not in roots:
            roots.append(cur)
        git = cur / ".git"
        if git.exists() or cur.parent == cur:
            break
        cur = cur.parent
    proj = os.environ.get("CLAUDE_PROJECT_DIR")
    if proj:
        roots.append(Path(proj).expanduser())
    ordered: list[Path] = []
    seen: set[Path] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            continue
        if resolved in seen:
            continue
        seen.add(resolved)
        ordered.append(resolved)
    return ordered


def find_goal_file() -> Path | None:
    """Goal file written by /sgpt-set: .sgpt/goal.json, else clauses.json or goal.txt."""
    env = os.environ.get("SGPT_GOAL_FILE")
    if env:
        path = Path(env).expanduser()
        return path if path.is_file() else None
    for root in _search_roots():
        for name in GOAL_FILENAMES:
            cand = root / ".sgpt" / name
            if cand.is_file():
                return cand
    return None


def load_goal(path: Path) -> dict:
    text = path.read_text(errors="replace")
    if path.suffix == ".txt":
        goal = text.strip()
        return {"goal": goal, "clauses": [goal] if goal else [], "path": str(path)}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        goal = text.strip()
        return {"goal": goal, "clauses": [goal] if goal else [], "path": str(path)}
    if isinstance(data, list):
        clauses = [str(item).strip() for item in data if str(item).strip()]
        return {"goal": "; ".join(clauses), "clauses": clauses, "path": str(path)}
    if isinstance(data, dict):
        goal = str(data.get("goal") or data.get("text") or "").strip()
        raw_clauses = data.get("clauses")
        if isinstance(raw_clauses, list):
            clauses = [str(item).strip() for item in raw_clauses if str(item).strip()]
        else:
            clauses = [goal] if goal else []
        if not goal:
            goal = "; ".join(clauses)
        return {"goal": goal, "clauses": clauses, "path": str(path)}
    return {"goal": "", "clauses": [], "path": str(path)}


def project_for_goal(path: Path) -> Path:
    if path.parent.name == ".sgpt":
        return path.parent.parent
    return path.parent


def active_goal() -> tuple[Path, dict] | None:
    path = find_goal_file()
    if path is None:
        return None
    goal = load_goal(path)
    if not (goal.get("goal") or "").strip():
        return None
    return path, goal


def plugin_data_dir() -> Path | None:
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    if data and str(data).strip():
        return Path(data).expanduser()
    return None


def _safe_session(session_id: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "default")
    return (cleaned or "default")[:80]


def state_base(create: bool) -> Path:
    base = plugin_data_dir() or (Path.cwd() / ".sgpt")
    if create:
        base.mkdir(parents=True, exist_ok=True)
    return base


def counter_path(session_id: str) -> Path:
    return state_base(create=False) / "auto-continue" / f"{_safe_session(session_id)}.json"


def read_continue_n(session_id: str, goal_text: str) -> tuple[int, Path, str]:
    fp = goal_fingerprint(goal_text)
    path = counter_path(session_id)
    n = 0
    if path.is_file():
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict) and data.get("goal") == fp:
                n = int(data.get("n") or 0)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            n = 0
    return max(0, n), path, fp


def write_continue_n(path: Path, n: int, fingerprint: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"n": n, "goal": fingerprint}) + "\n")


def maybe_continue(session_id: str, goal_text: str, verdict: str) -> tuple[bool, int, int]:
    """Block Stop only for NotYet, when SGPT_AUTO_CONTINUE=1, while count < max."""
    maxn = auto_continue_max()
    n, path, fp = read_continue_n(session_id, goal_text)
    if verdict != "NotYet" or not auto_continue_enabled() or n >= maxn:
        return False, n, maxn
    n2 = n + 1
    write_continue_n(path, n2, fp)
    return True, n2, maxn


def consume_lab_note(session_id: str) -> str | None:
    if not lab_enabled():
        return None
    path = state_base(create=True) / "lab-noted" / _safe_session(session_id)
    if path.exists():
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("1\n")
    return LAB_NOTE


def last_receipt(ws: Path) -> dict | None:
    path = ws.resolve() / ".sgpt" / "receipts.jsonl"
    if not path.is_file():
        return None
    last = None
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            last = obj
    return last


def append_receipt(record: dict, ws: Path) -> str:
    rid = str(record.get("id") or new_receipt_id())
    record["id"] = rid
    path = ws.resolve() / ".sgpt" / "receipts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return rid


def capture_status(ws: Path, debug: Path | None) -> str:
    script = _plugin_root() / "scripts" / "sgpt-status"
    if not script.exists():
        return "sgpt-status missing\n"
    env = os.environ.copy()
    cmd = ["bash", str(script)]
    if debug is not None:
        env["SGPT_DEBUG_FILE"] = str(debug)
        cmd.append(str(debug))
    try:
        result = subprocess.run(
            cmd,
            env=env,
            cwd=str(ws),
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"sgpt-status error: {exc}\n"
    text = result.stdout or ""
    if result.stderr:
        text += ("\n" if text else "") + result.stderr
    return text


def perform_check(ws: Path, stdout: str | None) -> dict:
    """status + clause + receipt sketch, then append one local receipt. Same pieces as /sgpt-check."""
    ws = ws.resolve()
    debug = discover_debug_file()
    status_text = capture_status(ws, debug)
    clause = evaluate_clause(ws, stdout)
    markers = read_debug_markers(debug if debug is not None and debug.is_file() else None)
    debug_for_view = debug if debug is not None else Path("/tmp/sgpt-debug.jsonl")
    view = local_receipt_view(debug_for_view, ws / "STOP.txt")
    verdict = classify_verdict(clause, markers)
    indep = clause.get("independent") if isinstance(clause.get("independent"), dict) else {}
    rid = new_receipt_id()
    record = {
        "id": rid,
        "ts": now_utc(),
        "verdict": verdict,
        "full_condition_ok": indep.get("full_condition_ok"),
        "auc_ge_0_75": indep.get("auc_ge_0_75"),
        "score_py_unchanged": indep.get("score_py_unchanged"),
        "stop_exists": indep.get("stop_exists", (clause.get("stop") or {}).get("exists")),
        "clause_error": clause.get("error"),
        "debug_markers": {
            key: markers.get(key)
            for key in ("ok_true", "ok_false", "impossible", "goal_set", "goal_active", "no_goal", "path")
        },
        "receipt_chain": {
            "goal_set": view.get("goal_set"),
            "n_stop_hook_feedbacks": view.get("n_stop_hook_feedbacks"),
            "goal_achieved_marker": view.get("goal_achieved_marker"),
            "result_subtype": view.get("result_subtype"),
            "stop_exists": view.get("stop_exists"),
            "stop_prefix": (view.get("stop_prefix") or "")[:120],
        },
        "status_tail": (status_text or "")[-1500:],
        "source": "sgpt-check",
    }
    append_receipt(record, ws)
    return {
        "verdict": verdict,
        "receipt_id": rid,
        "clause": clause,
        "markers": markers,
        "receipt_view": view,
        "status_text": status_text,
        "full_condition_ok": indep.get("full_condition_ok"),
        "record": record,
    }


def format_session_context(goal: dict, last: dict | None, lab: str | None) -> str:
    lines = ["SGPT SessionStart (observability only)."]
    lines.append("Goal: " + str(goal.get("goal") or "")[:500])
    clauses = goal.get("clauses") or []
    if clauses:
        lines.append("Clauses: " + " | ".join(str(item) for item in clauses)[:500])
    if last:
        lines.append(
            f"Last receipt: {last.get('id')} verdict={last.get('verdict')} at {last.get('ts')}"
        )
    else:
        lines.append("Last receipt: none")
    lines.append("Product /goal and --debug-file are still yours. This plugin does not send them.")
    if lab:
        lines.append(lab)
    return "\n".join(lines)


def format_stop_context(goal: dict, result: dict, continued: bool, n: int, maxn: int) -> str:
    markers = result.get("markers") or {}
    lines = [
        "SGPT Stop check (sgpt status + sgpt clause + receipt append; same pieces as /sgpt-check).",
        f"Verdict: {result.get('verdict')}",
        f"Receipt: {result.get('receipt_id')}",
        f"full_condition_ok: {result.get('full_condition_ok')}",
        "Goal: " + str(goal.get("goal") or "")[:300],
        (
            "debug impossible={impossible} ok:true={ok_true} ok:false={ok_false}".format(
                impossible=markers.get("impossible", 0),
                ok_true=markers.get("ok_true", 0),
                ok_false=markers.get("ok_false", 0),
            )
        ),
    ]
    err = (result.get("clause") or {}).get("error")
    if err:
        lines.append(f"clause note: {err}")
    lines.append(
        "Met only when full_condition_ok is true. Session success is not Met. "
        "Impossible is never auto-continued."
    )
    if continued:
        lines.append(
            f"Auto-continue: decision block {n}/{maxn} because verdict is NotYet and SGPT_AUTO_CONTINUE=1."
        )
    else:
        lines.append(
            "Auto-continue: not blocking (no exit 2). "
            "Set SGPT_AUTO_CONTINUE=1 to block Stop only on NotYet, up to SGPT_AUTO_CONTINUE_MAX (default 2)."
        )
    lines.append("Product /goal is not sent. C1–C3 and Intervention A stay slash/CLI.")
    return "\n".join(lines)


def cmd_set(args) -> int:
    text = (args.text or "").strip()
    if not text and not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    if not text:
        print("ERROR: sgpt set needs --text (a checkable goal). It does not send product /goal.", file=sys.stderr)
        return 2
    clauses = [item.strip() for item in (args.clause or []) if item and item.strip()]
    if not clauses:
        clauses = [text]
    payload = {
        "version": 1,
        "goal": text,
        "clauses": clauses,
        "written_by": "sgpt-set",
        "written_at": now_utc(),
        "note": "Local SGPT goal file for hooks. Does not send product /goal or start a debug session.",
    }
    dest = Path(args.file).expanduser() if args.file else Path.cwd() / ".sgpt" / "goal.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote {dest}")
    print("Next: send the product /goal yourself. This file only arms SGPT SessionStart/Stop hooks.")
    return 0


def cmd_check(args) -> int:
    ws = Path(args.workspace or ".").resolve()
    try:
        result = perform_check(ws, getattr(args, "stdout", None))
    except Exception as exc:
        print(f"SGPT check failed: {exc}", file=sys.stderr)
        return 1
    print("=== SGPT check (status + clause + receipt) ===")
    print((result.get("status_text") or "").rstrip())
    print()
    print("=== clause ===")
    print_clause_report(result["clause"])
    print()
    view = result["receipt_view"]
    print("=== receipt chain (local file) ===")
    print(f"goal_set: {view.get('goal_set')}")
    print(f"n_stop_hook_feedbacks: {view.get('n_stop_hook_feedbacks')}")
    print(f"goal_achieved_marker: {view.get('goal_achieved_marker')}")
    print(f"STOP.txt exists={view.get('stop_exists')}")
    print(f"verdict: {result['verdict']}")
    print(f"appended receipt: {result['receipt_id']}")
    print("Honesty: observability only. Product /goal is not sent. Met requires full_condition_ok.")
    return 0


def cmd_auto(_args=None) -> int:
    disabled = hooks_disabled()
    found = active_goal()
    ws = Path.cwd()
    if found:
        ws = project_for_goal(found[0])
    last = last_receipt(ws) if found else last_receipt(Path.cwd())
    data = plugin_data_dir()
    counter_dir = (data or (Path.cwd() / ".sgpt")) / "auto-continue"
    print("=== SGPT auto ===")
    print(f"hooks_enabled: {str(not disabled).lower()}")
    print(f"SGPT_HOOKS: {os.environ.get('SGPT_HOOKS', '(unset)')}")
    print(f"SGPT_AUTO: {os.environ.get('SGPT_AUTO', '(unset)')}")
    print(
        "SGPT_AUTO_CONTINUE: "
        f"{os.environ.get('SGPT_AUTO_CONTINUE', '(unset)')}  "
        "(set to 1 to block Stop on NotYet only)"
    )
    print(
        "SGPT_AUTO_CONTINUE_MAX: "
        f"{os.environ.get('SGPT_AUTO_CONTINUE_MAX', '(unset, default 2)')}"
    )
    print(
        "SGPT_AUTO_LAB: "
        f"{os.environ.get('SGPT_AUTO_LAB', '(unset)')}  "
        "(set to 1 for a one-time C1–C3 / intervene note; nothing is auto-run)"
    )
    print("disableAllHooks: set true in Claude Code settings to turn every hook off")
    print("disable env: SGPT_HOOKS=0 or SGPT_AUTO=0 — hooks exit 0 immediately")
    if found:
        path, goal = found
        print(f"goal_file: {path}")
        print("goal: " + goal["goal"][:300])
    else:
        print("goal_file: none")
        print("goal: (none — /sgpt-set writes .sgpt/goal.json; until then hooks stay silent)")
    if last:
        print(f"last_receipt: {last.get('id')} verdict={last.get('verdict')} ts={last.get('ts')}")
    else:
        print("last_receipt: none")
    print(f"counter_dir: {counter_dir}")
    print(
        "still manual: product /goal; claude --debug-file … --debug hooks; "
        "/sgpt-c1 /sgpt-c2 /sgpt-c3; /sgpt-intervene (live run needs --i-mean-it)"
    )
    print("hooks do not send /goal, do not start debug sessions, and do not run fake_low or intervene.")
    return 0


def _prepare_hook_cwd(data: dict) -> tuple[dict, tuple[Path, dict] | None]:
    apply_hook_cwd(data)
    found = active_goal()
    if found:
        os.chdir(project_for_goal(found[0]))
    return data, found


def cmd_hook_session(_args=None) -> int:
    if hooks_disabled():
        return 0
    try:
        data = read_hook_input()
        data, found = _prepare_hook_cwd(data)
        session_id = str(data.get("session_id") or "default")
        lab = consume_lab_note(session_id)
        if not found:
            if lab:
                emit_hook("SessionStart", lab)
            return 0
        _path, goal = found
        emit_hook("SessionStart", format_session_context(goal, last_receipt(Path.cwd()), lab))
        return 0
    except (Exception, SystemExit) as exc:
        emit_hook("SessionStart", f"SGPT SessionStart error (observability only): {exc}"[:500])
        return 0


def cmd_hook_stop(_args=None) -> int:
    if hooks_disabled():
        return 0
    try:
        data = read_hook_input()
        data, found = _prepare_hook_cwd(data)
        if not found:
            return 0
        _path, goal = found
        result = perform_check(Path.cwd(), None)
        session_id = str(data.get("session_id") or "default")
        continued, n, maxn = maybe_continue(session_id, goal["goal"], str(result["verdict"]))
        text = format_stop_context(goal, result, continued, n, maxn)
        if continued:
            reason = (
                f"SGPT auto-continue {n}/{maxn}: verdict NotYet. "
                f"Independent clauses are not met (full_condition_ok={result.get('full_condition_ok')}). "
                f"Keep working on the recorded goal. Receipt {result['receipt_id']}. "
                "Do not claim Met. Product /goal was not sent."
            )
            emit_hook("Stop", text, decision="block", reason=reason)
        else:
            emit_hook("Stop", text)
        return 0
    except (Exception, SystemExit) as exc:
        emit_hook("Stop", f"SGPT Stop check error (not continuing): {exc}"[:500])
        return 0


def cmd_hook_prompt(_args=None) -> int:
    if hooks_disabled() or not lab_enabled():
        return 0
    try:
        data = read_hook_input()
        data, _found = _prepare_hook_cwd(data)
        session_id = str(data.get("session_id") or "default")
        lab = consume_lab_note(session_id)
        if not lab:
            return 0
        emit_hook("UserPromptSubmit", lab)
        return 0
    except (Exception, SystemExit):
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

    p_check = sub.add_parser("check")
    p_check.add_argument("workspace", nargs="?", default=".")
    p_check.add_argument("--stdout", default=None)

    p_set = sub.add_parser("set")
    p_set.add_argument("--text", default=None)
    p_set.add_argument("--clause", action="append")
    p_set.add_argument("--file", default=None)

    sub.add_parser("auto")
    sub.add_parser("hook-session")
    sub.add_parser("hook-stop")
    sub.add_parser("hook-prompt")

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
        "check": cmd_check,
        "set": cmd_set,
        "auto": cmd_auto,
        "hook-session": cmd_hook_session,
        "hook-stop": cmd_hook_stop,
        "hook-prompt": cmd_hook_prompt,
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
