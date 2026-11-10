"""Offline, relocatable Windows installer; uses only the bundled Python stdlib.

No account stores are read. Application edits are built against the recipient's
own archive. Only the final resources-directory transaction may need UAC.
"""
from __future__ import annotations

import argparse
import copy
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import struct
import subprocess
import sys
import time
import uuid

NAME = "@local/dsh-paper-research-coach"
VERSION = "1.3.1"
HOST_VERSION = "0.2.1-rc.5"
PACKAGE_PATH = "dsh/node_modules/" + NAME
EXE = "DeepSeek Harness.exe"
ROOT = Path(__file__).resolve().parents[1]
FUSE_SENTINEL = b"dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX"


class InstallError(Exception):
    pass


def digest(file: Path) -> str:
    with file.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_json(file: Path):
    return json.loads(file.read_text(encoding="utf-8-sig"))


def write_json(file: Path, value):
    file.parent.mkdir(parents=True, exist_ok=True)
    temporary = file.with_name(file.name + ".prc-" + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(file)
    finally:
        temporary.unlink(missing_ok=True)


def tree_entry(tree, name):
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


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        with self.path.open("rb") as stream:
            header = stream.read(16)
            if len(header) != 16:
                raise InstallError("应用包不完整。请重新安装 DeepSeek Harness。")
            sizes = struct.unpack("<IIII", header)
            if sizes[0] != 4 or sizes[3] > 64 * 1024 * 1024:
                raise InstallError("不是受支持的 Electron 应用包。")
            self.tree = json.loads(stream.read(sizes[3]))
            self.start = 8 + sizes[1]
            self.size = self.path.stat().st_size - self.start
            if self.size < 0:
                raise InstallError("应用包长度不正确。")

    def read(self, name):
        node = tree_entry(self.tree, name)
        if node.get("unpacked"):
            return (Path(str(self.path) + ".unpacked") / name).read_bytes()
        offset, size = int(node["offset"]), node["size"]
        if offset < 0 or offset + size > self.size:
            raise InstallError("应用包文件索引不正确。")
        with self.path.open("rb") as stream:
            stream.seek(self.start + offset)
            result = stream.read(size)
        if len(result) != size:
            raise InstallError("应用包文件读取不完整。")
        return result

    def has_plugin(self):
        try:
            return NAME.encode() in self.read("lib/main.js")
        except (KeyError, OSError):
            return False


def integrity(data):
    block = 4194304
    return {"algorithm": "SHA256", "hash": hashlib.sha256(data).hexdigest(), "blockSize": block,
            "blocks": [hashlib.sha256(data[i:i + block]).hexdigest() for i in range(0, len(data), block)]}


def check_host(installation: Path):
    installation = installation.resolve()
    if not (installation / EXE).is_file():
        raise InstallError("所选目录中没有 DeepSeek Harness.exe。")
    archive = Archive(installation / "resources/app.asar")
    manifest = json.loads(archive.read("dsh/package.json"))
    version = manifest.get("version")
    if version != HOST_VERSION:
        raise InstallError(f"检测到 Harness {version}；此包已验证的版本为 {HOST_VERSION}。未修改应用，请使用对应版本。")
    # Respect a host that requires signed embedded archive hashes; never alter fuses.
    executable = (installation / EXE).read_bytes()
    offset = executable.find(FUSE_SENTINEL)
    if offset >= 0:
        wire = executable[offset + len(FUSE_SENTINEL):]
        if len(wire) > 6 and wire[0] == 1 and wire[1] > 4 and wire[6] == ord("1"):
            raise InstallError("此 Harness 启用了嵌入式应用包完整性校验，不支持本内置安装方式。未修改应用。")
    return archive


def build_archive(original: Path, output: Path, package_files):
    source = Archive(original)
    tree = copy.deepcopy(source.tree)
    changes = {}
    for name in ("lib/main.js", "dsh/node_modules/@deepseek-ai/dsh-app-boot/lib/index.js"):
        text = source.read(name).decode("utf-8")
        old = 'web: { bundles: ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app"] }'
        new = 'web: { bundles: ["@deepseek-ai/dsh-base", "@deepseek-ai/dsh-web-app", "' + NAME + '"] }'
        if old not in text and new not in text:
            raise InstallError("Harness 默认插件结构已变化，安装已停止。")
        text = text.replace(old, new)
        if name == "lib/main.js":
            old_handler = 'window.webContents.setWindowOpenHandler(({ url }) => {\n\t\tif (["http:", "https:"].includes(new URL(url).protocol)) shell.openExternal(url);'
            new_handler = 'window.webContents.setWindowOpenHandler(({ url }) => {\n\t\tconst paperDestination = new URL(url);\n\t\tif (paperDestination.protocol === "dsh-app:" && paperDestination.hostname === "app" && paperDestination.pathname.startsWith("/paper-research-coach/")) return { action: "allow", overrideBrowserWindowOptions: { title: "论文研读", autoHideMenuBar: true, webPreferences: { nodeIntegration: false, contextIsolation: true, sandbox: true } } };\n\t\tif (["http:", "https:"].includes(new URL(url).protocol)) shell.openExternal(url);'
            if old_handler not in text and new_handler not in text:
                raise InstallError("Harness 窗口接口已变化，安装已停止。")
            text = text.replace(old_handler, new_handler)
        changes[name] = text.encode("utf-8")
    manifest = json.loads(source.read("dsh/package.json"))
    manifest.setdefault("dependencies", {})[NAME] = VERSION
    changes["dsh/package.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    runtime = json.loads(source.read("dsh/desktop-runtime.json"))
    runtime["sharedPackages"] = [p for p in runtime["sharedPackages"] if p["name"] != NAME]
    runtime["sharedPackages"].append({"name": NAME, "version": VERSION, "path": "node_modules/" + NAME})
    changes["dsh/desktop-runtime.json"] = (json.dumps(runtime, ensure_ascii=False, indent=2) + "\n").encode()
    put_entry(tree, PACKAGE_PATH, {"files": {}})
    for relative, size in package_files:
        put_entry(tree, PACKAGE_PATH + "/" + relative, {"size": size, "unpacked": True})
    offset = source.size
    for name, content in changes.items():
        put_entry(tree, name, {"size": len(content), "offset": str(offset), "integrity": integrity(content)})
        offset += len(content)
    encoded = json.dumps(tree, ensure_ascii=False, separators=(",", ":")).encode()
    padded = encoded + b"\0" * (-len(encoded) % 4)
    header = struct.pack("<II", len(padded) + 4, len(encoded)) + padded
    with source.path.open("rb") as stream, output.open("wb") as target:
        target.write(struct.pack("<II", 4, len(header)))
        target.write(header)
        stream.seek(source.start)
        shutil.copyfileobj(stream, target, 8 * 1024 * 1024)
        for content in changes.values():
            target.write(content)
    check = Archive(output)
    if not check.has_plugin() or json.loads(check.read("dsh/package.json"))["dependencies"][NAME] != VERSION:
        raise InstallError("待安装应用包校验失败。")


def link_target(link: Path):
    if not os.path.lexists(link):
        return None
    if not link.is_junction():
        raise InstallError(f"已有同名实体目录或符号链接，未覆盖：{link}")
    return str(link.resolve())


def same_path(left, right):
    if left is None or right is None:
        return left is None and right is None
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(os.path.abspath(right))


def set_junction(link: Path, target, expected):
    current = link_target(link)
    if same_path(current, target):
        return
    if not same_path(current, expected):
        raise InstallError(f"插件链接在安装期间发生变化，未覆盖：{link}")
    if target is not None and not Path(target).is_dir():
        raise InstallError(f"插件目标目录不存在：{target}")
    if current is not None:
        link.rmdir()  # Remove this verified junction only; never recurse into its target.
    if target is not None:
        import _winapi
        link.parent.mkdir(parents=True, exist_ok=True)
        _winapi.CreateJunction(str(Path(target).resolve()), str(link.absolute()))


def protected_transaction(request_file: Path):
    request = read_json(request_file)
    installation = Path(request["installation"]).resolve()
    archive = installation / "resources/app.asar"
    link = Path(str(archive) + ".unpacked") / PACKAGE_PATH
    source = Path(request["source"]).resolve()
    work = request_file.resolve().parent
    if source.parent != work or source.name not in ("before.asar", "pending.asar"):
        raise InstallError("安装事务路径不正确。")
    if digest(archive) != request["expected_hash"] or digest(source) != request["source_hash"]:
        raise InstallError("应用或待安装包在安装期间发生变化，未覆盖。")
    old = link_target(link)
    if not same_path(old, request["expected_link"]):
        raise InstallError("应用的插件链接已变化，未覆盖。")
    temporary = archive.with_name("app.prc-" + uuid.uuid4().hex + ".asar")
    try:
        shutil.copy2(source, temporary)
        if digest(temporary) != request["source_hash"]:
            raise InstallError("应用包复制校验失败。")
        set_junction(link, request["target_link"], old)
        try:
            temporary.replace(archive)
        except BaseException:
            set_junction(link, old, request["target_link"])
            raise
    finally:
        temporary.unlink(missing_ok=True)


def run_elevated(request_file: Path):
    class ShellExecuteInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
    info = ShellExecuteInfo()
    info.cbSize, info.fMask, info.lpVerb, info.nShow = ctypes.sizeof(info), 0x40 | 0x100, "runas", 0
    info.lpFile = str(Path(sys.executable).with_name("pythonw.exe"))
    info.lpParameters = subprocess.list2cmdline(["-X", "utf8", str(Path(__file__).resolve()), "worker", "--request", str(request_file)])
    info.lpDirectory = str(ROOT)
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ShellExecuteInfo)]
    shell.ShellExecuteExW.restype = wintypes.BOOL
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        raise InstallError("管理员授权未完成，安装已停止。")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    try:
        while kernel.WaitForSingleObject(info.hProcess, 200) == 258:
            pass
    finally:
        kernel.CloseHandle(info.hProcess)
    result_file = request_file.with_suffix(".result.json")
    if not result_file.is_file():
        raise InstallError("管理员安装进程未返回结果。请查看安装备份目录。")
    result = read_json(result_file)
    if not result.get("ok"):
        raise InstallError(result.get("error", "管理员安装失败。"))


