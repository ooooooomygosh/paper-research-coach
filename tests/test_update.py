import hashlib
import json
import stat
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from paper_research_coach import __version__, relaunch, shortcut, updater
from paper_research_coach.cli import main
from paper_research_coach.server import create_app

WHEEL = "paper_research_coach-9.9.9-py3-none-any.whl"


def release(tag, *, draft=False, assets=None, url="https://example.test/r"):
    return {"tag_name": tag, "draft": draft, "html_url": url,
            "assets": [{"name": n, "browser_download_url": f"https://example.test/{tag}/{n}"} for n in (assets or [])]}


def test_versions_normalise_and_compare_like_the_wheel_says():
    assert updater.normalize("v2.0.0-rc.11") == "2.0.0rc11"
    assert updater.normalize("v2.1.0") == "2.1.0"
    with pytest.raises(updater.UpdateError):
        updater.normalize("nightly")
    assert updater.is_newer("2.0.0rc11", "2.0.0rc10") and updater.is_newer("2.0.0", "2.0.0rc99")
    assert not updater.is_newer("2.0.0rc10", "2.0.0rc10") and not updater.is_newer("garbage", "1.0.0")


def test_find_latest_picks_the_newest_installable_release_including_prereleases():
    data = [
        release("v2.0.0-rc.13", draft=True, assets=["paper_research_coach-2.0.0rc13-py3-none-any.whl"]),
        release("v2.0.0-rc.12", assets=["notes.txt"]),
        release("v2.0.0-rc.11", assets=["paper_research_coach-2.0.0rc11-py3-none-any.whl", "SHA256SUMS"]),
        release("v2.0.0-rc.10", assets=["paper_research_coach-2.0.0rc10-py3-none-any.whl"]),
    ]
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=data)))
    latest = updater.find_latest(client)
    assert latest["version"] == "2.0.0rc11" and latest["sums_url"].endswith("SHA256SUMS")
    assert latest["wheel_name"] == "paper_research_coach-2.0.0rc11-py3-none-any.whl"


def test_check_is_cached_for_a_day_quiet_on_failure_and_can_be_turned_off(store, monkeypatch):
    calls = []
    newer = {"version": "99.0.0", "tag": "v99.0.0", "notes_url": "https://example.test/notes"}

    def fetch():
        calls.append(1)
        return newer

    clock = [1000.0]
    state = updater.check(store, fetch=fetch, clock=lambda: clock[0])
    assert state == {"current": __version__, "available": True, "latest": "99.0.0", "notes_url": "https://example.test/notes"}
    updater.check(store, fetch=fetch, clock=lambda: clock[0] + 3600)
    assert len(calls) == 1  # still cached
    updater.check(store, fetch=fetch, clock=lambda: clock[0] + 25 * 3600)
    assert len(calls) == 2
    assert updater.check(store, force=True, fetch=fetch, clock=lambda: clock[0])["available"] and len(calls) == 3

    def broken():
        raise httpx.ConnectError("offline")

    quiet = updater.check(store, force=True, fetch=broken, clock=lambda: clock[0])
    assert quiet["available"]  # keeps the last known answer instead of raising
    monkeypatch.setenv("PRC_NO_UPDATE_CHECK", "1")
    assert updater.check(store, force=True, fetch=fetch) == {"current": __version__, "available": False, "disabled": True}


def fake_release(tmp_path, content=b"wheel bytes", sums=True, record=True):
    wheel = tmp_path / "remote" / WHEEL
    wheel.parent.mkdir()
    wheel.write_bytes(content)
    sums_file = tmp_path / "remote" / "SHA256SUMS"
    digest = hashlib.sha256(b"wheel bytes").hexdigest()
    sums_file.write_text(f"{digest}  {WHEEL}\n" if record else f"{digest}  other.whl\n")
    return {"tag": "v9.9.9", "version": "9.9.9", "notes_url": "n", "wheel_name": WHEEL,
            "wheel_url": wheel.as_uri(), "sums_url": sums_file.as_uri() if sums else ""}


