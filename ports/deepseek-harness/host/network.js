import {execFile} from 'node:child_process';
import {promisify} from 'node:util';

/** Follow an already configured Windows proxy when the Harness launch had no
 * explicit proxy environment. Uses the Harness's own dispatcher and disposer. */
export async function followWindowsProxy(ctx) {
  if (process.platform !== 'win32') return;
  const names = ['http_proxy', 'HTTP_PROXY', 'https_proxy', 'HTTPS_PROXY', 'all_proxy', 'ALL_PROXY'];
  const launch = ctx.get('launchEnvironment');
  if (names.some(name => launch?.get(name)?.value?.trim() || process.env[name]?.trim())) return;
  try {
    const run = promisify(execFile);
    const key = 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings';
    const [enabled, configured] = await Promise.all([
      run('reg.exe', ['query', key, '/v', 'ProxyEnable'], {windowsHide: true, timeout: 3000}),
      run('reg.exe', ['query', key, '/v', 'ProxyServer'], {windowsHide: true, timeout: 3000}),
    ]);
    if (!/REG_DWORD\s+0x1\b/.test(enabled.stdout)) return;
    let raw = /REG_SZ\s+(.+)/.exec(configured.stdout)?.[1].trim();
    if (!raw) return;
    if (raw.includes('=')) {
      const routes = Object.fromEntries(raw.split(';').map(part => part.split('=', 2)));
      raw = routes.https || routes.http;
    }
    if (!raw) return;
    const url = new URL(/^https?:\/\//.test(raw) ? raw : 'http://' + raw);
    if (!['http:', 'https:'].includes(url.protocol)) return;
    const [{installProxyFromEnvironment, proxyRouteFor}, {createLaunchEnvironmentSnapshot}] = await Promise.all([
      import('@deepseek-ai/dsh-http-proxy'), import('@deepseek-ai/dsh-launch-environment'),
    ]);
    if (proxyRouteFor(new URL('https://api.deepseek.com')).proxied) return;
    const environment = createLaunchEnvironmentSnapshot([{source: 'process', values: {HTTP_PROXY: url.href, HTTPS_PROXY: url.href, NO_PROXY: 'localhost,127.0.0.1'}}]);
    return await installProxyFromEnvironment(environment, () => {});
  } catch { /* Existing Harness transport remains available if OS lookup fails. */ }
}
