"""Static guards for the DEV-18 Test5 release gate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_test5_gate_requires_formal_runtime_and_real_integrations() -> None:
    text = (ROOT / "scripts/run_test5_release_gate.sh").read_text(encoding="utf-8")
    required = (
        "Python 3.12 is required",
        '"$python_bin" -m ruff check .',
        "./scripts/run_postgresql_gate.sh",
        "WANGXU_BACKEND_ENV_FILE",
        "AUTH_MODE=wecom",
        "WECOM_CORP_ID",
        "WECOM_AGENT_ID",
        "WECOM_APP_SECRET",
        "WANGXU_CHAT_ENV_FILE",
        "DASHSCOPE_API_KEY",
        'mode="api"',
        "real mini-program AppID",
        "npm run lint",
        "npm run build",
    )
    assert all(token in text for token in required)
    assert "[TEST5 BLOCKED]" in text


def test_real_wecom_e2e_script_never_embeds_secrets_or_tokens() -> None:
    path = ROOT / "scripts/run_wecom_real_e2e.py"
    text = path.read_text(encoding="utf-8")
    assert "/api/v1/auth/wecom" in text
    assert "/api/v1/me" in text
    assert "/api/v1/auth/ai-token" in text
    assert "/api/v1/auth/refresh" in text
    assert "/api/v1/auth/logout" in text
    assert "WECOM_TEST_LOGIN_CODE" in text
    assert "WECOM_TEST_EXPECTED_EMPLOYEE_NO" in text
    assert "WECOM_APP_SECRET" not in text
    assert "DASHSCOPE_API_KEY" not in text
    assert "print(access_token" not in text
    assert "print(refresh_token" not in text
