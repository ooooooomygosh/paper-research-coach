"""Warn (or fail with --strict) when shipped code changed but the version did not.

CI publishes a GitHub release named after the package version. If that release
already exists, new commits on main never reach the Releases page, so readers
keep downloading the old build. Needs git tags (actions/checkout fetch-depth: 0).
"""

import re
import runpy
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
SHIPPED = ["src", "frontend/src", "frontend/index.html", "skills", "pyproject.toml"]
version = runpy.run_path(str(root / "src/paper_research_coach/__init__.py"))["__version__"]
tag = "v" + re.sub(r"rc(\d+)$", r"-rc.\1", version)


def git(*args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


if git("rev-parse", "-q", "--verify", f"refs/tags/{tag}").returncode != 0:
    print(f"{tag} is not released yet; merging to main publishes it.")
    sys.exit(0)
changed = git("diff", "--name-only", tag, "HEAD", "--", *SHIPPED).stdout.split()
if not changed:
    print(f"{tag} is released and no shipped files changed since.")
    sys.exit(0)
message = (
    f"{tag} is already released, but {len(changed)} shipped file(s) changed since it, "
    "so readers cannot download these changes. Run "
    "`python scripts/bump_version.py <next version>` before merging."
)
print(("::error::" if "--strict" in sys.argv else "::warning::") + message)
sys.exit(1 if "--strict" in sys.argv else 0)
