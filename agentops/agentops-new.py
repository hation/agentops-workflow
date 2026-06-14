#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = ROOT_DIR / "examples"

TASK_TEMPLATE = """# AgentOps Task: {task_id}
# 由 agentops-new.py 生成，按需修改后交给 agentops-dispatch-codex.py 执行

task_id: {task_id}
project: {project}
workspace: {workspace}
provider: headroom
sandbox: {sandbox}
mode: {mode}
goal: |
{goal}
context:
{context_block}
constraints:
  - 不修改 .pilotdeck/ 目录
  - 不修改 .agentops/ 目录
{constraints_extra}
expected_output:
  - summary
{output_extra}
verification:
  - codex_exit_code_must_be_0
{verification_extra}
"""

PLAN_TEMPLATE = """# AgentOps Plan: {plan_id}
# 由 agentops-new.py 生成，按需修改后交给 agentops-dispatch-plan.py 执行

plan_id: {plan_id}
project: {project}
workspace: {workspace}
stop_on_failure: true
tasks:
{tasks_block}
"""


def detect_default_workspace():
    return str(ROOT_DIR)


def _truncate_text(text, limit=80):
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _latest_run_dir():
    runs_dir = ROOT_DIR / ".agentops" / "runs"
    if not runs_dir.exists():
        return None
    candidates = [path for path in runs_dir.iterdir() if path.is_dir() and (path / "result.json").exists()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path / "result.json").stat().st_mtime)


def _summary_line(summary):
    in_codex_result = False
    for line in summary.splitlines():
        stripped = line.strip()
        if stripped == "## Codex Result":
            in_codex_result = True
            continue
        if stripped.startswith("## ") and in_codex_result:
            break
        if not in_codex_result:
            continue
        if not stripped or stripped.startswith("#") or stripped.endswith("："):
            continue
        if stripped.startswith("-"):
            stripped = stripped.lstrip("- ").strip()
        if stripped in {"无", "success", "failed", "requires_review"}:
            continue
        return _truncate_text(stripped)
    return ""


def generate_auto_context():
    run_dir = _latest_run_dir()
    if not run_dir:
        return []
    result_path = run_dir / "result.json"
    summary_path = run_dir / "summary.md"
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    task_id = result.get("task_id") or run_dir.name
    status = result.get("status", "unknown")
    changed_count = len(result.get("changed_files") or [])
    context = [f"上一任务 {task_id} 状态为 {status}，改动文件数 {changed_count}。"]
    if summary_path.exists():
        summary_line = _summary_line(summary_path.read_text(encoding="utf-8"))
        if summary_line:
            context.append(f"上一任务摘要：{summary_line}")
    return context[:2]


def render_context_block(items):
    if not items:
        return "  []"
    return "\n".join(f"  - {item}" for item in items)


def render_literal_block(text):
    return "\n".join(f"  {line}" if line else "" for line in str(text).splitlines())


def render_task(args):
    context_items = generate_auto_context() if args.auto_context else []
    return TASK_TEMPLATE.format(
        task_id=args.id,
        project=args.project,
        workspace=args.workspace,
        sandbox=args.sandbox,
        mode=args.mode,
        goal=render_literal_block(args.goal or "描述该任务的目标（一两句话）"),
        context_block=render_context_block(context_items),
        constraints_extra=(
            "  - git_diff_must_be_empty\n"
            if args.sandbox == "read-only"
            else ""
        ),
        output_extra=(
            "  - changed_files\n" if args.sandbox == "workspace-write" else ""
        ),
        verification_extra=(
            "  - git_diff_must_be_empty\n"
            if args.sandbox == "read-only"
            else "  - changed_files_below_threshold: 20\n"
        ),
    )


def render_plan(args):
    task_lines = []
    depends = None
    for idx, tid in enumerate(args.tasks, start=1):
        task_lines.append(f"  - task_id: {tid}")
        task_lines.append(f"    task_file: {tid}.task.yaml")
        if depends:
            task_lines.append(f"    depends_on:")
            task_lines.append(f"      - {depends}")
        depends = tid
    return PLAN_TEMPLATE.format(
        plan_id=args.id,
        project=args.project,
        workspace=args.workspace,
        tasks_block="\n".join(task_lines),
    )


def write_if_not_exists(path, content, force):
    if path.exists() and not force:
        print(f"SKIP: {path} already exists (use --force to overwrite)")
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"CREATED: {path}")
    return True


def cmd_task(args):
    content = render_task(args)
    path = Path(args.out).expanduser() if args.out else EXAMPLES_DIR / f"{args.id}.task.yaml"
    if not path.is_absolute():
        path = (ROOT_DIR / path).resolve()
    if write_if_not_exists(path, content, args.force):
        print(f"next: python3 agentops/agentops-dispatch-codex.py {path}")
    return 0


def cmd_plan(args):
    if not args.tasks:
        print("ERROR: --tasks is required for plan command (comma-separated task ids)", file=sys.stderr)
        return 2
    content = render_plan(args)
    path = Path(args.out).expanduser() if args.out else EXAMPLES_DIR / f"{args.id}.plan.yaml"
    if not path.is_absolute():
        path = (ROOT_DIR / path).resolve()
    if write_if_not_exists(path, content, args.force):
        print(f"next: python3 agentops/agentops-dispatch-plan.py {path}")
    return 0


def build_parser():
    parser = argparse.ArgumentParser(description="Generate AgentOps task/plan YAML templates")
    parser.add_argument("--project", default="headroom", help="Project name")
    parser.add_argument("--workspace", default=detect_default_workspace(), help="Target workspace directory")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--out", help="Output file path (default: examples/<id>.<type>.yaml)")

    subparsers = parser.add_subparsers(dest="command", required=True)

    task_parser = subparsers.add_parser("task", help="Generate a task template")
    task_parser.add_argument("id", help="Task id (e.g., my-feature-001)")
    task_parser.add_argument("--sandbox", default="read-only", choices=["read-only", "workspace-write"], help="Sandbox mode")
    task_parser.add_argument("--mode", default="analysis", choices=["analysis", "change", "review"], help="Task mode")
    task_parser.add_argument("--goal", help="Short goal description")
    task_parser.add_argument("--auto-context", action="store_true", help="Add short context from latest AgentOps run")

    plan_parser = subparsers.add_parser("plan", help="Generate a plan template")
    plan_parser.add_argument("id", help="Plan id (e.g., my-plan-001)")
    plan_parser.add_argument("--tasks", help="Comma-separated task ids (e.g., step1,step2,step3)")

    return parser


def main():
    args = build_parser().parse_args()
    if args.command == "task":
        return cmd_task(args)
    if args.command == "plan":
        tasks_list = [t.strip() for t in args.tasks.split(",") if t.strip()] if args.tasks else []
        args.tasks = tasks_list
        return cmd_plan(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
