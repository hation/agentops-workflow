#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTOPS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
CODEX_CONFIG="${CODEX_CONFIG:-$HOME/.codex/config.toml}"
ORT_LINK="${ORT_LINK:-$HOME/.headroom/ort.dylib}"
EXIT_CODE=0

check_port() {
  local port="$1"
  local name="$2"
  if lsof -i :"$port" -sTCP:LISTEN -P -n >/dev/null 2>&1; then
    echo "OK: $name ($port) 正在监听"
  else
    echo "MISSING: $name ($port) 未监听"
    EXIT_CODE=1
  fi
}

check_file() {
  local path="$1"
  local name="$2"
  if [ -e "$path" ]; then
    echo "OK: $name 存在：$path"
  else
    echo "MISSING: $name 不存在：$path"
    EXIT_CODE=1
  fi
}

check_port 15721 "本机火山代理"
check_port 8789 "Headroom 稳定代理"
check_port 8790 "Headroom 优化代理"
check_port 18790 "PilotDeck Gateway"

HEADROOM_8790_PID=$(lsof -ti :8790 -sTCP:LISTEN -P -n | head -n 1 || true)
if [ -n "$HEADROOM_8790_PID" ]; then
  HEADROOM_8790_COMMAND=$(ps -p "$HEADROOM_8790_PID" -o command= || true)
  HEADROOM_8790_MODE=$(echo "$HEADROOM_8790_COMMAND" | grep -Eo 'start_headroom_(fast|balanced|direct)\.py' | head -n 1 || true)
  if [ -n "$HEADROOM_8790_MODE" ]; then
    echo "OK: Headroom 8790 当前模式：$HEADROOM_8790_MODE"
  else
    echo "MISSING: Headroom 8790 当前模式无法识别"
    EXIT_CODE=1
  fi
else
  echo "MISSING: Headroom 8790 当前模式无法识别"
  EXIT_CODE=1
fi

check_file "$ORT_LINK" "ONNX Runtime 稳定软链"

if curl -s http://127.0.0.1:8790/health >/dev/null 2>&1; then
  READY=$(curl -s http://127.0.0.1:8790/health | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d.get("ready"))' 2>/dev/null || echo "unknown")
  echo "OK: 8790 /health 可访问，ready=$READY"
else
  echo "MISSING: 8790 /health 不可访问"
  EXIT_CODE=1
fi

cd "$AGENTOPS_DIR"

if .venv-headroom/bin/python -c 'from headroom._core import hello; print(hello())' >/dev/null 2>&1; then
  echo "OK: Headroom Rust core 可加载"
else
  echo "MISSING: Headroom Rust core 加载失败"
  EXIT_CODE=1
fi

if otool -L .venv-headroom/lib/python3.13/site-packages/headroom/_core.cpython-313-darwin.so | grep -Fq "$ORT_LINK"; then
  echo "OK: Headroom Rust core 依赖稳定 ORT 路径"
else
  echo "MISSING: Headroom Rust core 未依赖 $ORT_LINK"
  EXIT_CODE=1
fi

if grep -q '\[model_providers.custom\]' "$CODEX_CONFIG"; then
  echo "OK: Codex custom provider 存在"
else
  echo "MISSING: Codex custom provider 缺失"
  EXIT_CODE=1
fi

if grep -q '\[model_providers.headroom\]' "$CODEX_CONFIG"; then
  echo "OK: Codex headroom provider 存在"
else
  echo "MISSING: Codex headroom provider 缺失"
  EXIT_CODE=1
fi

if grep -q 'base_url = "http://127.0.0.1:8789/v1"' "$CODEX_CONFIG"; then
  echo "OK: Codex headroom provider 指向 8789"
else
  echo "MISSING: Codex headroom provider 未指向 8789"
  EXIT_CODE=1
fi

if [ "$EXIT_CODE" -eq 0 ]; then
  echo "RESULT: AgentOps stack 核心链路检查通过"
else
  echo "RESULT: AgentOps stack 存在缺失项，请查看 MISSING 项"
fi

exit "$EXIT_CODE"
