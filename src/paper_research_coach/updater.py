"""Find, verify and install a newer release. Used by `prc update` and the workbench banner.

Only the project's own GitHub releases are ever used: no URL comes from the user or the
browser. A wheel is installed only after its SHA-256 matches the SHA256SUMS file that the
same release published. The check sends no data about you: one anonymous request to the
GitHub releases API, at most once a day, and `PRC_NO_UPDATE_CHECK=1` turns it off.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from packaging.version import InvalidVersion, Version

from . import __version__

REPO = os.environ.get("PRC_UPDATE_REPO", "ooooooomygosh/paper-research-coach")
RELEASES_URL = os.environ.get("PRC_RELEASES_URL") or f"https://api.github.com/repos/{REPO}/releases?per_page=10"
CHECK_INTERVAL = 24 * 3600
RETRY_AFTER_ERROR = 3600
SKILL_HOSTS = {"codex": ".agents/skills", "claude": ".claude/skills", "pi": ".pi/agent/skills"}
WHEEL = re.compile(r"^paper_research_coach-[^-]+-py3-none-any\.whl$")


class UpdateError(ValueError):
    """A problem the reader can act on, in plain words."""


def normalize(tag: str) -> str:
    """v2.0.0-rc.11 -> 2.0.0rc11 (the version the wheel carries)."""
    m = re.fullmatch(r"v?(\d+\.\d+\.\d+)(?:-rc\.?(\d+))?", tag.strip())
    if not m:
        raise UpdateError(f"无法识别版本号：{tag}")
    return m.group(1) + (f"rc{m.group(2)}" if m.group(2) else "")


def is_newer(candidate: str, current: str = __version__) -> bool:
    try:
        return Version(candidate) > Version(current)
    except InvalidVersion:
        return False


def find_latest(client: httpx.Client | None = None) -> dict | None:
    """The newest release that carries an installable wheel, pre-releases included."""
    own = client is None
    client = client or httpx.Client(timeout=8, follow_redirects=True, headers={"Accept": "application/vnd.github+json", "User-Agent": "paper-research-coach"})
    try:
        if RELEASES_URL.startswith("file://"):
            import json
            data = json.loads(Path(RELEASES_URL[7:]).read_text(encoding="utf-8"))
        else:
            response = client.get(RELEASES_URL)
            response.raise_for_status()
            data = response.json()
    finally:
        if own:
            client.close()
    best = None
    for release in data:
        if release.get("draft"):
            continue
        assets = {a["name"]: a["browser_download_url"] for a in release.get("assets", [])}
        wheel = next((n for n in assets if WHEEL.match(n)), None)
        if not wheel:
            continue
        try:
            version = normalize(release["tag_name"])
        except UpdateError:
            continue
        if best is None or Version(version) > Version(best["version"]):
            best = {
                "tag": release["tag_name"], "version": version, "notes_url": release.get("html_url", ""),
                "wheel_name": wheel, "wheel_url": assets[wheel], "sums_url": assets.get("SHA256SUMS", ""),
            }
    return best


def check(store, force: bool = False, fetch=find_latest, clock=time.time) -> dict:
    """The cached update state. Never raises: a failed check is simply 'no news'."""
    state = {"current": __version__, "available": False}
    if os.environ.get("PRC_NO_UPDATE_CHECK"):
        return {**state, "disabled": True}
    cached = store.setting("update-check", {}) or {}
    age = clock() - cached.get("checked_at", 0)
    limit = RETRY_AFTER_ERROR if cached.get("error") else CHECK_INTERVAL
    if force or age >= limit or cached.get("current") != __version__:
        try:
            latest = fetch()
            cached = {"checked_at": clock(), "current": __version__, "latest": latest}
        except (httpx.HTTPError, ValueError, OSError, KeyError):
            cached = {"checked_at": clock(), "current": __version__, "latest": cached.get("latest"), "error": True}
        store.set_setting("update-check", cached)
    latest = cached.get("latest")
    if latest and is_newer(latest["version"]):
        state.update(available=True, latest=latest["version"], notes_url=latest.get("notes_url", ""))
    return state


def download(release: dict, directory: Path, client: httpx.Client | None = None) -> Path:
    """Download the wheel and refuse it unless it matches the release's SHA256SUMS."""
    if not release.get("sums_url"):
        raise UpdateError("这个版本没有发布校验文件（SHA256SUMS），为安全起见不自动安装。请到 Releases 页面手动下载。")
    own = client is None
    client = client or httpx.Client(timeout=60, follow_redirects=True, headers={"User-Agent": "paper-research-coach"})

    def fetch(url):
        if url.startswith("file://") and RELEASES_URL.startswith("file://"):  # offline test mode only
            return Path(url[7:]).read_bytes()
        try:
            response = client.get(url)
            response.raise_for_status()
            return response.content
        except (httpx.HTTPError, ValueError):
            raise UpdateError("下载失败。请检查网络后重试，或到 Releases 页面手动下载。") from None

    try:
        sums = fetch(release["sums_url"]).decode("utf-8", "replace")
        expected = next((line.split()[0] for line in sums.splitlines() if line.split()[-1:] == [release["wheel_name"]]), "")
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise UpdateError("校验文件里找不到这个安装包的记录，已停止更新。")
        data = fetch(release["wheel_url"])
    finally:
        if own:
            client.close()
    if hashlib.sha256(data).hexdigest() != expected:
        raise UpdateError("安装包的校验值不符，已停止更新。请重试；如果反复出现，请到 Releases 页面手动下载。")
    path = directory / release["wheel_name"]
    path.write_bytes(data)
    return path


