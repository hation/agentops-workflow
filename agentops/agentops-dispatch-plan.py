#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

import yaml

from agentops_core import (
    ROOT_DIR,
    RUNS_DIR,
    now_iso,
    write_text,
    write_json,
    load_yaml,
    sync_plan_to_workspace,
    sync_plan_to_taskmaster,
    detect_workspace,
)

PLAN_RUNS_DIR = ROOT_DIR / ".agentops" / "plans"
DISPATCH_CODEX = ROOT_DIR / "agentops" / "agentops-dispatch-codex.py"


def validate_plan(plan):
    for field in ["plan_id", "project", "tasks"]:
        if field not in plan:
            raise ValueError(f"missing required field: {field}")
    if not isinstance(plan["tasks"], list) or not plan["tasks"]:
        raise ValueError("tasks must be a non-empty list")
    task_ids = []
    for task in plan["tasks"]:
        if not isinstance(task, dict):
            raise ValueError("each task must be a mapping")
        if "task_id" not in task:
            raise ValueError("each task must contain task_id")
        if "task_file" not in task:
            raise ValueError(f"task {task['task_id']} must contain task_file")
        task_ids.append(task["task_id"])
    duplicates = sorted({t for t in task_ids if task_ids.count(t) > 1})
    if duplicates:
        raise ValueError(f"duplicate task ids: {', '.join(duplicates)}")
    task_id_set = set(task_ids)
    for task in plan["tasks"]:
        for dependency in task.get("depends_on", []) or []:
            if dependency not in task_id_set:
                raise ValueError(f"task {task['task_id']} depends on unknown task: {dependency}")
    if not DISPATCH_CODEX.exists():
        raise ValueError(f"dispatcher not found: {DISPATCH_CODEX}")


def task_file_path(plan_path, task_file):
    path = Path(task_file).expanduser()
    if path.is_absolute():
        return path
    return (plan_path.parent / path).resolve()


