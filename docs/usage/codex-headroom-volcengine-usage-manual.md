# Codex 桌面端 + Headroom + 火山模型使用手册

更新时间：2026-06-11

## 1. 方案概览

这套方案由四部分组成：

```text
PilotDeck：管理项目 / Workspace / 项目记忆
Codex 桌面端：日常代码任务执行入口
Headroom：模型代理与上下文压缩
火山模型：实际大模型能力，模型为 ark-code-latest
```

当前可用三条链路：

```text
链路 A：Codex -> 本机火山代理 15721 -> 火山
链路 B：Codex -> Headroom 8789 -> 本机火山代理 15721 -> 火山
链路 C：请求/测试 -> Headroom 8790 优化模式 -> 本机火山代理 15721 -> 火山
```

推荐用法：

```text
日常稳定使用：链路 A 或链路 B
压缩收益验证：链路 C
```

## 2. 关键文件和目录

Codex 配置文件：

```text
$HOME/.codex/config.toml
```

Headroom 项目目录：

```text
<repo-root>
```

Headroom 8790 优化启动脚本：

```text
<repo-root>/headroom/servers/start_headroom_direct.py
```

Headroom 压缩收益验证脚本：

```text
<repo-root>/headroom/benchmarks/headroom_tool_output_compress_bench.py
```

方案记录文档：

```text
<repo-root>/docs/architecture/agentops-workflow-design.md
```

工具架构图文档：

```text
<repo-root>/docs/architecture/agentops-tools-architecture.md
```

video-analyzer PilotDeck 项目记忆：

```text
/path/to/your/workspace/.pilotdeck/memory/MEMORY.md
/.pilotdeck/projects/Users-xingan-Documents-software-workspace-video_anlalyer/memory/MEMORY.md
```

## 3. Codex provider 配置

当前 Codex 配置文件中有两个主要 provider。

### 3.1 custom：直连火山

配置位置：

```toml
model_provider = "custom"

[model_providers.custom]
base_url = "http://127.0.0.1:15721/v1"
wire_api = "responses"
```

链路：

```text
Codex 桌面端 -> 15721 -> 火山
```

适合：

```text
普通代码任务
小范围修改
稳定优先
不需要观察 Headroom 压缩收益
```

### 3.2 headroom：经过 Headroom 8789

配置位置：

```toml
[model_providers.headroom]
base_url = "http://127.0.0.1:8789/v1"
wire_api = "responses"
```

链路：

```text
Codex 桌面端 -> Headroom 8789 -> 15721 -> 火山
```

适合：

```text
多轮复杂任务
想统一经过 Headroom
后续观察上下文压缩效果
```

## 4. Codex 桌面端怎么用

使用 Codex 桌面端时，不需要每次都走终端命令模式。

日常流程：

```text
1. 确认本地火山代理 15721 正常
2. 如果想走 Headroom，确认 8789 正常
3. 打开 Codex 桌面端
4. 打开目标项目
5. 直接在桌面端里输入任务
```

如果 Codex 桌面端读取的是：

```text
$HOME/.codex/config.toml
```

那么它会使用该文件里的默认 provider。

当前默认：

```toml
model_provider = "custom"
```

如果想默认走 Headroom，可以改成：

```toml
model_provider = "headroom"
```

建议：

```text
日常先用 custom
复杂长任务再切 headroom
```

## 5. 每天使用前的状态检查

### 5.1 检查端口

```bash
lsof -i :15721 -sTCP:LISTEN -P -n
lsof -i :8789 -sTCP:LISTEN -P -n
lsof -i :8790 -sTCP:LISTEN -P -n
```

端口含义：

```text
15721：本机火山代理
8789：Headroom 稳定代理
8790：Headroom 优化/压缩验证代理
```

### 5.2 检查 8790 健康状态

```bash
curl -s http://127.0.0.1:8790/health | python3 -m json.tool
```

正常结果应包含：

```json
{
  "status": "healthy",
  "ready": true
}
```

### 5.3 检查 8790 压缩组件

```bash
curl -s http://127.0.0.1:8790/debug/warmup | python3 -m json.tool
```

当前正常状态应包含：

```text
code_aware: loaded
tree_sitter: loaded
smart_crusher: loaded
```

## 6. 如何启动服务

### 6.1 启动 Headroom 8789 稳定代理

