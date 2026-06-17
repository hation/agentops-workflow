import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
os.environ.setdefault("ORT_LIB_PATH", str(ROOT_DIR / ".deps" / "onnxruntime-osx-x86_64-1.23.2" / "lib"))
os.environ.setdefault("ORT_PREFER_DYNAMIC_LINK", "1")
os.environ["DYLD_LIBRARY_PATH"] = os.environ["ORT_LIB_PATH"] + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")
os.environ.setdefault("HEADROOM_TOIN_BACKEND", "none")
os.environ.setdefault("HEADROOM_TELEMETRY", "off")

import headroom.transforms.content_router as content_router
from headroom.transforms.content_router import ContentRouterConfig

content_router._detect_content = content_router._regex_detect_content_type

_original_init = ContentRouterConfig.__init__

def _patched_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    self.enable_kompress = False
    self.prefer_code_aware_for_code = True
    self.protect_recent_code = 0
    self.protect_analysis_context = False
    self.protect_recent_reads_fraction = 0.0

ContentRouterConfig.__init__ = _patched_init

from headroom.proxy.server import ProxyConfig, run_server

config = ProxyConfig(
    host="127.0.0.1",
    port=8789,
    openai_api_url="http://127.0.0.1:15721/v1",
    mode="token",
    optimize=True,
    cache_enabled=True,
    rate_limit_enabled=True,
    code_aware_enabled=True,
    compress_user_messages=True,
    read_lifecycle=True,
    memory_enabled=False,
    stateless=True,
    log_file=None,
)

run_server(config, print_banner=True)