def run_task(task, plan_path, plan_run_dir):
    path = task_file_path(plan_path, task["task_file"])
    started_at = now_iso()
    result = subprocess.run(
        [sys.executable, str(DISPATCH_CODEX), str(path)],
        cwd=str(ROOT_DIR),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    ended_at = now_iso()
    task_log_dir = plan_run_dir / "task-logs"
    task_log_dir.mkdir(parents=True, exist_ok=True)
    write_text(task_log_dir / f"{task['task_id']}.stdout.log", result.stdout)
    write_text(task_log_dir / f"{task['task_id']}.stderr.log", result.stderr)

    task_result_path = RUNS_DIR / task["task_id"] / "result.json"
    task_result = None
    if task_result_path.exists():
        task_result = json.loads(task_result_path.read_text(encoding="utf-8"))
    if result.returncode == 0 and task_result and task_result.get("status") == "success":
        status = "success"
    elif task_result and task_result.get("status") == "requires_review":
        status = "requires_review"
    else:
        status = "failed"
    return {
        "task_id": task["task_id"],
        "task_file": str(path),
        "depends_on": task.get("depends_on", []) or [],
        "started_at": started_at,
        "ended_at": ended_at,
        "dispatch_exit_code": result.returncode,
        "status": status,
        "task_result_path": str(task_result_path) if task_result_path.exists() else None,
        "task_summary_path": str(RUNS_DIR / task["task_id"] / "summary.md") if (RUNS_DIR / task["task_id"] / "summary.md").exists() else None,
        "stdout_log": str(task_log_dir / f"{task['task_id']}.stdout.log"),
        "stderr_log": str(task_log_dir / f"{task['task_id']}.stderr.log"),
    }


def runnable_tasks(tasks, completed):
    ready = []
    for task in tasks:
        task_id = task["task_id"]
        if task_id in completed:
            continue
        dependencies = task.get("depends_on", []) or []
        if all(dependency in completed and completed[dependency]["status"] == "success" for dependency in dependencies):
            ready.append(task)
    return ready


def blocked_tasks(tasks, completed):
    blocked = []
    for task in tasks:
        task_id = task["task_id"]
        if task_id in completed:
            continue
        blocked.append({
            "task_id": task_id,
            "depends_on": task.get("depends_on", []) or [],
            "status": "skipped",
            "reason": "dependencies not successful",
        })
    return blocked


def build_summary(plan, results, blocked, status):
    lines = [
        f"# Plan {plan['plan_id']} Summary",
        "",
        "## Status",
        "",
        status,
        "",
        "## Tasks",
        "",
    ]
    for item in results:
        lines.append(f"- {item['task_id']}: {item['status']} (dispatch_exit_code={item['dispatch_exit_code']})")
    for item in blocked:
        lines.append(f"- {item['task_id']}: skipped ({item['reason']})")
    lines.extend([
        "",
        "## Next",
        "",
    ])
    if status == "success":
        lines.append("- Trae 可读取每个 task 的 summary.md，并决定是否进入下一轮计划。")
    else:
        lines.append("- 先检查 failed/requires_review/skipped 任务，再决定是否重跑或拆分计划。")
    return "\n".join(lines) + "\n"


def dispatch_plan(plan_path):
    plan = load_yaml(plan_path)
    validate_plan(plan)
    plan_id = str(plan["plan_id"])
    stop_on_failure = bool(plan.get("stop_on_failure", True))
    plan_run_dir = PLAN_RUNS_DIR / plan_id
    plan_run_dir.mkdir(parents=True, exist_ok=True)
    write_text(plan_run_dir / "plan.yaml", plan_path.read_text(encoding="utf-8"))

    started_at = now_iso()
    completed = {}
    results = []
    stop_requested = False

    while len(completed) < len(plan["tasks"]):
        ready = runnable_tasks(plan["tasks"], completed)
        if not ready:
            break
        task = ready[0]
        item = run_task(task, plan_path, plan_run_dir)
        completed[task["task_id"]] = item
        results.append(item)
        if item["status"] != "success" and stop_on_failure:
            stop_requested = True
            break

    blocked = blocked_tasks(plan["tasks"], completed)
    if stop_requested:
        plan_status = "failed"
    elif blocked:
        plan_status = "failed"
    elif any(item["status"] != "success" for item in results):
        plan_status = "requires_review"
    else:
        plan_status = "success"

    ended_at = now_iso()
    workspace = detect_workspace(plan, plan_path)
    result = {
        "plan_id": plan_id,
        "status": plan_status,
        "project": plan["project"],
        "started_at": started_at,
        "ended_at": ended_at,
        "stop_on_failure": stop_on_failure,
        "tasks": results,
        "blocked_tasks": blocked,
        "plan_run_dir": str(plan_run_dir),
        "workspace": str(workspace) if workspace else None,
    }
    write_json(plan_run_dir / "plan-result.json", result)
    write_text(plan_run_dir / "summary.md", build_summary(plan, results, blocked, plan_status))
    if workspace:
        pilotdeck_plan_dir = sync_plan_to_workspace(plan_run_dir, workspace, plan_id)
        result["pilotdeck_plan_dir"] = str(pilotdeck_plan_dir)
        result["synced_to_workspace_pilotdeck"] = True
        taskmaster_path = sync_plan_to_taskmaster(plan_run_dir, plan, result, workspace)
        result["taskmaster_tasks_json"] = str(taskmaster_path)
        result["synced_to_taskmaster"] = True
        write_json(plan_run_dir / "plan-result.json", result)
    return result, plan_run_dir


def main():
    parser = argparse.ArgumentParser(description="Dispatch an AgentOps multi-task plan")
    parser.add_argument("plan", type=Path, help="Path to AgentOps plan YAML")
    args = parser.parse_args()

    try:
        result, plan_run_dir = dispatch_plan(args.plan.resolve())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"plan_id={result['plan_id']}")
    print(f"status={result['status']}")
    print(f"plan_run_dir={plan_run_dir}")
    print(f"task_count={len(result['tasks'])}")
    print(f"blocked_count={len(result['blocked_tasks'])}")
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
