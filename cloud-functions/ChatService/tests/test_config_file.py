"""DEV-18 secret-file contract for dedicated ChatService environment loading."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile

service_dir = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp_dir:
    env_file = Path(temp_dir) / "chatservice.env"
    env_file.write_text(
        "CHAT_REQUIRE_AUTH=true\n"
        "DASHSCOPE_API_KEY=file-key\n"
        "CHAT_SERVICE_JWT_SECRET_KEY=file-secret-with-at-least-32-characters\n",
        encoding="utf-8",
    )
    child_env = os.environ.copy()
    child_env["WANGXU_CHAT_ENV_FILE"] = str(env_file)
    child_env["DASHSCOPE_API_KEY"] = "process-key"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import config; print(config.QWEN_API_KEY); print(config.CHAT_REQUIRE_AUTH)",
        ],
        cwd=service_dir,
        env=child_env,
        check=True,
        capture_output=True,
        text=True,
    )

assert result.stdout.splitlines() == ["process-key", "True"]
print("ChatService test_config_file.py: PASS")