def apply_transaction(request_file: Path, no_elevate=False):
    try:
        protected_transaction(request_file)
    except PermissionError:
        if no_elevate:
            raise
        print("安装目录需要管理员权限；请在 Windows 提示中允许本次安装。", flush=True)
        run_elevated(request_file)


def verify_release(root=None):
    root = ROOT if root is None else root
    manifest = read_json(root / "RELEASE.json")
    if manifest.get("version") != VERSION or manifest.get("hostVersion") != HOST_VERSION:
        raise InstallError("发布清单与安装器版本不一致。")
    files = manifest["files"]
    for relative, expected in files.items():
        parts = PurePosixPath(relative)
        if parts.is_absolute() or ".." in parts.parts or "\\" in relative or ":" in relative:
            raise InstallError("发布清单包含无效路径。")
        file = root / relative
        if file.is_symlink() or not file.is_file() or file.stat().st_size != expected["size"] or digest(file) != expected["sha256"]:
            raise InstallError(f"安装包文件缺失或校验失败：{relative}。请重新完整解压。")
    essential = ["package/runtime/python/python.exe", "package/host/index.js", "package/host/studio-renderer.mjs", "package/client/client.js",
                 "package/runtime/python/Lib/site-packages/PyPDF2/__init__.py",
                 "package/integrations/answer-me-with-html/prc-renderer.mjs", "package/integrations/learn-from-materials/scripts/prc_render_page.py",
                 "package/integrations/learn-from-materials/scripts/extractor/prc_utils.py", "package/upstream/src/paper_research_coach/material_extract.py",
                 "package/upstream/src/paper_research_coach/static/index.html", "installer/install.py"]
    if any(name not in files for name in essential):
        raise InstallError("安装包缺少必需组件。")
    return manifest


