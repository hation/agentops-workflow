# Project AgentOps 工作流设计与落地方案

## 1. 背景与目标

本方案面向个人或小团队的软件研发智能体工作流，目标是把 Trae CN / Trae Work CN、PilotDeck、Codex、Headroom、OpenClaw、Hermes Agent 等工具组合成一套职责清晰、可控、可逐步落地的智能体研发系统。

核心目标：

- 统一研发主控入口
- 按项目隔离文件、记忆和技能
- 引入专业代码执行 Agent
- 支持远程消息触发任务
- 降低多 Agent 场景下的上下文和 token 成本
- 保持记忆可追溯、可编辑、可回滚
- 高风险操作保留人工审批

本方案不追求一次性全量部署，而是采用分阶段落地策略，先验证最小闭环，再逐步引入消息入口、云端执行和个人助理能力。

## 2. 总体架构

```text
                           ┌────────────────────────┐
                           │      Trae CN / Work CN  │
                           │  主控台 / 审批 / 开发入口 │
                           └───────────┬────────────┘
                                       │
                                       │ MCP / CLI / HTTP
                                       ▼
                           ┌────────────────────────┐
                           │       PilotDeck         │
                           │  项目工作舱 / 白盒记忆 / 调度 │
                           └───────────┬────────────┘
                                       │
                ┌──────────────────────┼──────────────────────┐
                │                      │                      │
                ▼                      ▼                      ▼
        ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
        │  Workspace A │       │  Workspace B │       │  Workspace C │
        │ 项目A文件/记忆/技能 │       │ 项目B文件/记忆/技能 │       │ 项目C文件/记忆/技能 │
        └──────┬───────┘       └──────┬───────┘       └──────┬───────┘
               │                      │                      │
               ▼                      ▼                      ▼
        ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
        │    Codex      │       │    Codex      │       │  Trae Agent  │
        │ 代码执行子Agent │       │ 测试/修复子Agent │       │ 研究/实验子Agent │
        └──────┬───────┘       └──────┬───────┘       └──────┬───────┘
               │                      │                      │
               ▼                      ▼                      ▼
         diff / test / patch    lint / test / report    analysis / report
```

远程入口：

```text
飞书 / Telegram / Slack / Discord / 微信等
        │
        ▼
    OpenClaw
        │
        ▼
    PilotDeck Workspace
```

横切优化层：

```text
Headroom：上下文压缩 / 工具输出压缩 / 代码压缩 / 可逆检索 / 成本优化
```

可选旁路：

```text
Hermes Agent：个人助理 / 自进化技能 / 跨会话个人记忆 / 定时自动化
```

## 3. 组件职责分工

### 3.1 Trae CN / Trae Work CN

定位：人类主控台与最终审批入口。

职责：

- 创建任务
- 下达指令
- 审查代码 diff
- 查看测试结果
- 管理 MCP / Skill
- 做最终审批
- 决定是否 commit、push、merge、发布

边界：

- 不承担所有后台长任务
- 不作为所有项目记忆的唯一存储
- 不直接替代项目工作舱

### 3.2 PilotDeck

定位：项目级 Agent 操作系统。

职责：

- 每个项目一个 Workspace
- 每个 Workspace 独立文件系统
- 每个 Workspace 独立记忆
- 每个 Workspace 独立技能
- 调度后台任务
- 保存任务轨迹
- 保存任务产物
- 支持白盒记忆查看、编辑、回滚

边界：

- 默认禁止跨 Workspace 访问
- 不自动执行高风险生产操作
- 不自动合并代码

### 3.3 Codex

定位：专业代码执行子 Agent。

职责：

- 修 bug
- 写测试
- 小范围重构
- 跑 lint
- 跑 typecheck
- 跑 test
- 生成 patch
- 根据 issue 做实现
- 审查当前 diff

边界：

- 不作为中央大脑
- 不管理长期记忆
- 不接入外部消息平台
- 不做权限审批
- 不自动 commit、push、merge

### 3.4 Headroom

定位：上下文压缩横切层。

职责：

- 压缩代码上下文
- 压缩工具输出
- 压缩 shell / CI / 测试日志
- 压缩 RAG chunks
- 压缩历史对话
- 保存原始内容，支持可逆检索
- 降低 token 成本
- 稳定上下文前缀，提高缓存命中

优先接入对象：

- Codex
- Trae Agent
- PilotDeck 任务上下文
- OpenClaw 消息输入
- MCP 工具输出

### 3.5 OpenClaw

定位：多平台消息入口与路由器。

职责：

- 接入飞书、Telegram、Slack、Discord、微信等消息平台
- 用户 pairing
- 用户白名单
- 群聊 mention 触发
- 将消息路由到正确 PilotDeck Workspace
- 回传任务摘要和结果

边界：

- 不作为核心决策大脑
- 不直接执行 shell
- 不直接改代码
- 不绕过 PilotDeck 写项目记忆

### 3.6 Hermes Agent

定位：可选旁路个人助理。

适合能力：

- 个人长期记忆
- 自生成技能
- 个人自动化
- 日报周报
- 提醒任务
- 跨平台个人对话

边界：

- 第一阶段不进入主研发链路
- 不直接写项目代码
- 不直接写 PilotDeck 项目记忆
- 不执行高危操作
- 只读查询 PilotDeck 任务状态和摘要

## 4. 核心设计原则

### 4.1 单一主控

最终决策权只保留在 Trae 和人类开发者手里。

Agent 可以建议，Codex 可以修改，PilotDeck 可以调度，OpenClaw 可以触发，但 commit、push、merge、发布、删除、生产操作必须人工确认。

### 4.2 项目记忆归 PilotDeck

项目级记忆统一进入 PilotDeck Workspace，包括：

- 技术栈
- 编码规范
- 测试命令
- 架构约定
- 业务规则
- 历史坑点
- 项目决策

Hermes 和 OpenClaw 不直接写项目记忆。

### 4.3 Codex 只做代码执行

Codex 的任务必须是可验证、可回滚、可审查的代码任务。

推荐任务类型：

- 修复具体 bug
- 增加指定测试
- 修复 lint / typecheck
- 生成 patch
- 审查 diff

不推荐任务类型：

- 长期管理项目
- 自主决定路线图
- 管理长期记忆
- 自动发布

### 4.4 OpenClaw 只做入口

OpenClaw 的任务链路应保持简单：

```text
收消息 → 鉴权 → 识别项目 → 路由到 PilotDeck → 回传结果
```

### 4.5 所有长上下文经过 Headroom

