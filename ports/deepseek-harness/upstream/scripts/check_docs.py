"""Offline guard for repository documentation links. No network or model calls."""
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

root = Path(__file__).resolve().parents[1]
paths = [root / name for name in ["README.md", "README.en.md", "CONTRIBUTING.md", "SECURITY.md"]]
paths += sorted((root / "docs").glob("*.md"))
errors = []
for path in paths:
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r"!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)", text):
        if urlsplit(target).scheme or target.startswith(("#", "//")):
            continue
        relative = unquote(target.split("#", 1)[0])
        if relative and not (path.parent / relative).exists():
            errors.append(f"{path.relative_to(root)}: missing {target}")
if errors:
    raise SystemExit("\n".join(errors))
print(f"Local documentation links: valid ({len(paths)} Markdown files)")
