from pathlib import Path


def test_control_system_has_no_legacy_runtime_sdk_dependency() -> None:
    project_root = Path(__file__).parents[2]
    inspected_files = [project_root / "pyproject.toml", *sorted((project_root / "src").rglob("*.py"))]
    content = "\n".join(path.read_text(encoding="utf-8") for path in inspected_files)

    assert "bank_agent_runtime" not in content
    assert "bank-agent-runtime" not in content
    assert "bank-agent-cli" not in content