以下内容进入模型前优先走 Headroom：

- 大文件
- 搜索结果
- CI 日志
- git diff
- 终端输出
- RAG chunks
- 历史对话
- 多 Agent 中间结果

### 4.6 Hermes 旁路验证

Hermes 先作为个人助理独立验证，不急于进入主研发链路。

## 5. 典型任务流

### 5.1 Trae 内发起代码修复任务

```text
Trae 发起任务
  → PilotDeck 选择 Workspace
  → Headroom 压缩上下文
  → Codex 定位问题、修改代码、运行测试
  → PilotDeck 保存轨迹和结果
  → Trae 展示 diff 和测试结果
  → 人工确认是否提交
```

### 5.2 飞书远程触发任务

```text
飞书消息
  → OpenClaw 鉴权和路由
  → PilotDeck 创建任务
  → Codex 在对应 Workspace 执行
  → Headroom 压缩上下文和日志
  → OpenClaw 回传摘要
  → Trae 中人工 review
```

### 5.3 后台长任务

适合任务：

- 技术债扫描
- 测试覆盖率分析
- 依赖升级影响分析
- Issue triage
- 代码库架构说明
- 文档生成

流程：

```text
Trae / OpenClaw
  → PilotDeck 创建后台任务
  → Codex / Trae Agent 执行分析
  → Headroom 压缩扫描结果
  → PilotDeck 保存报告
  → Trae / OpenClaw 通知用户
```

### 5.4 Hermes 个人助理旁路

```text
Telegram / Slack
  → Hermes
  → 只读查询 PilotDeck 任务摘要
  → 生成个人日报 / 周报 / 提醒
```

## 6. 权限边界

### 6.1 Codex 权限

| 权限 | 策略 |
| --- | --- |
| 读取当前 Workspace | 允许 |
| 修改当前 Workspace | 允许 |
| 运行测试 | 允许 |
| 运行 lint/typecheck | 允许 |
| 查看 git diff/status | 允许 |
| 生成 patch | 允许 |
| git commit | 初期禁止 |
| git push | 禁止 |
| merge PR | 禁止 |
| 访问生产环境 | 禁止 |
| 读取密钥文件 | 禁止 |
| 执行部署 | 禁止或人工审批 |

### 6.2 OpenClaw 权限

| 权限 | 策略 |
| --- | --- |
| 接收 IM 消息 | 允许 |
| 用户 pairing | 必须 |
| 白名单 | 必须 |
| 群聊 mention | 必须 |
| 路由任务 | 允许 |
| 直接执行 shell | 禁止 |
| 写代码 | 禁止 |
| 修改系统配置 | 禁止 |
| 自动部署 | 禁止 |

### 6.3 PilotDeck 权限

| 权限 | 策略 |
| --- | --- |
| 管理 Workspace | 允许 |
| 管理项目记忆 | 允许 |
| 管理任务队列 | 允许 |
| 调用 Codex | 允许 |
| 写项目文件 | 允许 |
| 跨 Workspace 访问 | 默认禁止 |
| 自动合并 | 禁止 |
| 生产操作 | 人工审批 |

### 6.4 Hermes 权限

| 权限 | 策略 |
| --- | --- |
| 个人提醒 | 允许 |
| 日报周报 | 允许 |
| 只读查询任务 | 允许 |
| 写项目代码 | 禁止 |
| 写项目记忆 | 禁止 |
| 自动生成核心技能并启用 | 禁止 |
| 高危操作 | 禁止 |

## 7. 数据与记忆设计

### 7.1 项目记忆

归属：PilotDeck Workspace。

内容：

- 项目技术栈
- 编码规范
- 测试命令
- 架构约定
- 业务规则
- 历史坑点
- 项目级决策

### 7.2 个人偏好记忆

归属：Hermes 或 Trae 设置。

内容：

- 报告格式偏好
- 常用模型偏好
- 工作节奏
- 审批方式
- 提醒设置

### 7.3 压缩原文记忆

归属：Headroom CCR Store。

内容：

- 原始日志
- 原始工具输出
- 原始代码上下文
- 原始 RAG chunk
- 原始长对话片段

用途：需要时 retrieve，不作为行为偏好记忆。

## 8. 任务状态模型

统一任务状态：

```text
created
validated
queued
running
needs_approval
completed
failed
cancelled
```

| 状态 | 含义 |
| --- | --- |
| created | 任务刚创建 |
| validated | 已完成鉴权和 Workspace 识别 |
| queued | 已进入队列 |
| running | 正在执行 |
| needs_approval | 需要人工审批 |
| completed | 已完成 |
| failed | 失败 |
| cancelled | 已取消 |

## 9. 推荐集成方式

优先采用 CLI / MCP / HTTP 的低耦合集成，避免一开始写过重的胶水代码。

```text
Trae 调 PilotDeck：MCP / HTTP
PilotDeck 调 Codex：CLI
Codex 走 Headroom：wrap 或 proxy
OpenClaw 调 PilotDeck：HTTP / Webhook
Hermes 查 PilotDeck：只读 API
```

Codex 执行概念命令：

```bash
headroom wrap codex -- "在当前 workspace 修复测试失败。只修改必要文件，完成后运行测试并输出 diff。"
```

如果 Codex 支持 OpenAI-compatible base URL：

```bash
export OPENAI_BASE_URL=http://localhost:8787/v1
codex "修复当前项目中的 lint 错误"
```

## 10. MCP 工具抽象

### 10.1 PilotDeck MCP

```text
workspace_list
workspace_create
workspace_get_memory
workspace_update_memory
task_create
task_status
task_result
task_cancel
```

### 10.2 Codex MCP

```text
codex_run
codex_review_diff
codex_fix_tests
codex_generate_patch
codex_explain_error
```

### 10.3 Headroom MCP

```text
headroom_compress
headroom_retrieve
headroom_stats
```

### 10.4 OpenClaw Webhook / MCP

```text
message_receive
message_reply
user_authorize
route_to_workspace
```

## 11. 分阶段落地方案

### Phase 1：本地研发最小闭环

目标架构：

```text
Trae → Headroom → Codex
```

目标：

- Codex 能完成小范围代码任务
- Headroom 能压缩 Codex 上下文
- Trae 能作为人工审批入口

验证任务：

- 选择一个测试项目
- 让 Codex 修复一个真实小 bug
- 要求运行测试
- 要求输出 diff、验证命令、结果和风险说明

成功标准：

- Codex 不越界改文件
- 测试可运行
- diff 可读
- Headroom 有压缩收益
- 人工可审查和回滚

