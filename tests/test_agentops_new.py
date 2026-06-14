import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "agentops" / "agentops-new.py"


def load_agentops_new():
    spec = importlib.util.spec_from_file_location("agentops_new", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_render_task_preserves_multiline_goal_as_valid_yaml():
    module = load_agentops_new()
    args = type(
        "Args",
        (),
        {
            "auto_context": False,
            "id": "deploy-plan-test",
            "project": "headroom",
            "workspace": "/tmp/project",
            "sandbox": "read-only",
            "mode": "analysis",
            "goal": "第一行\n\n第二行\n- item",
        },
    )()
    content = module.render_task(args)
    data = yaml.safe_load(content)
    assert data["task_id"] == "deploy-plan-test"
    assert data["goal"] == "第一行\n\n第二行\n- item\n"
