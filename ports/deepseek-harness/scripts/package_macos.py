"""Build a source installer with built UI and verified translation assets; no user data."""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-from", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    version = json.loads((root / "package.json").read_text())["version"]
    assets = args.assets_from / "runtime/assets"
    manifest = json.loads((root / "runtime/ASSET-MANIFEST.json").read_text())["files"]
    for name, item in manifest.items():
        if hashlib.sha256((assets / name).read_bytes()).hexdigest() != item["sha256"]:
            raise ValueError(f"Translation asset mismatch: {name}")
    output = root / "dist" / f"PRC-DSH-{version}-mac.zip"
    output.parent.mkdir(exist_ok=True)
    names = subprocess.check_output(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "."], cwd=root).decode().split("\0")
    with tempfile.TemporaryDirectory(prefix="prc-mac-package-") as temporary:
        stage = Path(temporary) / output.stem
        stage.mkdir()
        for name in names:
            source = root / name
            if not name or not source.is_file() or source.is_symlink():
                continue
            target = stage / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        for relative in ("upstream/src/paper_research_coach/static", "upstream/src/paper_research_coach/licenses"):
            shutil.copytree(root / relative, stage / relative)
        for name in manifest:
            target = stage / "runtime/assets" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(assets / name, target)
        launcher = stage / "安装.command"
        launcher.write_text('#!/bin/bash\nset -e\ncd "$(dirname "$0")"\nbash macos/install-macos.sh --skip-frontend\n')
        launcher.chmod(0o755)
        (stage / "安装说明.txt").write_text("完整解压后双击安装.command。需要已登录的兼容 DSH、uv、Node.js；首次安装需联网准备 Python 依赖。内含已构建页面与翻译资源，不含账户或个人文献。安装自动备份注册与数据库。完成后退出并重开 DSH。\n")
        checksums = {str(p.relative_to(stage)): hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.rglob("*") if p.is_file()}
        (stage / "PACKAGE-SHA256.json").write_text(json.dumps(checksums, ensure_ascii=False, indent=2))
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=5) as archive:
            for file in stage.rglob("*"):
                if file.is_file():
                    archive.write(file, file.relative_to(stage.parent))
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(".zip.sha256").write_text(digest + "  " + output.name + "\n")
    with zipfile.ZipFile(output) as archive:
        if archive.testzip():
            raise ValueError("ZIP integrity check failed")
    print(json.dumps({"path": str(output), "bytes": output.stat().st_size, "sha256": digest}))


if __name__ == "__main__":
    main()