def process_paths():
    command = "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Path -Unique | ConvertTo-Json -Compress"
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", command],
                            capture_output=True, text=True, encoding="utf-8", errors="replace", creationflags=0x08000000)
    if not result.stdout.strip():
        return []
    try:
        value = json.loads(result.stdout.lstrip("\ufeff"))
        return [value] if isinstance(value, str) else value or []
    except ValueError:
        return []


def require_stopped(installation, interactive):
    while any(same_path(path, installation / EXE) for path in process_paths()):
        if not interactive:
            raise InstallError("请先退出 DeepSeek Harness（包括托盘后台进程），再安装或卸载。")
        input("请先退出 DeepSeek Harness（包括托盘），然后按 Enter 继续；关闭本窗口可取消。")


def discover():
    candidates = [Path(p).parent for p in process_paths()]
    found = shutil.which(EXE)
    if found:
        candidates.append(Path(found).parent)
    import winreg
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY, winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths" + "\\" + EXE, 0, winreg.KEY_READ | view) as key:
                    candidates.append(Path(winreg.QueryValue(key, None).strip('"')).parent)
            except OSError:
                pass
            try:
                with winreg.OpenKey(hive, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0, winreg.KEY_READ | view) as key:
                    for index in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            with winreg.OpenKey(key, winreg.EnumKey(key, index)) as item:
                                title = str(winreg.QueryValueEx(item, "DisplayName")[0]).lower()
                                if "deepseek" not in title or "harness" not in title:
                                    continue
                                try:
                                    candidates.append(Path(winreg.QueryValueEx(item, "InstallLocation")[0]))
                                except OSError:
                                    pass
                                try:
                                    icon = str(winreg.QueryValueEx(item, "DisplayIcon")[0]).split(",")[0].strip('"')
                                    candidates.append(Path(icon).parent)
                                except OSError:
                                    pass
                        except OSError:
                            continue
            except OSError:
                pass
    for variable in ("LOCALAPPDATA", "ProgramFiles", "ProgramFiles(x86)"):
        if os.environ.get(variable):
            base = Path(os.environ[variable])
            candidates.extend(base / suffix for suffix in ("DeepSeek Harness", "Programs/DeepSeek Harness", "deepseek-harness", "DSH"))
    unique = []
    for candidate in candidates:
        if (candidate / EXE).is_file() and (candidate / "resources/app.asar").is_file() and not any(same_path(candidate, p) for p in unique):
            unique.append(candidate.resolve())
    return unique


