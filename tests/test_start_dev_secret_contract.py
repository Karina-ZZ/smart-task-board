"""DEV-18 release contract: local launcher uses the dedicated backend secret file."""

from pathlib import Path


def test_start_dev_uses_backend_secret_file_without_creating_root_dotenv() -> None:
    source = (Path(__file__).resolve().parents[1] / "scripts" / "start-dev.sh").read_text(
        encoding="utf-8"
    )

    assert "secrets/backend.env" in source
    assert "WANGXU_BACKEND_ENV_FILE" in source
    assert 'docker compose --env-file "$BACKEND_ENV_FILE"' in source
    assert "printf 'JWT_SECRET_KEY=" not in source
    assert "AI_API_KEY" not in source
    assert "if [ ! -f .env ]" not in source
