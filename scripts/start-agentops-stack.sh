#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AGENTOPS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
HEADROOM_DIR="$AGENTOPS_DIR"
ONNX_LIB="${ONNX_LIB:-$HEADROOM_DIR/.deps/onnxruntime-osx-x86_64-1.23.2/lib/libonnxruntime.1.23.2.dylib}"
ORT_LINK="${ORT_LINK:-$HOME/.headroom/ort.dylib}"

mkdir -p "$(dirname "$ORT_LINK")"
ln -sf "$ONNX_LIB" "$ORT_LINK"

if ! lsof -i :15721 -sTCP:LISTEN -P -n >/dev/null 2>&1; then
  echo "ERROR: 15721 本机火山代理未运行"
  exit 1
fi

cd "$AGENTOPS_DIR"

export ORT_LIB_PATH="$HEADROOM_DIR/.deps/onnxruntime-osx-x86_64-1.23.2/lib"
export ORT_PREFER_DYNAMIC_LINK=1
export DYLD_LIBRARY_PATH="$ORT_LIB_PATH:${DYLD_LIBRARY_PATH:-}"

if ! .venv-headroom/bin/python -c 'from headroom._core import hello; print(hello())' >/dev/null 2>&1; then
  echo "ERROR: Headroom Rust core 加载失败"
  exit 1
fi

if ! lsof -i :8789 -sTCP:LISTEN -P -n >/dev/null 2>&1; then
  nohup .venv-headroom/bin/python headroom/servers/start_headroom_direct.py \
    > /tmp/headroom_8789_direct.log 2>&1 &
fi

if ! lsof -i :8790 -sTCP:LISTEN -P -n >/dev/null 2>&1; then
  nohup .venv-headroom/bin/python headroom/servers/start_headroom_balanced.py \
    > /tmp/headroom_8790_balanced.log 2>&1 &
fi

sleep 5

echo "=== AgentOps Stack Status ==="
lsof -i :15721 -sTCP:LISTEN -P -n || true
lsof -i :8789 -sTCP:LISTEN -P -n || true
lsof -i :8790 -sTCP:LISTEN -P -n || true

echo "=== Headroom 8790 Health ==="
curl -s http://127.0.0.1:8790/health || true
echo
