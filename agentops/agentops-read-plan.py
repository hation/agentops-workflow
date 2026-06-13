#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path

from agentops_core import (
    ROOT_DIR,
    PLANS_DIR,
    load_json,
    read_text,
)


STATUS_LABEL = {
    "success": "SUCCESS",
    "failed": "FAILED",
    "requires_review": "REQUIRES_REVIEW",
    "skipped": "SKIPPED",
    "blocked": "BLOCKED",
}


def find_latest_plan():
    if not PLANS_DIR.exists():
        raise ValueError(f"plans directory does not exist: {PLANS_DIR}")
    candidates = [
        path
        for path in PLANS_DIR.iterdir()
        if path.is_dir() and (path / "plan-result.json").exists()
    ]
    if not candidates:
        raise ValueError(f"no plan runs found in: {PLANS_DIR}")
    return max(candidates, key=lambda path: (path / "plan-result.json").stat().st_mtime)


def resolve_plan_dir(plan_id, latest):
    if latest:
        return find_latest_plan()
    if not plan_id:
        raise ValueError("plan_id is required unless --latest is used")
    plan_dir = PLANS_DIR / plan_id
    if not plan_dir.exists() or not plan_dir.is_dir():
        raise ValueError(f"plan run not found: {plan_dir}")
    if not (plan_dir / "plan-result.json").exists():
        raise ValueError(f"plan-result.json not found in: {plan_dir}")
    return plan_dir


def describe_task_status(task):
    status = task.get("status", "unknown")
    label = STATUS_LABEL.get(status, status.upper())
    code = task.get("dispatch_exit_code")
    if code is not None:
        return f"{label} (dispatch_exit_code={code})"
    return label


def collect_next_action(result):
    status = result.get("status")
    tasks = result.get("tasks") or []
    blocked = result.get("blocked_tasks") or []

    if status == "success":
        return "所有任务成功；可由 Trae 逐任务审查 summary.md 后，决定是否派发下一阶段计划或直接合并变更。"

    failures = [t for t in tasks if t.get("status") == "failed"]
    reviews = [t for t in tasks if t.get("status") == "requires_review"]

    if failures and reviews:
        failed_ids = ", ".join(t["task_id"] for t in failures)
        review_ids = ", ".join(t["task_id"] for t in reviews)
        return (
            f"存在失败任务 ({failed_ids}) 与需审查任务 ({review_ids})；"
            "先修失败原因或审查变更，再重跑受影响步骤。"
        )
    if failures:
        failed_ids = ", ".join(t["task_id"] for t in failures)
        return f"任务 {failed_ids} 失败；查看对应 task-logs/*.stderr.log 与 result.json，修复后重跑。"
    if reviews:
        review_ids = ", ".join(t["task_id"] for t in reviews)
        return f"任务 {review_ids} 需要人工审查 diff.patch 与 changed_files；确认后由 Trae 决定是否继续。"
    if blocked:
        skipped_ids = ", ".join(t["task_id"] for t in blocked)
        return f"以下任务因依赖未满足被跳过：{skipped_ids}；优先修复上游任务后再重跑。"
    return "计划状态未知，需要人工检查 plan-result.json 与对应任务目录。"


def print_plan(plan_dir, show_summary):
    result = load_json(plan_dir / "plan-result.json")
    summary = read_text(plan_dir / "summary.md")
    tasks = result.get("tasks") or []
    blocked = result.get("blocked_tasks") or []

    print(f"plan_id: {result.get('plan_id')}")
    print(f"status: {result.get('status')}")
    print(f"project: {result.get('project')}")
    if result.get("workspace"):
        print(f"workspace: {result.get('workspace')}")
    if result.get("pilotdeck_plan_dir"):
        print(f"pilotdeck_plan_dir: {result.get('pilotdeck_plan_dir')}")
    print(f"started_at: {result.get('started_at')}")
    print(f"ended_at: {result.get('ended_at')}")
    print(f"stop_on_failure: {str(result.get('stop_on_failure')).lower()}")
    print(f"plan_run_dir: {plan_dir}")
    print(f"tasks_count: {len(tasks)}")
    print(f"blocked_tasks_count: {len(blocked)}")
    print(f"next_action: {collect_next_action(result)}")

    if tasks:
        print("\n=== tasks ===")
        for task in tasks:
            status = describe_task_status(task)
            print(f"- {task.get('task_id')}: {status}")
            print(f"    task_result: {task.get('task_result_path')}")
            print(f"    task_summary: {task.get('task_summary_path')}")
            if task.get("stdout_log"):
                print(f"    stdout_log: {task.get('stdout_log')}")
            if task.get("stderr_log"):
                print(f"    stderr_log: {task.get('stderr_log')}")
            depends = task.get("depends_on") or []
            if depends:
                print(f"    depends_on: {', '.join(depends)}")

    if blocked:
        print("\n=== blocked_tasks ===")
        for task in blocked:
            status = STATUS_LABEL.get(task.get("status"), task.get("status", "unknown").upper())
            reason = task.get("reason", "")
            print(f"- {task.get('task_id')}: {status} ({reason})")
            depends = task.get("depends_on") or []
            if depends:
                print(f"    depends_on: {', '.join(depends)}")

    failed_tasks = [t for t in tasks if t.get("status") in ("failed", "requires_review")]
    if failed_tasks:
        print("\n=== attention ===")
        for task in failed_tasks:
            print(f"- {task.get('task_id')}: {describe_task_status(task)} — 需处理后再继续")

    if show_summary:
        print("\n--- summary.md ---")
        print(summary.rstrip())


def list_plans(limit):
    if not PLANS_DIR.exists():
        return []
    plans = [
        path
        for path in PLANS_DIR.iterdir()
        if path.is_dir() and (path / "plan-result.json").exists()
    ]
    plans.sort(key=lambda path: (path / "plan-result.json").stat().st_mtime, reverse=True)
    return plans[:limit]


def print_plans(limit):
    plans = list_plans(limit)
    if not plans:
        print(f"no plan runs found in: {PLANS_DIR}")
        return
    for plan_dir in plans:
        result = load_json(plan_dir / "plan-result.json")
        tasks = result.get("tasks") or []
        failed = sum(1 for t in tasks if t.get("status") == "failed")
        review = sum(1 for t in tasks if t.get("status") == "requires_review")
        print(
            f"{result.get('plan_id')}\t"
            f"{result.get('status')}\t"
            f"tasks={len(tasks)}\t"
            f"failed={failed}\t"
            f"review={review}\t"
            f"{result.get('ended_at')}"
        )


def main():
    parser = argparse.ArgumentParser(description="Read AgentOps multi-task plan results")
    parser.add_argument("plan_id", nargs="?", help="Plan id to read")
    parser.add_argument("--latest", action="store_true", help="Read latest plan run")
    parser.add_argument("--summary", action="store_true", help="Print summary.md content")
    parser.add_argument("--list", action="store_true", help="List recent plan runs")
    parser.add_argument("--limit", type=int, default=10, help="Limit for --list")
    args = parser.parse_args()

    try:
        if args.list:
            print_plans(args.limit)
            return 0
        plan_dir = resolve_plan_dir(args.plan_id, args.latest)
        print_plan(plan_dir, args.summary)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