def browse_executable():
    class OpenFileName(ctypes.Structure):
        _fields_ = [("lStructSize", wintypes.DWORD), ("hwndOwner", wintypes.HWND), ("hInstance", wintypes.HINSTANCE),
                    ("lpstrFilter", wintypes.LPCWSTR), ("lpstrCustomFilter", wintypes.LPWSTR), ("nMaxCustFilter", wintypes.DWORD),
                    ("nFilterIndex", wintypes.DWORD), ("lpstrFile", wintypes.LPWSTR), ("nMaxFile", wintypes.DWORD),
                    ("lpstrFileTitle", wintypes.LPWSTR), ("nMaxFileTitle", wintypes.DWORD), ("lpstrInitialDir", wintypes.LPCWSTR),
                    ("lpstrTitle", wintypes.LPCWSTR), ("Flags", wintypes.DWORD), ("nFileOffset", wintypes.WORD),
                    ("nFileExtension", wintypes.WORD), ("lpstrDefExt", wintypes.LPCWSTR), ("lCustData", ctypes.c_ssize_t),
                    ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", wintypes.LPCWSTR), ("pvReserved", ctypes.c_void_p),
                    ("dwReserved", wintypes.DWORD), ("FlagsEx", wintypes.DWORD)]
    buffer = ctypes.create_unicode_buffer(32768)
    dialog = OpenFileName()
    dialog.lStructSize, dialog.lpstrFile, dialog.nMaxFile = ctypes.sizeof(dialog), ctypes.cast(buffer, wintypes.LPWSTR), len(buffer)
    dialog.lpstrFilter = "DeepSeek Harness\0DeepSeek Harness.exe\0\0"
    dialog.lpstrTitle = "选择已安装的 DeepSeek Harness.exe"
    dialog.Flags = 0x1000 | 0x800 | 0x8 | 0x80000
    comdlg = ctypes.WinDLL("comdlg32", use_last_error=True)
    comdlg.GetOpenFileNameW.argtypes = [ctypes.POINTER(OpenFileName)]
    comdlg.GetOpenFileNameW.restype = wintypes.BOOL
    if not comdlg.GetOpenFileNameW(ctypes.byref(dialog)):
        raise InstallError("未选择 Harness，操作已取消。")
    return Path(buffer.value).parent


