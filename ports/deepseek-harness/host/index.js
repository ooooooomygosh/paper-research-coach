import {createServer, request as httpRequest} from 'node:http';
import {randomBytes, timingSafeEqual} from 'node:crypto';
import {spawn} from 'node:child_process';
import {appendFileSync, existsSync, mkdirSync, readFileSync, realpathSync} from 'node:fs';
import {homedir} from 'node:os';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';
import {pluginUpdater} from './plugin-updater.js';
import {createInterface} from 'node:readline';
import {pipeline} from 'node:stream/promises';
import {modelState, modelStream, safeFailure, effortFor} from './model.js';
import {followWindowsProxy} from './network.js';
import {renderExplainer} from './studio-renderer.mjs';

export const name = 'paper-research-coach';
export const inject = ['llm', 'webServer', 'connection'];
export const PREFIX = '/paper-research-coach';
const here = path.dirname(fileURLToPath(import.meta.url));
// Resolve the unpacked junction before launching Python. Common per-user
// Electron installation paths otherwise make deep dependency paths too long.
const packageDir = realpathSync(path.dirname(here).replace(/\.asar([\\/])/, '.asar.unpacked$1'));

/** Distribution archives bundle a Windows interpreter under runtime/python; a
 * POSIX build (macOS/Linux) keeps a virtual environment in runtime/venv. Order
 * keeps Windows behaviour unchanged and lets config.python override both. */
export function resolveInterpreter(root, config = {}) {
  const candidates = [
    config.python,
    path.join(root, 'runtime', 'python', 'python.exe'),
    path.join(root, 'runtime', 'python', 'Scripts', 'python.exe'),
    path.join(root, 'runtime', 'venv', 'bin', 'python3'),
    path.join(root, 'runtime', 'venv', 'bin', 'python'),
    path.join(root, 'runtime', 'python', 'bin', 'python3'),
  ].filter(Boolean);
  return candidates.find(candidate => existsSync(candidate));
}

function equal(a, b) {
  const left = Buffer.from(a || ''), right = Buffer.from(b || '');
  return left.length === right.length && timingSafeEqual(left, right);
}

async function jsonBody(req) {
  const parts = []; let size = 0;
  for await (const chunk of req) {
    size += chunk.length;
    if (size > 64 * 1024 * 1024) throw new Error('Request exceeds bridge limit');
    parts.push(chunk);
  }
  return JSON.parse(Buffer.concat(parts).toString('utf8') || '{}');
}

function json(res, status, value) {
  res.writeHead(status, {'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store'});
  res.end(JSON.stringify(value));
}

/** Private model bridge: loopback + ephemeral secret, never exposed to renderer. */
export function createModelBridge(ctx, secret, log = () => {}) {
  return createServer(async (req, res) => {
    if (req.headers.origin || !equal(req.headers.authorization, `Bearer ${secret}`)) return json(res, 403, {error: 'Forbidden'});
    const abort = new AbortController();
    res.once('close', () => {if (!res.writableEnded) abort.abort();});
    try {
      if (req.url === '/render-html' && req.method === 'POST') {
        try { return json(res, 200, await renderExplainer(await jsonBody(req))); }
        catch (error) { return json(res, 422, {error: String(error.message).slice(0, 3000), code: 'RENDER_ERROR'}); }
      }
      if (req.url === '/state' && req.method === 'GET') {
        const state = await modelState(ctx);
        const models = await Promise.all(state.models.map(async item => {
          const info = await ctx.get('llm').resolveModelInfo(state.provider, item.id, abort.signal);
          return {model: item.id, displayName: item.name, supportedReasoningEfforts: (info.reasoning?.efforts || []).map(e => ({reasoningEffort: e.id, description: e.name})), defaultReasoningEffort: info.reasoning?.defaultEffort || ''};
        }));
        // Resolved reasoning levels live in the per-model info, not in listModels.
        state.effort = effortFor({model: state.model, models: models.map(item => ({id: item.model, supportedReasoningEfforts: item.supportedReasoningEfforts, defaultReasoningEffort: item.defaultReasoningEffort}))});
        return json(res, 200, {...state, models});
      }
      if (req.url !== '/stream' || req.method !== 'POST') return json(res, 404, {error: 'Not found'});
      const body = await jsonBody(req);
      log(`stream model=${body.model || '-'} effort=${body.effort || '-'} tools=${(body.tools || []).length} messages=${(body.messages || []).length}`);
      res.writeHead(200, {'content-type': 'application/x-ndjson', 'cache-control': 'no-store'});
      for await (const chunk of modelStream(ctx, body, abort.signal)) {
        if (abort.signal.aborted) break;
        if (!res.write(JSON.stringify(chunk) + '\n')) await new Promise(resolve => {res.once('drain', resolve); res.once('close', resolve);});
      }
      res.end();
    } catch (error) {
      const failure = safeFailure(error);
      log(`model bridge ${req.url} -> ${failure.code}: ${failure.message}`);
      if (!res.headersSent) json(res, 503, {error: failure.message, code: failure.code});
      else res.end(JSON.stringify({type: 'finish', reason: {kind: abort.signal.aborted ? 'aborted' : 'error', failure}}) + '\n');
    }
  });
}

