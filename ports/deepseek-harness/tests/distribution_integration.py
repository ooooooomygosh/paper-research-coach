"""Exercise the shipped CLI and full payload using an isolated recipient profile."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    release, work = args.release.resolve(), args.work.resolve()
    if work.exists():
        raise RuntimeError("Use a new isolated work directory")
    application, home = work / "app", work / "h"
    profile = home / "profiles/desktop"
    profile.mkdir(parents=True)
    archive = application / "resources/app.asar"
    archive.parent.mkdir(parents=True)
    shutil.copy2(args.archive, archive)
    # The reference archive is real. This sentinel executable is never launched.
    (application / "DeepSeek Harness.exe").write_bytes(b"Isolated installer validation fixture; never executed")
    original = {"private": True, "dependencies": {"unrelated": "1.0.0"},
                "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app", "unrelated"]}}}
    (profile / "package.json").write_text(json.dumps(original), encoding="utf-8")
    notes = home / "paper-research-coach/retain-my-notes.txt"
    notes.parent.mkdir()
    notes.write_text("接收方自己的笔记", encoding="utf-8")
    credentials = home / "retain-account-sentinel"
    credentials.write_bytes(b"no real account used in this test")
    original_hash = sha(archive)
    interpreter = release / "package/runtime/python/python.exe"
    installer = release / "installer/install.py"
    common = ["--installation", str(application), "--home", str(home), "--yes", "--no-elevate"]
    print("Starting full recipient installation, using the shipped interpreter and installer", flush=True)
    subprocess.run([str(interpreter), "-X", "utf8", str(installer), "install", *common], check=True)
    receipts = list((home / "plugin-installations/paper-research-coach").glob("*/active.json"))
    assert len(receipts) == 1
    record = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert record["installed_hash"] == sha(archive) and sha(archive) != original_hash
    payload = Path(record["payload"])
    probe = "import sys,json,PyPDF2; from pathlib import Path; import paper_research_coach; from paper_research_coach.server import create_app; assert sys.flags.isolated; assert PyPDF2.__version__=='3.0.1'; assert Path(paper_research_coach.__file__).is_relative_to(Path(sys.argv[1])/'upstream/src'); print(json.dumps({'installedRuntime':True,'isolated':True,'adaptedSource':True,'pdfParser':'PyPDF2 3.0.1'}))"
    subprocess.run([str(payload / "runtime/python/python.exe"), "-X", "utf8", "-c", probe, str(payload)], check=True)
    print("Verifying uninstall and data retention", flush=True)
    subprocess.run([str(interpreter), "-X", "utf8", str(installer), "uninstall", *common], check=True)
    assert sha(archive) == original_hash
    assert json.loads((profile / "package.json").read_text(encoding="utf-8")) == original
    assert notes.read_text(encoding="utf-8") == "接收方自己的笔记"
    assert credentials.read_bytes() == b"no real account used in this test"
    result = {"version": record["version"], "fullPayloadInstalled": True, "originalArchiveRestored": True,
              "profileRestored": True, "otherPluginRetained": True, "notesAndAccountSentinelRetained": True}
    (Path(__file__).parent / "distribution-integration.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
