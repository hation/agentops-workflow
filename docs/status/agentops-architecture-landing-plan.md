# AgentOps 工具架构落地开发计划

更新时间：2026-06-14

## 1. 目标

将当前 `Trae + PilotDeck + Codex + Headroom + 火山模型` 工具链从"已验证可行"推进到"可长期日常使用"的落地状态。

最终目标：

```text
1. Trae 作为工程总控台
2. PilotDeck 管理 Workspace 与项目记忆
3. Codex 桌面端作为代码执行 Agent
4. Headroom 8789 提供稳定模型代理链路
5. Headroom 8790 默认提供 balanced 调优链路，direct/fast 作为按需切换模式
6. 本机火山代理 15721 作为底层模型入口
7. 所有关键服务可一键启动、可健康检查、可故障恢复
```

相关文档：

```text
<repo-root>/docs/architecture/agentops-tools-architecture.md
<repo-root>/docs/usage/codex-headroom-volcengine-usage-manual.md
<repo-root>/docs/architecture/agentops-workflow-design.md
<repo-root>/docs/integration/agentops-pilotdeck-integration.md
```

## 2. 当前架构分层

```text
第 1 层：Trae，工程总控层
第 2 层：PilotDeck，项目管理与记忆层
第 3 层：Codex 桌面端 / Codex CLI，Agent 执行层
第 4 层：Headroom，模型代理与上下文压缩层
第 5 层：本机火山代理 15721 + 火山 ark-code-latest，模型底座层
```

推荐运行链路：

```text
日常稳定链路：Codex -> custom -> 15721 -> 火山
Headroom 稳定链路：Codex -> headroom -> 8789 -> 15721 -> 火山
默认调优链路：Trae / benchmark / 工具输出 -> 8790 balanced -> 15721 -> 火山
压缩验证链路：临时启动 start_headroom_direct.py -> 8790 -> 15721 -> 火山
低延迟验证链路：临时启动 start_headroom_fast.py -> 8790 -> 15721 -> 火山
```

## 3. 当前检查结果

检查时间：2026-06-14

### 3.1 已完成项

| 模块 | 状态 | 说明 |
|---|---|---|
| Trae | 已可作为主控使用 | 负责协调、执行命令、写文档、检查服务 |
| 本机火山代理 15721 | 正常运行 | `127.0.0.1:15721` 正在监听 |
| Codex custom provider | 已存在 | 指向 `http://127.0.0.1:15721/v1` |
| Codex headroom provider | 已存在 | 指向 `http://127.0.0.1:8789/v1` |
| 使用手册 | 已创建 | `codex-headroom-volcengine-usage-manual.md` |
| 架构图 | 已创建 | `agentops-tools-architecture.md` |
| 工作流设计 | 已完成 | `agentops-workflow-design.md` |
| PilotDeck 集成方案 | 已完成 | `agentops-pilotdeck-integration.md` |
| Headroom 8789 启动脚本 | 已存在 | `start_agentops_stack.sh` 调用 |
| Headroom 8790 启动脚本 | 已存在 | `start_headroom_balanced.py` 为默认模式 |
| 压缩 benchmark 脚本 | 已存在 | `headroom_tool_output_compress_bench.py` |
| ONNX Runtime 稳定软链 | 已完成 | `$HOME/.headroom/ort.dylib` |
| 一键启动脚本 | 已完成 | `start-agentops-stack.sh` |
| 健康检查脚本 | 已完成 | `check-agentops-stack.sh` |
| macOS launchd 自动恢复 | 已完成 | `com.xingan.agentops-stack.plist` |
| PilotDeck Gateway 端口 | 已固化 | Gateway 18790，18789 保留给 OpenClaw Control |
| Headroom 8790 balanced | 已默认启用 | 与 launchd 集成，重启后自动恢复 |
| Headroom 8790 fast/direct | 按需切换 | `start_headroom_fast.py` / `start_headroom_direct.py` |

### 3.2 AgentOps 脚本清单

