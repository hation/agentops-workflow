# AgentOps Workflow

AgentOps Workflow 是一个本地 Agent 编排实验项目，用于把任务模板、Codex 执行、结果落盘和 PilotDeck 可检索任务记录串成一个轻量闭环。

## 功能

- 生成 AgentOps task / plan YAML
- 调用 Codex 执行只读分析或 workspace-write 任务
- 将执行结果保存到 `.agentops/runs/`
- 将任务摘要同步到目标 workspace 的 `.pilotdeck/tasks/`
- 提供 Headroom 代理启动、健康检查和压缩验证脚本

## 目录结构

```text
agentops/              AgentOps CLI 和共享工具
headroom/servers/      Headroom 代理启动脚本
headroom/benchmarks/   Headroom 压缩验证脚本
scripts/               一键启动和健康检查脚本
examples/              task / plan 示例
docs/                  架构、集成、状态和使用文档
config/                配置示例
tests/                 pytest 测试
```

## 前置条件

- Python 3.12+
- Codex CLI 已配置可用 provider
- 本机模型代理按你的环境启动，例如 `http://127.0.0.1:15721/v1`
- 如需 Headroom：本地 `.venv-headroom/` 和 `.deps/` 依赖需自行准备，这些目录不会提交到 GitHub

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 快速开始

检查服务状态：

```bash
bash scripts/check-agentops-stack.sh
```

生成只读任务：

```bash
python3 agentops/agentops-new.py \
  --out examples/check-project.task.yaml \
  task check-project \
  --goal "总结当前项目的脚本目录、文档目录和任务记录目录"
```

执行任务：

```bash
python3 agentops/agentops-dispatch-codex.py examples/check-project.task.yaml
```

查看结果：

```bash
python3 agentops/agentops-read-result.py check-project
```

## 任务记录

执行结果会保存到：

```text
.agentops/runs/<task_id>/
```

如果 task 的 `workspace` 指向某个项目，还会同步到：

```text
<workspace>/.pilotdeck/tasks/<task_id>/
```

`.agentops/`、`.pilotdeck/` 和 `.taskmaster/` 是本地运行产物，默认不会提交。

## 文档

- 架构文档：[docs/architecture](docs/architecture)
- PilotDeck 集成：[docs/integration](docs/integration)
- 使用手册：[docs/usage](docs/usage)
- 当前状态：[docs/status](docs/status)

## 验证

```bash
python3 -m py_compile agentops/*.py headroom/servers/*.py headroom/benchmarks/*.py
python3 -m pytest tests/
```
