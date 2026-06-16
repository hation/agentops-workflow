#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTOPS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CODEX_CONFIG="${CODEX_CONFIG:-$HOME/.codex/config.toml}"
ORT_LINK="${ORT_LINK:-$HOME/.headroom/ort.dylib}"
EXIT_CODE=0

# 检查函数：区分必需和可选服务
check_essential_port() {
  local port="$1"
  local name="$2"
  if lsof -i :"$port" -sTCP:LISTEN -P -n >/dev/null 2>&1; then
    echo "OK: $name ($port) 正在监听"
  else
    echo "ERROR: $name ($port) 未监听 - 这是核心依赖"
    EXIT_CODE=1
  fi
}

check_optional_port() {
  local port="$1"
  local name="$2"
  local required_for="$3"
  if lsof -i :"$port" -sTCP:LISTEN -P -n >/dev/null 2>&1; then
    echo "OK: $name ($port) 正在监听"
  else
    echo "INFO: $name ($port) 未监听 - 仅影响 $required_for"
  fi
}

check_file() {
  local path="$1"
  local name="$2"
  if [ -e "$path" ]; then
    echo "OK: $name 存在：$path"
  else
    echo "ERROR: $name 不存在：$path - 这是核心依赖"
    EXIT_CODE=1
  fi
}

# 核心依赖服务检查
check_essential_port 15721 "本机火山代理"
check_essential_port 8790 "Headroom 优化代理"

# 可选服务检查
check_optional_port 8789 "Headroom 稳定代理" "8789 端口特定的稳定代理链路"
check_optional_port 18790 "PilotDeck Gateway" "PilotDeck 本地项目上下文服务"

# Headroom 8790 模式检查
HEADROOM_8790_PID=$(lsof -ti :8790 -sTCP:LISTEN -P -n | head -n 1 || true)
if [ -n "$HEADROOM_8790_PID" ]; then
  HEADROOM_8790_COMMAND=$(ps -p "$HEADROOM_8790_PID" -o command= || true)
  HEADROOM_8790_MODE=$(echo "$HEADROOM_8790_COMMAND" | grep -Eo 'start_headroom_(fast|balanced|direct)\.py' | head -n 1 || true)
  if [ -n "$HEADROOM_8790_MODE" ]; then
    echo "OK: Headroom 8790 当前模式：$HEADROOM_8790_MODE"
  else
    echo "INFO: Headroom 8790 当前模式无法识别"
  fi
else
  echo "ERROR: Headroom 8790 未运行"
  EXIT_CODE=1
fi

# 依赖文件检查
check_file "$ORT_LINK" "ONNX Runtime 稳定软链"

# Headroom 健康检查
if curl -s http://127.0.0.1:8790/health >/dev/null 2>&1; then
  READY=$(curl -s http://127.0.0.1:8790/health | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("ready"))' 2>/dev/null || echo "unknown")
  echo "OK: 8790 /health 可访问，ready=$READY"
else
  echo "ERROR: 8790 /health 不可访问 - 这是核心依赖"
  EXIT_CODE=1
fi

cd "$AGENTOPS_DIR"

# Headroom Rust core 检查
if .venv-headroom/bin/python -c 'from headroom._core import hello; print(hello())' >/dev/null 2>&1; then
  echo "OK: Headroom Rust core 可加载"
else
  echo "ERROR: Headroom Rust core 加载失败 - 这是核心依赖"
  EXIT_CODE=1
fi

if otool -L .venv-headroom/lib/python3.13/site-packages/headroom/_core.cpython-313-darwin.so | grep -Fq "$ORT_LINK"; then
  echo "OK: Headroom Rust core 依赖稳定 ORT 路径"
else
  echo "ERROR: Headroom Rust core 未依赖 $ORT_LINK - 这是核心依赖"
  EXIT_CODE=1
fi

# Codex 配置检查
if grep -q '\[model_providers.custom\]' "$CODEX_CONFIG"; then
  echo "OK: Codex custom provider 存在"
else
  echo "ERROR: Codex custom provider 缺失 - 这是核心依赖"
  EXIT_CODE=1
fi

if grep -q '\[model_providers.headroom\]' "$CODEX_CONFIG"; then
  echo "OK: Codex headroom provider 存在"
else
  echo "ERROR: Codex headroom provider 缺失 - 这是核心依赖"
  EXIT_CODE=1
fi

if grep -E 'base_url.*8789|base_url.*8790' "$CODEX_CONFIG"; then
  echo "OK: Codex headroom provider 指向 Headroom 代理"
else
  echo "ERROR: Codex headroom provider 未指向 Headroom 代理 - 这是核心依赖"
  EXIT_CODE=1
fi

# 最终状态总结
if [ "$EXIT_CODE" -eq 0 ]; then
  echo "================================"
  echo "RESULT: AgentOps 核心服务检查通过"
  echo "================================"
  echo "所有必需的核心依赖都已正常运行。"
  echo "可选服务可能未启动，但不影响基础功能。"
else
  echo "================================"
  echo "RESULT: AgentOps 核心服务检查失败"
  echo "================================"
  echo "存在一个或多个核心依赖服务未正常运行。"
  echo "请先修复 ERROR 标记的问题，然后再重新运行。"
fi

exit "$EXIT_CODE"