如果 8789 没启动，可以执行：

```bash
cd <repo-root>

export ORT_LIB_PATH="$PWD/.deps/onnxruntime-osx-x86_64-1.23.2/lib"
export ORT_PREFER_DYNAMIC_LINK=1
export DYLD_LIBRARY_PATH="$ORT_LIB_PATH:${DYLD_LIBRARY_PATH:-}"

nohup .venv-headroom/bin/headroom proxy \
  --port 8789 \
  --openai-api-url http://127.0.0.1:15721/v1 \
  --no-telemetry \
  --stateless \
  --no-optimize \
  > /tmp/headroom_8789.log 2>&1 &
```

### 6.2 启动 Headroom 8790 优化验证代理

```bash
cd <repo-root>

nohup .venv-headroom/bin/python start_headroom_direct.py \
  > /tmp/headroom_8790_direct.log 2>&1 &
```

启动后检查：

```bash
curl -s http://127.0.0.1:8790/health | python3 -m json.tool
```

## 7. 终端命令什么时候需要用

Codex 桌面端日常使用时，不需要每次用终端命令。

终端主要用于：

```text
启动 Headroom
检查端口状态
验证压缩收益
排查 502 / 连接失败
查看日志
```

不需要用终端来代替 Codex 桌面端操作。

## 8. 推荐工作流

### 8.1 稳定日常开发

使用 Codex 桌面端，默认 provider 保持：

```toml
model_provider = "custom"
```

链路：

```text
Codex 桌面端 -> 15721 -> 火山
```

适合：

```text
读代码
小范围修复
补测试
代码审查
```

### 8.2 多轮复杂任务

将默认 provider 切到：

```toml
model_provider = "headroom"
```

链路：

```text
Codex 桌面端 -> Headroom 8789 -> 15721 -> 火山
```

适合：

```text
多轮读文件
大项目诊断
多步修复
长上下文任务
```

### 8.3 压缩收益观测

使用 8790：

```text
Headroom 8790 优化模式
```

运行 benchmark：

```bash
cd <repo-root>

.venv-headroom/bin/python headroom_tool_output_compress_bench.py
```

预期结果：

```text
tokens_before=60274
tokens_after=287
tokens_saved=59987
savings_pct=99.52
```

## 9. 什么内容适合 Headroom 压缩

适合压缩：

```text
长测试日志
CI 构建输出
pytest / npm test 输出
grep / rg 搜索结果
重复 warning/error
多轮 agent 旧工具输出
长 traceback
```

谨慎压缩：

```text
源码全文
关键业务逻辑
正在修改的函数
精确 diff
安全敏感配置
```

原因：源码和 diff 对代码修复很关键，默认不建议强压。

## 10. 压缩验证结果

已验证场景：重复日志类旧工具输出。

结果：

```text
tokens_before = 60274
tokens_after  = 287
tokens_saved  = 59987
savings_pct   = 99.52%
transform     = router:log:0.00
```

结论：

```text
Headroom 对日志/旧工具输出类上下文压缩收益非常明显。
```

## 11. 当前技术状态

已完成：

```text
1. Codex 直连火山可用
2. Codex -> Headroom 8789 -> 火山可用
3. Headroom 8790 优化模式可用
4. Rust core 动态库加载问题已修复
5. 真实压缩收益已验证
6. PilotDeck 项目记忆已写入
```

Rust core 修复方式：

```text
_core.cpython-313-darwin.so 原依赖 @rpath/libonnxruntime.1.23.2.dylib
但该 so 没有 LC_RPATH
最初通过 install_name_tool -change 临时改为 /tmp/ort.dylib
现已迁移到稳定用户级路径 $HOME/.headroom/ort.dylib
$HOME/.headroom/ort.dylib 软链到本机 ONNX Runtime dylib
```

当前 8790 说明：

```text
Rust core 可加载
内容检测使用 Python regex fallback
log/code-aware/smart-crusher 路径可用
```

保留问题：

```text
Rust content detector 需要 ONNX Runtime API v24
当前 macOS x86_64 可用 wheel 是 ONNX Runtime 1.23.2，只支持 API v23
GitHub 最新 ONNX Runtime 1.26.0 没有 macOS x86_64 tgz，仅有 macOS arm64
```

这个问题不影响当前日志压缩收益验证。

