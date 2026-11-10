import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {pluginUpdater} from '../host/plugin-updater.js';

test('update status is local and does not expose installation paths or start a reader', () => {
  const root = mkdtempSync(path.join(tmpdir(), 'prc-updater-'));
  try {
    const packageDir = path.join(root, 'package'), dataDir = path.join(root, 'data');
    mkdirSync(packageDir); mkdirSync(path.join(dataDir, 'plugin-updates'), {recursive: true});
    writeFileSync(path.join(packageDir, 'package.json'), JSON.stringify({version: '1.3.1'}));
    writeFileSync(path.join(dataDir, 'plugin-updates/state.json'), JSON.stringify({state: 'staged', staged_version: '1.3.2', available: true, payload: '/private/install', backup: '/private/backup'}));
    const updater = pluginUpdater({packageDir, dataDir, home: root, executable: undefined, hostVersion: '0.2.2-rc.1'});
    const result = updater.status();
    assert.equal(result.current_version, '1.3.1');
    assert.equal(result.staged_version, '1.3.2');
    assert.equal(result.state, 'staged');
    assert.equal(result.payload, undefined);
    assert.equal(result.backup, undefined);
    updater.stop();
  } finally {rmSync(root, {recursive: true, force: true});}
});