确认点：

- 你当前使用的 Codex 形态是 CLI、IDE 插件还是 API？
- Codex 是否支持配置 OpenAI-compatible base URL？
- 是否优先在本地 Mac 上验证？

### Phase 2：加入 PilotDeck 项目隔离

目标架构：

```text
Trae → PilotDeck Workspace → Headroom → Codex
```

目标：

- 每个项目独立 Workspace
- 项目记忆可查看和编辑
- Codex 在指定 Workspace 内执行
- 任务轨迹可追踪

验证任务：

- 建立 1-2 个 Workspace
- 为每个 Workspace 配置项目路径、测试命令、编码约定
- 让 Codex 分别在不同 Workspace 执行任务

成功标准：

- 项目 A / B 记忆不串
- 工作目录不串
- 任务报告可回看
- 失败任务可复盘

确认点：

- 第一批要纳入的项目有哪些？
- 每个项目是否已有标准测试命令？
- 是否需要把 Workspace 放在本地，还是云端？

### Phase 3：加入 OpenClaw 远程入口

目标架构：

```text
飞书 / Telegram / Slack → OpenClaw → PilotDeck → Codex
```

目标：

- 支持从 IM 远程触发研发任务
- 支持任务结果回传
- 完成鉴权、白名单和群聊 mention 规则

验证任务：

- 先接入一个消息平台
- 先开放只读任务，例如查询任务状态、生成日报
- 再开放低风险代码任务，例如生成报告、审查 diff

成功标准：

- 未授权用户不能触发任务
- 群聊必须 mention 才触发
- 任务能正确路由到 Workspace
- 结果能回传
- 高危任务进入人工审批

确认点：

- 你优先接飞书、Telegram、Slack 还是其他平台？
- 是否只给你本人使用，还是小团队共用？
- 是否需要企业身份体系或飞书审批？

### Phase 4：云端执行与长任务

目标架构：

```text
PilotDeck → Codex Worker / Docker Sandbox
```

目标：

- 长任务后台执行
- 多任务并行
- 每个任务独立容器或沙箱
- 任务完成后输出 patch / report

验证任务：

- 技术债扫描
- 测试覆盖率分析
- 依赖升级影响分析
- CI 失败初步修复

成功标准：

- 容器内执行不污染宿主机
- 日志可追踪
- 失败可重试
- 产物可审查

确认点：

- 是否有可用云服务器？
- 是否接受 Docker 作为默认沙箱？
- 是否需要接 GitHub issue / PR？

### Phase 5：Hermes 旁路个人助理

目标架构：

```text
Telegram / Slack → Hermes → 只读 PilotDeck / OpenClaw / 日报
```

目标：

- 个人提醒
- 日报周报
- 任务摘要
- 非核心自动化

验证任务：

- 每日汇总 PilotDeck 完成任务
- 每周生成研发进展报告
- 提醒待审批任务

成功标准：

- 不写项目代码
- 不写项目记忆
- 不执行高危命令
- 只做只读汇总和轻量任务

确认点：

- 你是否真的需要长期个人助理？
- 是否需要跨平台个人记忆？
- 是否接受 Hermes 作为旁路，而不是主链路？

## 12. 观测与评估指标

### 12.1 效率指标

| 指标 | 目标 |
| --- | --- |
| 小 bug 修复耗时 | 下降 |
| 测试补全时间 | 下降 |
| issue triage 时间 | 下降 |
| 技术债扫描频率 | 提高 |
| 人工重复操作 | 减少 |

### 12.2 成本指标

| 指标 | 目标 |
| --- | --- |
| 单任务 token 消耗 | 下降 |
| Headroom 压缩率 | 目标 50%+ |
| 重复上下文比例 | 下降 |
| 高价模型调用比例 | 下降 |

### 12.3 质量指标

| 指标 | 目标 |
| --- | --- |
| 测试通过率 | 提高 |
| Agent 误改文件数 | 接近 0 |
| 需要返工的 patch | 下降 |
| 代码 review 问题数 | 下降 |
| 记忆污染事件 | 0 |

### 12.4 安全指标

| 指标 | 目标 |
| --- | --- |
| 未授权触发次数 | 0 |
| 高危操作自动执行次数 | 0 |
| 密钥泄露事件 | 0 |
| 跨 Workspace 访问 | 0 |
| 自动 push / merge | 0 |

## 13. MVP 建议

推荐先做 MVP：

```text
Trae + PilotDeck + Codex + Headroom
```

暂不加入：

- OpenClaw
- Hermes
- 云端 worker
- 自动 commit / push / merge

MVP 验证任务：

```text
在一个测试项目中，让 Codex 修复一个真实 bug。
要求：
1. 任务由 Trae 发起
2. 在 PilotDeck Workspace 内执行
3. Codex 通过 Headroom 压缩上下文
4. 输出 diff 和测试结果
5. 人工确认后再提交
```

MVP 成功后，再按顺序增加：

```text
OpenClaw → 飞书远程触发
Hermes → 个人助理旁路
云端 Worker → 长任务和并行任务
```

## 14. 待确认事项

请确认以下问题，以便进入具体部署实施：

1. Codex 的具体形态
   - CLI
   - IDE 插件
   - API
   - 其他

2. 第一批接入项目
   - 项目名称
   - 本地路径或仓库地址
   - 技术栈
   - 测试命令
   - 是否允许 Agent 修改代码

3. Headroom 接入优先级
   - 优先 wrap Codex
   - 优先 proxy 统一模型调用
   - 优先 MCP 工具压缩

4. PilotDeck 部署位置
   - 本地 Mac
   - 云服务器
   - Docker
   - 先本地后云端

5. OpenClaw 首个消息平台
   - 飞书
   - Telegram
   - Slack
   - Discord
   - 微信 / 企业微信

6. 安全策略
   - 是否禁止自动 commit
   - 是否禁止自动 push
   - 是否所有代码修改都必须 Trae 审批
   - 是否需要 Docker sandbox

7. Hermes 是否进入第一期
   - 不进入，只做后续旁路
   - 只做日报 / 提醒
   - 先不部署

## 15. 推荐确认方案

默认推荐选择：

```text
Phase 1 + Phase 2 作为第一期：
Trae + PilotDeck + Codex + Headroom

OpenClaw 作为第二期：
只接一个消息平台，先做只读和低风险任务

Hermes 作为第三期：
只做旁路个人助理，不进入主研发链路
```

默认安全策略：

