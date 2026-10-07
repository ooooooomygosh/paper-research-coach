import json, re
from pathlib import Path
import yaml

root = Path(__file__).resolve().parents[1]
skill = root / "skills/paper-research-coach"
text = (skill / "SKILL.md").read_text()
front = yaml.safe_load(text.split("---", 2)[1])
assert front["name"] == skill.name and re.fullmatch(
    "[a-z0-9]+(?:-[a-z0-9]+)*", front["name"]
)
assert len(front["name"]) <= 64 and 1 <= len(front["description"]) <= 1024
assert len(front["compatibility"]) <= 500 and len(text.splitlines()) < 500
assert all(
    isinstance(k, str) and isinstance(v, str) for k, v in front["metadata"].items()
)
for path in skill.rglob("*.md"):
    for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
        if not target.startswith(("http:", "https:", "#")):
            assert (path.parent / target.split("#")[0]).is_file(), (path, target)
for path in skill.rglob("*.json"):
    json.loads(path.read_text())
assert len(json.loads((root / "evals/scenarios.json").read_text())) >= 15
# One release version everywhere a user or host can see it.
version = re.search(r'^version = "([^"]+)"', (root / "pyproject.toml").read_text(), re.M)[1]
market = json.loads((root / ".claude-plugin/marketplace.json").read_text())
npm = json.loads((root / "frontend/package.json").read_text())["version"]
versions = {
    "pyproject.toml": version,
    "__init__.py": re.search(r'"([^"]+)"', (root / "src/paper_research_coach/__init__.py").read_text())[1],
    "SKILL.md": front["metadata"]["version"],
    "marketplace.json": market["metadata"]["version"],
    "package.json": re.sub(r"-rc\.(\d+)$", r"rc\1", npm),
}
assert len(set(versions.values())) == 1, versions
assert [p["skills"] for p in market["plugins"]] == [["./skills/" + front["name"]]], market
print(
    "Skill frontmatter, progressive-disclosure links, JSON assets, scenario manifest,"
    " plugin marketplace and release versions: valid"
)