| 脚本 | 职责 | 状态 |
|---|---|---|
| `agentops/agentops_core.py` | 共享工具：路径常量、I/O、同步逻辑 | ✅ 完整 |
| `agentops/agentops-dispatch-codex.py` | 单任务调度：执行 Codex、处理结果、安全检查 | ✅ 完整 |
| `agentops/agentops-dispatch-plan.py` | 多任务计划调度：依赖、失败停止、结果汇总 | ✅ 完整 |
| `agentops/agentops-read-result.py` | 读取单个任务结果 | ✅ 完整 |
| `agentops/agentops-read-plan.py` | 读取多任务计划结果 | ✅ 完整 |
| `agentops/agentops-new.py` | 任务/计划 YAML 模板生成 | ✅ 完整 |

### 3.3 PilotDeck Tier 集成状态

| Tier | 功能 | 状态 | 说明 |
|---|---|---|---|
| Tier 1 | 文件系统同步 | ✅ 完成 | `.pilotdeck/tasks/<task_id>/`、`.pilotdeck/plans/<plan_id>/` |
| Tier 2 | TaskMaster 同步 | ✅ 完成 | `.taskmaster/tasks/tasks.json` 写入 |
| Tier 3 | HTTP API + WebSocket | 暂缓 | PilotDeck UI 未接入 HTTP API |

### 3.4 Phase 落地状态总览

| Phase | 内容 | 状态 |
|---|---|---|
| Phase 1 | 本地研发最小闭环（Trae + PilotDeck + Codex + Headroom） | ✅ 已完成并验证 |
| Phase 2 | 加入 PilotDeck 项目隔离 | ✅ 已完成并验证 |
| Phase 3 | OpenClaw 远程入口（飞书/Telegram） | ❌ 尚未开始 |
| Phase 4 | 云端执行与长任务（Docker sandbox） | ❌ 尚未开始 |
| Phase 5 | Hermes 旁路个人助理 | ❌ 尚未开始 |

### 3.5 Headroom 压缩验证状态

| 场景 | 状态 | 压缩率 |
|---|---|---|
| 重复日志类旧工具输出 | ✅ 已验证 | 99.52%（60274 → 287 tokens） |
| 代码审查/源码全文 | ⚠️ 保守不压缩 | 默认不压缩以保留代码细节 |
| 结构化 JSON 工具输出 | ⚠️ 待补测 | 本轮未压缩，后续可调 JSON/SmartCrusher 策略 |
| Rust content detector | ⚠️ Python regex fallback | ONNX Runtime API v24 不匹配，1.23.2 fallback 可用 |

## 4. 当前缺口

| 优先级 | 缺口 | 当前状态 |
|---|---|---|
| 高 | 端到端新任务验证 | 需跑一个新的 video-analyzer 只读任务，验证 TaskMaster 写入链路 |
| 高 | `agentops-new.py` 模板质量 | 需实际走一遍：新建 → dispatch → 查看结果，验证 YAML schema 一致性 |
| 中 | Headroom 代码/JSON 场景压缩收益 | 仅日志类已验证，代码 diff 和 JSON 输出待补测 |
| 中 | OpenClaw Phase 3 | 尚未开始（飞书/Telegram 消息入口） |
| 低 | Rust content detector 与 ONNX API mismatch | 已用 Python regex fallback，非阻塞 |
| 低 | MCP 服务封装 | 设计文档 §10 有列表，当前以 CLI 方式调用 |

## 5. 推荐执行顺序

### P0 — 必做（短期 1-2 周）

```text
1. 端到端新任务验证
   - 跑一个新的 video-analyzer 只读任务（例如："识别 CLI 入口与主要调用链"）
   - 确认 .taskmaster/tasks/tasks.json 字段完整
   - 用 agentops-read-result.py 能正确回读

2. agentops-new.py 模板质量检查
   - 新建一个计划 YAML -> dispatch -> 查看结果
   - 确认生成的 schema 与 dispatch-plan.py 期望完全一致

3. Headroom 代码审查与 JSON 场景压缩收益验证
   - 用 headroom_tool_output_compress_bench.py 新增代码 diff / JSON 样例
   - 对比 8790 balanced / direct / fast 三种模式
```

### P1 — 应做（中期 1 个月）

```text
4. OpenClaw Phase 3 最小实现：飞书消息 -> PilotDeck 任务
   - 最小 MVP：飞书 bot 接收消息，只支持"只读指令"（status、summary）
   - 结果回传到飞书 chat
   - 使用设计文档 §6.2 权限策略：仅白名单用户可触发

5. 任务状态事件时间戳
   - 在 result.json 和 plan-result.json 中补充状态变更时间戳
   - 让 agentops-read-result.py / agentops-read-plan.py 能打印时间线
```