```text
禁止自动 commit
禁止自动 push
禁止自动 merge
禁止生产操作
禁止读取密钥文件
所有代码修改必须人工 review
外部消息入口必须白名单 + pairing + mention
```

默认 MVP 验证项目：

```text
选择一个非生产核心项目，执行一个真实小 bug 修复或测试补全任务。
```

## 16. 执行待办总表

本章节用于把方案落地拆成可跟踪的待办事项。状态分为：

```text
未开始 / 进行中 / 待确认 / 已完成 / 暂缓
```

### 16.1 当前整体待办

| 编号 | 待办事项 | 优先级 | 状态 | 产出物 | 备注 |
| --- | --- | --- | --- | --- | --- |
| T-001 | 确认第一期是否采用默认方案 | 高 | 待确认 | 第一阶段范围确认 | 默认推荐 Trae + PilotDeck + Codex + Headroom |
| T-002 | 确认 Codex 具体形态 | 高 | 待确认 | Codex 接入方式 | CLI / IDE 插件 / API / 其他 |
| T-003 | 确认第一批试点项目 | 高 | 待确认 | 项目清单与路径 | 建议选择非生产核心项目 |
| T-004 | 确认 Headroom 接入模式 | 高 | 待确认 | Headroom 接入决策 | wrap Codex / proxy / MCP 压缩 |
| T-005 | 确认 PilotDeck 部署位置 | 高 | 待确认 | 部署目标 | 本地 Mac / Docker / 云端 |
| T-006 | 确认安全策略 | 高 | 待确认 | 权限边界 | 默认禁止自动 commit/push/merge |
| T-007 | 安装并验证 Headroom | 高 | 未开始 | headroom perf / 压缩报告 | 先验证 token 收益 |
| T-008 | 安装并验证 Codex | 高 | 未开始 | Codex 单任务执行结果 | 先单独跑通小任务 |
| T-009 | 用 Headroom 包装 Codex | 高 | 未开始 | 压缩前后对比 | 验证是否影响代码质量 |
| T-010 | 部署 PilotDeck 本地实例 | 高 | 未开始 | 可访问的 PilotDeck 服务 | 第一阶段优先本地或 Docker |
| T-011 | 创建第一个 PilotDeck Workspace | 高 | 未开始 | Workspace 配置 | 绑定试点项目路径 |
| T-012 | 配置项目级记忆与规则 | 中 | 未开始 | Workspace Memory | 包括测试命令、编码规范、禁止事项 |
| T-013 | 跑通 MVP 代码任务 | 高 | 未开始 | diff + 测试结果 + 执行记录 | 不自动提交 |
| T-014 | 汇总 MVP 复盘报告 | 中 | 未开始 | MVP 验证报告 | 包含效率、质量、成本、安全指标 |
| T-015 | 决定是否进入 OpenClaw 第二期 | 中 | 待确认 | 第二期决策 | MVP 稳定后再决定 |
| T-016 | 选择 OpenClaw 首个消息平台 | 中 | 待确认 | 消息平台选择 | 推荐飞书或 Telegram 二选一 |
| T-017 | 决定 Hermes 是否旁路试验 | 低 | 暂缓 | Hermes 试验范围 | 不进入第一期主链路 |

## 17. 第一期落地执行清单

第一期目标：

```text
Trae → PilotDeck Workspace → Headroom → Codex → diff / test / patch → Trae 人工审批
```

### 17.1 第一期范围

纳入：

- Trae CN / Trae Work CN
- PilotDeck
- Codex
- Headroom
- 一个试点项目
- 一个真实小任务

不纳入：

- OpenClaw 消息入口
- Hermes Agent
- 自动 commit
- 自动 push
- 自动 merge
- 生产部署
- 多项目并行
- 云端 Worker

### 17.2 第一期任务拆解

#### Step 1：确认基础信息

| 编号 | 任务 | 状态 | 需要用户提供 |
| --- | --- | --- | --- |
| P1-001 | 确认 Codex 形态 | 待确认 | CLI / IDE 插件 / API |
| P1-002 | 确认试点项目 | 待确认 | 项目路径或仓库地址 |
| P1-003 | 确认项目技术栈 | 待确认 | Node / Python / Rust / Go / 其他 |
| P1-004 | 确认测试命令 | 待确认 | 例如 npm test / pytest / cargo test |
| P1-005 | 确认是否允许 Agent 修改代码 | 待确认 | 默认允许但不自动提交 |

#### Step 2：Headroom 验证

| 编号 | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P1-006 | 安装 Headroom | 未开始 | 命令可执行 |
| P1-007 | 运行 headroom perf | 未开始 | 能看到压缩统计 |
| P1-008 | 验证 headroom proxy 或 wrap | 未开始 | 能代理或包装一次模型调用 |
| P1-009 | 记录压缩收益 | 未开始 | 输出压缩率和质量观察 |

#### Step 3：Codex 验证

| 编号 | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P1-010 | 单独运行 Codex | 未开始 | 能完成简单代码任务 |
| P1-011 | 限定 Codex 工作目录 | 未开始 | 不访问非项目路径 |
| P1-012 | 要求 Codex 输出 diff | 未开始 | diff 可读可审查 |
| P1-013 | 要求 Codex 运行测试 | 未开始 | 返回测试命令和结果 |

#### Step 4：Headroom + Codex 联调

| 编号 | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P1-014 | 用 Headroom wrap Codex | 未开始 | Codex 可正常执行 |
| P1-015 | 或配置 Codex 走 Headroom proxy | 未开始 | 请求进入 Headroom |
| P1-016 | 对比压缩前后输出质量 | 未开始 | 质量无明显下降 |
| P1-017 | 记录失败场景 | 未开始 | 形成风险清单 |

#### Step 5：PilotDeck 工作舱验证

| 编号 | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P1-018 | 部署 PilotDeck 本地实例 | 未开始 | 服务可启动 |
| P1-019 | 创建试点 Workspace | 未开始 | Workspace 可访问 |
| P1-020 | 绑定项目目录 | 未开始 | 只访问指定项目 |
| P1-021 | 写入项目规则记忆 | 未开始 | 可查看和编辑 |
| P1-022 | 记录测试命令和禁止事项 | 未开始 | Codex 执行前可读取 |

#### Step 6：MVP 任务执行

