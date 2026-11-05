"""Installer transactions are exercised against isolated application/profile trees."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import struct

import pytest

SOURCE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prc_distribution", SOURCE / "distribution/installer.py")
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def write_archive(path, *, version=installer.HOST_VERSION, extra=""):
    default = 'web: { bundles: ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app"] }'
    main = default + '\nwindow.webContents.setWindowOpenHandler(({ url }) => {\n\t\tif (["http:", "https:"].includes(new URL(url).protocol)) shell.openExternal(url);\n});\n' + extra
    contents = {"lib/main.js": main.encode(), "dsh/node_modules/@deepseek-ai/dsh-app-boot/lib/index.js": default.encode(),
                "dsh/package.json": json.dumps({"version": version, "dependencies": {"unrelated": "1.2.3"}}).encode(),
                "dsh/desktop-runtime.json": json.dumps({"sharedPackages": [{"name": "unrelated", "path": "node_modules/unrelated", "version": "1.2.3"}]}).encode(),
                "unrelated/data.bin": b"preserve this exact original data\x00\x01\xff"}
    tree, offset = {"files": {}}, 0
    for name, data in contents.items():
        installer.put_entry(tree, name, {"size": len(data), "offset": str(offset), "integrity": installer.integrity(data)})
        offset += len(data)
    encoded = json.dumps(tree).encode()
    padded = encoded + b"\0" * (-len(encoded) % 4)
    header = struct.pack("<II", len(padded) + 4, len(encoded)) + padded
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<II", 4, len(header)) + header + b"".join(contents.values()))


@pytest.fixture
def context(tmp_path, monkeypatch):
    root = tmp_path / "解压目录 with spaces"
    root.mkdir()
    product = {
        "package/runtime/python/python.exe": b"test runtime, never executed",
        "package/runtime/python/Lib/site-packages/PyPDF2/__init__.py": b"# dependency fixture, never executed",
        "package/host/index.js": b"export const name = 'paper-research-coach';",
        "package/host/studio-renderer.mjs": b"// renderer fixture, never executed",
        "package/integrations/answer-me-with-html/prc-renderer.mjs": b"// adapted bundle fixture, never executed",
        "package/integrations/learn-from-materials/scripts/prc_render_page.py": b"# adapted template fixture, never executed",
        "package/integrations/learn-from-materials/scripts/extractor/prc_utils.py": b"# adapted extraction fixture, never executed",
        "package/upstream/src/paper_research_coach/material_extract.py": b"# worker fixture, never executed",
        "package/client/client.js": b"// client fixture",
        "package/upstream/src/paper_research_coach/static/index.html": b"<!doctype html><title>fixture</title>",
        "installer/install.py": b"# isolated fixture",
    }
    files = {}
    for name, contents in product.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
        files[name] = {"size": len(contents), "sha256": installer.digest(path)}
    installer.write_json(root / "RELEASE.json", {"version": installer.VERSION, "hostVersion": installer.HOST_VERSION, "files": files})
    installation = tmp_path / "接收方 Apps/DeepSeek Harness"
    write_archive(installation / "resources/app.asar")
    (installation / installer.EXE).write_bytes(b"fake exe; never launched")
    home = tmp_path / "用户数据"
    profile = home / "profiles/desktop"
    profile.mkdir(parents=True)
    original = {"private": True, "dependencies": {"unrelated": "1.2.3"},
                "dsh": {"profile": {"bundles": ["@deepseek-ai/dsh-base", "unrelated"]}}, "custom": {"retain": True}}
    installer.write_json(profile / "package.json", original)
    state_dir = home / "plugin-installations/paper-research-coach/test"
    args = argparse.Namespace(home=home, yes=True, no_elevate=True)
    monkeypatch.setattr(installer, "ROOT", root)
    monkeypatch.setattr(installer, "process_paths", lambda: [])
    return argparse.Namespace(root=root, installation=installation, home=home, profile=profile, original=original,
                              state=state_dir, args=args, archive=installation / "resources/app.asar")


def test_install_repeat_and_uninstall_preserve_other_plugins_and_data(context):
    c = context
    before_hash = installer.digest(c.archive)
    data = c.home / "paper-research-coach/precious-note.txt"
    data.parent.mkdir()
    data.write_text("用户自己的笔记", encoding="utf-8")
    # A credential-like sentinel exists outside the profile manifest and is never accessed.
    credentials = c.home / "account-private-store"
    credentials.write_bytes(b"recipient-account-sentinel")
    record = installer.install(c.args, c.installation, c.profile, c.state)
    patched = installer.Archive(c.archive)
    assert patched.read("unrelated/data.bin") == b"preserve this exact original data\x00\x01\xff"
    assert NAME_BYTES in patched.read("lib/main.js")
    assert b'paperDestination.hostname === "app"' in patched.read("lib/main.js")
    assert installer.NAME in installer.read_json(c.profile / "package.json")["dsh"]["profile"]["bundles"]
    assert installer.same_path(installer.link_target(c.profile / "node_modules" / installer.NAME), record["payload"])
    repeat = installer.install(c.args, c.installation, c.profile, c.state)
    assert repeat == record
    assert len([p for p in c.state.iterdir() if p.is_dir()]) == 1
    current = installer.read_json(c.profile / "package.json")
    current["dependencies"]["another-plugin"] = "3.0"
    current["dsh"]["profile"]["bundles"].append("another-plugin")
    installer.write_json(c.profile / "package.json", current)
    installer.uninstall(c.args, c.installation, c.state)
    assert installer.digest(c.archive) == before_hash
    manifest = installer.read_json(c.profile / "package.json")
    assert manifest["dependencies"] == {"unrelated": "1.2.3", "another-plugin": "3.0"}
    assert manifest["dsh"]["profile"]["bundles"] == c.original["dsh"]["profile"]["bundles"] + ["another-plugin"]
    assert manifest["custom"] == c.original["custom"]
    assert not os.path.lexists(c.profile / "node_modules" / installer.NAME)
    assert not os.path.lexists(Path(str(c.archive) + ".unpacked") / installer.PACKAGE_PATH)
    assert data.read_text(encoding="utf-8") == "用户自己的笔记"
    assert credentials.read_bytes() == b"recipient-account-sentinel"
    assert installer.read_json(c.state / "active.json")["uninstalled"]


NAME_BYTES = installer.NAME.encode()


def test_failed_profile_commit_rolls_back_app_and_links(context, monkeypatch):
    c = context
    old_hash = installer.digest(c.archive)
    write = installer.write_json

    def fail_once(path, value):
        if path == c.profile / "package.json" and installer.NAME in value.get("dependencies", {}):
            raise OSError("simulated profile disk error")
        write(path, value)

    monkeypatch.setattr(installer, "write_json", fail_once)
    with pytest.raises(OSError, match="simulated profile"):
        installer.install(c.args, c.installation, c.profile, c.state)
    assert installer.digest(c.archive) == old_hash
    assert installer.read_json(c.profile / "package.json") == c.original
    assert not os.path.lexists(c.profile / "node_modules" / installer.NAME)
    assert not os.path.lexists(Path(str(c.archive) + ".unpacked") / installer.PACKAGE_PATH)
    assert not (c.state / "active.json").exists()


def test_unsupported_host_refused_without_changes(context):
    c = context
    write_archive(c.archive, version="9.0.0")
    before = installer.digest(c.archive)
    with pytest.raises(installer.InstallError, match="9.0.0"):
        installer.install(c.args, c.installation, c.profile, c.state)
    assert installer.digest(c.archive) == before
    assert not c.state.exists()
    assert installer.read_json(c.profile / "package.json") == c.original


def test_running_host_refused(context, monkeypatch):
    c = context
    monkeypatch.setattr(installer, "process_paths", lambda: [str(c.installation / installer.EXE)])
    with pytest.raises(installer.InstallError, match="退出"):
        installer.install(c.args, c.installation, c.profile, c.state)
    assert not c.state.exists()


def test_tampered_release_refused(context):
    c = context
    (c.root / "package/host/index.js").write_bytes(b"tampered")
    with pytest.raises(installer.InstallError, match="校验失败"):
        installer.install(c.args, c.installation, c.profile, c.state)
    assert not c.state.exists()


def test_manifest_path_traversal_refused(context):
    c = context
    file = c.root / "RELEASE.json"
    manifest = installer.read_json(file)
    manifest["files"]["../private-file"] = {"size": 1, "sha256": "bad"}
    installer.write_json(file, manifest)
    with pytest.raises(installer.InstallError, match="无效路径"):
        installer.verify_release(c.root)


def test_uninstall_keeps_official_app_update(context):
    c = context
    installer.install(c.args, c.installation, c.profile, c.state)
    write_archive(c.archive, version="0.3.0", extra="// official updated core")
    updated_hash = installer.digest(c.archive)
    installer.uninstall(c.args, c.installation, c.state)
    assert installer.digest(c.archive) == updated_hash
    assert installer.read_json(c.profile / "package.json") == c.original


def test_uninstall_refuses_overwriting_other_app_edits(context):
    c = context
    installer.install(c.args, c.installation, c.profile, c.state)
    with c.archive.open("ab") as stream:
        stream.write(b"another tool's change")
    changed_hash = installer.digest(c.archive)
    with pytest.raises(installer.InstallError, match="其他工具修改"):
        installer.uninstall(c.args, c.installation, c.state)
    assert installer.digest(c.archive) == changed_hash
    assert installer.NAME in installer.read_json(c.profile / "package.json")["dependencies"]


def test_previous_plugin_links_and_config_are_restored(context):
    c = context
    old_payload = c.home / "older-plugin"
    old_payload.mkdir()
    old_manifest = c.original | {"dependencies": {installer.NAME: "link:" + old_payload.as_posix(), "unrelated": "1.2.3"},
                                "dsh": {"profile": {"bundles": [installer.NAME, "unrelated"]}}}
    installer.write_json(c.profile / "package.json", old_manifest)
    profile_link = c.profile / "node_modules" / installer.NAME
    core_link = Path(str(c.archive) + ".unpacked") / installer.PACKAGE_PATH
    installer.set_junction(profile_link, str(old_payload), None)
    installer.set_junction(core_link, str(old_payload), None)
    installer.install(c.args, c.installation, c.profile, c.state)
    installer.uninstall(c.args, c.installation, c.state)
    assert installer.read_json(c.profile / "package.json") == old_manifest
    assert installer.same_path(installer.link_target(profile_link), str(old_payload))
    assert installer.same_path(installer.link_target(core_link), str(old_payload))


def test_integrity_enforced_host_refused_without_changing_executable(context):
    c = context
    data = b"prefix" + installer.FUSE_SENTINEL + bytes([1, 9]) + b"101110011"
    (c.installation / installer.EXE).write_bytes(data)
    with pytest.raises(installer.InstallError, match="完整性校验"):
        installer.check_host(c.installation)
    assert (c.installation / installer.EXE).read_bytes() == data


@pytest.mark.skipif(not os.environ.get("PRC_REFERENCE_ASAR"), reason="optional real Harness archive")
def test_build_against_real_host_preserves_unmodified_files(tmp_path):
    source = Path(os.environ["PRC_REFERENCE_ASAR"])
    output = tmp_path / "real-patched.asar"
    before = installer.Archive(source)
    installer.build_archive(source, output, [("host/index.js", 100)])
    after = installer.Archive(output)
    changed = {"lib/main.js", "dsh/node_modules/@deepseek-ai/dsh-app-boot/lib/index.js", "dsh/package.json", "dsh/desktop-runtime.json"}
    seen = 0

    def walk(tree, prefix=""):
        for name, node in tree.get("files", {}).items():
            relative = prefix + name
            if "files" in node:
                yield from walk(node, relative + "/")
            elif not node.get("unpacked"):
                yield relative

    paths = list(walk(before.tree))
    stride = max(1, len(paths) // 100)
    for name in paths[::stride]:
        if name not in changed and not name.startswith(installer.PACKAGE_PATH + "/"):
            assert before.read(name) == after.read(name)
            seen += 1
    assert seen >= 50
    assert after.has_plugin()