def choose_installation(args, state_base):
    if args.installation:
        return args.installation.resolve()
    candidates = []
    if args.action == "uninstall":
        for active in state_base.glob("*/active.json"):
            record = read_json(active)
            if not record.get("uninstalled"):
                candidates.append(Path(record["installation"]))
    if not candidates:
        candidates = discover()
    if len(candidates) == 1:
        return candidates[0]
    if args.yes:
        raise InstallError("无法唯一确定 Harness 路径，请指定 --installation。")
    if candidates:
        print("发现多个 Harness 安装：")
        for index, path in enumerate(candidates, 1):
            print(f"  {index}. {path}")
        value = input("输入序号；直接按 Enter 可浏览选择：").strip()
        if value.isdigit() and 1 <= int(value) <= len(candidates):
            return candidates[int(value) - 1]
    print("请在文件选择窗口中选择已安装的 DeepSeek Harness.exe。", flush=True)
    return browse_executable().resolve()


def profile_values(manifest):
    deps = manifest.get("dependencies", {})
    bundles = manifest.get("dsh", {}).get("profile", {}).get("bundles", [])
    return {"dependency_existed": NAME in deps, "dependency": deps.get(NAME),
            "bundle_positions": [index for index, value in enumerate(bundles) if value == NAME]}


def enable_manifest(manifest, payload):
    result = copy.deepcopy(manifest)
    result.setdefault("dependencies", {})[NAME] = "link:" + payload.as_posix()
    bundles = result.setdefault("dsh", {}).setdefault("profile", {}).setdefault("bundles", [])
    if NAME not in bundles:
        bundles.append(NAME)
    return result


def restore_manifest(manifest, before):
    result = copy.deepcopy(manifest)
    dependencies = result.setdefault("dependencies", {})
    if before["dependency_existed"]:
        dependencies[NAME] = before["dependency"]
    else:
        dependencies.pop(NAME, None)
    bundles = result.setdefault("dsh", {}).setdefault("profile", {}).setdefault("bundles", [])
    bundles[:] = [value for value in bundles if value != NAME]
    for index in before["bundle_positions"]:
        bundles.insert(min(index, len(bundles)), NAME)
    return result