| 编号 | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P1-023 | 创建一个真实小任务 | 未开始 | bug 修复或测试补全 |
| P1-024 | 由 Trae 发起任务 | 未开始 | 指令清晰可追踪 |
| P1-025 | PilotDeck 路由到 Workspace | 未开始 | 任务进入正确项目 |
| P1-026 | Codex 执行修改 | 未开始 | 只修改必要文件 |
| P1-027 | Codex 运行验证命令 | 未开始 | 输出测试结果 |
| P1-028 | Trae 人工 review | 未开始 | 人工确认 diff |
| P1-029 | 记录是否通过 | 未开始 | 形成 MVP 结果 |

#### Step 7：复盘与进入下一阶段决策

| 编号 | 任务 | 状态 | 验收标准 |
| --- | --- | --- | --- |
| P1-030 | 汇总任务执行时间 | 未开始 | 有效率数据 |
| P1-031 | 汇总 token / 压缩收益 | 未开始 | 有成本数据 |
| P1-032 | 汇总代码质量问题 | 未开始 | 有质量数据 |
| P1-033 | 汇总越权或误操作风险 | 未开始 | 有安全数据 |
| P1-034 | 决定是否进入 OpenClaw 第二期 | 待确认 | 明确 Go / No-Go |

## 18. 用户确认清单

请在开始实施前确认以下选项。

### 18.1 推荐默认选项

```text
Codex：待用户确认
试点项目：选择一个非生产核心项目
Headroom：优先 wrap Codex；如果不可行，再使用 proxy
PilotDeck：优先本地或 Docker 部署
OpenClaw：第一期不部署
Hermes：第一期不部署
安全策略：禁止自动 commit/push/merge，所有代码修改人工 review
```

### 18.2 需要用户回复的信息

请按以下格式回复：

```text
1. Codex 形态：
2. 试点项目路径或仓库：
3. 项目技术栈：
4. 测试命令：
5. 是否允许 Agent 修改代码：是/否
6. PilotDeck 部署方式：本地 / Docker / 云端
7. Headroom 接入方式：wrap Codex / proxy / 暂不确定
8. 安全策略是否采用默认：是/否
```

## 19. 当前会话已完成事项

| 编号 | 已完成事项 | 产出 |
| --- | --- | --- |
| D-001 | 调研 Headroom 项目能力 | 明确其作为上下文压缩层 |
| D-002 | 评估 OpenClaw / Hermes / PilotDeck / Trae 的角色 | 明确组件职责边界 |
| D-003 | 设计 Codex 嵌入方式 | Codex 定位为代码执行子 Agent |
| D-004 | 形成整体 AgentOps 架构 | Trae + PilotDeck + Codex + Headroom + OpenClaw + Hermes |
| D-005 | 保存架构设计文档 | agentops-workflow-design.md |
| D-006 | 补充分阶段落地方案 | Phase 1 到 Phase 5 |
| D-007 | 补充执行待办总表 | T-001 到 T-017 |
| D-008 | 补充第一期待办拆解 | P1-001 到 P1-034 |

## 20. 当前实施状态

### 20.1 本机环境盘点

已完成第一轮环境检查，并完成 Headroom 与 PilotDeck 本机安装验证。

| 组件 | 检测结果 | 版本 / 路径 | 状态 |
| --- | --- | --- | --- |
| Node.js | 已安装 | v25.8.0 | 可用 |
| npm | 已安装 | 11.11.0 | 可用 |
| pnpm | 未检测到 | - | 当前 PilotDeck 已用 npm 跑通，暂不需要 pnpm |
| Python | 已安装 | Python 3.12.8 / Python 3.13 venv | 可用 |
| uv | 已安装 | uv 0.11.7 | 可用 |
| Docker | 已安装但本阶段不用 | Docker 27.5.1 | 用户已确认继续本机安装，不走 Docker |
| git | 已安装 | git 2.33.0 | 可用 |
| Codex | 已定位电脑端内置 CLI，并已永久加入 PATH | `/usr/local/bin/codex` → `/Applications/Codex.app/Contents/Resources/codex`，0.136.0-alpha.2 | 可直接运行 `codex` 并接入 Headroom |
| Headroom | 已安装并验证 | `.venv-headroom/bin/headroom`，0.24.0 | 可用 |
| PilotDeck | 已安装并验证 | `<pilotdeck-root>` | 本机服务可用 |

### 20.2 Headroom 本机安装结果

Headroom 已在本机隔离虚拟环境中安装成功：

```text
.venv-headroom/bin/headroom --version
headroom, version 0.24.0
```

已验证可用命令：

```text
headroom wrap
headroom proxy
headroom mcp
```

`headroom wrap` 已确认支持以下第一期相关入口：

```text
headroom wrap codex
headroom wrap openclaw
```

本机安装采用 Python 3.13 虚拟环境，并手动下载 ONNX Runtime macOS x86_64 v1.23.2 解决 `ort-sys` 构建依赖：

```bash
export ORT_LIB_PATH="$PWD/.deps/onnxruntime-osx-x86_64-1.23.2/lib"
export ORT_PREFER_DYNAMIC_LINK=1
export DYLD_LIBRARY_PATH="$ORT_LIB_PATH:${DYLD_LIBRARY_PATH:-}"
```

本阶段暂未安装 `memory` extra，原因是 Python 3.13 + macOS x86_64 下 `torch` 依赖未找到匹配 wheel。第一期先使用 `proxy`、`mcp`、`code` 能力完成 Codex 包装和上下文压缩验证。

### 20.3 PilotDeck 本机启动结果

本机已有 PilotDeck 源码安装：

```text
<pilotdeck-root>
```

已复用现有依赖目录并按源码开发模式启动：

```bash
PILOTDECK_GATEWAY_PORT=18790 PILOTDECK_GATEWAY_URL=ws://127.0.0.1:18790/ws npm run dev
```

已验证端口：

```text
Web 后端：http://localhost:3001
Web 前端：http://localhost:5173
Gateway：http://127.0.0.1:18790
Gateway WebSocket：ws://127.0.0.1:18790/ws
```

说明：本机 18789 端口已有旧 PilotDeck 网关进程占用，因此本次验证使用 18790，避免影响旧实例。3001 会重定向到 5173，5173 返回 200，18790 返回 404 属于网关 HTTP 根路径无页面的正常表现；服务日志显示 UI bridge 已连接到 `ws://127.0.0.1:18790/ws`。

### 20.4 第一阶段执行状态更新

