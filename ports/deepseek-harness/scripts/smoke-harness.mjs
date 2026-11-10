/** Boot the actual bundled Harness runtime, with an isolated plugin database. */
import {fileURLToPath, pathToFileURL} from 'node:url';
import path from 'node:path';
import {existsSync, mkdirSync, symlinkSync, writeFileSync} from 'node:fs';
import assert from 'node:assert/strict';
for (const method of ['log', 'info', 'warn', 'error']) {
  const write = console[method].bind(console);
  console[method] = (...args) => write(...args.map(value => typeof value === 'string' ? value.replace(/([?&]token=)[^\s]+/g, '$1<redacted>') : value));
}
const pkg = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const reference = process.env.DSH_PRC_TEST_REFERENCE_PATH || path.join(pkg, '..', 'dsh-desktop-reference', 'dsh');
const {loadProfileDirectory, loadLayeredEnv} = await import(pathToFileURL(path.join(reference, 'node_modules/@deepseek-ai/dsh-app-boot/lib/index.js')));
const {runProfile} = await import(pathToFileURL(path.join(reference, 'node_modules/@deepseek-ai/dsh/lib/profile-boot.js')));
const profileDir = path.join(pkg, '.test-profile');
mkdirSync(profileDir, {recursive: true});
const localModules = path.join(profileDir, 'node_modules', '@local');
mkdirSync(localModules, {recursive: true});
const localPackage = path.join(localModules, 'dsh-paper-research-coach');
if (!existsSync(localPackage)) symlinkSync(pkg, localPackage, 'junction');
writeFileSync(path.join(profileDir, 'package.json'), JSON.stringify({name: 'paper-coach-test', private: true, dependencies: {'@local/dsh-paper-research-coach': 'link:' + pkg}, dsh: {profile: {bundles: ['@deepseek-ai/dsh-base', '@deepseek-ai/dsh-web-app', '@local/dsh-paper-research-coach']}}}));
writeFileSync(path.join(profileDir, 'cordis.patch.yml'), JSON.stringify([
  {id: 'web-runtime', name: '@deepseek-ai/dsh-web-app', config: {openBrowser: false, printUrl: false}},
  {id: 'desktop-product-telemetry', disabled: true}, {id: 'product-analytics', disabled: true},
  {id: 'paper-research-coach', config: {dataDir: path.join(pkg, '.test-data')}},
]));
const anchor = path.join(reference, 'node_modules/@deepseek-ai/dsh/package.json');
const profile = loadProfileDirectory('dsh', profileDir, anchor);
process.env.DSH_CLIENT_VERSION = JSON.parse((await import('node:fs')).readFileSync(path.join(reference, 'package.json'), 'utf8')).version;
console.log('Starting bundled Harness verification');
const app = await runProfile({environment: loadLayeredEnv('dsh'), profile: 'desktop', resolvedProfile: {profile, installAnchor: anchor}, patchFiles: [], args: ['--no-open', '--host', '127.0.0.1', '--port', '0']});
const {ctx} = app;
try {
  const origin = `http://127.0.0.1:${ctx.webServer.port}`;
  const login = await fetch(ctx.connection.authenticatedUrl(origin), {redirect: 'manual'});
  const cookie = login.headers.getSetCookie().map(c => c.split(';')[0]).join('; ');
  assert.ok(cookie);
  const api = async (endpoint, body) => {
    const response = await fetch(origin + '/paper-research-coach/api/' + endpoint, {method: body === undefined ? 'GET' : 'POST', headers: {cookie, ...(body === undefined ? {} : {'content-type': 'application/json', origin})}, body: body === undefined ? undefined : JSON.stringify(body)});
    const text = await response.text();
    assert.ok(response.ok, `${endpoint}: HTTP ${response.status}: ${text.slice(0, 500)}`);
    assert.ok(text, `${endpoint}: empty HTTP ${response.status} response`);
    const data = JSON.parse(text);
    return data;
  };
  const state = await api('state');
  const status = await api('coach/status');
  console.log(JSON.stringify({test: 'actual-harness-runtime', state: status.state, account: status.message, models: status.models.map(m => m.model), papers: state.papers.length}));
  assert.equal(status.state, 'ready');
  const page = await fetch(origin + '/paper-research-coach/', {headers: {cookie}});
  assert.equal(page.status, 200);
  assert.ok((await page.text()).includes('/paper-research-coach/assets/'));
  console.log('Workbench document loaded');
  const noAuth = await fetch(origin + '/paper-research-coach/api/state');
  assert.equal(noAuth.status, 401);
  console.log('Unauthenticated workbench access refused');
  if (process.env.PRC_LEARNING_TEST === '1') {
    const {smokeLearning} = await import('./smoke-learning.mjs');
    await smokeLearning({origin, cookie, pkg});
  }
  if (process.env.PRC_LIVE_TEST === '1') {
    const paper = await api('import', {title: 'Synthetic integration verification', path: path.join(pkg, '.test-fixture.pdf'), goal: 'Check evidence in this synthetic teaching document'});
    await api('coach/send/' + paper.id, {operation_id: 'integration-' + Date.now(), content: '请读取第1页原文，用一句话说明这份材料讨论的研究问题，并调用 prc_show 标出依据。', page_index: 0, intent: 'detour', help_mode: 'explain'});
    let snapshot;
    const deadline = Date.now() + 180000;
    do {
      await new Promise(r => setTimeout(r, 1000));
      snapshot = await api('coach/conversation/' + paper.id);
    } while (snapshot.busy && Date.now() < deadline);
    const answer = snapshot.messages.filter(m => m.role === 'assistant').at(-1);
    assert.equal(answer?.status, 'completed', JSON.stringify(answer));
    assert.ok(answer.content);
    assert.ok(answer.actions?.some(a => a.kind === 'focus'), JSON.stringify(answer));
    console.log(JSON.stringify({test: 'live-account-tool-loop', status: answer.status, sourceHighlight: true, responseCharacters: answer.content.length}));
  }
  if (process.env.PRC_TRANSLATION_TEST === '1') {
    const settings = await api('translation/settings');
    assert.ok(settings.component.ready, JSON.stringify(settings.component));
    const paper = await api('import', {title: 'Synthetic translation verification', path: path.join(pkg, '.test-translation.pdf')});
    const existing = (await api('translation/' + paper.id + '/jobs')).data;
    let job = existing.find(j => ['queued', 'running'].includes(j.state)) || existing.find(j => j.state === 'completed' && j.pdf_ready);
    if (!job) job = await api('translation/' + paper.id + '/jobs', {operation_id: 'translation-' + Date.now(), source_version: paper.source_version});
    const deadline = Date.now() + 480000;
    let previous = '';
    while (['running', 'queued'].includes(job.state) && Date.now() < deadline) {
      await new Promise(r => setTimeout(r, 2000));
      job = await api('translation/jobs/' + job.id);
      if (job.stage !== previous) {console.log(JSON.stringify({test: 'live-translation-progress', state: job.state, stage: job.stage})); previous = job.stage;}
    }
    assert.equal(job.state, 'completed', JSON.stringify(job));
    assert.ok(job.pdf_ready);
    for (const view of ['mono', 'dual']) {
      const pdf = await fetch(origin + '/paper-research-coach/api/translation/jobs/' + job.id + '/pdf/' + view, {headers: {cookie}});
      assert.equal(pdf.status, 200);
      assert.equal(Buffer.from(await pdf.arrayBuffer()).subarray(0, 5).toString(), '%PDF-');
    }
    console.log(JSON.stringify({test: 'live-account-bilingual-translation', state: job.state, pdfReady: job.pdf_ready, documents: job.documents}));
  }
  if (process.env.PRC_HOLD_TEST === '1') {
    writeFileSync(path.join(pkg, '.test-server.json'), JSON.stringify({origin, cookie}));
    console.log('Test server ready');
    await new Promise(resolve => process.once('SIGINT', resolve));
  }
} finally {
  console.log('Stopping test runtime');
  await app.shutdown.shutdown(0);
  console.log('Test runtime stopped');
}
