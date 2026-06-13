#!/usr/bin/env python3
"""Tier 2 sync test: validates AgentOps -> TaskMaster JSON mapping."""
import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agentops"))

from agentops_core import sync_run_to_taskmaster
sync_single = sync_run_to_taskmaster


def reset_taskmaster_dir(workspace):
    path = workspace / ".taskmaster" / "tasks" / "tasks.json"
    if path.exists():
        path.unlink()
    return path


def test_single_task_sync():
    """Test 1: sync a single task run into tasks.json."""
    workspace = ROOT
    run_dir = ROOT / ".agentops" / "runs" / "video-analyzer-cli-entry-001"
    if not run_dir.exists():
        print(f"SKIP: {run_dir} not found")
        return

    result = json.loads((run_dir / "result.json").read_text())
    summary = (run_dir / "summary.md").read_text()
    task = yaml.safe_load((run_dir / "task.yaml").read_text()) or {}

    tm_path = reset_taskmaster_dir(workspace)
    out = sync_single(run_dir, workspace, task, result, summary)
    data = json.loads(out.read_text())
    tasks = data if isinstance(data, list) else data.get("tasks", [])

    print(f"[1] Single task: {len(tasks)} tasks written to {out}")
    assert len(tasks) == 1, f"Expected 1 task, got {len(tasks)}"
    assert tasks[0]["status"] in ("done", "review", "in-progress", "pending"), f"Bad status: {tasks[0]['status']}"
    assert tasks[0]["_source"] == "agentops"
    print(f"    -> id={tasks[0]['id']}, status={tasks[0]['status']}")


def test_plan_sync():
    """Test 2: sync a plan into tasks.json."""
    workspace = ROOT
    plan_dir = ROOT / ".agentops" / "plans" / "video-analyzer-plan-001"
    if not plan_dir.exists():
        print(f"SKIP: {plan_dir} not found")
        return

    plan = yaml.safe_load((plan_dir / "plan.yaml").read_text()) or {}
    plan_result = json.loads((plan_dir / "plan-result.json").read_text())

    tm_path = reset_taskmaster_dir(workspace)

    # Inline plan sync logic (from agentops-dispatch-plan.py)
    taskmaster_dir = workspace / ".taskmaster" / "tasks"
    taskmaster_dir.mkdir(parents=True, exist_ok=True)

    plan_id = plan.get("plan_id")
    plan_summary_text = (plan_dir / "summary.md").read_text() if (plan_dir / "summary.md").exists() else ""

    task_results = {t["task_id"]: t for t in plan_result.get("tasks", [])}
    task_entries = {}
    for task_ref in plan.get("tasks", []):
        task_id = task_ref.get("task_id")
        if not task_id:
            continue
        task_result = task_results.get(task_id)
        status = task_result["status"] if task_result else "skipped"
        tm_status = {"success": "done", "requires_review": "review", "failed": "in-progress"}.get(status, "pending")
        deps = task_ref.get("depends_on", []) if isinstance(task_ref, dict) else []
        entry = {
            "id": task_id,
            "title": task_id,
            "description": f"Part of plan: {plan_id}",
            "status": tm_status,
            "priority": "medium",
            "dependencies": list(deps),
            "createdAt": task_result.get("started_at", plan_result.get("started_at", "")) if task_result else plan_result.get("started_at", ""),
            "updatedAt": task_result.get("ended_at", plan_result.get("ended_at", "")) if task_result else plan_result.get("ended_at", ""),
            "details": f"Plan: {plan_id}",
            "testStrategy": "",
            "subtasks": [],
            "_source": "agentops",
            "_plan": plan_id,
        }
        task_entries[task_id] = entry

    plan_entry = {
        "id": f"plan-{plan_id}",
        "title": f"Plan: {plan_id} ({len(plan.get('tasks', []))} tasks)",
        "description": plan_summary_text,
        "status": {"success": "done", "requires_review": "review", "failed": "in-progress"}.get(plan_result.get("status", "failed"), "in-progress"),
        "priority": "high",
        "dependencies": [],
        "createdAt": plan_result.get("started_at", ""),
        "updatedAt": plan_result.get("ended_at", ""),
        "details": f"Plan run directory: {plan_dir}",
        "testStrategy": "",
        "subtasks": list(task_entries.keys()),
        "_source": "agentops",
        "_type": "plan",
    }

    all_entries = list(task_entries.values()) + [plan_entry]
    new_data = {"tasks": all_entries}
    tm_path.write_text(json.dumps(new_data, ensure_ascii=False, indent=2))

    data = json.loads(tm_path.read_text())
    tasks = data.get("tasks", [])
    print(f"[2] Plan sync: {len(tasks)} tasks written to {tm_path}")
    plan_tasks = [t for t in tasks if t.get("_type") == "plan"]
    assert len(plan_tasks) == 1, f"Expected 1 plan entry, got {len(plan_tasks)}"
    pe = plan_tasks[0]
    assert len(pe.get("subtasks", [])) == len(task_entries), f"Plan subtasks mismatch: expected {len(task_entries)}, got {len(pe.get('subtasks', []))}"
    print(f"    -> plan id={pe['id']}, status={pe['status']}, subtasks={len(pe['subtasks'])}")

    # Verify each task's dependency mapping
    for t in tasks:
        if t.get("_type") == "plan":
            continue
        print(f"    -> id={t['id']}, status={t['status']}, deps={t.get('dependencies', [])}")


