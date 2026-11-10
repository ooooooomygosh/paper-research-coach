"""DSH release updates: download while reading, install only before host startup.

This module deliberately never invokes the independent workbench wheel updater.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import urllib.request
import zipfile
from filelock import FileLock, Timeout
from packaging.version import Version

REPO = 'ooooooomygosh/paper-research-coach'
API = f'https://api.github.com/repos/{REPO}/releases?per_page=30'
MAX_ARCHIVE = 1024 * 1024 * 1024
MAX_EXPANDED = 3 * MAX_ARCHIVE


def fetch(url, limit=2 * 1024 * 1024):
    req = urllib.request.Request(url, headers={'User-Agent': 'PRC-DSH-Updater', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(req, timeout=30) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('更新清单超出大小限制。')
    return data


def release_asset(tag, name):
    return f'https://github.com/{REPO}/releases/download/{tag}/{name}'


def manifest_asset(manifest, current, host, machine):
    version = str(manifest.get('version', ''))
    import re
    if manifest.get('schema_version') != 1 or not re.fullmatch(r'\d+\.\d+\.\d+', version):
        raise ValueError('不支持的 DSH 更新清单。')
    if manifest.get('tag') != 'dsh-v' + version:
        raise ValueError('DSH 更新标签不匹配。')
    if host not in manifest.get('host_versions', []):
        raise ValueError('此更新与当前 Harness 版本不兼容。')
    if Version(version) <= Version(current):
        return None
    asset = manifest.get('assets', {}).get(machine)
    if not asset:
        raise ValueError('此更新尚无当前平台的安装包。')
    expected = f'PRC-DSH-{version}-mac.zip'
    if machine != 'darwin-arm64' or asset.get('name') != expected:
        raise ValueError('不支持的 DSH 平台安装包。')
    if not re.fullmatch(r'[a-f0-9]{64}', str(asset.get('sha256', ''))):
        raise ValueError('更新校验值无效。')
    if type(asset.get('size')) is not int or not 0 < asset['size'] <= MAX_ARCHIVE:
        raise ValueError('更新文件大小无效。')
    return asset


def verified_extract(archive, destination, version):
    prefix = f'PRC-DSH-{version}-mac'
    with zipfile.ZipFile(archive) as bundle:
        items = bundle.infolist()
        if len(items) > 60000 or sum(x.file_size for x in items) > MAX_EXPANDED:
            raise ValueError('更新解压大小超出限制。')
        for item in items:
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if ('\\' in item.filename or path.is_absolute() or '..' in path.parts
                    or not path.parts or path.parts[0] != prefix or stat.S_ISLNK(mode)):
                raise ValueError('更新包包含不安全的文件路径。')
        for required in ('package.json', 'host/index.js', 'macos/install-macos.sh',
                         'upstream/src/paper_research_coach/embedded.py',
                         'upstream/src/paper_research_coach/static/index.html'):
            if f'{prefix}/{required}' not in bundle.namelist():
                raise ValueError('更新包缺少必要文件：' + required)
        package = json.loads(bundle.read(f'{prefix}/package.json'))
        if package.get('version') != version or package.get('name') != '@local/dsh-paper-research-coach':
            raise ValueError('更新包版本或名称不匹配。')
        bundle.extractall(destination)
    return Path(destination) / prefix


class PluginUpdater:
    def __init__(self, data, package, host, home=None, machine=None):
        self.data, self.package = Path(data), Path(package).resolve()
        self.home = Path(home or os.environ.get('DSH_HOME') or Path.home() / '.dsh')
        self.directory = self.data / 'plugin-updates'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.state_file = self.directory / 'state.json'
        self.lock = FileLock(str(self.directory / 'update.lock'))
        self.current = json.loads((self.package / 'package.json').read_text())['version']
        self.host = host
        self.machine = machine or ('darwin-arm64' if sys.platform == 'darwin' and platform.machine() == 'arm64' else f'{sys.platform}-{platform.machine()}')

    def status(self):
        try:
            state = json.loads(self.state_file.read_text())
        except (OSError, ValueError):
            state = {}
        return {'state': 'idle', 'checked_at': 0, 'staged_version': None, 'available': False,
                'auto': True, 'message': '每日自动检查 DSH 插件更新。', **state,
                'current_version': self.current}

    def save(self, **changes):
        state = {**self.status(), **changes}
        temp = self.state_file.with_suffix('.tmp')
        temp.write_text(json.dumps(state, ensure_ascii=False))
        temp.chmod(0o600)
        temp.replace(self.state_file)
        return state

    def check(self, force=False):
        with self.lock:
            previous = self.status()
            if previous['state'] in ('checking', 'downloading'):
                previous = self.save(state='idle', checked_at=0, message='恢复上次中断的更新检查。')
            if previous['state'] in ('staged', 'installing', 'applied'):
                return previous
            if not force and time.time() - previous['checked_at'] < 86400:
                return previous
            self.save(state='checking', message='正在检查 DSH 专属发布。', checked_at=time.time())
            try:
                releases = json.loads(fetch(API))
                import re
                releases = [x for x in releases if re.fullmatch(r'dsh-v\d+\.\d+\.\d+', str(x.get('tag_name', ''))) and not x.get('draft')]
                releases.sort(key=lambda x: Version(x['tag_name'][5:]), reverse=True)
                if not releases:
                    return self.save(state='idle', message='当前没有新的 DSH 专属发布。')
                release = releases[0]
                manifest = json.loads(fetch(release_asset(release['tag_name'], 'dsh-release.json')))
                if manifest.get('tag') != release['tag_name']:
                    raise ValueError('发布与清单标签不匹配。')
                asset = manifest_asset(manifest, self.current, self.host, self.machine)
                if not asset:
                    return self.save(state='idle', available=False, message='DSH 插件已是当前版本。')
                self.save(state='downloading', available=True, message='后台下载并校验更新；阅读不会中断。')
                archive = self.directory / (asset['name'] + '.download')
                req = urllib.request.Request(release_asset(manifest['tag'], asset['name']), headers={'User-Agent': 'PRC-DSH-Updater'})
                total, digest = 0, hashlib.sha256()
                with urllib.request.urlopen(req, timeout=60) as response, archive.open('wb') as output:
                    while chunk := response.read(1024 * 1024):
                        total += len(chunk)
                        if total > asset['size'] or total > MAX_ARCHIVE:
                            raise ValueError('更新包超过声明大小。')
                        digest.update(chunk)
                        output.write(chunk)
                if total != asset['size'] or digest.hexdigest() != asset['sha256']:
                    raise ValueError('更新包 SHA-256 或大小不符，旧版已保留。')
                destination = self.directory / ('prepared-' + manifest['version'])
                if destination.exists():
                    shutil.rmtree(destination)
                payload = verified_extract(archive, destination, manifest['version'])
                # Never run install here: this process runs beside an active reader.
                self.save(state='staged', staged_version=manifest['version'], manifest=manifest,
                          archive=str(archive), payload=str(payload), message='更新已准备；下次完全退出并重新打开 Harness 时安装。')
                return self.status()
            except Exception as exc:
                return self.save(state='error', error=str(exc)[:500], message='更新未完成，当前阅读和旧版保持可用。')

    def backup(self):
        directory = self.directory / ('backup-' + str(time.time_ns()))
        directory.mkdir()
        profile = self.home / 'profiles/desktop/package.json'
        if not profile.is_file():
            raise ValueError('未找到 desktop profile。')
        shutil.copy2(profile, directory / 'profile.json')
        link = self.home / 'profiles/desktop/node_modules/@local/dsh-paper-research-coach'
        if link.exists() and not link.is_symlink():
            raise ValueError('当前注册方式不支持自动替换，请手动升级。')
        (directory / 'registration.json').write_text(json.dumps({'target': str(link.resolve()) if link.exists() else None}))
        for current, dirs, names in os.walk(self.data):
            dirs[:] = [x for x in dirs if x not in ('plugin-updates', 'babeldoc-env', 'cache', 'translations', 'logs')]
            for name in names:
                if not name.endswith('.sqlite3'):
                    continue
                source = Path(current) / name
                target = directory / 'data' / source.relative_to(self.data)
                target.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as original, sqlite3.connect(target) as copy:
                    original.backup(copy)
                target.chmod(0o600)
        return directory

    def rollback(self):
        state = self.status()
        backup = Path(state['backup'])
        if not backup.resolve().is_relative_to(self.directory.resolve()):
            raise ValueError('备份位置无效。')
        profile = self.home / 'profiles/desktop/package.json'
        shutil.copy2(backup / 'profile.json', profile)
        target = json.loads((backup / 'registration.json').read_text())['target']
        link = profile.parent / 'node_modules/@local/dsh-paper-research-coach'
        if link.is_symlink():
            link.unlink()
        if target and not link.exists():
            link.symlink_to(target, target_is_directory=True)
        if (backup / 'data').exists():
            for source in (backup / 'data').rglob('*.sqlite3'):
                destination = self.data / source.relative_to(backup / 'data')
                # Only called before the backend starts; preserve the failed database as well.
                if destination.exists():
                    shutil.copy2(destination, destination.with_suffix('.failed-update.sqlite3'))
                for suffix in ('-wal', '-shm'):
                    Path(str(destination) + suffix).unlink(missing_ok=True)
                shutil.copy2(source, destination)
        self.save(state='rolled_back', message='升级未确认或失败，已恢复旧版及数据备份。', staged_version=None)
        return {'package_dir': target or str(self.package), 'rolled_back': True}

    def apply_pending(self, installer=None):
        # A plugin reload or another window is not an application restart.
        # Never replace a registered version or restore data while any reader is alive.
        reader = FileLock(str(self.directory / 'reader.lock'))
        try:
            reader.acquire(timeout=0)
        except Timeout:
            return {'package_dir': str(self.package), 'changed': False, 'reading_active': True}
        try:
            return self._apply_pending(installer)
        except Timeout:
            return {'package_dir': str(self.package), 'changed': False, 'checking_active': True}
        finally:
            reader.release()

    def _apply_pending(self, installer=None):
        with self.lock.acquire(timeout=0):
            state = self.status()
            if state['state'] == 'installing' or (state['state'] == 'applied' and not state.get('confirmed')):
                return self.rollback()
            if os.environ.get('PRC_DSH_NO_AUTO_UPDATE') == '1' and state['state'] == 'staged':
                return {'package_dir': str(self.package), 'changed': False}
            if state['state'] != 'staged':
                return {'package_dir': str(self.package), 'changed': False}
            try:
                manifest = state['manifest']
                asset = manifest_asset(manifest, self.current, self.host, self.machine)
                if not asset:
                    self.save(state='idle', staged_version=None)
                    return {'package_dir': str(self.package), 'changed': False}
                archive = Path(state['archive']).resolve()
                if not archive.is_relative_to(self.directory.resolve()):
                    raise ValueError('暂存路径无效。')
                with archive.open('rb') as file:
                    archive_hash = hashlib.file_digest(file, 'sha256').hexdigest()
                if archive_hash != asset['sha256']:
                    raise ValueError('暂存更新校验失败。')
                # Re-extract from the verified ZIP: never execute a modified extracted script.
                destination = self.directory / ('install-' + manifest['version'])
                if destination.exists(): shutil.rmtree(destination)
                payload = verified_extract(archive, destination, manifest['version'])
                backup = self.backup()
                self.save(state='installing', backup=str(backup), previous_package=str(self.package), confirmed=False)
                if installer:
                    installer(payload)
                else:
                    env = {**os.environ, 'DSH_HOME': str(self.home), 'PRC_DSH_RUNTIME_FROM': str(self.package), 'UV_OFFLINE': '1', 'PATH': '/opt/homebrew/bin:/usr/local/bin:' + os.environ.get('PATH', '')}
                    subprocess.run(['/bin/bash', str(payload / 'macos/install-macos.sh'), '--skip-frontend'],
                                   env=env, check=True, stdout=sys.stderr, stderr=sys.stderr, timeout=900)
                installed = self.home / f'builtin-plugins/paper-research-coach-{manifest["version"]}-mac'
                if json.loads((installed / 'package.json').read_text())['version'] != manifest['version']:
                    raise ValueError('安装版本验证失败。')
                self.save(state='applied', message='已切换新版本，等待阅读服务启动确认。')
                return {'package_dir': str(installed), 'changed': True}
            except Exception as exc:
                if self.status().get('state') in ('installing', 'applied'):
                    self.rollback()
                self.save(state='error', error=str(exc)[:500], message='安装失败，继续使用旧版。')
                return {'package_dir': str(self.package), 'changed': False, 'error': str(exc)}

    def confirm(self):
        with self.lock:
            state = self.status()
            if state['state'] == 'applied':
                self.save(state='idle', confirmed=True, staged_version=None, available=False, message='新版本阅读服务已启动，旧版备份已保留。')
                # Only discard this update's validated temporary material. The old
                # installation, profile and database backup remain available.
                version = state.get('manifest', {}).get('version', '')
                if version:
                    for directory in (self.directory / ('prepared-' + version), self.directory / ('install-' + version)):
                        if directory.resolve().is_relative_to(self.directory.resolve()):
                            with contextlib.suppress(OSError): shutil.rmtree(directory)
                archive = Path(state.get('archive', self.directory / 'absent'))
                if archive.resolve().is_relative_to(self.directory.resolve()) and archive.name.endswith('.zip.download'):
                    with contextlib.suppress(OSError): archive.unlink()



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['status', 'check', 'daemon', 'apply', 'rollback', 'confirm'])
    for arg in ('data', 'package', 'host', 'home'):
        parser.add_argument('--' + arg, required=arg != 'home')
    args = parser.parse_args()
    updater = PluginUpdater(args.data, args.package, args.host, args.home)
    if args.command == 'daemon':
        while True:
            updater.check()
            time.sleep(3600)
    elif args.command == 'check': print(json.dumps(updater.check(force=True), ensure_ascii=False))
    elif args.command == 'apply': print(json.dumps(updater.apply_pending(), ensure_ascii=False))
    elif args.command == 'rollback':
        with FileLock(str(updater.directory / 'reader.lock'), timeout=10):
            print(json.dumps(updater.rollback(), ensure_ascii=False))
    elif args.command == 'confirm': updater.confirm()
    else: print(json.dumps(updater.status(), ensure_ascii=False))

if __name__ == '__main__': main()
