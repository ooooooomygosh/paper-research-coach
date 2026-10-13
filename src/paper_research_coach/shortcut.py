"""A double-click launcher, so opening the workbench never needs a terminal."""

from __future__ import annotations

import shlex
import stat
import sys
from pathlib import Path

NAME = "Paper Research Coach"


def _python_for_windows() -> str:
    # pythonw has no console window; fall back to python when it is missing.
    exe = Path(sys.executable)
    windowless = exe.with_name("pythonw.exe")
    return str(windowless if windowless.is_file() else exe)


def create(home: Path | None = None, platform: str | None = None) -> list[str]:
    """Create the launcher for this system and return the files written."""
    home = home or Path.home()
    platform = platform or sys.platform
    desktop = home / "Desktop"
    desktop = desktop if desktop.is_dir() else home
    run = [sys.executable, "-m", "paper_research_coach.cli", "open"]
    written: list[Path] = []
    if platform == "darwin":
        target = desktop / f"{NAME}.command"
        target.write_text("#!/bin/sh\nexec " + " ".join(shlex.quote(a) for a in run) + "\n", encoding="utf-8")
        target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        written.append(target)
    elif platform == "win32":
        target = desktop / f"{NAME}.cmd"
        target.write_text(f'@echo off\r\nstart "" "{_python_for_windows()}" -m paper_research_coach.cli open\r\n', encoding="utf-8")
        written.append(target)
    else:
        entry = (
            "[Desktop Entry]\nType=Application\n"
            f"Name={NAME}\nComment=Read papers with evidence and your own judgment\n"
            "Exec=" + " ".join(shlex.quote(a) for a in run) + "\n"
            "Terminal=false\nCategories=Education;Office;\n"
        )
        menu = home / ".local/share/applications"
        menu.mkdir(parents=True, exist_ok=True)
        target = menu / "paper-research-coach.desktop"
        target.write_text(entry, encoding="utf-8")
        target.chmod(0o755)
        written.append(target)
        if (home / "Desktop").is_dir():
            copy = home / "Desktop" / "paper-research-coach.desktop"
            copy.write_text(entry, encoding="utf-8")
            copy.chmod(0o755)
            written.append(copy)
    return [str(p) for p in written]