def install(args, installation, profile, state_dir):
    print("校验安装包（包含内置运行库和翻译资源）…", flush=True)
    release = verify_release()
    archive = check_host(installation)
    require_stopped(installation, not args.yes)
    profile_file = profile / "package.json"
    if not profile_file.is_file():
        raise InstallError("未找到 Harness desktop profile。请先启动 Harness、完成登录并退出，再运行安装。自定义配置可用 --profile 指定。")
    current_hash = digest(archive.path)
    release_hash = digest(ROOT / "RELEASE.json")
    active_file = state_dir / "active.json"
    if active_file.exists():
        active = read_json(active_file)
        if not active.get("uninstalled") and not same_path(active["profile"], profile):
            raise InstallError("此 Harness 的安装记录属于另一份 profile。请先卸载该记录，或使用原 profile。")
        if not active.get("uninstalled") and active["release_hash"] == release_hash and active["installed_hash"] == current_hash:
            expected = active["payload"]
            if same_path(link_target(profile / "node_modules" / NAME), expected) and same_path(link_target(Path(str(archive.path) + ".unpacked") / PACKAGE_PATH), expected) and NAME in read_json(profile_file).get("dsh", {}).get("profile", {}).get("bundles", []):
                if all((Path(expected) / name.removeprefix("package/")).is_file() and digest(Path(expected) / name.removeprefix("package/")) == info["sha256"] for name, info in release["files"].items() if name.startswith("package/")):
                    print("此版本已完整安装，无需重复安装。")
                    return active
            raise InstallError("已安装记录存在但文件或链接有变化。请先运行本包的卸载脚本，再重新安装。")
        if not active.get("uninstalled"):
            raise InstallError("发现本安装器的另一份安装记录。请先用本包的卸载脚本卸载，再安装。论文数据会保留。")
    manifest = read_json(profile_file)
    profile_link = profile / "node_modules" / NAME
    core_link = Path(str(archive.path) + ".unpacked") / PACKAGE_PATH
    before_profile_link, before_core_link = link_target(profile_link), link_target(core_link)
    work = state_dir / (datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8])
    payload = args.home / "builtin-plugins" / ("paper-research-coach-" + VERSION + "-" + release_hash[:12])
    if payload.exists() and not payload.is_dir():
        raise InstallError("插件运行库目标已被同名文件占用。")
    payload_items = [(key.removeprefix("package/"), info) for key, info in release["files"].items() if key.startswith("package/")]
    if any(len(str(payload / relative)) >= 260 for relative, _ in payload_items):
        raise InstallError("Harness 用户目录过长，部分运行库文件会超出 Windows 路径限制。请为 Harness 配置较短的 DSH_HOME 后重试。")
    required = sum(info["size"] for _, info in payload_items) + archive.path.stat().st_size * 3
    if shutil.disk_usage(args.home).free < required + 100 * 1024 * 1024:
        raise InstallError("用户数据盘空间不足，请至少空出 4 GB。")
    if shutil.disk_usage(installation).free < archive.path.stat().st_size * 2 + 100 * 1024 * 1024:
        raise InstallError("Harness 安装盘空间不足，请至少空出 1 GB。")
    work.mkdir(parents=True, exist_ok=False)
    print("复制独立运行库并备份原应用…", flush=True)
    for relative, info in payload_items:
        target = payload / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and digest(target) == info["sha256"]:
            continue
        shutil.copyfile(ROOT / "package" / relative, target)
        if digest(target) != info["sha256"]:
            raise InstallError(f"运行库复制校验失败：{relative}")
    shutil.copy2(archive.path, work / "before.asar")
    if digest(work / "before.asar") != current_hash:
        raise InstallError("应用备份校验失败。")
    shutil.copy2(profile_file, work / "before-package.json")
    print("为当前 Harness 构建内置应用包…", flush=True)
    build_archive(archive.path, work / "pending.asar", [(name, info["size"]) for name, info in payload_items])
    installed_hash = digest(work / "pending.asar")
    request = {"installation": str(installation), "source": str(work / "pending.asar"),
               "expected_hash": current_hash, "source_hash": installed_hash,
               "expected_link": before_core_link, "target_link": str(payload)}
    request_file = work / "apply.json"
    write_json(request_file, request)
    record = {"version": VERSION, "host_version": HOST_VERSION, "release_hash": release_hash,
              "installation": str(installation), "profile": str(profile), "payload": str(payload),
              "original_hash": current_hash, "installed_hash": installed_hash, "backup": str(work),
              "before_profile": profile_values(manifest), "before_profile_link": before_profile_link,
              "before_core_link": before_core_link, "installed_at": datetime.now(timezone.utc).isoformat()}
    write_json(work / "receipt.json", record)
    apply_transaction(request_file, args.no_elevate)
    try:
        set_junction(profile_link, str(payload), before_profile_link)
        write_json(profile_file, enable_manifest(manifest, payload))
        write_json(active_file, record)
    except BaseException:
        set_junction(profile_link, before_profile_link, str(payload))
        write_json(profile_file, manifest)
        rollback = request | {"source": str(work / "before.asar"), "expected_hash": installed_hash,
                              "source_hash": current_hash, "expected_link": str(payload), "target_link": before_core_link}
        rollback_file = work / "rollback.json"
        write_json(rollback_file, rollback)
        apply_transaction(rollback_file, args.no_elevate)
        raise
    print(f"安装完成。重新打开 Harness，点击左侧【论文研读】。\n备份与卸载记录：{work}\n论文数据保存在：{args.home / 'paper-research-coach'}")
    return record


