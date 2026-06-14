import runpy
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin" / "agentops"


def load_cli():
    return runpy.run_path(str(BIN), run_name="agentops_cli_test")


def test_slugify_and_task_id_generation(monkeypatch, tmp_path):
    cli = load_cli()

    class FakeDatetime:
        @classmethod
        def now(cls):
            return type("T", (), {"strftime": lambda self, fmt: "20260614-120000"})()

    monkeypatch.setitem(cli["timestamp"].__globals__, "datetime", FakeDatetime)
    workspace = tmp_path / "My Project!"
    workspace.mkdir()
    assert cli["slugify"]("My Project!") == "my-project"
    assert cli["make_task_id"]("audit", workspace) == "audit-my-project-20260614-120000"


def test_create_task_uses_current_workspace_and_read_only(monkeypatch, tmp_path):
    cli = load_cli()
    calls = []

    def fake_run(cmd, cwd=cli["ROOT_DIR"]):
        calls.append((cmd, cwd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setitem(cli["create_task"].__globals__, "run_command", fake_run)
    code, out = cli["create_task"]("audit-demo", tmp_path, "分析项目", "read-only", "analysis")
    assert code == 0
    assert out.name == "audit-demo.task.yaml"
    cmd = calls[0][0]
    assert str(cli["AGENTOPS_DIR"] / "agentops-new.py") in cmd
    assert "--workspace" in cmd
    assert cmd[cmd.index("--workspace") + 1] == str(tmp_path)
    assert cmd[cmd.index("--sandbox") + 1] == "read-only"
    assert cmd[cmd.index("--mode") + 1] == "analysis"
    assert cmd[cmd.index("--goal") + 1] == "分析项目"


def test_fix_uses_workspace_write(monkeypatch, tmp_path):
    cli = load_cli()
    calls = []

    def fake_create_task(task_id, workspace, goal, sandbox, mode):
        calls.append((task_id, workspace, goal, sandbox, mode))
        task_file = tmp_path / f"{task_id}.task.yaml"
        task_file.write_text("task", encoding="utf-8")
        return 0, task_file

    monkeypatch.setitem(cli["cmd_do"].__globals__, "create_task", fake_create_task)
    monkeypatch.setitem(cli["cmd_do"].__globals__, "dispatch_task", lambda task_file: 0)
    monkeypatch.setitem(cli["cmd_do"].__globals__, "read_task", lambda task_id, summary=True: 0)
    args = type("Args", (), {"workspace": str(tmp_path), "goal": "修复 README", "task_id": "fix-demo", "no_summary": True})()
    assert cli["cmd_do"](args, "fix", "workspace-write", "change") == 0
    assert calls == [("fix-demo", tmp_path.resolve(), "修复 README", "workspace-write", "change")]


def test_deploy_creates_read_only_plan_task(monkeypatch, tmp_path):
    cli = load_cli()
    calls = []

    def fake_create_task(task_id, workspace, goal, sandbox, mode):
        calls.append((task_id, workspace, goal, sandbox, mode))
        task_file = tmp_path / f"{task_id}.task.yaml"
        task_file.write_text("task", encoding="utf-8")
        return 0, task_file

    monkeypatch.setitem(cli["cmd_deploy"].__globals__, "create_task", fake_create_task)
    monkeypatch.setitem(cli["cmd_deploy"].__globals__, "dispatch_task", lambda task_file: 0)
    monkeypatch.setitem(cli["cmd_deploy"].__globals__, "read_task", lambda task_id, summary=True: 0)
    args = type("Args", (), {"workspace": ".", "target": str(tmp_path), "task_id": "deploy-demo", "no_summary": True, "auto_local": False, "plan_only": True})()
    assert cli["cmd_deploy"](args) == 0
    assert calls[0][0] == "deploy-demo"
    assert calls[0][1] == tmp_path.resolve()
    assert calls[0][3] == "read-only"
    assert calls[0][4] == "analysis"
    assert "拆解部署准备任务" in calls[0][2]


def test_deploy_auto_local_still_stops_after_plan(monkeypatch, tmp_path, capsys):
    cli = load_cli()
    monkeypatch.setitem(cli["cmd_deploy"].__globals__, "create_task", lambda task_id, workspace, goal, sandbox, mode: (0, tmp_path / "task.yaml"))
    monkeypatch.setitem(cli["cmd_deploy"].__globals__, "dispatch_task", lambda task_file: 0)
    monkeypatch.setitem(cli["cmd_deploy"].__globals__, "read_task", lambda task_id, summary=True: 0)
    args = type("Args", (), {"workspace": str(tmp_path), "target": None, "task_id": "deploy-demo", "no_summary": True, "auto_local": True, "plan_only": False})()
    assert cli["cmd_deploy"](args) == 0
    assert "不会自动修改文件" in capsys.readouterr().out


def test_last_local_reads_latest_pilotdeck_summary(tmp_path, capsys):
    cli = load_cli()
    tasks = tmp_path / ".pilotdeck" / "tasks"
    older = tasks / "older"
    newer = tasks / "newer"
    older.mkdir(parents=True)
    newer.mkdir(parents=True)
    older_summary = older / "summary.md"
    newer_summary = newer / "summary.md"
    older_summary.write_text("old summary", encoding="utf-8")
    newer_summary.write_text("new summary", encoding="utf-8")
    args = type("Args", (), {"workspace": str(tmp_path), "local": True, "no_summary": False})()
    assert cli["cmd_last"](args) == 0
    output = capsys.readouterr().out
    assert "task_id: newer" in output
    assert "new summary" in output
