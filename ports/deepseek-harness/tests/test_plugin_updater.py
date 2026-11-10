"""Isolated updater checks; never touch installed profiles or call real installers."""
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import zipfile
import pytest
from paper_research_coach import plugin_updater as mod


def bundle(version='1.3.2', extra=None):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        root = f'PRC-DSH-{version}-mac/'
        archive.writestr(root + 'package.json', json.dumps({'name': '@local/dsh-paper-research-coach', 'version': version}))
        for name in ('host/index.js', 'macos/install-macos.sh', 'upstream/src/paper_research_coach/embedded.py', 'upstream/src/paper_research_coach/static/index.html'):
            archive.writestr(root + name, 'fixture')
        if extra: archive.writestr(extra, 'bad')
    return stream.getvalue()


@pytest.fixture
def setup(tmp_path, monkeypatch):
    package = tmp_path / 'old'
    package.mkdir()
    (package / 'package.json').write_text(json.dumps({'version': '1.3.1'}))
    home, data = tmp_path / 'home', tmp_path / 'home/data'
    profile = home / 'profiles/desktop/package.json'
    profile.parent.mkdir(parents=True)
    profile.write_text('{"old":true}')
    link = profile.parent / 'node_modules/@local/dsh-paper-research-coach'
    link.parent.mkdir(parents=True)
    link.symlink_to(package)
    updater = mod.PluginUpdater(data, package, '0.2.2-rc.1', home, machine='darwin-arm64')
    payload = bundle()
    manifest = {'schema_version': 1, 'version': '1.3.2', 'tag': 'dsh-v1.3.2',
                'host_versions': ['0.2.2-rc.1'], 'assets': {'darwin-arm64': {
                    'name': 'PRC-DSH-1.3.2-mac.zip', 'sha256': hashlib.sha256(payload).hexdigest(), 'size': len(payload)}}}
    monkeypatch.setattr(mod, 'fetch', lambda url: json.dumps([{'tag_name': 'dsh-v1.3.2'} ] if url == mod.API else manifest).encode())
    monkeypatch.setattr(mod.urllib.request, 'urlopen', lambda *a, **k: io.BytesIO(payload))
    return updater, manifest, profile, link


def test_background_only_stages_and_checks_once_daily(setup, monkeypatch):
    updater, _, profile, link = setup
    assert updater.check()['state'] == 'staged'
    assert profile.read_text() == '{"old":true}'
    assert link.resolve() == updater.package
    monkeypatch.setattr(mod, 'fetch', lambda *_: pytest.fail('staged updates do not re-download'))
    assert updater.check()['state'] == 'staged'


def test_wrong_hash_never_changes_registration(setup):
    updater, manifest, profile, link = setup
    manifest['assets']['darwin-arm64']['sha256'] = '0' * 64
    assert updater.check()['state'] == 'error'
    assert link.resolve() == updater.package
    assert profile.read_text() == '{"old":true}'


@pytest.mark.parametrize('mutate', [lambda m: m.update(host_versions=['unknown']), lambda m: m.update(tag='v2.0.0'), lambda m: m['assets']['darwin-arm64'].update(name='../other.zip')])
def test_incompatible_or_untrusted_manifest(setup, mutate):
    updater, manifest, _, link = setup
    mutate(manifest)
    assert updater.check()['state'] == 'error'
    assert link.resolve() == updater.package


@pytest.mark.parametrize('unsafe', ['../outside', '/absolute', 'PRC-DSH-1.3.2-mac/../../escape', 'PRC-DSH-1.3.2-mac/..\\evil'])
def test_archive_paths_are_checked_before_extraction(tmp_path, unsafe):
    archive = tmp_path / 'bad.zip'
    archive.write_bytes(bundle(extra=unsafe))
    with pytest.raises(ValueError): mod.verified_extract(archive, tmp_path / 'extract', '1.3.2')
    assert not (tmp_path / 'extract').exists()


def test_install_failure_restores_registration_and_database(setup):
    updater, _, profile, link = setup
    database = updater.data / 'notebook.sqlite3'
    with sqlite3.connect(database) as connection:
        connection.execute('create table example(value text)')
        connection.execute("insert into example values('original')")
    updater.check()
    def fail(_):
        profile.write_text('{"broken":true}')
        with sqlite3.connect(database) as connection: connection.execute("update example set value='new'")
        raise RuntimeError('installer failed')
    assert not updater.apply_pending(installer=fail)['changed']
    assert profile.read_text() == '{"old":true}'
    assert link.resolve() == updater.package
    with sqlite3.connect(database) as connection: assert connection.execute('select value from example').fetchone()[0] == 'original'