def uninstall(args, installation, state_dir):
    active_file = state_dir / "active.json"
    if not active_file.is_file():
        raise InstallError("此安装目录没有本安装器的安装记录；未修改应用。")
    record = read_json(active_file)
    if record.get("uninstalled"):
        print("此插件已经卸载；论文和备份仍保留。")
        return record
    require_stopped(installation, not args.yes)
    archive = installation / "resources/app.asar"
    current_hash = digest(archive)
    work = Path(record["backup"])
    profile = Path(record["profile"])
    profile_file = profile / "package.json"
    manifest = read_json(profile_file)
    expected_dep = "link:" + Path(record["payload"]).as_posix()
    if manifest.get("dependencies", {}).get(NAME) != expected_dep:
        raise InstallError("插件配置已被其他安装方式修改，未覆盖。请在 Harness 的插件管理中移除对应插件。")
    profile_link = profile / "node_modules" / NAME
    if not same_path(link_target(profile_link), record["payload"]):
        raise InstallError("用户插件链接已变化，未修改。")
    request = None
    if current_hash == record["installed_hash"]:
        if digest(work / "before.asar") != record["original_hash"]:
            raise InstallError("原应用备份校验失败，未修改。")
        request = {"installation": str(installation), "source": str(work / "before.asar"),
                   "expected_hash": current_hash, "source_hash": record["original_hash"],
                   "expected_link": record["payload"], "target_link": record["before_core_link"]}
    elif Archive(archive).has_plugin():
        raise InstallError("应用包在安装后被其他工具修改。为保留这些修改，未用旧备份覆盖；请先恢复对应原包或通过 Harness 插件管理停用。")
    else:
        print("检测到 Harness 已更新，保留当前应用版本；移除本插件的用户配置。")
    if request:
        request_file = work / "uninstall.json"
        write_json(request_file, request)
        apply_transaction(request_file, args.no_elevate)
    try:
        set_junction(profile_link, record["before_profile_link"], record["payload"])
        write_json(profile_file, restore_manifest(manifest, record["before_profile"]))
    except BaseException:
        set_junction(profile_link, record["payload"], record["before_profile_link"])
        write_json(profile_file, manifest)
        if request:
            rollback = request | {"source": str(work / "pending.asar"), "expected_hash": record["original_hash"],
                                  "source_hash": record["installed_hash"], "expected_link": record["before_core_link"],
                                  "target_link": record["payload"]}
            rollback_file = work / "undo-uninstall.json"
            write_json(rollback_file, rollback)
            apply_transaction(rollback_file, args.no_elevate)
        raise
    record["uninstalled"] = datetime.now(timezone.utc).isoformat()
    write_json(active_file, record)
    print("卸载完成。论文、笔记、账户配置、运行库和原应用备份均保留；现在可重新启动 Harness。")
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description="Paper Research Coach · DeepSeek Harness 内置版安装器")
    parser.add_argument("action", choices=["install", "uninstall", "check", "worker"])
    parser.add_argument("--installation", type=Path, help="Harness 安装目录（含 DeepSeek Harness.exe）")
    parser.add_argument("--home", type=Path, default=Path(os.environ.get("DSH_HOME", Path.home() / ".dsh")))
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--yes", action="store_true", help="使用明确指定路径，无交互提示")
    parser.add_argument("--no-elevate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--request", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if sys.platform != "win32" or platform.machine().upper() not in ("AMD64", "X86_64"):
        raise InstallError("此安装包仅适用于 Windows x64。")
    if args.action == "worker":
        if args.request is None:
            raise InstallError("缺少安装事务。")
        try:
            protected_transaction(args.request)
            result = {"ok": True}
        except Exception as error:
            result = {"ok": False, "error": str(error)}
        write_json(args.request.with_suffix(".result.json"), result)
        return 0 if result["ok"] else 1
    print(f"Paper Research Coach {VERSION} · DeepSeek Harness 内置版\n兼容：Windows x64 / Harness {HOST_VERSION}\n")
    if args.action == "check":
        release = verify_release()
        print(f"安装包校验通过：{len(release['files'])} 个文件。无须联网下载依赖。")
        return 0
    args.home = args.home.resolve()
    if not args.home.is_dir():
        raise InstallError("未找到 Harness 用户目录。请先启动 Harness 并登录。")
    state_base = args.home / "plugin-installations/paper-research-coach"
    installation = choose_installation(args, state_base)
    profile = (args.profile or args.home / "profiles/desktop").resolve()
    identity = hashlib.sha256(os.path.normcase(str(installation.resolve())).encode()).hexdigest()[:16]
    state_dir = state_base / identity
    print(f"Harness 目录：{installation}\n用户配置：{profile}")
    if not args.yes:
        input("请退出 Harness（含托盘），按 Enter 开始；关闭此窗口可取消。")
    if args.action == "install":
        install(args, installation, profile, state_dir)
    else:
        uninstall(args, installation, state_dir)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (InstallError, OSError, ValueError, KeyError) as error:
        print(f"\n操作未完成：{error}\n如已建立备份，可在 Harness 用户目录的 plugin-installations/paper-research-coach 中找到。", file=sys.stderr)
        sys.exit(1)
    except (KeyboardInterrupt, EOFError):
        print("\n操作已取消。", file=sys.stderr)
        sys.exit(130)
