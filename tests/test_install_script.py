"""Run scripts/install.sh for real against a local stub release (no network, no GitHub)."""

import base64
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "install.sh"
NAME = "paper_research_coach-9.9.9-py3-none-any.whl"
pytestmark = pytest.mark.skipif(not (shutil.which("sh") and shutil.which("curl")), reason="needs sh and curl")


def stub_wheel(path: Path) -> None:
    """A tiny installable wheel whose `prc --version` answers like the real one."""
    files = {
        "stubprc/__init__.py": "",
        "stubprc/cli.py": "import sys\n\ndef main():\n    print('prc 9.9.9' if '--version' in sys.argv else 'stub')\n",
        "paper_research_coach-9.9.9.dist-info/METADATA": "Metadata-Version: 2.1\nName: paper-research-coach\nVersion: 9.9.9\n",
        "paper_research_coach-9.9.9.dist-info/WHEEL": "Wheel-Version: 1.0\nGenerator: test\nRoot-Is-Purelib: true\nTag: py3-none-any\n",
        "paper_research_coach-9.9.9.dist-info/entry_points.txt": "[console_scripts]\nprc = stubprc.cli:main\n",
    }
    record = []
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            data = text.encode()
            z.writestr(name, data)
            digest = base64.urlsafe_b64encode(hashlib.sha256(data).digest()).rstrip(b"=").decode()
            record.append(f"{name},sha256={digest},{len(data)}")
        record.append("paper_research_coach-9.9.9.dist-info/RECORD,,")
        z.writestr("paper_research_coach-9.9.9.dist-info/RECORD", "\n".join(record) + "\n")


@pytest.fixture
def release(tmp_path):
    folder = tmp_path / "release"
    folder.mkdir()
    stub_wheel(folder / NAME)
    digest = hashlib.sha256((folder / NAME).read_bytes()).hexdigest()
    (folder / "SHA256SUMS").write_text(f"{digest}  {NAME}\n")

    def index(*assets):
        listing = [{"tag_name": "v9.9.9", "draft": False, "assets": [{"name": a, "browser_download_url": (folder / a).as_uri()} for a in assets]}]
        (tmp_path / "releases.json").write_text(json.dumps(listing))
        return (tmp_path / "releases.json").as_uri()

    return folder, index


def run(tmp_path, url, path=None, **extra):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = {"HOME": str(home), "PATH": path or os.environ["PATH"], "PRC_RELEASES_URL": url, "PRC_INSTALL_METHOD": "venv",
           "PRC_VENV_DIR": str(home / "venv"), "PRC_BIN_DIR": str(home / "bin"), **extra}
    return subprocess.run([shutil.which("sh"), str(SCRIPT)], capture_output=True, text=True, env=env, timeout=240), home


def test_installs_a_verified_release_and_the_command_works(tmp_path, release):
    _, index = release
    result, home = run(tmp_path, index(NAME, "SHA256SUMS"))
    assert result.returncode == 0, result.stderr + result.stdout
    assert "Installed: prc 9.9.9" in result.stdout
    assert subprocess.run([str(home / "bin" / "prc"), "--version"], capture_output=True, text=True).stdout.strip() == "prc 9.9.9"
    again, _ = run(tmp_path, index(NAME, "SHA256SUMS"))  # a second run updates in place
    assert again.returncode == 0 and "Installed: prc 9.9.9" in again.stdout


def test_refuses_a_tampered_wheel_and_installs_nothing(tmp_path, release):
    folder, index = release
    (folder / NAME).write_bytes((folder / NAME).read_bytes() + b"tampered")
    result, home = run(tmp_path, index(NAME, "SHA256SUMS"))
    assert result.returncode == 1 and "Checksum mismatch" in result.stderr
    assert not (home / "bin").exists() and not (home / "venv").exists()


def test_refuses_a_release_without_checksums(tmp_path, release):
    folder, index = release
    (folder / "SHA256SUMS").unlink()
    result, home = run(tmp_path, index(NAME))
    assert result.returncode == 1 and "SHA256SUMS" in result.stderr and not (home / "bin").exists()


def test_says_what_to_do_when_there_is_no_installer(tmp_path, release):
    _, index = release
    minimal = tmp_path / "minimal"
    minimal.mkdir()
    for tool in "curl grep sed cut head mktemp rm mkdir dirname ln cat sha256sum tr".split():
        found = shutil.which(tool)
        if found:
            (minimal / tool).symlink_to(found)
    result, _ = run(tmp_path, index(NAME, "SHA256SUMS"), path=str(minimal), PRC_INSTALL_METHOD="")
    assert result.returncode == 1 and "astral.sh/uv" in result.stderr and "--install-uv" in result.stderr