def test_download_installs_only_what_the_release_checksums_say(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "RELEASES_URL", "file:///offline-test.json")
    out = tmp_path / "out"
    out.mkdir()
    tampered = tmp_path / "tampered"
    tampered.mkdir()
    path = updater.download(fake_release(tmp_path), out)
    assert path.read_bytes() == b"wheel bytes"
    with pytest.raises(updater.UpdateError, match="校验值不符"):
        updater.download(fake_release(tampered, content=b"tampered"), out)


@pytest.mark.parametrize("kwargs,message", [({"sums": False}, "SHA256SUMS"), ({"record": False}, "找不到这个安装包")])
def test_download_refuses_without_a_matching_checksum(tmp_path, monkeypatch, kwargs, message):
    monkeypatch.setattr(updater, "RELEASES_URL", "file:///offline-test.json")
    with pytest.raises(updater.UpdateError, match=message):
        updater.download(fake_release(tmp_path, **kwargs), tmp_path)


def test_a_release_page_cannot_make_the_updater_read_local_files(tmp_path):
    # Outside offline test mode, file:// is not a download source: the request goes to httpx and fails.
    release_ = fake_release(tmp_path)
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    with pytest.raises(updater.UpdateError, match="下载失败"):
        updater.download(release_, tmp_path, client)


def test_apply_downloads_installs_then_refreshes_skills_in_that_order(store, monkeypatch, tmp_path):
    order = []
    monkeypatch.setattr(updater, "download", lambda r, d, client=None: order.append("download") or d / "w.whl")
    monkeypatch.setattr(updater, "install", lambda w: order.append("install"))
    monkeypatch.setattr(updater, "refresh_skills", lambda d: order.append("skills") or ["claude"])
    release_ = {"version": "99.0.0", "notes_url": "u", "tag": "v99.0.0"}
    result = updater.apply(store, release_)
    assert order == ["download", "install", "skills"]
    assert result == {"updated": True, "from": __version__, "to": "99.0.0", "skills": ["claude"], "notes_url": "u"}
    assert updater.apply(store, {"version": __version__, "notes_url": ""}) == {"updated": False, "current": __version__}


def test_installer_uses_pip_when_present_and_uv_for_uv_made_environments(monkeypatch, tmp_path):
    wheel = tmp_path / WHEEL
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0))
    assert updater.installer_command(wheel)[1:4] == ["-m", "pip", "install"]
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 1))
    monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/uv")
    assert updater.installer_command(wheel)[:3] == ["/usr/bin/uv", "pip", "install"]
    monkeypatch.setattr("shutil.which", lambda name: None)
    with pytest.raises(updater.UpdateError, match="pip 或 uv"):
        updater.installer_command(wheel)


