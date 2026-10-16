#!/usr/bin/env python3
"""Black-box checks for SGPT Claude Code hooks. No goal_policy repo required."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "sgpt_cli.py"


def run(args, *, cwd, env, stdin="", timeout=30):
    proc = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=cwd,
        env=env,
        input=stdin,
        text=True,
        capture_output=True,
        timeout=timeout,
    )
    return proc


def base_env(tmp: Path) -> dict:
    env = os.environ.copy()
    for key in list(env):
        if key.startswith("SGPT_") or key in {
            "CLAUDE_PLUGIN_DATA",
            "CLAUDE_PLUGIN_ROOT",
            "CLAUDE_PROJECT_DIR",
            "CLAUDE_DEBUG_FILE",
        }:
            env.pop(key, None)
    env["HOME"] = str(tmp / "home")
    env["CLAUDE_PLUGIN_ROOT"] = str(ROOT)
    env["CLAUDE_PLUGIN_DATA"] = str(tmp / "plugin-data")
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    Path(env["CLAUDE_PLUGIN_DATA"]).mkdir(parents=True, exist_ok=True)
    return env


def write_goal(project: Path, text: str = "DONE.txt exists and contains ok") -> None:
    dest = project / ".sgpt"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "goal.json").write_text(
        json.dumps({"version": 1, "goal": text, "clauses": [text]}, ensure_ascii=False) + "\n"
    )


def hook_input(project: Path, session_id: str, event: str = "Stop") -> str:
    return json.dumps(
        {"session_id": session_id, "cwd": str(project), "hook_event_name": event}
    )


def parse_only_json(stdout: str) -> dict:
    text = stdout.strip()
    assert text, "expected JSON stdout"
    data = json.loads(text)
    assert isinstance(data, dict)
    return data


def stub_repo(tmp: Path, full_ok: bool) -> Path:
    repo = tmp / "stub-repo"
    pkg = repo / "src" / "goal_policy"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "goal_interp_recsys.py").write_text(
        textwrap.dedent(
            f"""
            def independent_evid_full_ok(stdout, files):
                return {{
                    "full_condition_ok": {full_ok!r},
                    "auc_ge_0_75": {full_ok!r},
                    "score_py_unchanged": True,
                    "stop_exists": True,
                }}
            """
        )
    )
    return repo


def test_hooks_json():
    raw = json.loads((ROOT / "hooks" / "hooks.json").read_text())
    assert "hooks" in raw and isinstance(raw["hooks"], dict)
    for event, sub in (
        ("SessionStart", "hook-session"),
        ("Stop", "hook-stop"),
        ("UserPromptSubmit", "hook-prompt"),
    ):
        groups = raw["hooks"][event]
        hook = groups[0]["hooks"][0]
        assert hook["type"] == "command"
        assert hook["command"] == "python3"
        assert hook["args"][0] == "${CLAUDE_PLUGIN_ROOT}/scripts/sgpt_cli.py"
        assert hook["args"][1] == sub
        assert "intervene" not in json.dumps(hook)
    blob = json.dumps(raw)
    assert "fake_low" not in blob
    assert "${CLAUDE_PLUGIN_ROOT}" in blob


def test_silent_without_goal(tmp: Path):
    project = tmp / "empty"
    project.mkdir()
    env = base_env(tmp)
    for cmd, event in (("hook-session", "SessionStart"), ("hook-stop", "Stop"), ("hook-prompt", "UserPromptSubmit")):
        proc = run([cmd], cwd=project, env=env, stdin=hook_input(project, "s", event))
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == "", proc.stdout
    assert not (project / ".sgpt" / "receipts.jsonl").exists()


def test_disable_flags(tmp: Path):
    project = tmp / "proj"
    project.mkdir()
    write_goal(project)
    for flag in ("SGPT_HOOKS", "SGPT_AUTO"):
        env = base_env(tmp)
        env[flag] = "0"
        env["SGPT_AUTO_CONTINUE"] = "1"
        env["SGPT_AUTO_LAB"] = "1"
        proc = run(
            ["hook-stop"],
            cwd=project,
            env=env,
            stdin=hook_input(project, "dis"),
        )
        assert proc.returncode == 0, proc.stderr
        assert proc.stdout == ""
        assert not (project / ".sgpt" / "receipts.jsonl").exists()
        sess = run(
            ["hook-session"],
            cwd=project,
            env=env,
            stdin=hook_input(project, "dis", "SessionStart"),
        )
        assert sess.returncode == 0 and sess.stdout == ""


def test_stop_notyet_no_block(tmp: Path):
    project = tmp / "notyet"
    project.mkdir()
    write_goal(project)
    env = base_env(tmp)
    proc = run(["hook-stop"], cwd=project, env=env, stdin=hook_input(project, "ny"))
    assert proc.returncode == 0, proc.stderr
    data = parse_only_json(proc.stdout)
    assert "decision" not in data
    ctx = data["hookSpecificOutput"]
    assert ctx["hookEventName"] == "Stop"
    assert "Verdict: NotYet" in ctx["additionalContext"]
    assert "Receipt: rcpt-" in ctx["additionalContext"]
    lines = (project / ".sgpt" / "receipts.jsonl").read_text().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["verdict"] == "NotYet"
    assert rec["id"] in ctx["additionalContext"]
    assert not (tmp / "plugin-data" / "auto-continue").exists()


def test_auto_continue_cap_and_impossible_and_met(tmp: Path):
    project = tmp / "cont"
    project.mkdir()
    goal = "AUC goal"
    write_goal(project, goal)
    env = base_env(tmp)
    env["SGPT_AUTO_CONTINUE"] = "1"
    env["SGPT_AUTO_CONTINUE_MAX"] = "2"
    env["SGPT_DEBUG_FILE"] = str(project / "missing-debug.jsonl")

    first = run(["hook-stop"], cwd=project, env=env, stdin=hook_input(project, "cap"))
    assert first.returncode == 0, first.stderr
    body = parse_only_json(first.stdout)
    assert body["decision"] == "block"
    assert "NotYet" in body["reason"]
    assert "Receipt: rcpt-" in body["hookSpecificOutput"]["additionalContext"]
    rid = json.loads((project / ".sgpt" / "receipts.jsonl").read_text().splitlines()[-1])["id"]
    assert rid in body["reason"]
    count = json.loads((tmp / "plugin-data" / "auto-continue" / "cap.json").read_text())
    assert count["n"] == 1

    second = run(["hook-stop"], cwd=project, env=env, stdin=hook_input(project, "cap"))
    assert parse_only_json(second.stdout)["decision"] == "block"
    count = json.loads((tmp / "plugin-data" / "auto-continue" / "cap.json").read_text())
    assert count["n"] == 2

    third = run(["hook-stop"], cwd=project, env=env, stdin=hook_input(project, "cap"))
    third_body = parse_only_json(third.stdout)
    assert "decision" not in third_body
    assert "Verdict: NotYet" in third_body["hookSpecificOutput"]["additionalContext"]
    count = json.loads((tmp / "plugin-data" / "auto-continue" / "cap.json").read_text())
    assert count["n"] == 2

    # Impossible wins over a stub Met and never blocks, even with continue armed.
    imp_project = tmp / "imp"
    imp_project.mkdir()
    write_goal(imp_project, goal)
    debug = imp_project / "debug.jsonl"
    debug.write_text('{"ok": false, "impossible": true}\n')
    env_i = base_env(tmp)
    env_i["SGPT_AUTO_CONTINUE"] = "1"
    env_i["SGPT_REPO"] = str(stub_repo(tmp, True))
    env_i["SGPT_DEBUG_FILE"] = str(debug)
    env_i["CLAUDE_PLUGIN_DATA"] = str(tmp / "plugin-data-imp")
    proc = run(["hook-stop"], cwd=imp_project, env=env_i, stdin=hook_input(imp_project, "imp"))
    assert proc.returncode == 0, proc.stderr
    body = parse_only_json(proc.stdout)
    assert "decision" not in body
    assert "Verdict: Impossible" in body["hookSpecificOutput"]["additionalContext"]
    assert "fake_low" not in proc.stdout

    met_project = tmp / "met"
    met_project.mkdir()
    write_goal(met_project, goal)
    env_m = base_env(tmp)
    env_m["SGPT_AUTO_CONTINUE"] = "1"
    env_m["SGPT_REPO"] = str(stub_repo(tmp / "metstub", True))
    env_m["SGPT_DEBUG_FILE"] = str(met_project / "no-debug.jsonl")
    env_m["CLAUDE_PLUGIN_DATA"] = str(tmp / "plugin-data-met")
    proc = run(["hook-stop"], cwd=met_project, env=env_m, stdin=hook_input(met_project, "met"))
    assert proc.returncode == 0, proc.stderr
    body = parse_only_json(proc.stdout)
    assert "decision" not in body
    assert "Verdict: Met" in body["hookSpecificOutput"]["additionalContext"]
    rec = json.loads((met_project / ".sgpt" / "receipts.jsonl").read_text().splitlines()[-1])
    assert rec["verdict"] == "Met"
    assert rec["full_condition_ok"] is True


def test_session_and_lab(tmp: Path):
    project = tmp / "sess"
    project.mkdir()
    write_goal(project, "keep the lamp on")
    env = base_env(tmp)
    stop = run(["hook-stop"], cwd=project, env=env, stdin=hook_input(project, "lab1"))
    rid = json.loads((project / ".sgpt" / "receipts.jsonl").read_text().splitlines()[-1])["id"]
    assert rid in stop.stdout

    env["SGPT_AUTO_LAB"] = "1"
    sess = run(
        ["hook-session"],
        cwd=project,
        env=env,
        stdin=hook_input(project, "lab1", "SessionStart"),
    )
    assert sess.returncode == 0, sess.stderr
    body = parse_only_json(sess.stdout)
    assert body["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    text = body["hookSpecificOutput"]["additionalContext"]
    assert "keep the lamp on" in text
    assert rid in text
    assert "verdict=NotYet" in text
    assert "/sgpt-c1" in text
    assert "does not send product /goal" in text
    assert "--i-mean-it" in text

    prompt = run(
        ["hook-prompt"],
        cwd=project,
        env=env,
        stdin=hook_input(project, "lab1", "UserPromptSubmit"),
    )
    assert prompt.returncode == 0 and prompt.stdout == ""

    other = run(
        ["hook-prompt"],
        cwd=project,
        env=env,
        stdin=hook_input(project, "other-session", "UserPromptSubmit"),
    )
    note = parse_only_json(other.stdout)
    assert note["hookSpecificOutput"]["hookEventName"] == "UserPromptSubmit"
    assert "does not run Intervention A" in note["hookSpecificOutput"]["additionalContext"]

    # Lab off: prompt stays silent even on a fresh session.
    env.pop("SGPT_AUTO_LAB")
    quiet = run(
        ["hook-prompt"],
        cwd=project,
        env=env,
        stdin=hook_input(project, "brand-new", "UserPromptSubmit"),
    )
    assert quiet.returncode == 0 and quiet.stdout == ""

    # No goal, lab on: SessionStart still notes helpers, Stop stays silent.
    bare = tmp / "bare"
    bare.mkdir()
    env["SGPT_AUTO_LAB"] = "1"
    env["CLAUDE_PLUGIN_DATA"] = str(tmp / "plugin-data-bare")
    noted = run(
        ["hook-session"],
        cwd=bare,
        env=env,
        stdin=hook_input(bare, "bare", "SessionStart"),
    )
    assert " /sgpt-c3" in parse_only_json(noted.stdout)["hookSpecificOutput"]["additionalContext"] or "/sgpt-c3" in noted.stdout
    stopped = run(["hook-stop"], cwd=bare, env=env, stdin=hook_input(bare, "bare"))
    assert stopped.returncode == 0 and stopped.stdout == ""
    assert not (bare / ".sgpt" / "receipts.jsonl").exists()


def test_set_auto_and_clause_regression(tmp: Path):
    project = tmp / "set"
    project.mkdir()
    env = base_env(tmp)
    proc = run(["set", "--text", "The file DONE.txt contains ok"], cwd=project, env=env)
    assert proc.returncode == 0, proc.stderr
    goal = json.loads((project / ".sgpt" / "goal.json").read_text())
    assert goal["goal"] == "The file DONE.txt contains ok"
    assert "does not send" in goal["note"].lower() or "Does not send" in goal["note"]
    assert "/goal" in proc.stdout

    auto = run(["auto"], cwd=project, env=env)
    assert auto.returncode == 0, auto.stderr
    assert "SGPT_AUTO_CONTINUE" in auto.stdout
    assert "SGPT_HOOKS" in auto.stdout
    assert "disableAllHooks" in auto.stdout
    assert "SGPT_AUTO_LAB" in auto.stdout
    assert "DONE.txt" in auto.stdout
    assert "fake_low" in auto.stdout  # documented as not auto-run

    missing = run(["set"], cwd=project, env=env)
    assert missing.returncode == 2

    clause = run(["clause", str(project)], cwd=project, env=env)
    assert clause.returncode == 2
    report = json.loads(clause.stdout)
    assert report["independent"] is None
    assert "goal_policy" in report["error"]

    versions = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text())
    assert versions["version"] == "1.1.0"
    assert market["plugins"][0]["version"] == "1.1.0"


def test_counter_falls_back_to_project_sgpt(tmp: Path):
    project = tmp / "fallback"
    project.mkdir()
    (project / ".sgpt").mkdir()
    (project / ".sgpt" / "clauses.json").write_text(
        json.dumps(["alpha clause", "beta clause"])
    )
    env = base_env(tmp)
    env.pop("CLAUDE_PLUGIN_DATA")
    env["SGPT_AUTO_CONTINUE"] = "1"
    env["SGPT_AUTO_CONTINUE_MAX"] = "2"
    proc = run(["hook-stop"], cwd=tmp, env=env, stdin=hook_input(project, "fb"))
    assert proc.returncode == 0, proc.stderr
    body = parse_only_json(proc.stdout)
    assert body["decision"] == "block"
    assert "alpha clause" in body["hookSpecificOutput"]["additionalContext"]
    count = json.loads((project / ".sgpt" / "auto-continue" / "fb.json").read_text())
    assert count["n"] == 1
    assert not (tmp / "plugin-data" / "auto-continue" / "fb.json").exists()


def main() -> int:
    import tempfile

    test_hooks_json()
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        test_silent_without_goal(tmp)
        test_disable_flags(tmp)
        test_stop_notyet_no_block(tmp)
        test_auto_continue_cap_and_impossible_and_met(tmp)
        test_session_and_lab(tmp)
        test_set_auto_and_clause_regression(tmp)
        test_counter_falls_back_to_project_sgpt(tmp)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
