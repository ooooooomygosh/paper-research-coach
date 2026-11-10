/** DSH-only update bootstrap. No in-session code replacement or wheel updater. */
import {spawn} from 'node:child_process';
import {existsSync, readFileSync, mkdirSync, appendFileSync} from 'node:fs';
import path from 'node:path';

export function pluginUpdater({packageDir, dataDir, home, executable, hostVersion}) {
  const directory = path.join(dataDir, 'plugin-updates');
  mkdirSync(directory, {recursive: true});
  const children = new Set();
  let checking = false;
  function run(command, background = false) {
    return new Promise((resolve, reject) => {
      if (!executable) return reject(new Error('内置更新运行库不可用。'));
      const child = spawn(executable, ['-m', 'paper_research_coach.plugin_updater', command,
        '--data', dataDir, '--package', packageDir, '--host', hostVersion, '--home', home], {
        env: {...process.env, PYTHONPATH: path.join(packageDir, 'upstream/src'), PYTHONUNBUFFERED: '1'},
        stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true,
      });
      children.add(child);
      let output = '', diagnostics = '';
      child.stdout.on('data', chunk => {output = (output + chunk).slice(-20000);});
      child.stderr.on('data', chunk => {diagnostics = (diagnostics + chunk).slice(-2000);});
      child.once('error', reject);
      child.once('exit', code => {
        children.delete(child);
        if (code !== 0) return reject(new Error(diagnostics || `更新任务退出 (${code})`));
        if (background) return resolve({});
        try { resolve(output.trim() ? JSON.parse(output.trim().split('\n').at(-1)) : {}); }
        catch { reject(new Error('更新状态返回无效。')); }
      });
    });
  }
  function status() {
    let value = {};
    try { value = JSON.parse(readFileSync(path.join(directory, 'state.json'), 'utf8')); } catch {}
    const current = JSON.parse(readFileSync(path.join(packageDir, 'package.json'), 'utf8')).version;
    return {current_version: current, state: checking ? 'checking' : value.state || 'idle', checked_at: value.checked_at || 0,
      staged_version: value.staged_version || null, available: !!value.available, auto: process.env.PRC_DSH_NO_AUTO_UPDATE !== '1',
      message: value.message || '每日自动检查 DSH 专属更新；在下次启动时安装。', error: value.error || ''};
  }
  function check() {
    if (!checking) {
      checking = true;
      run('check').catch(error => {try {appendFileSync(path.join(directory, 'updater.log'), `${new Date().toISOString()} ${error.message}\n`);} catch {}})
        .finally(() => {checking = false;});
    }
    return status();
  }
  return {run, status, check,
    start() { if (process.env.PRC_DSH_NO_AUTO_UPDATE !== '1') run('daemon', true).catch(() => {}); },
    stop() { for (const child of children) child.kill(); children.clear(); },
  };
}