def test_refresh_skills_only_touches_copies_that_prc_made(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    (tmp_path / ".claude/skills/paper-research-coach").mkdir(parents=True)
    (tmp_path / ".claude/skills/paper-research-coach/SKILL.md").write_text("x")
    (tmp_path / ".agents/skills").mkdir(parents=True)  # a host without our skill
    seen = []
    monkeypatch.setattr(subprocess, "run", lambda cmd, **k: seen.append(cmd) or subprocess.CompletedProcess(cmd, 0))
    assert updater.refresh_skills("/data") == ["claude"]
    assert seen[0][-4:] == ["install-skill", "--host", "claude", "--force"]
    assert seen[0][0] == sys.executable


def test_server_reports_updates_and_runs_one_update_job(store, monkeypatch):
    app = create_app(store, "token")
    client = TestClient(app, base_url="http://127.0.0.1")
    headers = {"Authorization": "Bearer token", "Origin": "http://127.0.0.1"}
    monkeypatch.setattr(updater, "check", lambda s, **k: {"current": __version__, "available": True, "latest": "99.0.0", "notes_url": "n"})
    assert client.get("/api/update", headers=headers).json()["latest"] == "99.0.0"
    monkeypatch.setattr(updater, "apply", lambda s: {"updated": True, "from": __version__, "to": "99.0.0", "skills": []})
    started = client.post("/api/update/apply", headers=headers)
    assert started.status_code == 200
    deadline = time.time() + 5
    while time.time() < deadline and client.get("/api/update", headers=headers).json()["job"]["state"] == "running":
        time.sleep(0.05)
    job = client.get("/api/update", headers=headers).json()["job"]
    assert job == {"state": "done", "message": "已更新。请重新运行 prc open。"}  # a test app has no server to restart
    assert client.post("/api/system/restart", headers=headers).json() == {"restarting": False}
    # Nothing is installed when no newer version exists.
    monkeypatch.setattr(updater, "check", lambda s, **k: {"current": __version__, "available": False})
    app.state.update_job.update(state="idle")
    assert client.post("/api/update/apply", headers=headers).status_code == 400


def test_a_failed_update_is_reported_in_plain_words_not_a_traceback(store, monkeypatch):
    app = create_app(store, "token")
    client = TestClient(app, base_url="http://127.0.0.1")
    headers = {"Authorization": "Bearer token", "Origin": "http://127.0.0.1"}
    monkeypatch.setattr(updater, "check", lambda s, **k: {"current": __version__, "available": True, "latest": "99.0.0"})

    def boom(s):
        raise updater.UpdateError("安装包的校验值不符，已停止更新。")

    monkeypatch.setattr(updater, "apply", boom)
    client.post("/api/update/apply", headers=headers)
    deadline = time.time() + 5
    while time.time() < deadline and app.state.update_job["state"] == "running":
        time.sleep(0.05)
    assert app.state.update_job == {"state": "error", "message": "安装包的校验值不符，已停止更新。"}


def test_a_restartable_server_spawns_its_replacement_then_stops(store, monkeypatch):
    spawned = []
    monkeypatch.setattr("paper_research_coach.launcher.spawn_relaunch", lambda s, port, pid: spawned.append((port, pid)))
    app = create_app(store, "token")

    class Server:
        should_exit = False

    app.state.server, app.state.port = Server(), 8791
    client = TestClient(app, base_url="http://127.0.0.1")
    r = client.post("/api/system/restart", headers={"Authorization": "Bearer token", "Origin": "http://127.0.0.1"})
    assert r.json() == {"restarting": True}
    deadline = time.time() + 3
    while time.time() < deadline and not app.state.server.should_exit:
        time.sleep(0.05)
    assert app.state.server.should_exit and spawned and spawned[0][0] == 8791


def test_relaunch_waits_for_the_old_process_then_replaces_itself_with_a_server(monkeypatch):
    alive = iter([None, None, OSError()])

    def kill(pid, sig):
        result = next(alive)
        if result:
            raise result

    execs = []
    monkeypatch.setattr("os.kill", kill)
    monkeypatch.setattr("os.execv", lambda exe, argv: execs.append(argv))
    monkeypatch.setattr("time.sleep", lambda s: None)
    relaunch.main(["--data-dir", "/d", "--port", "8791", "--wait-pid", "4242"])
    assert execs[0] == [sys.executable, "-m", "paper_research_coach.cli", "--data-dir", "/d", "serve", "--no-open", "--port", "8791"]


@pytest.mark.parametrize("platform,name", [("darwin", "Paper Research Coach.command"), ("win32", "Paper Research Coach.cmd"), ("linux", "paper-research-coach.desktop")])
def test_shortcut_creates_a_launcher_for_each_system(tmp_path, platform, name):
    (tmp_path / "Desktop").mkdir()
    written = shortcut.create(tmp_path, platform)
    target = next(Path(p) for p in written if Path(p).name == name)
    text = target.read_text()
    assert "paper_research_coach.cli" in text and " open" in text.replace("\r\n", " ")
    if platform == "darwin":
        assert target.stat().st_mode & stat.S_IXUSR and text.startswith("#!/bin/sh")
        assert str(tmp_path / "Desktop") in str(target)
    if platform == "linux":
        assert "Terminal=false" in text


def test_prc_alone_opens_the_workbench_and_update_check_reports(tmp_path, monkeypatch, capsys):
    opened = []
    monkeypatch.setattr("paper_research_coach.launcher.open_workbench", lambda store, port, paper, conv, new: opened.append(port) or {"opened": True})
    monkeypatch.setattr("sys.argv", ["prc", "--data-dir", str(tmp_path / "d")])
    main()
    assert opened == [8765] and json.loads(capsys.readouterr().out)["opened"]
    monkeypatch.setattr(updater, "check", lambda store, force=False, **k: {"current": __version__, "available": True, "latest": "99.0.0"})
    monkeypatch.setattr("sys.argv", ["prc", "--data-dir", str(tmp_path / "d"), "update", "--check"])
    main()
    assert json.loads(capsys.readouterr().out)["latest"] == "99.0.0"


def test_skill_copies_follow_the_running_version_at_startup(private_home):
    ours = private_home / ".agents/skills/paper-research-coach"
    ours.mkdir(parents=True)
    (ours / "SKILL.md").write_text("---\nname: paper-research-coach\n---\nold text")
    (ours / "my-notes.txt").write_text("kept")
    foreign = private_home / ".claude/skills/paper-research-coach"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("---\nname: someone-elses-skill\n---")
    assert updater.sync_skills() == ["codex"]
    assert "old text" not in (ours / "SKILL.md").read_text() and (ours / "references/branch.md").is_file()
    assert (ours / updater.STAMP).read_text().strip() == __version__ and (ours / "my-notes.txt").read_text() == "kept"
    assert (foreign / "SKILL.md").read_text().endswith("someone-elses-skill\n---")
    assert updater.sync_skills() == []  # already current


def test_background_update_installs_then_restarts_only_when_nobody_reads(store, monkeypatch):
    import paper_research_coach.launcher as launcher
    app = create_app(store, "token")
    client = TestClient(app, base_url="http://127.0.0.1")
    headers = {"Authorization": "Bearer token", "Origin": "http://127.0.0.1"}
    monkeypatch.setenv("PRC_IDLE_RESTART", "0")
    monkeypatch.delenv("PRC_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(updater, "check", lambda s, **k: {"current": __version__, "available": True, "latest": "99.0.0"})
    installs, restarts = [], []
    monkeypatch.setattr(updater, "apply", lambda s: installs.append(1) or {"updated": True, "from": __version__, "to": "99.0.0", "skills": []})
    monkeypatch.setattr(launcher, "spawn_relaunch", lambda *a: restarts.append(a))
    # Switched off: nothing happens.
    assert client.post("/api/update/settings", json={"auto": False}, headers=headers).json() == {"auto": False}
    app.state.auto_update_round()
    assert not installs
    client.post("/api/update/settings", json={"auto": True}, headers=headers)
    app.state.server = type("Server", (), {"should_exit": False})()
    app.state.viewers = 1  # a page is open
    app.state.auto_update_round()
    assert installs == [1] and app.state.update_job["state"] == "ready" and "已装好" in app.state.update_job["message"]
    app.state.auto_update_round()
    assert not restarts  # the reader is still here
    app.state.viewers = 0
    app.state.auto_update_round()
    assert restarts and app.state.server.should_exit and installs == [1]


def test_a_ready_update_needs_only_a_restart(store, monkeypatch):
    app = create_app(store, "token")
    client = TestClient(app, base_url="http://127.0.0.1")
    headers = {"Authorization": "Bearer token", "Origin": "http://127.0.0.1"}
    monkeypatch.setattr(updater, "check", lambda s, **k: {"current": __version__, "available": True, "latest": "99.0.0"})
    monkeypatch.setattr(updater, "apply", lambda s: pytest.fail("must not install twice"))
    app.state.update_job.update(state="ready", version="99.0.0", message="m")
    job = client.post("/api/update/apply", headers=headers).json()
    assert job["state"] == "done" and "prc" in job["message"]  # no server object in a test app
    assert client.get("/api/update", headers=headers).json()["auto"] in (True, False)


def test_install_skill_sync_cli(private_home, capsys, monkeypatch, tmp_path):
    from paper_research_coach import cli
    monkeypatch.setattr("sys.argv", ["prc", "--data-dir", str(tmp_path / "d"), "install-skill", "--host", "pi"])
    cli.main()
    copy = private_home / ".pi/agent/skills/paper-research-coach"
    assert (copy / updater.STAMP).read_text().strip() == __version__
    (copy / updater.STAMP).write_text("0.0.1")
    monkeypatch.setattr("sys.argv", ["prc", "--data-dir", str(tmp_path / "d"), "install-skill", "--sync"])
    cli.main()
    assert '"pi"' in capsys.readouterr().out
