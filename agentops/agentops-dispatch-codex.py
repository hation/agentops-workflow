#!/usr/bin/env python3
import argparse
import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

from agentops_core import (
    ROOT_DIR,
    RUNS_DIR,
    now_iso,
    write_text,
    write_json,
    load_yaml,
    sync_run_to_workspace,
    sync_run_to_taskmaster,
)

REQUIRED_FIELDS = [
    "task_id",
    "project",
    "workspace",
    "provider",
    "sandbox",
    "mode",
    "goal",
    "constraints",
    "expected_output",
    "verification",
]
ALLOWED_PROVIDERS = {"custom", "headroom"}
ALLOWED_SANDBOXES = {"read-only", "workspace-write"}
DEFAULT_MAX_CHANGED_FILES = 10
SENSITIVE_PATTERNS = [
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "*.crt",
    "*token*",
    "*secret*",
    "*credential*",
    "**/.env",
    "**/.env.*",
    "**/*.pem",
    "**/*.key",
    "**/*.crt",
    "**/*token*",
    "**/*secret*",
    "**/*credential*",
]


def load_task(path):
    return load_yaml(path)


def validate_task(task):
    missing = [field for field in REQUIRED_FIELDS if field not in task]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")
    if task["provider"] not in ALLOWED_PROVIDERS:
        raise ValueError(f"provider must be one of: {', '.join(sorted(ALLOWED_PROVIDERS))}")
    if task["sandbox"] not in ALLOWED_SANDBOXES:
        raise ValueError(f"sandbox must be one of: {', '.join(sorted(ALLOWED_SANDBOXES))}")
    workspace = Path(task["workspace"]).expanduser()
    if not workspace.exists() or not workspace.is_dir():
        raise ValueError(f"workspace does not exist or is not a directory: {workspace}")
    verification_commands = task.get("verification_commands", [])
    if verification_commands is not None and not isinstance(verification_commands, list):
        raise ValueError("verification_commands must be a list when provided")
    max_changed_files = task.get("max_changed_files", DEFAULT_MAX_CHANGED_FILES)
    if not isinstance(max_changed_files, int) or max_changed_files < 0:
        raise ValueError("max_changed_files must be a non-negative integer")
    if shutil.which("codex") is None:
        raise ValueError("codex command not found in PATH")


def ensure_run_dir(task_id):
    run_dir = RUNS_DIR / task_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def normalize_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def render_prompt(task):
    context = "\n".join(f"- {item}" for item in normalize_list(task.get("context")))
    constraints = "\n".join(f"- {item}" for item in normalize_list(task.get("constraints")))
    expected_output = "\n".join(f"- {item}" for item in normalize_list(task.get("expected_output")))
    sections = []
    if context.strip():
        sections.append(f"背景：\n{context}")
    if constraints.strip():
        sections.append(f"约束：\n{constraints}")
    if expected_output.strip():
        sections.append(f"期望：\n{expected_output}")
    details = "\n".join(sections)
    sandbox_rule = "sandbox: read-only"
    if task["sandbox"] == "workspace-write":
        sandbox_rule = "sandbox: workspace-write"
    return f"""项目：{task['project']}
工作目录：{task['workspace']}
模式：{task['mode']} | {sandbox_rule}

目标：{task['goal']}
{details}

限制：不要改 .pilotdeck/、.agentops/；不要 commit/push；改动超 10 个文件先停并说明

输出格式：
- 修改文件：
- 实现摘要：
- 验证命令：
- 验证结果：
- 风险：
- 建议下一步：
"""


