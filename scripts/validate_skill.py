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
print(
    "Skill frontmatter, progressive-disclosure links, JSON assets and scenario manifest: valid"
)
