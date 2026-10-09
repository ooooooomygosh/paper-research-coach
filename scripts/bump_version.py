"""Set one release version everywhere a user or host can see it.

Usage: python scripts/bump_version.py 2.0.0rc10

Updates pyproject.toml, the package, SKILL.md, the plugin marketplace and the
frontend package files, and turns CHANGELOG "Unreleased" into the new version.
Merging the result to main lets CI publish the matching GitHub release.
"""

import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
if len(sys.argv) != 2 or not re.fullmatch(r"\d+\.\d+\.\d+(rc\d+)?", sys.argv[1]):
    raise SystemExit("Usage: python scripts/bump_version.py 2.0.0rc10")
version = sys.argv[1]
npm = re.sub(r"rc(\d+)$", r"-rc.\1", version)


def sub(path, pattern, replacement, count=1):
    file = root / path
    text, n = re.subn(pattern, replacement, file.read_text(encoding="utf-8"), count=count, flags=re.M)
    if n != count:
        raise SystemExit(f"{path}: expected {count} version field(s), found {n}")
    file.write_text(text, encoding="utf-8")


sub("pyproject.toml", r'^version = "[^"]+"', f'version = "{version}"')
sub("src/paper_research_coach/__init__.py", r'^__version__ = "[^"]+"', f'__version__ = "{version}"')
sub("skills/paper-research-coach/SKILL.md", r'^  version: "[^"]+"', f'  version: "{version}"')
market = root / ".claude-plugin/marketplace.json"
data = json.loads(market.read_text(encoding="utf-8"))
data["metadata"]["version"] = version
market.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
for path in ["frontend/package.json", "frontend/package-lock.json"]:
    file = root / path
    data = json.loads(file.read_text(encoding="utf-8"))
    data["version"] = npm
    if "packages" in data:
        data["packages"][""]["version"] = npm
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
changelog = root / "CHANGELOG.md"
text = changelog.read_text(encoding="utf-8")
if f"## {version}\n" not in text:
    if "## Unreleased\n" not in text:
        raise SystemExit("CHANGELOG.md has no '## Unreleased' section to release")
    text = text.replace("## Unreleased\n", f"## Unreleased\n\n## {version}\n", 1)
    changelog.write_text(text, encoding="utf-8")
print(f"Version set to {version} (npm {npm}); tag on merge: v{npm}")
