import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
os.environ.setdefault("ORT_LIB_PATH", str(ROOT_DIR / ".deps" / "onnxruntime-osx-x86_64-1.23.2" / "lib"))
os.environ.setdefault("ORT_PREFER_DYNAMIC_LINK", "1")
os.environ["DYLD_LIBRARY_PATH"] = os.environ["ORT_LIB_PATH"] + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")
os.environ.setdefault("HEADROOM_TOIN_BACKEND", "none")
os.environ.setdefault("HEADROOM_TELEMETRY", "off")

from headroom.transforms.content_router import ContentRouterConfig

_original_init = ContentRouterConfig.__init__

def _patched_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    self.enable_kompress = False

ContentRouterConfig.__init__ = _patched_init

from headroom.proxy.server import ProxyConfig, run_server

config = ProxyConfig(
    host="127.0.0.1",
    port=8790,
    openai_api_url="http://127.0.0.1:15721/v1",
    mode="token",
    optimize=False,
    cache_enabled=True,
    rate_limit_enabled=False,
    code_aware_enabled=False,
    compress_user_messages=False,
    read_lifecycle=False,
    memory_enabled=False,
    stateless=True,
    log_file=None,
)

run_server(config, print_banner=True)
