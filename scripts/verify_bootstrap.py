import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "AGENTS.md",
    "CODEX_KICKOFF.md",
    "README.md",
    ".env.example",
    ".gitignore",
    "docker-compose.yml",
    "docs/BLUEPRINT.md",
    "docs/DECISIONS.md",
    "docs/SPRINT_01.md",
    "docs/WINDOWS_CODEX_HANDOFF.md",
    "packages/schemas/candidate-business.schema.json",
    "packages/schemas/provenance.schema.json",
]

missing = [path for path in REQUIRED if not (ROOT / path).exists()]
for schema in [
    ROOT / "packages/schemas/candidate-business.schema.json",
    ROOT / "packages/schemas/provenance.schema.json",
]:
    with schema.open("r", encoding="utf-8") as handle:
        json.load(handle)

if missing:
    print("Bootstrap verification FAILED")
    for path in missing:
        print(f"- missing: {path}")
    sys.exit(1)

print("Bootstrap verification PASSED")
print(f"Root: {ROOT}")
print(f"Required files checked: {len(REQUIRED)}")