def test_success_only_activates_at_next_start_and_requires_health_confirmation(setup):
    updater, _, profile, link = setup
    updater.check()
    assert updater.status()['state'] == 'staged'
    def install(payload):
        destination = updater.home / 'builtin-plugins/paper-research-coach-1.3.2-mac'
        destination.mkdir(parents=True)
        (destination / 'package.json').write_text((payload / 'package.json').read_text())
        link.unlink()
        link.symlink_to(destination)
        profile.write_text('{"new":true}')
    result = updater.apply_pending(installer=install)
    assert result['changed'] and updater.status()['state'] == 'applied'
    restored = updater.apply_pending()  # A failed/no-ready startup must recover.
    assert restored['rolled_back'] and link.resolve() == updater.package
    assert profile.read_text() == '{"old":true}'


def test_prepared_zip_tampering_cannot_run_installer(setup):
    updater, _, profile, _ = setup
    updater.check()
    Path(updater.status()['archive']).write_bytes(b'changed')
    result = updater.apply_pending(installer=lambda _: pytest.fail('must not run'))
    assert not result['changed'] and profile.read_text() == '{"old":true}'


def test_confirmed_update_does_not_roll_back(setup):
    updater, _, profile, _ = setup
    backup = updater.backup()
    updater.save(state='applied', backup=str(backup), confirmed=False)
    updater.confirm()
    assert updater.status()['state'] == 'idle'
    assert updater.status()['confirmed'] is True
    assert updater.apply_pending()['changed'] is False


def test_interrupted_install_restores_before_opening_reading_service(setup):
    updater, _, profile, _ = setup
    backup = updater.backup()
    profile.write_text('{"incomplete":true}')
    updater.save(state='installing', backup=str(backup), confirmed=False)
    assert updater.apply_pending()['rolled_back']
    assert profile.read_text() == '{"old":true}'


def test_interrupted_download_resumes_and_prerelease_is_accepted(setup, monkeypatch):
    updater, manifest, _, _ = setup
    original = mod.fetch
    monkeypatch.setattr(mod, 'fetch', lambda url: json.dumps([{'tag_name': 'dsh-v1.3.2', 'prerelease': True, 'draft': False}]).encode() if url == mod.API else original(url))
    updater.save(state='downloading', checked_at=mod.time.time())
    assert updater.check()['state'] == 'staged'


def test_zip_symlinks_are_not_extracted(tmp_path):
    archive = tmp_path / 'link.zip'
    with zipfile.ZipFile(archive, 'w') as bundle:
        item = zipfile.ZipInfo('PRC-DSH-1.3.2-mac/link')
        item.create_system = 3
        item.external_attr = 0o120777 << 16
        bundle.writestr(item, '/tmp/outside')
    with pytest.raises(ValueError): mod.verified_extract(archive, tmp_path / 'extract', '1.3.2')


def test_active_reader_prevents_installation_even_on_plugin_reload(setup):
    from filelock import FileLock
    updater, _, profile, _ = setup
    updater.check()
    with FileLock(str(updater.directory / 'reader.lock')):
        result = updater.apply_pending(installer=lambda _: pytest.fail('active reader must be untouched'))
    assert result['reading_active'] and not result['changed']
    assert updater.status()['state'] == 'staged'
    assert profile.read_text() == '{"old":true}'


def test_health_confirmation_cleans_only_this_updates_temporary_material(setup):
    updater, _, _, _ = setup
    updater.check()
    staged = updater.status()
    backup = updater.backup()
    install = updater.directory / 'install-1.3.2'
    install.mkdir()
    updater.save(state='applied', backup=str(backup), confirmed=False)
    updater.confirm()
    assert not Path(staged['archive']).exists()
    assert not Path(staged['payload']).parent.exists()
    assert not install.exists()
    assert backup.exists() and updater.package.exists()
    assert updater.status()['confirmed']


def test_startup_never_waits_for_a_background_download(tmp_path):
    from paper_research_coach.plugin_updater import PluginUpdater
    from filelock import FileLock
    package = tmp_path / "package"
    package.mkdir()
    (package / "package.json").write_text('{"version":"1.3.1"}')
    updater = PluginUpdater(tmp_path / "data", package, "0.2.2-rc.1", tmp_path / "home")
    with FileLock(str(updater.directory / "update.lock")):
        result = updater.apply_pending()
    assert result["checking_active"] is True
    assert result["changed"] is False
