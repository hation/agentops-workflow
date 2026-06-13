import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
os.environ.setdefault("ORT_LIB_PATH", str(ROOT_DIR / ".deps" / "onnxruntime-osx-x86_64-1.23.2" / "lib"))
os.environ.setdefault("ORT_PREFER_DYNAMIC_LINK", "1")
os.environ["DYLD_LIBRARY_PATH"] = os.environ["ORT_LIB_PATH"] + ":" + os.environ.get("DYLD_LIBRARY_PATH", "")

from headroom.transforms.content_router import ContentRouterConfig

_original_init = ContentRouterConfig.__init__

def _patched_init(self, *args, **kwargs):
    _original_init(self, *args, **kwargs)
    self.enable_kompress = False

ContentRouterConfig.__init__ = _patched_init

from headroom.cli import main

main.main(
    args=[
        "proxy",
        "--port",
        "8790",
        "--openai-api-url",
        "http://127.0.0.1:15721/v1",
        "--no-telemetry",
        "--stateless",
        "--code-aware",
        "--intercept-tool-results",
    ],
    standalone_mode=True,
)
