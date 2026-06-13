#!/usr/bin/env python3
"""Verify failure plan sync works correctly."""
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agentops"))

from agentops_core import sync_plan_to_taskmaster

ws = ROOT
tm_path = ws / ".taskmaster" / "tasks" / "tasks.json"
if tm_path.exists():
    tm_path.unlink()

plan_dir = ROOT / ".agentops" / "plans" / "failure-plan-001"
plan_data = yaml.safe_load((plan_dir / "plan.yaml").read_text())
plan_result = json.loads((plan_dir / "plan-result.json").read_text())

out = sync_plan_to_taskmaster(plan_dir, plan_data, plan_result, ws)
data = json.loads(out.read_text())
tasks = data.get("tasks", [])

print(f"Failure plan: {len(tasks)} tasks written")
for t in tasks:
    subtasks = t.get("subtasks", []) or []
    extra = ""
    if t.get("_type") == "plan":
        extra = f" (plan-entry, subtasks={len(subtasks)})"
    print(f"  - [{t['status']}] {t['id']}{extra}")

plan_entry = next(t for t in tasks if t.get("_type") == "plan")
print(f"Plan entry status: {plan_entry['status']}")
assert plan_entry["status"] == "in-progress", f"Expected in-progress but got {plan_entry['status']}"

failed_task = next(t for t in tasks if t["id"] == "failure-verification-command-001")
assert failed_task["status"] == "in-progress", f"Failed task should be in-progress: {failed_task['status']}"
print(f"Failed task correctly marked: {failed_task['status']}")

blocked_id = "video-analyzer-plan-step1-cli-entry"
blocked_task = next((t for t in tasks if t["id"] == blocked_id), None)
if blocked_task:
    print(f"Blocked task {blocked_id}: {blocked_task['status']}")

print("Failure plan test PASSED ✓")