| 编号 | 事项 | 状态 | 说明 |
| --- | --- | --- | --- |
| P1-001 | 确认 Codex 形态 | 已完成 | Codex 电脑端自带 CLI：`/Applications/Codex.app/Contents/Resources/codex` |
| P1-006 | 安装 Headroom | 已完成 | `headroom --version` 输出 0.24.0 |
| P1-008 | 验证 headroom proxy 或 wrap | 部分完成 | 已确认 `headroom wrap codex` 支持 Codex CLI；还需做真实代理调用 |
| P1-010 | 单独运行 Codex | 部分完成 | `codex --version` 和 `codex doctor` 已运行；真实任务依赖试点项目确认 |
| P1-018 | 部署 PilotDeck 本地实例 | 已完成 | `<pilotdeck-root>` 本机源码服务已启动并验证 |

## 21. 第一阶段具体安装部署步骤

第一阶段继续按默认安全策略执行：

```text
禁止自动 commit
禁止自动 push
禁止自动 merge
禁止生产操作
禁止读取密钥文件
所有代码修改必须人工 review
```

### 21.1 步骤 A：安装并验证 Headroom

状态：已完成本机安装和基础命令验证。

实际采用命令：

```bash
python3.13 -m venv .venv-headroom
.venv-headroom/bin/python -m pip install --upgrade pip setuptools wheel
export ORT_LIB_PATH="$PWD/.deps/onnxruntime-osx-x86_64-1.23.2/lib"
export ORT_PREFER_DYNAMIC_LINK=1
export DYLD_LIBRARY_PATH="$ORT_LIB_PATH:${DYLD_LIBRARY_PATH:-}"
.venv-headroom/bin/python -m pip install --upgrade --force-reinstall --no-cache-dir "headroom-ai[proxy,mcp,code]==0.24.0"
.venv-headroom/bin/headroom --version
.venv-headroom/bin/headroom wrap --help
.venv-headroom/bin/headroom proxy --help
.venv-headroom/bin/headroom mcp --help
```

验收结果：

- `headroom --version` 正常输出 0.24.0
- `headroom wrap`、`headroom proxy`、`headroom mcp` 均可用
- `headroom wrap codex` 命令入口存在
- 下一步需在 Codex 可运行后验证真实模型调用链路

### 21.2 步骤 B：确认 Codex 形态

状态：已确认。Codex 电脑端内置完整 CLI，并已永久加入 PATH。

实际路径：

```text
/usr/local/bin/codex -> /Applications/Codex.app/Contents/Resources/codex
```

验证结果：

```text
codex-cli 0.136.0-alpha.2
```

已完成永久配置：

```bash
ln -s /Applications/Codex.app/Contents/Resources/codex /usr/local/bin/codex
```

同时已在 `~/.zshrc` 和 `~/.zprofile` 写入 Codex 资源目录 PATH 作为双保险；最终验证中，登录 shell、交互 shell、最小 PATH 环境均可直接运行 `codex`。

Codex doctor 已确认配置可加载、认证存在、SQLite 状态健康。当前注意事项：

- `TERM=dumb` 是当前自动化终端环境导致，不代表电脑端不可用
- provider reachability 探测超时，但返回过 HTTP 401，说明网络和鉴权配置仍需在真实任务中验证
- MCP 配置有可选问题，需要后续结合 Headroom MCP 注册结果再处理

Headroom 包装 Codex 的推荐命令：

```bash
export ORT_LIB_PATH="$PWD/.deps/onnxruntime-osx-x86_64-1.23.2/lib"
export DYLD_LIBRARY_PATH="$ORT_LIB_PATH:${DYLD_LIBRARY_PATH:-}"
.venv-headroom/bin/headroom wrap codex -- -C /path/to/project "执行一个只读诊断任务，不修改文件"
```

### 21.3 步骤 C：部署 PilotDeck

状态：已完成本机启动验证，不使用 Docker。

当前启动方式：

```bash
cd <pilotdeck-root>/ui
PILOTDECK_GATEWAY_PORT=18790 PILOTDECK_GATEWAY_URL=ws://127.0.0.1:18790/ws npm run dev
```

访问地址：

```text
http://localhost:5173/
```

后续需要继续完成：

- 确认 Workspace 数据放在当前机器哪个目录
- 确认第一个试点项目路径
- 根据试点项目写入 Workspace 初始规则

### 21.4 步骤 D：建立第一个 Workspace

目标：给试点项目创建独立工作舱。

需要写入 Workspace 的初始规则：

```text
1. 项目路径
2. 技术栈
3. 安装命令
4. 测试命令
5. lint / typecheck 命令
6. 禁止读取密钥文件
7. 禁止自动 commit / push / merge
8. 所有修改必须输出 diff 并等待人工 review
```

### 21.5 步骤 E：执行 MVP 任务

目标：跑通第一条真实代码任务。

推荐任务类型：

```text
1. 修复一个小 bug
2. 补一个小测试
3. 修复一个 lint 问题
4. 解释并整理一个模块，不直接改代码
```

任务完成后必须输出：

```text
1. 修改文件列表
2. diff 摘要
3. 执行过的验证命令
4. 测试 / lint / typecheck 结果
5. 风险说明
6. 是否建议人工合并
```

## 22. 当前试点 Workspace

第一批试点项目已确认：

```text
/path/to/your/workspace
```

PilotDeck 已添加现有 Workspace：

```text
name: Users-xingan-Documents-software-workspace-video_anlalyer
displayName: video_anlalyer
path: /path/to/your/workspace
```

项目结构判断：这是一个 Python 视频分析/剪辑工作区，包含多个子项目和视频素材目录。

主要代码子项目：

```text
AI-Montage-Agent
video-analyzer
story-ai-cutting
scripts
```

需要避免首次 Codex 诊断扫描的大文件/运行产物目录：

```text
videos
AI-Montage-Agent/uploads
story-ai-cutting/source
__pycache__
video-analyzer/.venv
```

建议第一轮 Codex 只读诊断优先限定到代码子目录，例如：

```text
/path/to/your/video-analyzer
```

或：

```text
/path/to/your/AI-Montage-Agent
```

## 23. 下一步建议

建议下一步先做三件事：

```text
1. 使用 Headroom wrap Codex 执行一个只读诊断任务
2. 根据诊断结果选择第一个小任务，例如补测试、修 lint、整理依赖
3. 再决定是否允许 Codex 进入 workspace-write 模式修改代码
```

第一次联调建议只读、不改代码、不运行重型视频处理。

### 23.1 当前联调结论

已完成以下验证：

```text
1. Codex 电脑端 CLI 可直接运行
2. PilotDeck 已添加 video_anlalyer Workspace
3. Codex 直连火山 custom provider 最小请求成功返回 OK
4. Headroom proxy 已能启动并接收 Codex 请求
5. 试点项目 video-analyzer 没有被修改
```

