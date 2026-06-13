# PilotDeck UI/API 集成评估

**项目：** AgentOps × PilotDeck × Trae × Codex
**日期：** 2026-06-13
**状态：** Analysis Complete — 3 Tiers Identified

---

## 1. PilotDeck 架构要点

### 1.1 HTTP API 层（PilotDeck UI 服务器）

```
GET    /api/taskmaster/tasks/:projectName     # 读取 .taskmaster/tasks/tasks.json
POST   /api/taskmaster/add-task/:projectName   # 通过 task-master-ai CLI 添加任务
PUT    /api/taskmaster/update-task/:projectName/:taskId  # 更新任务状态/内容
POST   /api/taskmaster/init/:projectName        # 初始化 TaskMaster 目录
GET    /api/taskmaster/next/:projectName        # 调用 task-master CLI 取下一任务
GET    /api/taskmaster/detect/:projectName      # 检测 TaskMaster 配置状态
POST   /api/taskmaster/parse-prd/:projectName   # 从 PRD 生成任务
GET    /api/taskmaster/prd/:projectName          # 列出/读取 .taskmaster/docs/*.md
POST   /api/taskmaster/prd/:projectName          # 写入 PRD 文件
DELETE /api/taskmaster/prd/:projectName/:file    # 删除 PRD 文件
```

### 1.2 WebSocket 实时通知

- `/utils/taskmaster-websocket.js` 提供 `broadcastTaskMasterProjectUpdate` / `broadcastTaskMasterTasksUpdate`
- UI 侧的 TaskMaster 上下文可以订阅这些广播事件，动态刷新任务列表

### 1.3 核心 TypeScript Runtime

- `src/task/storage/TaskOutputStore.ts` — 任务输出的 ring buffer，支持 `totalBytes()` / `readSlice(offset, maxBytes)` / `append(chunk)` / disk spill
- `src/task/runtime/BackgroundTaskRuntime.ts` — 后台任务运行时（spawn/stop/状态管理）
- `src/agent/` — Agent Loop：输入处理、工具调用、结果汇总
- `src/router/` — 会话路由、token 统计、fallback

### 1.4 存储约定

```
<project_path>/
├── .taskmaster/
│   ├── tasks/tasks.json        # 任务清单（JSON，支持 tagged 格式）
│   ├── config.json             # TaskMaster 配置
│   ├── docs/*.md               # PRD / 产品需求文档
│   └── ...
└── .pilotdeck/                 # PilotDeck 自身会话 / 记忆
    └── (由 pilotdeck-paths.ts 管理)
```

---

## 2. AgentOps 当前状态

我们的 `agentops-*` 工具目前在项目根目录 `/path/to/<project>/` 下管理：

```
<project_root>/
├── .agentops/
│   ├── runs/                   # 每次 Codex 任务执行的产物
│   │   ├── <task_id>/
│   │   │   ├── result.json     # 状态、exit code、changed_files
│   │   │   ├── summary.md      # 任务摘要
│   │   │   └── diff.patch      # 文件变更 patch
│   ├── plans/                  # 多任务计划的产物
│   │   └── <plan_id>/
│   │       ├── plan-result.json
│   │       ├── summary.md
│   │       └── task-logs/      # plan 中每个任务的 stdout/stderr
```

CLI 工具：

| 脚本 | 作用 |
|------|------|
| `agentops/agentops-dispatch-codex.py` | 执行单个 Codex 任务 |
| `agentops/agentops-dispatch-plan.py` | 执行多任务 plan，支持 depends_on |
| `agentops/agentops-read-result.py` | 查询任务结果 |
| `agentops/agentops-read-plan.py` | 查询 plan 结果 |
| `agentops/agentops-new.py` | 生成 task/plan 模板 |

---

## 3. 集成方案（3 层阶梯）

### Tier 1（已实现）：文件系统同步

**策略：** AgentOps 将运行产物复制到 `<workspace>/.pilotdeck/tasks/` 和 `<workspace>/.pilotdeck/plans/`

**状态：** ✅ Task 同步已在 `agentops-dispatch-codex.py` 实现
**状态：** ✅ Plan 同步已在 `agentops-dispatch-plan.py` 实现

```
workspace/
├── .pilotdeck/
│   ├── tasks/<task_id>/{result.json, summary.md, diff.patch, ...}
│   └── plans/<plan_id>/{plan-result.json, summary.md, task-logs/*}
└── .taskmaster/               # ← PilotDeck 已有管理通道
```

**说明：** PilotDeck 不直接读取 `.pilotdeck/tasks/`，但它会扫描项目目录。下一步是将 AgentOps 结果映射到 PilotDeck 已知的格式。

---

### Tier 2（建议立即做）：tasks.json 桥接

**目标：** 将 AgentOps 的任务状态写入 `.taskmaster/tasks/tasks.json`，使 PilotDeck UI 的 `TasksV2.tsx` 面板可以原生显示

**映射：**

| AgentOps task 字段 | TaskMaster task.json 字段 |
|---|---|
| task_id | id |
| goal / 摘要的首行 | title |
| summary.md 全文 | description |
| result.json.status (`success`/`failed`/`requires_review`) | status → `done`/`in-progress`/`review` |
| result.json.started_at / ended_at | createdAt / updatedAt |
| depends_on（plan 中） | dependencies |
| result.json.changed_files | details |

**实现建议：** 在 `agentops-dispatch-codex.py` 成功/失败回调后追加一个 `sync_to_taskmaster()` 函数：