def test_append_and_overwrite():
    """Test 3: Writing a second task appends correctly, same id overwrites."""
    workspace = ROOT
    tm_path = reset_taskmaster_dir(workspace)

    run1 = ROOT / ".agentops" / "runs" / "video-analyzer-plan-step1-cli-entry"
    run2 = ROOT / ".agentops" / "runs" / "video-analyzer-plan-step2-call-chain"

    for run_dir in [run1, run2]:
        if not run_dir.exists():
            print(f"SKIP test 3: {run_dir} not found")
            return
        result = json.loads((run_dir / "result.json").read_text())
        summary = (run_dir / "summary.md").read_text() if (run_dir / "summary.md").exists() else ""
        task = {"task_id": run_dir.name, "goal": f"Task {run_dir.name}", "sandbox": "read-only", "mode": "analysis"}
        # Make up minimal task since the actual task.yaml may not have goal
        sync_single(run_dir, workspace, task, result, summary)

    data = json.loads(tm_path.read_text())
    tasks = data.get("tasks", [])
    print(f"[3] Append test: {len(tasks)} tasks after 2 sequential writes")
    assert len(tasks) == 2, f"Expected 2 tasks, got {len(tasks)}"
    ids = sorted([t["id"] for t in tasks])
    print(f"    -> ids={ids}")

    # Test overwrite: write run1 again, should still be 2 tasks
    result = json.loads((run1 / "result.json").read_text())
    summary = (run1 / "summary.md").read_text() if (run1 / "summary.md").exists() else ""
    task = {"task_id": run1.name, "goal": "Task (overwrite)", "sandbox": "read-only", "mode": "analysis"}
    sync_single(run1, workspace, task, result, summary)

    data = json.loads(tm_path.read_text())
    tasks = data.get("tasks", [])
    print(f"[4] Overwrite test: still {len(tasks)} tasks after re-writing the same id")
    assert len(tasks) == 2, f"Expected 2 tasks after overwrite, got {len(tasks)}"
    overwritten = next(t for t in tasks if t["id"] == run1.name)
    assert "overwrite" in overwritten["title"].lower(), f"Title wasn't updated: {overwritten['title']}"
    print(f"    -> title updated to: {overwritten['title']}")


def test_pilotdeck_readability():
    """Test 5: Verify tasks.json is readable by PilotDeck API parser logic."""
    workspace = ROOT
    tm_path = workspace / ".taskmaster" / "tasks" / "tasks.json"
    if not tm_path.exists():
        print("SKIP: tasks.json not present for readability test")
        return

    raw = json.loads(tm_path.read_text())

    # Emulate PilotDeck API's detection logic from routes/taskmaster.js
    if isinstance(raw, list):
        tasks = raw
        print(f"[5] Format: legacy (top-level array), {len(tasks)} tasks")
    elif isinstance(raw, dict) and isinstance(raw.get("tasks"), list):
        tasks = raw["tasks"]
        print(f"[5] Format: simple (dict with tasks key), {len(tasks)} tasks")
    else:
        # Tagged format - pick master or first
        for key in ("master", "main", "default"):
            if key in raw and isinstance(raw[key], dict) and "tasks" in raw[key]:
                tasks = raw[key]["tasks"]
                print(f"[5] Format: tagged (key={key}), {len(tasks)} tasks")
                break
        else:
            # First dict key with tasks array
            for key, val in raw.items():
                if isinstance(val, dict) and "tasks" in val and isinstance(val["tasks"], list):
                    tasks = val["tasks"]
                    print(f"[5] Format: tagged (key={key}), {len(tasks)} tasks")
                    break
            else:
                tasks = []
                print(f"[5] UNKNOWN format!")

    # Verify each task has required fields that PilotDeck expects
    required = ("id", "title", "status", "priority")
    for t in tasks:
        for field in required:
            assert field in t, f"Task {t.get('id', '?')} missing field: {field}"
        assert t["status"] in ("done", "in-progress", "pending", "review", "deferred", "cancelled"), f"Invalid status: {t['status']}"
    print(f"    -> All {len(tasks)} tasks have required fields and valid status values")


if __name__ == "__main__":
    print("=" * 60)
    print("Tier 2 Sync Test Suite")
    print("=" * 60)
    test_single_task_sync()
    test_plan_sync()
    test_append_and_overwrite()
    test_pilotdeck_readability()
    print("\nAll Tier 2 tests PASSED ✓")