当前链路状态：

```text
Codex -> Headroom proxy 8789 -> 本机火山代理 15721 -> 火山 ark-code-latest
```

该链路已经验证可用。最小请求“只回答 OK”成功返回 OK；`video-analyzer` 项目只读验证请求也成功完成。

关键修复点：

```text
1. 旧失败链路是 Headroom 直接转发到火山公网地址，/v1/responses 返回 502
2. Codex 直连火山成功使用的是本机火山代理 http://127.0.0.1:15721/v1
3. 新 Headroom 上游改为 http://127.0.0.1:15721/v1
4. Codex headroom provider 指向 http://127.0.0.1:8789/v1
5. headroom provider 复用 custom provider 的鉴权字段
```

Headroom 启动命令：

```bash
cd <repo-root>
export ORT_LIB_PATH="$PWD/.deps/onnxruntime-osx-x86_64-1.23.2/lib"
export ORT_PREFER_DYNAMIC_LINK=1
export DYLD_LIBRARY_PATH="$ORT_LIB_PATH:${DYLD_LIBRARY_PATH:-}"
.venv-headroom/bin/headroom proxy \
  --port 8789 \
  --openai-api-url http://127.0.0.1:15721/v1 \
  --no-telemetry \
  --stateless \
  --no-optimize \
  --codex-wire-debug
```

推荐当前 Headroom + Codex 只读诊断命令：

```bash
OPENAI_BASE_URL=http://127.0.0.1:8789/v1 codex exec \
  -c 'model_provider="headroom"' \
  -C /path/to/your/video-analyzer \
  --sandbox read-only \
  --skip-git-repo-check \
  "只读诊断这个 Python video-analyzer 子项目：总结项目结构、依赖、可用测试命令、潜在风险；不要修改任何文件，不要运行视频处理，不要读取密钥文件。"
```

保留注意事项：

```text
1. 8789 Headroom 依赖 15721 本机火山代理先启动
2. 当前使用 --no-optimize 保证代理启动稳定；后续可单独验证优化模式
3. Codex 启动日志中 auth_mode 可能仍显示 Chatgpt，但实际请求已通过 Headroom 8789 成功完成
```

如果希望先诊断 `AI-Montage-Agent`，把 `-C` 路径替换为：

```text
/path/to/your/AI-Montage-Agent
```

### 23.2 MVP 执行结果

已使用 Codex 直连火山 custom provider 完成 `video-analyzer` 只读诊断。诊断未修改文件、未运行视频处理、未读取密钥文件。

诊断发现的首批风险包括：

```text
1. OpenAI-compatible 与 Ollama 客户端 requests.post 未设置 timeout，API 调用可能无限挂起
2. --start-stage 2/3 恢复逻辑可能不可用
3. UI cleanup 可能删除当前工作目录下已有 output 产物
4. API 参数透传缺少白名单
5. 主包核心视频处理和 client error handling 测试覆盖不足
```

第一个小任务已选择并执行：

```text
给 GenericOpenAIAPIClient 和 OllamaClient 增加默认 60 秒请求 timeout，并保留构造函数 timeout 参数以便后续覆盖。
```

修改文件：

```text
/path/to/your/video-analyzer/video_analyzer/clients/generic_openai_api.py
/path/to/your/video-analyzer/video_analyzer/clients/ollama.py
```

验证结果：

```text
python3 -m py_compile video_analyzer/clients/generic_openai_api.py video_analyzer/clients/ollama.py
通过

GenericOpenAIAPIClient mock requests.post timeout 验证
通过，timeout=7 被传入

OllamaClient mock requests.post timeout 验证
通过，timeout=9 被传入
```

已有轻量测试状态：

```text
python3 test_prompt_loading.py
失败，原因是 PromptLoader 当前优先加载包内默认 prompt，导致临时自定义 prompt 断言失败；该失败与本次 timeout 改动无关。
```

第二个小任务已选择并执行：

```text
修复 PromptLoader 自定义 prompt 优先级：当用户传入 prompt_dir 且对应文件存在时，优先加载用户目录；找不到时再回退到包内默认 prompt。
```

修改文件：

```text
/path/to/your/video-analyzer/video_analyzer/prompt.py
```

验证结果：

```text
python3 test_prompt_loading.py
通过，输出 All tests passed!

python3 -m py_compile video_analyzer/prompt.py video_analyzer/clients/generic_openai_api.py video_analyzer/clients/ollama.py
通过

自定义 prompt 覆盖行为 mock 验证
通过，返回 override
```

当前源码改动：

```text
video_analyzer/clients/generic_openai_api.py
video_analyzer/clients/ollama.py
video_analyzer/prompt.py
```

第三个小任务已选择并执行：

```text
为两个 client timeout 行为补正式单元测试。
```

新增文件：

```text
/path/to/your/video-analyzer/test_client_timeouts.py
```

覆盖场景：

```text
1. GenericOpenAIAPIClient 使用默认 timeout
2. GenericOpenAIAPIClient 支持自定义 timeout
3. OllamaClient 使用默认 timeout
4. OllamaClient 支持自定义 timeout
```

验证结果：

```text
python3 test_client_timeouts.py
通过，4 个用例 OK

python3 test_prompt_loading.py
通过，输出 All tests passed!

python3 -m py_compile test_client_timeouts.py test_prompt_loading.py video_analyzer/prompt.py video_analyzer/clients/generic_openai_api.py video_analyzer/clients/ollama.py
通过
```

当前源码改动：

```text
video_analyzer/clients/generic_openai_api.py
video_analyzer/clients/ollama.py
video_analyzer/prompt.py
test_client_timeouts.py
```

第四个小任务已选择并执行：

```text
处理 UI cleanup 的 output 删除风险，并修复 UI 表单参数透传缺少白名单问题。
```

修改文件：

```text
/path/to/your/video-analyzer/video-analyzer-ui/video_analyzer_ui/server.py
```

新增文件：

```text
/path/to/your/video-analyzer/test_ui_server_safety.py
```

修复内容：

```text
1. 新增 build_analysis_command，仅允许前端支持的 CLI 参数进入 video-analyzer 命令
2. 未知表单参数返回 400，避免任意 --参数 透传
3. cleanup_session_files 只清理当前 session 的 upload/results 目录
4. 移除 cleanup 对当前工作目录 output/ 的删除行为，避免误删已有分析产物
```

验证结果：

