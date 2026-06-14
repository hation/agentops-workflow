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
git clone https://github.com/hation/agentops-workflow.git
cd agentops-workflow
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

建议把全局入口加入 `PATH`：

```bash
export PATH="$PWD/bin:$PATH"
```

也可以创建软链：

```bash
ln -sf "$PWD/bin/agentops" /usr/local/bin/agentops
```

## 快速开始

在任意目标项目目录中运行：

```bash
agentops doctor
agentops audit
```

自定义只读分析：

```bash
agentops run "分析当前项目的登录流程和权限校验逻辑"
```

允许修改当前项目：

```bash
agentops fix "修复 README 中过期的启动命令"
```

查看最近结果：

```bash
agentops last
agentops last --local
```

如果没有配置全局入口，也可以从工具仓库直接运行：

```bash
/path/to/agentops-workflow/bin/agentops --workspace /path/to/target-project audit
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
