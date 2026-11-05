import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, writeFileSync, rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {modelState, modelStream, safeFailure} from '../host/model.js';
import {createModelBridge, resolveInterpreter} from '../host/index.js';

function harness() {
  const seen = [];
  const llm = {
    async listModels(provider) {assert.equal(provider, 'deepseek-account'); return [{provider, id: 'flash', name: 'Flash'}];},
    async resolveModelInfo() {return {reasoning: {efforts: [{id: 'max', name: 'Max'}]}};},
    async prepareCall(config, signal) {seen.push({config, signal}); return {config: {...config, maxTokens: 1000}, async *stream(options) {seen.push(options); yield {type: 'text-delta', index: 0, text: 'verified'}; yield {type: 'finish', reason: {kind: 'stop'}};}};},
  };
  return {seen, ctx: {get(name) {return {llm, agentDefaultModel: {currentSelection() {return {provider: 'api-key', model: 'other'};}}, attachments: {async saveImages(images) {seen.push(images); return [{id: 'image'}];}}}[name];}}};
}

test('uses signed-in account route even if the chat selected a key provider', async () => {
  const {ctx, seen} = harness();
  assert.equal((await modelState(ctx)).model, 'flash');
  const signal = new AbortController().signal;
  const output = [];
  for await (const item of modelStream(ctx, {effort: 'max', messages: [{role: 'user', content: [{type: 'text', text: 'paper'}]}]}, signal)) output.push(item);
  assert.equal(output[0].provider, 'deepseek-account');
  assert.equal(seen[0].config.provider, 'deepseek-account');
  assert.equal(seen[0].config.reasoningEffort, 'max');
  assert.equal(seen[1].maxTokens, 1000);
  assert.equal(seen[1].signal, signal);
});

test('page images are admitted through the Harness attachment store', async () => {
  const {ctx, seen} = harness();
  for await (const _ of modelStream(ctx, {messages: [{role: 'user', content: [{type: 'inline-image', url: 'data:image/png;base64,aW1hZ2U='}]}]}, new AbortController().signal)) {}
  assert.equal(seen[1][0].data.toString(), 'image');
  assert.deepEqual(seen[2].messages[0].content, [{type: 'image', attachment: {id: 'image'}}]);
});

test('private bridge refuses missing secrets and cross-origin requests', async t => {
  const {ctx} = harness();
  const server = createModelBridge(ctx, 'test-secret');
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  t.after(() => server.close());
  const base = `http://127.0.0.1:${server.address().port}`;
  assert.equal((await fetch(base + '/state')).status, 403);
  assert.equal((await fetch(base + '/state', {headers: {Authorization: 'Bearer test-secret', Origin: 'https://example.com'}})).status, 403);
  const response = await fetch(base + '/state', {headers: {Authorization: 'Bearer test-secret'}});
  assert.equal(response.status, 200);
  assert.equal((await response.json()).provider, 'deepseek-account');
});

test('provider diagnostics never expose credential-bearing exceptions', () => {
  assert.ok(!JSON.stringify(safeFailure(new Error('secret-auth-token'))).includes('secret-auth-token'));
});

/** Lay out a fake package directory with the given interpreter files. */
function packageWith(files) {
  const root = mkdtempSync(path.join(tmpdir(), 'prc-interpreter-'));
  for (const relative of files) {
    const target = path.join(root, relative);
    mkdirSync(path.dirname(target), {recursive: true});
    writeFileSync(target, '');
  }
  return root;
}

test('a POSIX build finds the virtual environment interpreter', t => {
  const root = packageWith(['runtime/venv/bin/python3']);
  t.after(() => rmSync(root, {recursive: true, force: true}));
  assert.equal(resolveInterpreter(root), path.join(root, 'runtime/venv/bin/python3'));
});

test('Windows keeps preferring its bundled interpreter over runtime/venv', t => {
  const root = packageWith(['runtime/python/python.exe', 'runtime/venv/bin/python3']);
  t.after(() => rmSync(root, {recursive: true, force: true}));
  assert.equal(resolveInterpreter(root), path.join(root, 'runtime/python/python.exe'));
});

test('config.python overrides every bundled interpreter', t => {
  const root = packageWith(['runtime/python/python.exe', 'custom/python3']);
  t.after(() => rmSync(root, {recursive: true, force: true}));
  const custom = path.join(root, 'custom/python3');
  assert.equal(resolveInterpreter(root, {python: custom}), custom);
});

test('a package without any runtime reports nothing to launch', t => {
  const root = packageWith(['host/index.js']);
  t.after(() => rmSync(root, {recursive: true, force: true}));
  assert.equal(resolveInterpreter(root), undefined);
});
