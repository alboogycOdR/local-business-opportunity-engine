from pathlib import Path


def test_bootstrap_contains_codex_contracts() -> None:
    root = Path(__file__).resolve().parents[1]
    required = [
        root / "AGENTS.md",
        root / "CODEX_KICKOFF.md",
        root / "docs" / "BLUEPRINT.md",
        root / "docs" / "SPRINT_01.md",
        root / "docker-compose.yml",
        root / ".env.example",
    ]
    assert all(path.exists() for path in required)
