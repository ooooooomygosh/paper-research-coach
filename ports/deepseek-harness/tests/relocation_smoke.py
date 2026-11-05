"""Verify the packaged interpreter and backend outside the development tree."""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import queue
import secrets
import subprocess
import sys
import threading
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--release", type=Path, required=True)
    parser.add_argument("--work", type=Path, required=True)
    args = parser.parse_args()
    package = args.release.resolve() / "package"
    args.work.mkdir(parents=True, exist_ok=True)
    interpreter = package / "runtime/python/python.exe"
    environment = os.environ | {"PYTHONHOME": "C:\\invalid-external-python", "PYTHONPATH": "C:\\invalid-external-site"}
    probe = """
import importlib.metadata,json,os,sys
from pathlib import Path
import numpy,scipy,onnxruntime,pymupdf,pypdfium2,fastapi,uvicorn
import paper_research_coach
from babeldoc import const
const.CACHE_FOLDER=Path(sys.argv[1])
const.TIKTOKEN_CACHE_FOLDER=const.CACHE_FOLDER/'tiktoken'
from babeldoc.format.pdf import high_level
from babeldoc.translator.translator import BaseTranslator
import ctypes
from ctypes import wintypes
k=ctypes.WinDLL('kernel32',use_last_error=True)
k.GetModuleHandleW.argtypes=[wintypes.LPCWSTR];k.GetModuleHandleW.restype=wintypes.HMODULE
k.GetModuleFileNameW.argtypes=[wintypes.HMODULE,wintypes.LPWSTR,wintypes.DWORD]
for library in ['msvcp140.dll','msvcp140_1.dll','vcruntime140.dll','vcruntime140_1.dll']:
    module=k.GetModuleHandleW(library); assert module,library
    buffer=ctypes.create_unicode_buffer(32768);k.GetModuleFileNameW(module,buffer,len(buffer))
    assert Path(buffer.value).parent==Path(sys.executable).parent,(library,buffer.value)
assert sys.flags.isolated
assert not sys.flags.ignore_environment == 0
assert 'upstream' in paper_research_coach.__file__
print(json.dumps({'test':'portable-runtime','isolated':bool(sys.flags.isolated),'appLocalCppRuntime':True,'python':sys.version.split()[0],'babeldoc':importlib.metadata.version('BabelDOC'),'pdf':pymupdf.VersionBind,'onnxProviders':onnxruntime.get_available_providers()}))
"""
    subprocess.run([str(interpreter), "-X", "utf8", "-c", probe, str(package / "runtime/assets")], env=environment, check=True)
    token = secrets.token_urlsafe(32)
    environment |= {"PRC_EMBEDDED": "1", "PRC_DATA": str(args.work / "empty-library"), "PRC_SESSION_TOKEN": token,
                    "DSH_HOME": str(args.work), "DSH_PRC_ASSETS": str(package / "runtime/assets"),
                    "DSH_PRC_BRIDGE_URL": "http://127.0.0.1:1", "DSH_PRC_BRIDGE_TOKEN": secrets.token_urlsafe(32),
                    "PRC_NO_UPDATE_CHECK": "1", "PRC_NO_AUTO_UPDATE": "1", "PYTHONUNBUFFERED": "1"}
    log = args.work / "backend-stderr.log"
    with log.open("wb") as errors:
        process = subprocess.Popen([str(interpreter), "-X", "utf8", "-m", "paper_research_coach.embedded"],
                                   cwd=package, env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors)
        lines = queue.Queue()
        def receive():
            for line in process.stdout:
                try:
                    data = json.loads(line)
                    if data.get("event") == "ready":
                        lines.put(data)
                except (UnicodeDecodeError, ValueError):
                    pass
        threading.Thread(target=receive, daemon=True).start()
        try:
            ready = lines.get(timeout=45)
            base = f"http://127.0.0.1:{ready['port']}"
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def request(path, authenticated=True):
                headers = {"Authorization": "Bearer " + token} if authenticated else {}
                with opener.open(urllib.request.Request(base + path, headers=headers), timeout=15) as response:
                    return response.status, response.read()
            status, body = request("/")
            assert status == 200 and b"/paper-research-coach/assets/" in body
            status, state = request("/api/state")
            data = json.loads(state)
            assert status == 200 and data["papers"] == []
            try:
                request("/api/state", authenticated=False)
            except urllib.error.HTTPError as error:
                assert error.code == 401
            else:
                raise AssertionError("Backend accepted missing session token")
            print(json.dumps({"test": "relocated-embedded-backend", "page": True, "emptyLibrary": True, "unauthenticatedDenied": True}))
        finally:
            process.stdin.close()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        assert process.returncode == 0, log.read_text(encoding="utf-8", errors="replace")[-2000:]


if __name__ == "__main__":
    main()
