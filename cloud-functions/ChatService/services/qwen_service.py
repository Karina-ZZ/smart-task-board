"""Qwen OpenAI-compatible client used only inside ChatService."""

from __future__ import annotations

import json
from pathlib import Path
from urllib import error, request

import config

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "task_intake.md"


class QwenService:
    def __init__(self, completion_client=None) -> None:
        self.completion_client = completion_client

    def task_intake(self, context: dict[str, object]) -> dict[str, object]:
        messages = [
            {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
            {"role": "user", "content": json.dumps(context, ensure_ascii=False, default=str)},
        ]
        response = self.completion_client(messages) if self.completion_client else self._chat_completion(messages)
        content = self._message_content(response)
        parsed = self._parse_json(content)
        if not isinstance(parsed, dict):
            raise ValueError("Qwen返回结果不是JSON对象")
        return parsed

    def transcribe(self, audio_base64: str, file_name: str) -> str:
        if not config.QWEN_ASR_MODEL:
            raise RuntimeError("当前ChatService未配置QWEN_ASR_MODEL")
        ext = (file_name.rsplit(".", 1)[-1] if "." in file_name else "mp3").lower()
        payload = {
            "model": config.QWEN_ASR_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": audio_base64, "format": ext}},
                    {"type": "text", "text": "请只返回这段中文语音的逐字转写文本。"},
                ],
            }],
            "temperature": 0,
        }
        response = self._post_json(self._completion_endpoint(), payload)
        return self._message_content(response).strip()

    def _chat_completion(self, messages):
        if not config.QWEN_API_KEY:
            raise RuntimeError("ChatService未配置QWEN_API_KEY")
        return self._post_json(self._completion_endpoint(), {
            "model": config.QWEN_MODEL,
            "messages": messages,
            "temperature": 0,
            "response_format": {"type": "json_object"},
        })

    @staticmethod
    def _completion_endpoint() -> str:
        base = config.QWEN_BASE_URL.rstrip("/")
        return base if base.endswith("/chat/completions") else f"{base}/chat/completions"

    @staticmethod
    def _post_json(endpoint: str, payload: dict[str, object]):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            endpoint,
            data=body,
            headers={
                "Authorization": f"Bearer {config.QWEN_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=config.QWEN_TIMEOUT_SECONDS) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Qwen HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError("Qwen网络请求失败") from exc

    @staticmethod
    def _message_content(response) -> str:
        try:
            return str(response["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("Qwen响应缺少message content") from exc

    @staticmethod
    def _parse_json(content: str):
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:].strip()
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            start = stripped.find("{")
            end = stripped.rfind("}")
            if start >= 0 and end > start:
                return json.loads(stripped[start:end + 1])
            raise
