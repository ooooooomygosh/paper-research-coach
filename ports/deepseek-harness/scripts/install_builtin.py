"""Install the complete workbench as a default, bundled Harness component.

Preserves the original archive, original profile manifest and original plugin
data. New files are staged before swapping the archive. Never modifies account
credentials, application security settings or the signed Electron executable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import struct
import os
import subprocess
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NAME = "@local/dsh-paper-research-coach"
VERSION = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))["version"]
PACKAGE_PATH = "dsh/node_modules/" + NAME


def integrity(data):
    size = 4194304
    return {"algorithm": "SHA256", "hash": hashlib.sha256(data).hexdigest(), "blockSize": size,
            "blocks": [hashlib.sha256(data[i:i+size]).hexdigest() for i in range(0, len(data), size)]}


def entry(tree, name):
    node = tree
    for part in name.split("/"):
        node = node["files"][part]
    return node


def put_entry(tree, name, value):
    node = tree
    parts = name.split("/")
    for part in parts[:-1]:
        node = node.setdefault("files", {}).setdefault(part, {"files": {}})
    node.setdefault("files", {})[parts[-1]] = value


def junction(link, target):
    if link.exists():
        if link.resolve() != target.resolve():
            owned = target.resolve().parent
            if link.is_junction() and link.resolve().is_relative_to(owned):
                link.rmdir()  # Removes only this verified junction, never its contents.
            else:
                raise ValueError(f"已有不同的插件目录，未覆盖：{link}")
        else:
            return
    link.parent.mkdir(parents=True, exist_ok=True)
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
                    f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(target)} | Out-Null"],
                   check=True, capture_output=True, creationflags=0x08000000)


def prepare(installation, profile):
    resources = installation.resolve() / "resources"
    archive = resources / "app.asar"
    if not archive.is_file():
        raise ValueError("找不到 DeepSeek Harness 的 resources/app.asar。")
    pending = ROOT / "dist" / "app.paper-coach-pending.asar"
    pending.parent.mkdir(exist_ok=True)
    backup = ROOT / "backups" / datetime.now().strftime("%Y%m%d-%H%M%S")
    backup.mkdir(parents=True, exist_ok=True)
    shutil.copy2(archive, backup / "app.asar")
    with archive.open("rb") as source:
        sizes = struct.unpack("<IIII", source.read(16))
        tree = json.loads(source.read(sizes[3]))
        payload_start = 8 + sizes[1]
        payload_size = archive.stat().st_size - payload_start
        changes = {}

        def read(name):
            node = entry(tree, name)
            if node.get("unpacked"):
                return (Path(str(archive) + ".unpacked") / name).read_bytes()
            source.seek(payload_start + int(node["offset"]))
            return source.read(node["size"])

        def change(name, data):
            changes[name] = data.encode("utf-8") if isinstance(data, str) else data

        for name in ("lib/main.js", "dsh/node_modules/@deepseek-ai/dsh-app-boot/lib/index.js"):
            text = read(name).decode("utf-8")
            old = 'web: { bundles: ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app"] }'
            new = 'web: { bundles: ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app", "' + NAME + '"] }'
            if old not in text and new not in text:
                raise ValueError("Harness 的默认插件结构已变化，未修改安装文件。")
            text = text.replace(old, new)
            if name == "lib/main.js":
                existing = 'window.webContents.setWindowOpenHandler(({ url }) => {\n\t\tif (["http:", "https:"].includes(new URL(url).protocol)) shell.openExternal(url);'
                updated = 'window.webContents.setWindowOpenHandler(({ url }) => {\n\t\tconst paperDestination = new URL(url);\n\t\tif (paperDestination.protocol === "dsh-app:" && paperDestination.hostname === "app" && paperDestination.pathname.startsWith("/paper-research-coach/")) return { action: "allow", overrideBrowserWindowOptions: { title: "论文研读", autoHideMenuBar: true, webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true } } };\n\t\tif (["http:", "https:"].includes(new URL(url).protocol)) shell.openExternal(url);'
                if existing not in text and updated not in text:
                    raise ValueError("Harness 的窗口处理结构已变化，未修改安装文件。")
                text = text.replace(existing, updated)
            change(name, text)
        manifest = json.loads(read("dsh/package.json"))
        manifest["dependencies"][NAME] = VERSION
        change("dsh/package.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        runtime = json.loads(read("dsh/desktop-runtime.json"))
        existing = next((item for item in runtime["sharedPackages"] if item["name"] == NAME), None)
        if existing:
            existing["version"] = VERSION
        else:
            runtime["sharedPackages"].append({"name": NAME, "version": VERSION, "path": "node_modules/" + NAME})
        change("dsh/desktop-runtime.json", json.dumps(runtime, ensure_ascii=False, indent=2) + "\n")

        physical = profile.resolve().parents[1] / "builtin-plugins" / ("paper-research-coach-" + VERSION)
        physical.mkdir(parents=True, exist_ok=True)
        include = ["host", "client", "locale", "icon.svg", "package.json", "cordis.patch.yml", "runtime", "README.md", "THIRD_PARTY.md", "integrations", "upstream/src", "upstream/skills", "upstream/LICENSE", "upstream/docs/BabelDOC-0.6.4-LICENSE.txt", "upstream/docs/THIRD_PARTY_ANSWER_ME_WITH_HTML.md", "upstream/docs/THIRD_PARTY_TRANSLATION.md"]
        count = 0
        for relative in include:
            origin = ROOT / relative
            if not origin.exists():
                continue
            files = [origin] if origin.is_file() else origin.rglob("*")
            for file in files:
                if not file.is_file() or any(part in ("__pycache__", ".git", "node_modules", ".pytest_cache") for part in file.parts) or file.suffix == ".pyc":
                    continue
                rel = file.relative_to(ROOT)
                target = physical / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if not target.is_file() or target.stat().st_size != file.stat().st_size or target.stat().st_mtime_ns != file.stat().st_mtime_ns:
                    shutil.copy2(file, target)
                put_entry(tree, PACKAGE_PATH + "/" + rel.as_posix(), {"size": file.stat().st_size, "unpacked": True})
                count += 1
        offset = payload_size
        for name, data in changes.items():
            put_entry(tree, name, {"size": len(data), "offset": str(offset), "integrity": integrity(data)})
            offset += len(data)
        encoded = json.dumps(tree, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        padded = encoded + b"\0" * ((-len(encoded)) % 4)
        header = struct.pack("<II", len(padded) + 4, len(encoded)) + padded
        with pending.open("wb") as output:
            output.write(struct.pack("<II", 4, len(header)))
            output.write(header)
            source.seek(payload_start)
            shutil.copyfileobj(source, output, 8 * 1024 * 1024)
            for data in changes.values():
                output.write(data)
    # Verify the staged archive before the user-facing application is stopped.
    with pending.open("rb") as file:
        sizes = struct.unpack("<IIII", file.read(16))
        check = json.loads(file.read(sizes[3]))
        assert entry(check, PACKAGE_PATH + "/host/index.js")["unpacked"]
        node = entry(check, "dsh/package.json")
        file.seek(8 + sizes[1] + int(node["offset"]))
        assert json.loads(file.read(node["size"]))["dependencies"][NAME] == VERSION
    with pending.open("rb") as file:
        pending_hash = hashlib.file_digest(file, "sha256").hexdigest()
    state = {"installation": str(installation.resolve()), "profile": str(profile.resolve()), "archive": str(archive), "pending": str(pending), "pending_sha256": pending_hash, "backup": str(backup), "payload": str(physical), "files": count}
    (ROOT / ".install-state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"prepared": True, "files": count, "backup": str(backup)}, ensure_ascii=False))


def enable_profile(profile, state):
    manifest_path = profile.resolve() / "package.json"
    if not manifest_path.is_file():
        raise ValueError("找不到 desktop profile。请先打开 Harness。")
    backup_manifest = Path(state["backup"]) / "profile-package.json"
    baseline = ROOT / "backups" / "original-profile-package.json"
    if not baseline.exists():
        shutil.copy2(manifest_path, baseline)
    if not backup_manifest.exists():
        shutil.copy2(baseline, backup_manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bundles = manifest.setdefault("dsh", {}).setdefault("profile", {}).setdefault("bundles", [])
    bundles[:] = [name for name in bundles if name != "@local/dsh-paper-coach"]
    if NAME not in bundles:
        bundles.append(NAME)
    manifest.setdefault("dependencies", {})[NAME] = "link:" + Path(state["payload"]).as_posix()
    junction(profile.resolve() / "node_modules" / NAME, Path(state["payload"]))
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    patch = profile.resolve() / "cordis.patch.yml"
    with patch.open("a", encoding="utf-8") as file:
        file.write("\n# Paper Research Coach full workbench is enabled.\n")


def activate(profile):
    state = json.loads((ROOT / ".install-state.json").read_text(encoding="utf-8"))
    archive, pending = Path(state["archive"]), Path(state["pending"])
    if not pending.is_file() or archive.name != "app.asar":
        raise ValueError("待安装文件缺失，请先执行 prepare。")
    with pending.open("rb") as file:
        if hashlib.file_digest(file, "sha256").hexdigest() != state["pending_sha256"]:
            raise ValueError("待安装包校验未通过，未修改应用。")
    enable_profile(profile, state)
    junction(Path(str(archive) + ".unpacked") / PACKAGE_PATH, Path(state["payload"]))
    staged = archive.with_name("app.paper-coach-installing.asar")
    shutil.copy2(pending, staged)
    staged.replace(archive)
    print(json.dumps({"installed": True, "archive": str(archive), "backup": state["backup"]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "enable-user", "activate"])
    parser.add_argument("--installation", type=Path, default=Path(r"D:\APPS\DSH"))
    parser.add_argument("--profile", type=Path, default=Path.home() / ".dsh/profiles/desktop")
    args = parser.parse_args()
    if args.action == "prepare":
        prepare(args.installation, args.profile)
    elif args.action == "enable-user":
        enable_profile(args.profile, json.loads((ROOT / ".install-state.json").read_text(encoding="utf-8")))
        print("Full workbench enabled in the desktop profile")
    else:
        activate(args.profile)
