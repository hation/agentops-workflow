#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from agentops_core import (
    ROOT_DIR,
    RUNS_DIR,
    load_json,
    read_text,
)


def find_latest_run():
    if not RUNS_DIR.exists():
        raise ValueError(f"runs directory does not exist: {RUNS_DIR}")
    candidates = [path for path in RUNS_DIR.iterdir() if path.is_dir() and (path / "result.json").exists()]
    if not candidates:
        raise ValueError(f"no task runs found in: {RUNS_DIR}")
    return max(candidates, key=lambda path: (path / "result.json").stat().st_mtime)


def resolve_run_dir(task_id, latest):
    if latest:
        return find_latest_run()
    if not task_id:
        raise ValueError("task_id is required unless --latest is used")
    run_dir = RUNS_DIR / task_id
    if not run_dir.exists() or not run_dir.is_dir():
        raise ValueError(f"task run not found: {run_dir}")
    if not (run_dir / "result.json").exists():
        raise ValueError(f"result.json not found in: {run_dir}")
    return run_dir


def collect_next_action(result):
    status = result.get("status")
    if status == "success":
        return "可由 Trae 审查 summary.md 后决定是否派发下一步任务。"
    if status == "requires_review":
        return "需要人工审查 diff.patch、changed_files 和 Codex 输出，确认是否允许继续。"
    if status == "failed":
        return "需要先查看 codex-stderr.log、codex-stdout.log 和 result.json，修复失败原因后再重跑。"
    return "状态未知，需要人工检查 run 目录。"


def print_run(run_dir, show_summary):
    result = load_json(run_dir / "result.json")
    summary = read_text(run_dir / "summary.md")
    changed_files = result.get("changed_files") or []

    print(f"task_id: {result.get('task_id')}")
    print(f"status: {result.get('status')}")
    print(f"project: {result.get('project')}")
    print(f"workspace: {result.get('workspace')}")
    print(f"provider: {result.get('provider')}")
    print(f"sandbox: {result.get('sandbox')}")
    print(f"mode: {result.get('mode')}")
    print(f"codex_exit_code: {result.get('codex_exit_code')}")
    print(f"git_diff_empty: {str(result.get('git_diff_empty')).lower()}")
    print(f"changed_files_count: {len(changed_files)}")
    print(f"run_dir: {run_dir}")
    print(f"summary: {run_dir / 'summary.md'}")
    print(f"result: {run_dir / 'result.json'}")
    print(f"diff: {run_dir / 'diff.patch'}")
    print(f"next_action: {collect_next_action(result)}")

    if changed_files:
        print("changed_files:")
        for file_name in changed_files:
            print(f"- {file_name}")

    if show_summary:
        print("\n--- summary.md ---")
        print(summary.rstrip())


def list_runs(limit):
    if not RUNS_DIR.exists():
        return []
    runs = [path for path in RUNS_DIR.iterdir() if path.is_dir() and (path / "result.json").exists()]
    runs.sort(key=lambda path: (path / "result.json").stat().st_mtime, reverse=True)
    return runs[:limit]


def print_runs(limit):
    runs = list_runs(limit)
    if not runs:
        print(f"no task runs found in: {RUNS_DIR}")
        return
    for run_dir in runs:
        result = load_json(run_dir / "result.json")
        print(
            f"{result.get('task_id')}\t"
            f"{result.get('status')}\t"
            f"{result.get('provider')}\t"
            f"{result.get('sandbox')}\t"
            f"{result.get('ended_at')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Read AgentOps Codex task results")
    parser.add_argument("task_id", nargs="?", help="Task id to read")
    parser.add_argument("--latest", action="store_true", help="Read latest task run")
    parser.add_argument("--summary", action="store_true", help="Print summary.md content")
    parser.add_argument("--list", action="store_true", help="List recent task runs")
    parser.add_argument("--limit", type=int, default=10, help="Limit for --list")
    args = parser.parse_args()

    try:
        if args.list:
            print_runs(args.limit)
            return 0
        run_dir = resolve_run_dir(args.task_id, args.latest)
        print_run(run_dir, args.summary)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