### P2 — 可延后（稳定后再做）

```text
6. MCP 服务封装
7. Phase 4：Docker sandbox 长任务
8. Phase 5：Hermes 个人助理
```

## 6. 一键启动与健康检查

### 6.1 启动脚本

```bash
bash <repo-root>/scripts/start-agentops-stack.sh
```

### 6.2 健康检查

```bash
bash <repo-root>/scripts/check-agentops-stack.sh
```

### 6.3 端口验收标准

```bash
lsof -i :15721 -sTCP:LISTEN -P -n  # 本机火山代理
lsof -i :8789 -sTCP:LISTEN -P -n   # Headroom 稳定代理
lsof -i :8790 -sTCP:LISTEN -P -n   # Headroom 优化代理
lsof -i :18790 -sTCP:LISTEN -P -n # PilotDeck Gateway
```

### 6.4 Headroom Rust core 验收

```bash
cd <repo-root>
.venv-headroom/bin/python -c 'from headroom._core import hello; print(hello())'
# 预期：headroom-core
```

### 6.5 压缩收益验收

```bash
cd <repo-root>
.venv-headroom/bin/python headroom_tool_output_compress_bench.py
# 预期：savings_pct=99.52
```

## 7. 交付物清单

### 7.1 核心文档

```text
<repo-root>/docs/architecture/agentops-workflow-design.md        # 工作流设计
<repo-root>/docs/status/agentops-architecture-landing-plan.md  # 本文档
<repo-root>/docs/architecture/agentops-tools-architecture.md    # 架构图
<repo-root>/docs/usage/codex-headroom-volcengine-usage-manual.md  # 使用手册
<repo-root>/docs/integration/agentops-pilotdeck-integration.md  # PilotDeck 集成方案
```

### 7.2 核心脚本

```text
<repo-root>/agentops/agentops_core.py              # 共享工具模块
<repo-root>/agentops/agentops-dispatch-codex.py   # 单任务调度
<repo-root>/agentops/agentops-dispatch-plan.py    # 多任务计划调度
<repo-root>/agentops/agentops-read-result.py      # 任务结果读取
<repo-root>/agentops/agentops-read-plan.py        # 计划结果读取
<repo-root>/agentops/agentops-new.py              # 任务/计划模板生成
```

### 7.3 Headroom 相关

```text
<repo-root>/headroom/servers/start_headroom_balanced.py     # balanced 模式（默认）
<repo-root>/headroom/servers/start_headroom_direct.py       # direct 模式（压缩验证）
<repo-root>/headroom/servers/start_headroom_fast.py         # fast 模式（低延迟）
<repo-root>/headroom/servers/start_headroom_no_kompress.py  # no_kompress 模式
<repo-root>/headroom/benchmarks/headroom_tool_output_compress_bench.py  # 压缩 benchmark
<repo-root>/headroom/benchmarks/headroom_compress_api_bench.py           # 压缩 API benchmark
<repo-root>/headroom/benchmarks/headroom_compression_bench.py            # 压缩 benchmark
```

### 7.4 运维脚本

```text
<repo-root>/scripts/start-agentops-stack.sh       # 一键启动
<repo-root>/scripts/check-agentops-stack.sh       # 健康检查
$HOME/.headroom/start-agentops-stack-launchd.sh      # launchd 入口脚本
$HOME/Library/LaunchAgents/com.xingan.agentops-stack.plist  # macOS 自动恢复
$HOME/.headroom/ort.dylib                               # ONNX Runtime 稳定软链
```

## 8. 当前结论

Phase 1（本地研发最小闭环）已完成并验证，Phase 2（PilotDeck 项目隔离）也已完整落地。

**已验证的核心能力：**
- Trae + PilotDeck + Codex + Headroom 四组件链路跑通
- 单任务执行与多任务计划调度
- 任务结果文件系统同步 + TaskMaster 状态同步
- Headroom 日志类输入 99.52% 压缩率
- 核心服务一键启动、健康检查、macOS launchd 自动恢复

**下一阶段优先事项：**
- P0：端到端新任务验证 + 模板质量检查
- P1：OpenClaw Phase 3 飞书消息入口最小 MVP

**暂缓事项：**
- Phase 4（Docker sandbox）、Phase 5（Hermes 个人助理）待 Phase 3 稳定后再评估