function bridgeLog(dataDir, line) {
  try {
    const dir = path.join(dataDir, 'logs');
    mkdirSync(dir, {recursive: true});
    appendFileSync(path.join(dir, 'bridge.log'), `${new Date().toISOString()} ${line}\n`);
  } catch { /* diagnostics must never break the turn */ }
}

export async function apply(ctx, config = {}) {
  const updateHome = config.updateHome || process.env.DSH_HOME || path.join(homedir(), '.dsh');
  const updateData = config.dataDir || path.join(updateHome, 'paper-research-coach');
  let hostVersion = config.hostVersion || '';
  try { hostVersion ||= JSON.parse(readFileSync(path.join(process.env.DSH_APP || '/Applications/DeepSeek Harness.app', 'Contents/Resources/app/dsh/package.json'), 'utf8')).version; } catch {}
  const updates = pluginUpdater({packageDir, dataDir: updateData, home: updateHome,
    executable: resolveInterpreter(packageDir, config), hostVersion});
  if (!config._update_bootstrapped) {
    try {
      const prepared = await updates.run('apply');
      if (prepared.package_dir && path.resolve(prepared.package_dir) !== packageDir) {
        try {
          const next = await import(pathToFileURL(path.join(prepared.package_dir, 'host/index.js')).href);
          return await next.apply(ctx, {...config, _update_bootstrapped: true, _update_just_installed: !!prepared.changed});
        } catch (error) {
          const restored = await updates.run('rollback');
          const previous = await import(pathToFileURL(path.join(restored.package_dir, 'host/index.js')).href);
          return await previous.apply(ctx, {...config, _update_bootstrapped: true});
        }
      }
    } catch (error) { bridgeLog(updateData, 'DSH update deferred: ' + error.message); }
  }
  updates.start();
  ctx.effect(() => () => updates.stop());
  const restoreNetwork = await followWindowsProxy(ctx);
  if (restoreNetwork) ctx.effect(() => restoreNetwork);
  const dataDir = config.dataDir || path.join(process.env.DSH_HOME || path.join(homedir(), '.dsh'), 'paper-research-coach');
  mkdirSync(dataDir, {recursive: true});
  const secret = randomBytes(32).toString('base64url');
  const backendToken = randomBytes(32).toString('base64url');
  let bridge, child, closing = false, address, startup;

  const start = () => {
    if (closing) return Promise.reject(new Error('论文研读正在关闭。'));
    if (startup) return startup;
    startup = (async () => {
      bridge = createModelBridge(ctx, secret, line => bridgeLog(dataDir, line));
      await new Promise((resolve, reject) => {bridge.once('error', reject); bridge.listen(0, '127.0.0.1', resolve);});
      const executable = resolveInterpreter(packageDir, config);
      if (!executable) throw new Error('论文研读的内置 Python 运行库缺失，请重新安装插件。');
      child = spawn(executable, ['-X', 'utf8', '-m', 'paper_research_coach.embedded'], {
        cwd: packageDir, windowsHide: true,
        env: {...process.env, NO_PROXY: 'localhost,127.0.0.1', no_proxy: 'localhost,127.0.0.1', PYTHONPATH: path.join(packageDir, 'upstream', 'src'), PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8', PYTHONUNBUFFERED: '1', PRC_EMBEDDED: '1', PRC_DATA: dataDir, PRC_SESSION_TOKEN: backendToken, DSH_PRC_ASSETS: path.join(packageDir, 'runtime', 'assets'), DSH_PRC_BRIDGE_URL: `http://127.0.0.1:${bridge.address().port}`, DSH_PRC_BRIDGE_TOKEN: secret, PRC_NO_UPDATE_CHECK: '1', PRC_NO_AUTO_UPDATE: '1'},
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      let diagnostics = '';
      child.stderr.setEncoding('utf8');
      child.stderr.on('data', text => {diagnostics = (diagnostics + text).slice(-8000);});
      const port = await new Promise((resolve, reject) => {
        const timeout = setTimeout(() => reject(new Error('论文研读启动超时')), 45000);
        const lines = createInterface({input: child.stdout});
        child.once('error', error => {clearTimeout(timeout); reject(error);});
        child.once('exit', code => {
          clearTimeout(timeout);
          if (process.env.PRC_TEST_DEBUG === '1') console.warn(diagnostics.replaceAll(secret, '[redacted]').replaceAll(backendToken, '[redacted]'));
          reject(new Error(`论文研读运行库退出 (${code})`));
        });
        lines.on('line', line => {
          try {
            const value = JSON.parse(line);
            if (value.event === 'ready') {clearTimeout(timeout); resolve(value.port);}
          } catch { /* Library diagnostics are not model credentials. */ }
        });
      });
      child.stderr.on('data', () => {});
      child.once('exit', () => {address = undefined; startup = undefined; bridge?.close();});
      address = {host: '127.0.0.1', port};
      if (updates.status().state === 'applied') await updates.run('confirm');
      return address;
    })().catch(error => {startup = undefined; bridge?.close(); child?.kill(); throw error;});
    return startup;
  };

  // Validate a just-installed version now, even if the reader opens no paper
  // before quitting. No account/model request is needed for backend readiness.
  if (config._update_just_installed) {
    try { await start(); }
    catch (error) { updates.stop(); throw error; }
  }

  const proxy = async (req, res) => {
    const connection = ctx.get('connection');
    const rejection = connection.requestRejection({headers: req.headers});
    if (rejection) {res.writeHead(rejection); res.end(); return;}
    try {
      const url = new URL(req.url || '/', 'http://127.0.0.1');
      const relative = url.pathname.slice(PREFIX.length) || '/';
      if (relative === '/api/plugin-update' && req.method === 'GET') return json(res, 200, updates.status());
      if (relative === '/api/plugin-update/check' && req.method === 'POST') return json(res, 200, updates.check());
      const target = await start();
      const headers = {...req.headers, host: `127.0.0.1:${target.port}`, authorization: `Bearer ${backendToken}`};
      delete headers.cookie; delete headers.origin; delete headers.connection;
      const upstream = httpRequest({...target, path: relative + url.search, method: req.method, headers}, response => {
        const outgoing = {...response.headers};
        delete outgoing['set-cookie'];
        delete outgoing['content-security-policy'];
        outgoing['content-security-policy'] = "default-src 'self'; script-src 'self' 'wasm-unsafe-eval'; style-src 'self' 'unsafe-inline'; font-src 'self' data:; img-src 'self' data: blob:; worker-src 'self' blob:; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'; object-src 'none'";
        if (relative.startsWith('/api/workspace/view/')) outgoing['content-security-policy'] = "sandbox allow-scripts allow-forms allow-downloads allow-modals; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; media-src data: blob:; connect-src 'none'; frame-ancestors 'self'; form-action 'none'; base-uri 'none'; object-src 'none'";
        res.writeHead(response.statusCode || 502, outgoing);
        pipeline(response, res).catch(() => {});
      });
      upstream.once('error', () => {if (!res.headersSent) json(res, 502, {error: '论文研读服务连接中断，请重新打开。'}); else res.end();});
      res.once('close', () => {if (!res.writableEnded) upstream.destroy();});
      pipeline(req, upstream).catch(() => upstream.destroy());
    } catch (error) {json(res, 503, {error: error.message});}
  };
  ctx.effect(() => ctx.webServer.register({kind: 'prefix', path: PREFIX, handler: proxy}));
  ctx.effect(() => async () => {
    closing = true;
    const running = child;
    if (running && running.exitCode === null) {
      running.stdin.end();
      await new Promise(resolve => {
        const timer = setTimeout(() => {running.kill(); resolve();}, 3000);
        running.once('exit', () => {clearTimeout(timer); resolve();});
      });
    }
    bridge?.closeAllConnections();
    bridge?.close();
  });
  if (ctx.get('skills')) {
    const skillDir = path.join(packageDir, 'upstream', 'skills', 'paper-research-coach');
    const integration = 'Harness 集成说明：本技能已经内置。完整的带读、原文定位、图文讲解和进度工具在左侧“论文研读”工作台的教练对话中提供，AI 沿用 Harness 登录账户。若当前是 Harness 主聊天，可直接用宿主模型解释读法；操作论文记录时引导到工作台。不要安装或运行 Codex CLI，不要要求另填 API Key。\n\n';
    ctx.effect(() => ctx.get('skills').register({name: 'paper-research-coach', description: '论文精读、证据核查、批判思考、研究想法和回忆复习。完整工作台在左侧“论文研读”。', content: integration + readFileSync(path.join(skillDir, 'SKILL.md'), 'utf8'), resourceBase: {kind: 'directory', path: skillDir}, invocation: {modelInvocable: true, userInvocable: true}}));
  }
}
