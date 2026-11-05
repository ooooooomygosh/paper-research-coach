"""Optional macOS login service for the local workbench and folder polling."""

from __future__ import annotations

import os
import plistlib
import subprocess
import sys
from pathlib import Path

LABEL = "io.paper-research-coach.workbench"


def manage(action, store, port=8765):
    if sys.platform != "darwin":
        raise ValueError(
            "Login service is available on macOS; run prc serve on this platform"
        )
    plist = Path.home() / "Library/LaunchAgents" / f"{LABEL}.plist"
    domain = f"gui/{os.getuid()}"
    if action == "install":
        if not 1024 <= port <= 65535:
            raise ValueError("Choose a port between 1024 and 65535")
        plist.parent.mkdir(parents=True, exist_ok=True)
        if plist.exists():
            subprocess.run(
                ["launchctl", "bootout", domain, str(plist)], capture_output=True
            )
        settings = {
            "Label": LABEL,
            "ProgramArguments": [
                sys.executable,
                "-m",
                "paper_research_coach.cli",
                "--data-dir",
                str(store.root),
                "serve",
                "--no-open",
                "--port",
                str(port),
            ],
            "RunAtLoad": True,
            "KeepAlive": True,
            "ThrottleInterval": 10,
            "StandardOutPath": "/dev/null",
            "StandardErrorPath": "/dev/null",
            "ProcessType": "Background",
        }
        with plist.open("wb") as f:
            plistlib.dump(settings, f)
        plist.chmod(0o600)
        result = subprocess.run(
            ["launchctl", "bootstrap", domain, str(plist)],
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise ValueError(
                "Background service could not start; close any service using this port and retry"
            )
        return {
            "installed": True,
            "url": f"http://127.0.0.1:{port}/",
            "startup": "on login",
            "data_dir": str(store.root),
        }
    if action == "stop":
        result = subprocess.run(
            ["launchctl", "bootout", domain, str(plist)], capture_output=True
        )
        return {"stopped": result.returncode == 0, "config_preserved": plist.exists()}
    result = subprocess.run(
        ["launchctl", "print", f"{domain}/{LABEL}"], capture_output=True, text=True
    )
    return {
        "installed": plist.exists(),
        "running": result.returncode == 0 and "state = running" in result.stdout,
    }
