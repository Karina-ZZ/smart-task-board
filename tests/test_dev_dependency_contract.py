"""Release guard for the declared development dependency contract."""
from pathlib import Path


def test_dev_dependency_uses_official_httpx_package() -> None:
    pyproject = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(
        encoding="utf-8"
    )
    assert '"httpx>=0.27,<1.0"' in pyproject
    assert "httpx2" not in pyproject
