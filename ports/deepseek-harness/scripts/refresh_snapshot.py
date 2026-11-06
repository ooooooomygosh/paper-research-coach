"""Keep SOURCE_SNAPSHOT.json true: hash every file of this folder and list what differs from the standalone workbench.

    python scripts/refresh_snapshot.py check                       # exit 1 if the file is out of date
    python scripts/refresh_snapshot.py write [--baseline COMMIT]   # rewrite it; a new COMMIT moves the baseline

`upstream/` is a copy of the standalone workbench taken at a commit of this repository (the baseline). The
file records that commit, the workbench version found in `upstream/`, a SHA-256 for every file here (UTF-8
text with CRLF read as LF, binary bytes as they are) and the files of `upstream/` that differ from the
baseline. Run `check` after any change here and `write` after syncing a newer workbench. It needs git and the
baseline commit; it does not need the network, Harness or an account.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "SOURCE_SNAPSHOT.json"
SKIP = {"SOURCE_SNAPSHOT.json"}  # it cannot contain its own hash


def git(*args: str, cwd: Path = ROOT) -> bytes:
    done = subprocess.run(["git", *args], cwd=cwd, capture_output=True)
    if done.returncode:
        raise SystemExit(f"git {' '.join(args)} failed: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout


def digest(data: bytes) -> str:
    try:
        data.decode("utf-8")
        data = data.replace(b"\r\n", b"\n")
    except UnicodeDecodeError:
        pass
    return hashlib.sha256(data).hexdigest()


def files() -> list[str]:
    """Files of this folder that git tracks or would add (build output and other ignored files are left out)."""
    out = git("ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", ".")
    return sorted({name for name in out.decode("utf-8").split("\0") if name and name not in SKIP and (ROOT / name).is_file()})


def workbench_version() -> str:
    text = (ROOT / "upstream/src/paper_research_coach/__init__.py").read_text(encoding="utf-8")
    return re.search(r'__version__\s*=\s*"([^"]+)"', text).group(1)


def baseline_blob(commit: str, path: str) -> bytes | None:
    done = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True)
    return done.stdout if done.returncode == 0 else None


def compute(commit: str) -> dict:
    names = files()
    changed = []
    for name in names:
        if not name.startswith("upstream/"):
            continue
        original = baseline_blob(commit, name[len("upstream/"):])
        mine = (ROOT / name).read_bytes()
        if original is None:
            changed.append({"path": name[len("upstream/"):], "change": "added"})
        elif digest(mine) != digest(original):
            changed.append({"path": name[len("upstream/"):], "change": "modified"})
    return {
        "version": workbench_version(),
        "commit": commit,
        "sourceFiles": {name: digest((ROOT / name).read_bytes()) for name in names},
        "upstreamChangedFiles": changed,
    }


def render(record: dict) -> str:
    return json.dumps(record, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("mode", choices=["check", "write"])
    cli.add_argument("--baseline", help="commit of this repository that upstream/ was taken from (default: the recorded one)")
    args = cli.parse_args()
    record = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    commit = args.baseline or record["upstream"]["commit"]
    fresh = compute(commit)
    if args.mode == "write":
        record["upstream"] = {**record["upstream"], "version": fresh["version"], "commit": fresh["commit"]}
        record["sourceFiles"] = fresh["sourceFiles"]
        record["upstreamChangedFiles"] = fresh["upstreamChangedFiles"]
        SNAPSHOT.write_text(render(record), encoding="utf-8")
        print(f"Wrote {SNAPSHOT.name}: workbench {fresh['version']} at {commit[:12]}, "
              f"{len(fresh['sourceFiles'])} files hashed, {len(fresh['upstreamChangedFiles'])} differ from the baseline.")
        return 0
    problems = []
    if record["upstream"]["version"] != fresh["version"]:
        problems.append(f"version: recorded {record['upstream']['version']}, upstream/ has {fresh['version']}")
    if record["upstream"]["commit"] != commit:
        problems.append(f"baseline commit: recorded {record['upstream']['commit'][:12]}, checked against {commit[:12]}")
    recorded, now = record["sourceFiles"], fresh["sourceFiles"]
    for name in sorted(set(recorded) | set(now)):
        if recorded.get(name) != now.get(name):
            problems.append(f"{name}: " + ("not recorded" if name not in recorded else "no longer present" if name not in now else "content changed"))
    if record["upstreamChangedFiles"] != fresh["upstreamChangedFiles"]:
        problems.append("upstreamChangedFiles: the list of files that differ from the baseline has changed")
    if problems:
        print(f"{SNAPSHOT.name} is out of date ({len(problems)} difference(s)); run: python scripts/refresh_snapshot.py write")
        for line in problems[:20]:
            print("  -", line)
        if len(problems) > 20:
            print(f"  ... and {len(problems) - 20} more")
        return 1
    print(f"{SNAPSHOT.name} is up to date: workbench {fresh['version']} at {commit[:12]}, {len(now)} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