```text
python3 test_ui_server_safety.py
通过，3 个用例 OK

python3 test_client_timeouts.py
通过，4 个用例 OK

python3 test_prompt_loading.py
通过，输出 All tests passed!

python3 -m py_compile test_ui_server_safety.py test_client_timeouts.py test_prompt_loading.py video-analyzer-ui/video_analyzer_ui/server.py video_analyzer/prompt.py video_analyzer/clients/generic_openai_api.py video_analyzer/clients/ollama.py
通过
```

当前源码改动：

```text
video-analyzer-ui/video_analyzer_ui/server.py
video_analyzer/clients/generic_openai_api.py
video_analyzer/clients/ollama.py
video_analyzer/prompt.py
test_client_timeouts.py
test_ui_server_safety.py
```

第五个小任务已选择并执行：

```text
处理 --start-stage 2/3 的状态恢复设计。
```

修改文件：

```text
/path/to/your/video-analyzer/video_analyzer/cli.py
```

新增文件：

```text
/path/to/your/video-analyzer/test_stage_resume.py
```

修复内容：

```text
1. start-stage > 1 时从 output/analysis.json 恢复已有结果
2. 从 output/frames/frame_*.jpg 恢复 frames 列表
3. 从 analysis.json 恢复 transcript 和 frame_analyses
4. stage 3 缺少 frame_analyses 时明确报错
5. 移除 cli.py 中未使用的 torch 导入，减少 CLI 导入副作用
```

验证结果：

```text
python3 test_stage_resume.py
通过，6 个用例 OK

python3 test_ui_server_safety.py
通过，3 个用例 OK

python3 test_client_timeouts.py
通过，4 个用例 OK

python3 test_prompt_loading.py
通过，输出 All tests passed!

python3 -m py_compile test_stage_resume.py test_ui_server_safety.py test_client_timeouts.py test_prompt_loading.py video_analyzer/cli.py video-analyzer-ui/video_analyzer_ui/server.py video_analyzer/prompt.py video_analyzer/clients/generic_openai_api.py video_analyzer/clients/ollama.py
通过
```

当前环境注意事项：

```text
test_stage_resume.py 导入 cli.py 时，仍会经 analyzer -> audio_processor 触发 torch/NumPy 兼容警告；测试退出码为 0。该警告来自当前 Python 环境中 torch 与 NumPy 2.x 的二进制兼容问题，不是本次 stage 恢复逻辑失败。
```

当前源码改动：

```text
video-analyzer-ui/video_analyzer_ui/server.py
video_analyzer/cli.py
video_analyzer/clients/generic_openai_api.py
video_analyzer/clients/ollama.py
video_analyzer/prompt.py
test_client_timeouts.py
test_stage_resume.py
test_ui_server_safety.py
```

下一步建议：

```text
1. 审查并整理 README/默认配置/setup.py 不一致问题
2. 视情况补充 UI 集成测试，需要安装 Flask/Werkzeug 依赖
3. 最终收尾：完整 diff review、生成提交说明，由用户决定是否 commit
```

### 23.3 Phase 1 收尾结果

2026-06-11 已完成第一阶段本地研发最小闭环收尾。

已完成事项：

```text
1. Codex 直连火山 custom provider 可用
2. Codex -> Headroom proxy -> 本机火山代理 -> 火山链路可用
3. PilotDeck 已添加 video_anlalyer Workspace
4. 已在 PilotDeck 项目路径写入 video-analyzer 项目规则记忆
5. 已用 video-analyzer 完成真实小任务：timeout、PromptLoader、UI safety、start-stage resume
6. 已补充并运行轻量测试
7. 已提交 video-analyzer 修复 commit：701fd8e fix(video-analyzer): harden API clients and UI safety
```

Headroom 压缩验证结论：

```text
已修复 Rust core 动态库加载问题：
1. _core.cpython-313-darwin.so 原依赖 @rpath/libonnxruntime.1.23.2.dylib，但没有 LC_RPATH
2. install_name_tool -add_rpath 因 Mach-O header padding 不足失败
3. 最初通过 install_name_tool -change 把依赖临时改为 /tmp/ort.dylib；后续已迁移到稳定用户级路径 $HOME/.headroom/ort.dylib，并软链到本机 ONNX Runtime dylib
4. 验证 from headroom._core import hello 成功返回 headroom-core
5. 8790 优化模式已健康启动，/debug/warmup 显示 code_aware/tree_sitter/smart_crusher 已加载

真实压缩收益已验证：
- 场景：重复日志类旧工具输出
- tokens_before: 60274
- tokens_after: 287
- tokens_saved: 59987
- savings_pct: 99.52%
- transforms_applied: router:log:0.00

保留说明：
- 代码审查/源码全文场景默认保守不压缩，以避免破坏代码细节
- 结构化 JSON 工具输出本轮未压缩，后续可单独调 JSON/SmartCrusher 策略
- Rust content detector 运行时仍存在 ONNX Runtime API v24 与本机 1.23.2 API v23 不匹配问题；
  当前测试启动器使用 Python regex detector fallback 绕过该检测点，实际 log compressor 可正常产生压缩收益
```

验证命令结果：

```text
python3 test_client_timeouts.py          通过，4 个用例
python3 test_prompt_loading.py           通过
python3 test_ui_server_safety.py         通过，3 个用例
python3 test_stage_resume.py             通过，6 个用例
python3 -m py_compile ...                通过
```

保留风险与后续事项：

```text
1. 若要彻底恢复 Rust content detector，需要匹配 ONNX Runtime API v24；当前 macOS x86_64 可用 wheel 最高为 1.23.2
2. GitHub 最新 ONNX Runtime 1.26.0 已无 macOS x86_64 tgz，仅有 macOS arm64；如需完全消除该问题，需要自行编译 x86_64 ORT 或重建 Headroom core 对 1.23.2 API
3. test_stage_resume.py 仍会触发 torch 与 NumPy 2.x 兼容警告，但测试退出码为 0
4. README、默认配置、setup.py 版本信息仍待整理
5. OpenClaw 远程入口、Hermes 旁路、云端 Worker 均未进入第一阶段范围
```

当前结论：

```text
Phase 1 的最小研发闭环已经跑通：
Trae/PilotDeck 管理项目上下文，Codex 直连或经 Headroom 代理调用火山模型，
在试点项目中完成真实修复、测试验证和 git commit。

Phase 1 最小闭环已完成，并已验证 Headroom 在日志类旧工具输出场景下具备显著压缩收益。
当前 8790 优化模式适合用于验证和观测压缩收益；日常 Codex 仍可继续使用 8789 稳定透传链路。
```