"""AgentOps Core — shared utilities for all AgentOps scripts.

Every agentops-*.py script imports from here to avoid code duplication.
Public functions are grouped by concern:

* I/O helpers:       now_iso, write_text, write_json, load_json, read_text, load_yaml
* Path constants:    ROOT_DIR, RUNS_DIR, PLANS_DIR, DISPATCH_CODEX_SCRIPT
* PilotDeck sync:    sync_run_to_workspace, sync_plan_to_workspace, detect_workspace
* TaskMaster sync:   sync_run_to_taskmaster, sync_plan_to_taskmaster
"""
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT_DIR / ".agentops" / "runs"
PLANS_DIR = ROOT_DIR / ".agentops" / "plans"
DISPATCH_CODEX_SCRIPT = ROOT_DIR / "agentops" / "agentops-dispatch-codex.py"


# ────────────────────────────── I/O helpers ──────────────────────────────


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def write_text(path, content):
    Path(path).write_text(content, encoding="utf-8")


def write_json(path, data):
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def load_json(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def read_text(path):
    path = Path(path)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_yaml(path):
    with open(path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    if not isinstance(data, dict):
        raise ValueError(f"YAML file must contain a mapping: {path}")
    return data


# ─────────────────────── PilotDeck / workspace sync ──────────────────────


def sync_run_to_workspace(run_dir, workspace, task_id):
    """Copy a completed task run into workspace/.pilotdeck/tasks/<task_id>."""
    workspace = Path(workspace)
    run_dir = Path(run_dir)
    target_dir = workspace / ".pilotdeck" / "tasks" / str(task_id)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(run_dir, target_dir)
    return target_dir


def sync_plan_to_workspace(plan_run_dir, workspace, plan_id):
    """Copy a completed plan run into workspace/.pilotdeck/plans/<plan_id>."""
    workspace = Path(workspace)
    plan_run_dir = Path(plan_run_dir)
    target_dir = workspace / ".pilotdeck" / "plans" / str(plan_id)
    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(plan_run_dir, target_dir)
    return target_dir


def detect_workspace(plan, plan_path):
    """Resolve the workspace directory from plan config or task files."""
    if plan.get("workspace"):
        path = Path(plan["workspace"]).expanduser()
        if not path.is_absolute():
            path = (Path(plan_path).parent / path).resolve()
        return path
    for task in plan.get("tasks", []):
        task_file = task.get("task_file")
        if not task_file:
            continue
        task_path = Path(task_file)
        if not task_path.is_absolute():
            task_path = (Path(plan_path).parent / task_path).resolve()
        if not task_path.exists():
            continue
        try:
            task_data = yaml.safe_load(task_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(task_data, dict) and task_data.get("workspace"):
            return Path(task_data["workspace"]).expanduser()
    return None


# ─────────────────────── TaskMaster (tasks.json) sync ───────────────────────


TASKMASTER_STATUS_MAP = {
    "success": "done",
    "requires_review": "review",
    "failed": "in-progress",
    "skipped": "pending",
}


def status_to_taskmaster(agentops_status):
    """Map an AgentOps status string to a PilotDeck TaskMaster status."""
    return TASKMASTER_STATUS_MAP.get(agentops_status, "in-progress")


def _taskmaster_path(workspace):
    return Path(workspace) / ".taskmaster" / "tasks" / "tasks.json"


def _load_existing_tasks(tasks_json_path):
    """Read existing tasks.json and detect its structural format.

    Returns dict with keys: 'tasks' list and '_format' marker, or None.
    """
    if not tasks_json_path.exists():
        return None
    try:
        raw = load_json(tasks_json_path)
    except (json.JSONDecodeError, OSError):
        return None

    if isinstance(raw, list):
        return {"tasks": raw, "_format": "legacy"}
    if isinstance(raw, dict):
        if "tasks" in raw and isinstance(raw["tasks"], list):
            raw["_format"] = "simple"
            return raw
        raw["_format"] = "tagged"
        return raw
    return None


def _merge_entries(existing, new_entries):
    """Merge new entries into the existing tasks.json structure.

    Same-id entries in existing are overwritten (idempotent re-runs).
    """
    new_ids = {entry["id"] for entry in new_entries}

    if existing is None:
        return {"tasks": list(new_entries)}

    if existing.get("_format") == "legacy":
        kept = [t for t in existing.get("tasks", [])
                if isinstance(t, dict) and t.get("id") not in new_ids]
        return kept + list(new_entries)

    if existing.get("_format") == "simple":
        kept = [t for t in existing.get("tasks", [])
                if isinstance(t, dict) and t.get("id") not in new_ids]
        merged = {k: v for k, v in existing.items() if k != "_format"}
        merged["tasks"] = kept + list(new_entries)
        return merged

    # tagged format: find the right tag key
    tag_key = None
    for key in ("master", "main", "default"):
        if key in existing and isinstance(existing.get(key), dict) \
                and "tasks" in existing.get(key):
            tag_key = key
            break
    if tag_key is None:
        for key, val in existing.items():
            if isinstance(val, dict) and "tasks" in val \
                    and isinstance(val["tasks"], list):
                tag_key = key
                break
    tag_key = tag_key or "master"

    tag_block = existing.get(tag_key, {}) if isinstance(existing.get(tag_key, {}), dict) else {}
    current = tag_block.get("tasks", []) if isinstance(tag_block, dict) else []
    current = [t for t in current if isinstance(t, dict) and t.get("id") not in new_ids]
    current.extend(new_entries)

    merged = {k: v for k, v in existing.items() if k != "_format"}
    if tag_key in merged and isinstance(merged.get(tag_key), dict):
        merged[tag_key]["tasks"] = current
    else:
        merged[tag_key] = {"tasks": current}
    return merged


def _atomic_write_json(path, data):
    path = Path(path)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _extract_task_title(task, summary_text):
    """Derive a human-readable title for a task entry."""
    goal = task.get("goal") if isinstance(task, dict) else None
    if goal:
        title = str(goal).strip().splitlines()[0]
        return title[:120]
    if summary_text:
        for line in summary_text.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("-"):
                return stripped[:120]
    return str(task.get("task_id", "unknown-task")) if isinstance(task, dict) else str(task)


def sync_run_to_taskmaster(run_dir, workspace, task, result, summary_text):
    """Write a single task run into workspace/.taskmaster/tasks/tasks.json."""
    workspace = Path(workspace)
    run_dir = Path(run_dir)
    tasks_json_path = _taskmaster_path(workspace)
    tasks_json_path.parent.mkdir(parents=True, exist_ok=True)

    task_id = str(task.get("task_id")) if isinstance(task, dict) else str(task)
    changed_files = result.get("changed_files") or []

    details_lines = [
        f"AgentOps run: {run_dir}",
        f"Sandbox: {result.get('sandbox', 'n/a')} | Mode: {result.get('mode', 'n/a')}",
        f"Codex exit code: {result.get('codex_exit_code', 'n/a')}",
        f"Git diff empty: {str(result.get('git_diff_empty', False)).lower()}",
        f"Changed files ({len(changed_files)}):",
    ]
    for cf in changed_files:
        details_lines.append(f"  - {cf}")
    if result.get("risk_summary"):
        details_lines.append(f"Risk: {result['risk_summary']}")

    entry = {
        "id": task_id,
        "title": _extract_task_title(task, summary_text),
        "description": summary_text or result.get("goal", ""),
        "status": status_to_taskmaster(result.get("status", "failed")),
        "priority": "medium",
        "dependencies": [],
        "createdAt": result.get("started_at", ""),
        "updatedAt": result.get("ended_at", ""),
        "details": "\n".join(details_lines),
        "testStrategy": "",
        "subtasks": [],
        "_source": "agentops",
    }

    existing = _load_existing_tasks(tasks_json_path)
    merged = _merge_entries(existing, [entry])
    _atomic_write_json(tasks_json_path, merged)
    return tasks_json_path


def sync_plan_to_taskmaster(plan_run_dir, plan, plan_result, workspace):
    """Write plan + each of its sub-tasks into workspace/.taskmaster/tasks/tasks.json."""
    workspace = Path(workspace)
    plan_run_dir = Path(plan_run_dir)
    tasks_json_path = _taskmaster_path(workspace)
    tasks_json_path.parent.mkdir(parents=True, exist_ok=True)

    plan_id = str(plan.get("plan_id", ""))
    plan_summary_text = read_text(plan_run_dir / "summary.md")

    task_results = {t["task_id"]: t for t in plan_result.get("tasks", [])}
    task_entries = []
    for task_ref in plan.get("tasks", []):
        if not isinstance(task_ref, dict):
            continue
        task_id = task_ref.get("task_id")
        if not task_id:
            continue
        task_result = task_results.get(task_id)
        status = task_result["status"] if task_result else "skipped"

        details_lines = [f"Plan: {plan_id}"]
        if task_result:
            details_lines.append(f"Task result path: {task_result.get('task_result_path', 'n/a')}")
            details_lines.append(f"Dispatch exit code: {task_result.get('dispatch_exit_code', 'n/a')}")
        else:
            details_lines.append("Status: blocked / skipped")

        deps = task_ref.get("depends_on", []) or []
        entry = {
            "id": str(task_id),
            "title": str(task_id),
            "description": f"Part of plan: {plan_id}",
            "status": status_to_taskmaster(status),
            "priority": "medium",
            "dependencies": list(deps),
            "createdAt": (task_result or plan_result or {}).get("started_at", ""),
            "updatedAt": (task_result or plan_result or {}).get("ended_at", ""),
            "details": "\n".join(details_lines),
            "testStrategy": "",
            "subtasks": [],
            "_source": "agentops",
            "_plan": plan_id,
        }
        task_entries.append(entry)

    plan_entry = {
        "id": f"plan-{plan_id}",
        "title": f"Plan: {plan_id} ({len(plan.get('tasks', []))} tasks)",
        "description": plan_summary_text,
        "status": status_to_taskmaster(plan_result.get("status", "failed")),
        "priority": "high",
        "dependencies": [],
        "createdAt": plan_result.get("started_at", ""),
        "updatedAt": plan_result.get("ended_at", ""),
        "details": (
            f"Plan run directory: {plan_run_dir}\n"
            f"Task count: {len(plan_result.get('tasks', []))}\n"
            f"Blocked/skipped: {len(plan_result.get('blocked_tasks', []))}"
        ),
        "testStrategy": "",
        "subtasks": [e["id"] for e in task_entries],
        "_source": "agentops",
        "_type": "plan",
    }

    all_entries = task_entries + [plan_entry]
    existing = _load_existing_tasks(tasks_json_path)
    merged = _merge_entries(existing, all_entries)
    _atomic_write_json(tasks_json_path, merged)
    return tasks_json_path