def run_command(args, cwd):
    return subprocess.run(
        args,
        cwd=str(cwd),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def run_shell_command(command, cwd):
    return subprocess.run(
        command,
        cwd=str(cwd),
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git_output(workspace, args):
    if not (workspace / ".git").exists():
        return ""
    result = run_command(["git", *args], workspace)
    return result.stdout if result.returncode == 0 else result.stdout + result.stderr


def workspace_snapshot(workspace):
    if (workspace / ".git").exists():
        return set()
    ignored_parts = {"__pycache__", ".venv-headroom", ".deps"}
    ignored_prefixes = {
        Path(".agentops/runs"),
        Path(".agentops/plans"),
        Path(".pilotdeck/tasks"),
        Path(".pilotdeck/plans"),
    }
    files = set()
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(workspace)
        if any(part in ignored_parts for part in relative.parts):
            continue
        if any(relative == prefix or prefix in relative.parents for prefix in ignored_prefixes):
            continue
        files.add(str(relative))
    return files


def snapshot_status(before_files, after_files):
    added = sorted(after_files - before_files)
    deleted = sorted(before_files - after_files)
    lines = [f"?? {path}" for path in added]
    lines.extend(f" D {path}" for path in deleted)
    return "\n".join(lines) + ("\n" if lines else "")


def extract_codex_answer(stdout):
    marker = "codex\n"
    if marker in stdout:
        return stdout.split(marker, 1)[1].strip()
    lines = stdout.strip().splitlines()
    content_lines = []
    for line in lines:
        if line.startswith("20") and "codex_otel" in line:
            continue
        if line.startswith("tokens used"):
            break
        content_lines.append(line)
    return "\n".join(content_lines).strip()


def parse_changed_files(status_text):
    changed = []
    deleted = []
    for line in status_text.splitlines():
        if not line.strip():
            continue
        status = line[:2]
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        changed.append({"status": status, "path": path, "raw": line})
        if "D" in status:
            deleted.append(path)
    return changed, deleted


def find_sensitive_files(changed_files):
    sensitive = []
    for item in changed_files:
        path = item["path"]
        lower_path = path.lower()
        for pattern in SENSITIVE_PATTERNS:
            if fnmatch.fnmatch(lower_path, pattern.lower()):
                sensitive.append(path)
                break
    return sensitive


def _filter_codex_stderr(stderr):
    lines = stderr.splitlines()
    kept = []
    for line in lines:
        stripped = line.strip()
        if "tokens used" in stripped or "ERROR" in stripped or "WARN" in stripped:
            kept.append(line)
    return "\n".join(kept) + ("\n" if kept else "")


def run_verification_commands(commands, workspace, run_dir):
    results = []
    log_parts = []
    for index, command in enumerate(commands, start=1):
        result = run_shell_command(str(command), workspace)
        item = {
            "index": index,
            "command": str(command),
            "exit_code": result.returncode,
            "stdout_file": f"verify-{index}-stdout.log",
            "stderr_file": f"verify-{index}-stderr.log",
        }
        write_text(run_dir / item["stdout_file"], result.stdout)
        write_text(run_dir / item["stderr_file"], result.stderr)
        if not result.stderr.strip():
            (run_dir / item["stderr_file"]).unlink()
            item["stderr_file"] = None
        log_parts.append(f"$ {command}\nexit_code={result.returncode}\n\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}\n")
        results.append(item)
    write_text(run_dir / "verify.log", "\n---\n".join(log_parts))
    return results


def build_summary(task, status, codex_answer, result):
    verification_lines = [
        f"- codex_exit_code: {result['codex_exit_code']}",
        f"- git_diff_empty: {str(result['git_diff_empty']).lower()}",
        f"- changed_files: {len(result['changed_files'])}",
        f"- verification_passed: {str(result['verification_passed']).lower()}",
    ]
    if result["verification_results"]:
        verification_lines.append("- verification_commands:")
        for item in result["verification_results"]:
            verification_lines.append(f"  - {item['command']} -> {item['exit_code']}")
    return f"""# Task {task['task_id']} — {status}

## Summary

{codex_answer or '无可解析输出，请查看 codex-stdout.log 和 codex-stderr.log。'}

## Checks

{chr(10).join(verification_lines)}
"""


def decide_status(codex_exit_code, sandbox, git_diff_empty, verification_passed, changed_files, deleted_files, sensitive_files, max_changed_files):
    if codex_exit_code != 0 or not verification_passed:
        return "failed"
    if sandbox == "read-only" and not git_diff_empty:
        return "requires_review"
    if len(changed_files) > max_changed_files:
        return "requires_review"
    if deleted_files or sensitive_files:
        return "requires_review"
    return "success"


def build_risk_summary(status, sandbox, git_diff_empty, verification_passed, changed_files, deleted_files, sensitive_files, max_changed_files):
    risks = []
    if sandbox == "read-only":
        risks.append("- 静态分析结果需要人工审查；本任务未运行项目业务命令。")
    if sandbox == "read-only" and not git_diff_empty:
        risks.append("- read-only 任务产生了 git diff，需要人工审查。")
    if sandbox == "workspace-write":
        risks.append("- workspace-write 任务已产生或允许产生代码变更，必须由 Trae 审查 diff.patch。")
    if len(changed_files) > max_changed_files:
        risks.append(f"- 修改文件数量 {len(changed_files)} 超过限制 {max_changed_files}。")
    if deleted_files:
        risks.append("- 检测到删除文件：" + ", ".join(deleted_files))
    if sensitive_files:
        risks.append("- 检测到敏感文件变更：" + ", ".join(sensitive_files))
    if not verification_passed:
        risks.append("- verification_commands 存在失败命令。")
    if status == "success" and not risks:
        risks.append("- 未发现自动拦截风险，仍需人工审查 Codex 输出。")
    return "\n".join(risks)


def build_next_summary(status):
    if status == "success":
        return "- Trae 读取 summary.md、result.json 和 diff.patch 后决定是否派发下一步任务。"
    if status == "requires_review":
        return "- 先人工审查 diff.patch、changed_files 和风险项，再决定是否继续。"
    return "- 先处理失败原因和 verify.log，再重跑或拆分任务。"


def dispatch(task_path):
    task = load_task(task_path)
    validate_task(task)
    task_id = str(task["task_id"])
    workspace = Path(task["workspace"]).expanduser().resolve()
    run_dir = ensure_run_dir(task_id)
    started_at = now_iso()

    prompt = render_prompt(task)
    write_text(run_dir / "task.yaml", task_path.read_text(encoding="utf-8"))
    write_text(run_dir / "codex-prompt.md", prompt)

    before_snapshot = workspace_snapshot(workspace)
    before_status = git_output(workspace, ["status", "--short"])
    before_diff = git_output(workspace, ["diff", "--"])
    write_text(run_dir / "git-status-before.txt", before_status)
    write_text(run_dir / "git-diff-before.patch", before_diff)
    if not before_status.strip():
        (run_dir / "git-status-before.txt").unlink()
    if not before_diff.strip():
        (run_dir / "git-diff-before.patch").unlink()

    codex_args = [
        "codex",
        "exec",
        "-c",
        f'model_provider="{task["provider"]}"',
        "--sandbox",
        task["sandbox"],
        "--skip-git-repo-check",
        prompt,
    ]
    codex_result = run_command(codex_args, workspace)
    write_text(run_dir / "codex-stdout.log", codex_result.stdout)
    filtered_stderr = _filter_codex_stderr(codex_result.stderr)
    write_text(run_dir / "codex-stderr.log", filtered_stderr)
    if not filtered_stderr.strip():
        (run_dir / "codex-stderr.log").unlink()

    verification_commands = normalize_list(task.get("verification_commands"))
    verification_results = run_verification_commands(verification_commands, workspace, run_dir) if verification_commands else []
    verification_passed = all(item["exit_code"] == 0 for item in verification_results)

    ended_at = now_iso()
    after_status = git_output(workspace, ["status", "--short"])
    after_diff = git_output(workspace, ["diff", "--"])
    after_snapshot = workspace_snapshot(workspace)
    if not after_status and not after_diff and before_snapshot:
        after_status = snapshot_status(before_snapshot, after_snapshot)
    write_text(run_dir / "git-status-after.txt", after_status)
    write_text(run_dir / "diff.patch", after_diff)
    if not after_status.strip():
        (run_dir / "git-status-after.txt").unlink()
    if not after_diff.strip():
        (run_dir / "diff.patch").unlink()

    changed_items, deleted_files = parse_changed_files(after_status)
    changed_files = [item["raw"] for item in changed_items]
    sensitive_files = find_sensitive_files(changed_items)
    git_diff_empty = after_diff.strip() == ""
    max_changed_files = task.get("max_changed_files", DEFAULT_MAX_CHANGED_FILES)
    status = decide_status(
        codex_result.returncode,
        task["sandbox"],
        git_diff_empty,
        verification_passed,
        changed_files,
        deleted_files,
        sensitive_files,
        max_changed_files,
    )
    risk_summary = build_risk_summary(
        status,
        task["sandbox"],
        git_diff_empty,
        verification_passed,
        changed_files,
        deleted_files,
        sensitive_files,
        max_changed_files,
    )
    next_summary = build_next_summary(status)

    result = {
        "task_id": task_id,
        "status": status,
        "project": task["project"],
        "workspace": str(workspace),
        "provider": task["provider"],
        "sandbox": task["sandbox"],
        "mode": task["mode"],
        "started_at": started_at,
        "ended_at": ended_at,
        "codex_exit_code": codex_result.returncode,
        "changed_files": changed_files,
        "changed_file_count": len(changed_files),
        "deleted_files": deleted_files,
        "sensitive_files": sensitive_files,
        "max_changed_files": max_changed_files,
        "git_diff_empty": git_diff_empty,
        "verification_commands": verification_commands,
        "verification_results": verification_results,
        "verification_passed": verification_passed,
        "risk_summary": risk_summary,
        "next_summary": next_summary,
        "output_files": {
            "task": "task.yaml",
            "prompt": "codex-prompt.md",
            "stdout": "codex-stdout.log",
            "stderr": "codex-stderr.log",
            "summary": "summary.md",
            "diff": "diff.patch",
            "verify": "verify.log" if verification_commands else None,
        },
    }

    codex_answer = extract_codex_answer(codex_result.stdout)
    summary_text = build_summary(task, status, codex_answer, result)
    sync_target_dir = workspace / ".pilotdeck" / "tasks" / task_id
    result["pilotdeck_task_dir"] = str(sync_target_dir)
    result["synced_to_workspace_pilotdeck"] = True
    write_json(run_dir / "result.json", result)
    write_text(run_dir / "summary.md", summary_text)
    sync_run_to_workspace(run_dir, workspace, task_id)
    taskmaster_path = sync_run_to_taskmaster(run_dir, workspace, task, result, summary_text)
    result["taskmaster_tasks_json"] = str(taskmaster_path)
    result["synced_to_taskmaster"] = True
    write_json(run_dir / "result.json", result)
    return result, run_dir


def main():
    parser = argparse.ArgumentParser(description="Dispatch an AgentOps task to Codex")
    parser.add_argument("task", type=Path, help="Path to AgentOps task YAML")
    args = parser.parse_args()

    try:
        result, run_dir = dispatch(args.task.resolve())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"task_id={result['task_id']}")
    print(f"status={result['status']}")
    print(f"run_dir={run_dir}")
    print(f"codex_exit_code={result['codex_exit_code']}")
    print(f"git_diff_empty={str(result['git_diff_empty']).lower()}")
    print(f"verification_passed={str(result['verification_passed']).lower()}")
    print(f"changed_file_count={result['changed_file_count']}")
    return 0 if result["status"] == "success" else 2


if __name__ == "__main__":
    raise SystemExit(main())
