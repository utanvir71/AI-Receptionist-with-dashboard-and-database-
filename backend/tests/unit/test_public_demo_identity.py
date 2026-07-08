"""Regression checks for the fictional public-demo restaurant identity."""

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PUBLIC_TEXT_FILES = (
    PROJECT_ROOT / "README.md",
    PROJECT_ROOT / "pyproject.toml",
    PROJECT_ROOT / "app" / "__init__.py",
    PROJECT_ROOT / "app" / "main.py",
    PROJECT_ROOT / "app" / "services" / "notification_service.py",
    PROJECT_ROOT / "docs" / "ai-receptionist-v1-plan.md",
    PROJECT_ROOT / "docs" / "development-sessions.md",
    PROJECT_ROOT / "docs" / "kb" / "abcd-steakhouse-kb.md",
    PROJECT_ROOT / "docs" / "vapi-receptionist-prompt.md",
    PROJECT_ROOT / "docs" / "vapi-tool-migration.md",
)
def test_public_demo_files_use_only_fictional_restaurant_identity() -> None:
    for path in PUBLIC_TEXT_FILES:
        assert path.exists(), f"missing public demo file: {path}"

    combined_text = "\n".join(path.read_text(encoding="utf-8") for path in PUBLIC_TEXT_FILES)

    assert "ABCD Steakhouse Gangnam" in combined_text
    assert "Tanveer" in combined_text