```
agentops-dispatch-codex.py:
  └─ after execution
      ├─ result.json written        (existing)
      ├─ summary.md written          (existing)
      ├─ sync_to_workspace()         (existing → .pilotdeck/tasks/)
      └─ sync_to_taskmaster()        (new → .taskmaster/tasks/tasks.json)
```

**优点：**
- 无需改动 PilotDeck 代码，只遵循它已有的约定
- UI 中的 "Tasks" 标签页会直接显示 AgentOps 任务
- API `GET /api/taskmaster/tasks/:projectName` 自动支持

**注意事项：**
- `tasks.json` 有 legacy（数组）和 tagged（顶层 key 是 branch/tag）两种格式。我们的同步器必须检测格式并保留原有结构
- `TaskOutputStore` 的 disk spill 路径可以配置为 `.taskmaster/logs/<task_id>.log`，让 output 有持久化位置

---

### Tier 3（中期规划）：HTTP API 桥接 + 反向通知

**目标：** Trae 能通过 PilotDeck 的 HTTP API 发起 AgentOps 任务，并通过 WebSocket 接收实时状态更新

**数据流：**

```
  Trae (用户会话)
    │
    │  POST /api/taskmaster/add-task/:projectName
    │    { title, description, priority }
    │    └─ PilotDeck 调用 task-master-ai CLI
    │       └─ 写入 .taskmaster/tasks/tasks.json
    │
    │  [PilotDeck 侧可增加一个 hook：agentops-dispatch-from-task]
    │  ┌─ 检测到新 task.status = "in-progress"
    │  │  执行：agentops-dispatch-codex.py <task_id>
    │  │  写入 .agentops/runs/<task_id>/
    │  │  broadcastTaskMasterTasksUpdate(wss, projectName) ← WebSocket 广播
    │  └─ 最终更新 task.status = "done" / "review"
    │
    │  [UI 侧]
    │  GET /api/taskmaster/tasks/:projectName  ← 轮询或订阅 WebSocket
    │  TasksV2.tsx 渲染任务列表和状态
    └─ 用户点击查看 → 读取 .agentops/runs/<task_id>/summary.md 和 diff.patch
```

**建议新增的 PilotDeck API（可通过插件或 fork）：**

```
POST  /api/agentops/dispatch
      { task_id, plan_id?, mode, workspace }
      → 执行 agentops-dispatch-codex.py 或 agentops-dispatch-plan.py
      → 返回 { run_dir, status }

GET   /api/agentops/result/:projectName/:task_id
      → 返回 result.json + summary.md

GET   /api/agentops/plan/:projectName/:plan_id
      → 返回 plan-result.json + 每个 task 的摘要

WebSocket broadcast:
      { type: "agentops.task.update", task_id, status, summary }
```

**PilotDeck 插件路径探索：**
- PilotDeck 支持 `plugins/` 目录 → 可以将 AgentOps 封装为 PilotDeck 插件
- `src/adapters/web/httpRouter.ts` 可以挂载额外的 `/api/agentops/*` 路由
- `src/tool/builtin/` 目录下可以新增 `agentops.ts` 工具，让 Codex 主动调用 AgentOps

---

## 4. 风险与挑战

| 风险 | 影响 | 缓解 |
|---|---|---|
| PilotDeck 内部 API 会随版本变化 | 高 | 仅依赖文件系统约定（Tier 1-2），避免强绑定内部 API |
| tasks.json 格式：tagged vs legacy | 中 | 读写前检测格式，保留原始结构；加 version 字段 |
| 并发写入冲突（Trae + PilotDeck 同时写 tasks.json） | 中 | AgentOps 侧写入加文件锁（`fcntl` 或 rename-atomic），PilotDeck API 已走 `async/await` |
| 跨平台路径（Windows/macOS/Linux） | 中 | 统一使用 `pathlib.Path`（Python）和 `path.join`（Node.js），避免硬编码分隔符 |
| 失败任务未清理可能污染 UI | 低 | AgentOps 的 `status = failed/review` 显式标记，UI 侧可过滤 |

---

## 5. 推荐执行顺序

1. **立即（本周）：** 完成 Tier 1 的验证（实际跑一次 plan 后确认 `.pilotdeck/plans/` 已生成）
2. **短期（下 2 周）：** 实现 Tier 2 — `sync_to_taskmaster()` 函数，让 PilotDeck UI 能直接看到 AgentOps 任务
3. **中期（1-2 月）：** 评估 PilotDeck 插件系统可行性，决定是否走 Tier 3
4. **可选：** 在 PilotDeck UI 的 `TasksV2.tsx` 增加 "AgentOps 结果" 链接，点击跳转到 `.agentops/runs/<task_id>/summary.md` 的渲染页面

---

## 6. 验证清单（验收标准）

- ✅ AgentOps 工具能在项目根目录独立运行，不依赖 PilotDeck
- ✅ `.pilotdeck/tasks/` 和 `.pilotdeck/plans/` 有完整产物
- ⬜ PilotDeck UI 的 Tasks 标签页可以看到 AgentOps 生成的任务（需 Tier 2）
- ⬜ 任务状态在 AgentOps 执行期间会在 PilotDeck UI 中实时更新（需 Tier 3）
- ⬜ 多任务 plan 的依赖顺序在 PilotDeck UI 中正确显示（需 Tier 2 + dependency 映射）