## 12. 故障排查

### 12.1 Codex 桌面端报 502

检查：

```bash
lsof -i :15721 -sTCP:LISTEN -P -n
lsof -i :8789 -sTCP:LISTEN -P -n
```

判断：

```text
15721 不在：火山代理没启动
8789 不在：Headroom 稳定代理没启动
```

### 12.2 8790 不健康

检查日志：

```bash
tail -100 /tmp/headroom_8790_direct.log
```

重启：

```bash
lsof -ti :8790 -sTCP:LISTEN -P -n | xargs -r kill -9

cd <repo-root>

nohup .venv-headroom/bin/python start_headroom_direct.py \
  > /tmp/headroom_8790_direct.log 2>&1 &
```

### 12.3 Rust core 加载失败

检查：

```bash
cd <repo-root>

.venv-headroom/bin/python -c 'from headroom._core import hello; print(hello())'
```

正常输出：

```text
headroom-core
```

如果失败，检查稳定软链：

```bash
ls -l $HOME/.headroom/ort.dylib
```

如果软链丢失，重建：

```bash
mkdir -p $HOME/.headroom

ln -sf \
  <repo-root>/.deps/onnxruntime-osx-x86_64-1.23.2/lib/libonnxruntime.1.23.2.dylib \
  $HOME/.headroom/ort.dylib
```

同时确认 `_core` 当前依赖路径：

```bash
cd <repo-root>

otool -L .venv-headroom/lib/python3.13/site-packages/headroom/_core.cpython-313-darwin.so | grep ort.dylib
```

预期看到：

```text
$HOME/.headroom/ort.dylib
```

## 13. 自动恢复与 Trae 接入结论

### 13.1 macOS 自动恢复

当前已配置用户级 LaunchAgent：

```text
$HOME/Library/LaunchAgents/com.xingan.agentops-stack.plist
```

LaunchAgent 入口：

```text
$HOME/.headroom/start-agentops-stack-launchd.sh
```

它会在登录时调用 AgentOps 启动逻辑，恢复：

```text
15721 上游检查
8789 Headroom 稳定代理
8790 Headroom 优化代理
$HOME/.headroom/ort.dylib 稳定软链
```

检查状态：

```bash
launchctl print gui/$(id -u)/com.xingan.agentops-stack | head -80
<repo-root>/scripts/check-agentops-stack.sh
```

回滚自动恢复：

```bash
launchctl bootout gui/$(id -u) $HOME/Library/LaunchAgents/com.xingan.agentops-stack.plist
rm $HOME/Library/LaunchAgents/com.xingan.agentops-stack.plist
```

### 13.2 Trae 接入结论

已只读检查 Trae 本地配置目录：

```text
/.trae-cn
$HOME/Library/Application Support/Trae CN
$HOME/Library/Application Support/TRAE SOLO CN
```

结论：

```text
未发现稳定、可安全编辑的本地 OpenAI-compatible provider 配置入口。
因此不强改 Trae 配置。
当前推荐保持 Trae 作为工程主控台，Codex 负责通过 custom/headroom provider 走火山链路。
```

如果 Trae 后续官方开放自定义模型配置，推荐值为：

```text
base_url = http://127.0.0.1:8789/v1
model = ark-code-latest
api_key = PROXY_MANAGED
```

### 13.3 Rust detector 结论

已调查低风险修复路径：

```text
1. 本地没有 Headroom Rust 源码构建链
2. PyPI macOS x86_64 onnxruntime 最高为 1.23.2
3. GitHub ONNX Runtime 1.24.1+ 仅提供 osx-arm64 包
4. 当前不进行高风险源码编译
5. 继续使用 Python regex detector fallback，保留已验证的 log/code-aware/smart-crusher 压缩路径
```

## 14. 最终建议

日常建议：

```text
1. Codex 桌面端默认用 custom，保证稳定
2. 多轮复杂任务可切到 headroom
3. 8790 只用于压缩收益验证和后续调优
4. 日志、测试输出、旧工具输出最适合 Headroom 压缩
5. 源码全文和关键 diff 不建议强制压缩
```

一句话总结：

```text
PilotDeck 管项目上下文，Codex 桌面端执行任务，15721/8789 提供日常模型链路，8790 用来验证和调优 Headroom 压缩收益。
```