def installer_command(wheel: Path) -> list[str]:
    """pip when this environment has it, otherwise uv (uv-made environments ship without pip)."""
    if subprocess.run([sys.executable, "-m", "pip", "--version"], capture_output=True).returncode == 0:
        return [sys.executable, "-m", "pip", "install", "--upgrade", "--disable-pip-version-check", str(wheel)]
    import shutil
    uv = shutil.which("uv")
    if uv:
        return [uv, "pip", "install", "--python", sys.executable, "--upgrade", str(wheel)]
    raise UpdateError("找不到 pip 或 uv，无法在这个环境里更新。请重新运行安装脚本。")


def install(wheel: Path) -> None:
    result = subprocess.run(installer_command(wheel), capture_output=True, text=True, timeout=900)
    if result.returncode:
        tail = (result.stderr or result.stdout).strip().splitlines()[-3:]
        raise UpdateError("安装没有成功：" + " ".join(tail)[:300])


def installed_skill_hosts() -> list[str]:
    return [h for h, base in SKILL_HOSTS.items() if (Path.home() / base / "paper-research-coach" / "SKILL.md").is_file()]


def refresh_skills(data_dir: str) -> list[str]:
    """Overwrite copies of the Skill that `prc install-skill` made. Plugin installs are left to the host."""
    done = []
    for host in installed_skill_hosts():
        # A fresh process, so the copy comes from the newly installed package.
        r = subprocess.run([sys.executable, "-m", "paper_research_coach.cli", "--data-dir", data_dir, "install-skill", "--host", host, "--force"], capture_output=True)
        if r.returncode == 0:
            done.append(host)
    return done


def apply(store, release: dict | None = None) -> dict:
    """Install the newest release. The caller restarts the workbench afterwards."""
    release = release or find_latest()
    if not release or not is_newer(release["version"]):
        return {"updated": False, "current": __version__}
    with tempfile.TemporaryDirectory(prefix="prc-update-") as directory:
        wheel = download(release, Path(directory))
        install(wheel)
    skills = refresh_skills(str(store.root))
    store.set_setting("update-check", {"checked_at": time.time(), "current": release["version"], "latest": release})
    return {"updated": True, "from": __version__, "to": release["version"], "skills": skills, "notes_url": release["notes_url"]}
