"""Build a shareable, credential-free Windows distribution from explicit inputs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.2.0"
SLUG = f"PRC-DSH-{VERSION}-win-x64"
ARCHIVE_FOLDER = f"PRC-DSH-{VERSION}"
OMIT_PARTS = {"__pycache__", "node_modules", ".git", ".pytest_cache", ".ruff_cache", ".vite", ".DS_Store"}
FORBIDDEN = {".dsh", ".test-data", ".test-profile", "backups", "install-result.json", ".install-state.json", "direct_url.json"}


def digest(file):
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def excluded(path, relative):
    if any(part in OMIT_PARTS for part in relative.parts) or path.suffix in (".pyc", ".pyo") or path.name == "direct_url.json":
        return True
    if relative.parts[:3] == ("runtime", "python", "Scripts"):
        return True  # Windows console wrappers embed the original build interpreter path.
    return False


def copy_inputs(stage, include_runtime=True):
    # Only product code, public upstream source and portable dependencies are allowed.
    allow = ["host", "client", "locale", "icon.svg", "package.json", "cordis.patch.yml", "runtime",
             "THIRD_PARTY.md", "功能与验收.md", "docs", "upstream", "integrations", "scripts/prepare_integrations.py"]
    if not include_runtime:
        allow.remove("runtime")
    count = 0
    for name in allow:
        source = ROOT / name
        expected = set()
        candidates = [source] if source.is_file() else source.rglob("*")
        for file in candidates:
            relative = file.relative_to(ROOT)
            if excluded(file, relative) or not file.is_file():
                continue
            if file.is_symlink() or any(part in FORBIDDEN for part in relative.parts):
                raise RuntimeError(f"Excluded private or linked input: {relative}")
            expected.add(relative.as_posix())
            target = stage / "package" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.is_file() or target.stat().st_size != file.stat().st_size or digest(target) != digest(file):
                shutil.copyfile(file, target)
            count += 1
            if count % 4000 == 0:
                print(f"Staged {count} product/source files", flush=True)
        if not include_runtime and source.is_dir():
            # Only remove obsolete generated/source files in this verified
            # release staging tree. Never touch source, installed plugins or data.
            copied_dir = stage / "package" / name
            for old in copied_dir.rglob("*"):
                if old.is_file() and old.relative_to(stage / "package").as_posix() not in expected:
                    if not old.resolve().is_relative_to(stage.resolve()):
                        raise RuntimeError("Refusing stale file outside release staging")
                    old.unlink()
    (stage / "package/README.md").write_text((ROOT / "distribution/README.txt").read_text(encoding="utf-8"), encoding="utf-8")


def write_launchers(stage):
    installer = stage / "installer/install.py"
    installer.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "distribution/installer.py", installer)
    shutil.copyfile(ROOT / "distribution/README.txt", stage / "先读我.txt")
    # Resolve everything relative to the portable interpreter, ignoring any
    # recipient-wide Python home/path or user site packages.
    (stage / "package/runtime/python/python312._pth").write_text(
        "DLLs\nLib\n../../upstream/src\nLib/site-packages\nimport site\n", encoding="ascii")
    for filename, action in (("安装.cmd", "install"), ("卸载.cmd", "uninstall"), ("检查安装包.cmd", "check")):
        content = ('@echo off\r\nsetlocal DisableDelayedExpansion\r\nchcp 65001 >nul\r\n'
                   'title Paper Research Coach - DeepSeek Harness\r\n'
                   'if not exist "%~dp0package\\runtime\\python\\python.exe" (\r\n'
                   '  echo Please extract the ENTIRE ZIP before running this installer.\r\n'
                   '  pause\r\n  exit /b 1\r\n)\r\n'
                   f'"%~dp0package\\runtime\\python\\python.exe" -X utf8 "%~dp0installer\\install.py" {action} %*\r\n'
                   'set "PRC_EXIT=%ERRORLEVEL%"\r\necho.\r\npause\r\nexit /b %PRC_EXIT%\r\n')
        (stage / filename).write_bytes(content.encode("ascii"))


def frontend_licenses(stage):
    lock = json.loads((ROOT / "upstream/frontend/package-lock.json").read_text(encoding="utf-8"))
    notices = ["Frontend dependency licenses (including build dependencies)", "Original lockfile: upstream/frontend/package-lock.json", ""]
    for relative, info in sorted(lock.get("packages", {}).items()):
        if not relative.startswith("node_modules/"):
            continue
        folder = ROOT / "upstream/frontend" / relative
        metadata_file = folder / "package.json"
        if not metadata_file.is_file():
            continue
        meta = json.loads(metadata_file.read_text(encoding="utf-8-sig"))
        notices.extend(["=" * 72, f"{meta.get('name', relative)} {meta.get('version', info.get('version', ''))}",
                        f"License: {meta.get('license', info.get('license', 'See package source'))}"])
        for file in sorted(folder.iterdir()):
            if file.is_file() and file.name.lower().startswith(("license", "licence", "copying", "notice")):
                notices.extend([f"--- {file.name} ---", file.read_text(encoding="utf-8", errors="replace")])
    destination = stage / "package/licenses/frontend-dependencies.txt"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(notices) + "\n", encoding="utf-8")


def manifest(stage):
    files = {}
    private_tokens = [str(Path.home()).encode(), str(Path.home()).replace("\\", "/").encode(),
                      str(ROOT).encode(), str(ROOT).replace("\\", "/").encode()]
    total = 0
    for file in sorted(stage.rglob("*")):
        relative = file.relative_to(stage)
        if excluded(file, relative) or not file.is_file() or relative.as_posix() == "RELEASE.json":
            continue
        if file.is_symlink() or any(part in FORBIDDEN for part in relative.parts) or file.suffix == ".asar":
            raise RuntimeError(f"Unexpected private/disallowed file: {relative}")
        size = file.stat().st_size
        # Compiled caches are excluded above; scan public text and launcher contents
        # for accidental absolute paths from this build machine.
        if file.suffix.lower() in (".py", ".js", ".ts", ".json", ".txt", ".md", ".cmd", ".ps1", ".html", ".yml", ".toml", ".map", ".cfg", ".pth", ".ini") and size < 16 * 1024 * 1024:
            contents = file.read_bytes()
            if any(token and token in contents for token in private_tokens):
                raise RuntimeError(f"Build-machine path leaked into public file: {relative}")
        files[relative.as_posix()] = {"size": size, "sha256": digest(file)}
        total += size
    value = {"name": "paper-research-coach-deepseek-harness", "version": VERSION, "hostVersion": "0.2.1-rc.5",
             "platform": "win32-x64", "upstreamVersion": "2.0.0rc13", "fileCount": len(files), "unpackedBytes": total,
             "buildTime": datetime.now(timezone.utc).isoformat(), "files": files}
    (stage / "RELEASE.json").write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Manifest: {len(files)} files, {total / 1048576:.1f} MiB, no account/profile/data/backups", flush=True)
    return value


def archive(stage, value):
    destination = ROOT / "dist" / (SLUG + ".zip")
    temporary = destination.with_suffix(".zip.tmp")
    entries = sorted([*value["files"], "RELEASE.json"])
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as output:
        for index, relative in enumerate(entries, 1):
            info = zipfile.ZipInfo(ARCHIVE_FOLDER + "/" + relative, date_time=(2026, 11, 4, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            with (stage / relative).open("rb") as source, output.open(info, "w", force_zip64=True) as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
            if index % 4000 == 0:
                print(f"Archived {index}/{len(entries)} files", flush=True)
    with zipfile.ZipFile(temporary) as check:
        if check.testzip() is not None:
            raise RuntimeError("ZIP CRC verification failed")
        if len(check.infolist()) != len(entries):
            raise RuntimeError("ZIP file count mismatch")
    temporary.replace(destination)
    sha = digest(destination)
    destination.with_suffix(".zip.sha256").write_text(sha + "  " + destination.name + "\n", encoding="ascii")
    result = {"zip": str(destination), "stage": str(stage), "sha256": sha, "bytes": destination.stat().st_size,
              "fileCount": value["fileCount"], "unpackedBytes": value["unpackedBytes"]}
    (ROOT / "dist/latest-release.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-only", action="store_true")
    parser.add_argument("--archive-stage", type=Path)
    parser.add_argument("--refresh-stage", type=Path)
    args = parser.parse_args()
    if args.archive_stage or args.refresh_stage:
        stage = (args.archive_stage or args.refresh_stage).resolve()
        if not stage.is_relative_to((ROOT / "dist/release").resolve()):
            raise RuntimeError("Stage must be inside this project's dist/release")
        if args.refresh_stage:
            copy_inputs(stage, include_runtime=False)
            write_launchers(stage)
    else:
        stage = ROOT / "dist/release" / ("r-" + uuid.uuid4().hex[:8])
        stage.mkdir(parents=True, exist_ok=False)
        copy_inputs(stage)
        write_launchers(stage)
        frontend_licenses(stage)
        (ROOT / "dist/latest-stage.txt").write_text(str(stage), encoding="utf-8")
    if args.archive_stage:
        value = json.loads((stage / "RELEASE.json").read_text(encoding="utf-8"))
        for name, expected in value["files"].items():
            if digest(stage / name) != expected["sha256"]:
                raise RuntimeError(f"Release snapshot changed: {name}")
    else:
        value = manifest(stage)
    if not args.stage_only:
        archive(stage, value)
    else:
        print(json.dumps({"stage": str(stage)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
