import test from 'node:test';
import assert from 'node:assert/strict';
import {modelState, modelStream, effortFor, DEFAULT_MODEL, DEFAULT_EFFORT} from '../host/model.js';

function ctxWith(models, selection) {
  return {
    get(name) {
      return {
        llm: {async listModels(provider) {assert.equal(provider, 'deepseek-account'); return models;}},
        agentDefaultModel: {currentSelection() {return selection;}},
      }[name];
    },
  };
}

test('the coach defaults to DeepSeek Flash at high reasoning', async () => {
  const ctx = ctxWith(
    [{id: 'gpt-6-luna', name: 'Luna'}, {id: 'deepseek-v4-pro', name: 'V4 Pro'}, {id: 'deepseek-flash', name: 'Flash'}],
    {provider: 'deepseek-account', model: 'deepseek-v4-pro'},
  );
  const state = await modelState(ctx);
  assert.equal(DEFAULT_MODEL, 'deepseek-flash');
  assert.equal(DEFAULT_EFFORT, 'high');
  assert.equal(state.model, 'deepseek-flash');
  assert.equal(state.defaultEffort, 'high');
});

test('the reported effort comes from the resolved model info', () => {
  const resolved = {
    model: 'deepseek-flash',
    models: [{id: 'deepseek-flash', supportedReasoningEfforts: [{reasoningEffort: 'off'}, {reasoningEffort: 'high'}], defaultReasoningEffort: 'high'}],
  };
  assert.equal(effortFor(resolved), 'high');
});

test('an account without Flash keeps its own default', async () => {
  const ctx = ctxWith([{id: 'deepseek-v4-pro'}, {id: 'gpt-6-luna'}], {provider: 'deepseek-account', model: 'gpt-6-luna'});
  assert.equal((await modelState(ctx)).model, 'gpt-6-luna');
});

test('reasoning effort never asks for a level the model does not declare', () => {
  const declared = {model: 'm', models: [{id: 'm', supportedReasoningEfforts: [{reasoningEffort: 'off'}, {reasoningEffort: 'max'}], defaultReasoningEffort: 'max'}]};
  assert.equal(effortFor(declared), 'max');
  const strings = {model: 'm', models: [{id: 'm', reasoning: {efforts: ['off', 'high'], defaultEffort: 'off'}}]};
  assert.equal(effortFor(strings), 'high');
  const silent = {model: 'm', models: [{id: 'm'}]};
  assert.equal(effortFor(silent), '');
});

test('a request without an effort inherits the declared default', async () => {
  const seen = [];
  const llm = {
    async listModels() {return [{id: 'deepseek-flash', name: 'Flash'}];},
    async resolveModelInfo() {return {reasoning: {efforts: [{id: 'off'}, {id: 'high'}, {id: 'max'}]}};},
    async prepareCall(config) {seen.push(config); return {config, async *stream() {yield {type: 'finish', reason: {kind: 'stop'}};}};},
  };
  const ctx = {get(name) {return {llm, agentDefaultModel: {currentSelection() {return undefined;}}, attachments: {async saveImages() {return [];}}}[name];}};
  for await (const _ of modelStream(ctx, {messages: [{role: 'user', content: [{type: 'text', text: 'paper'}]}]}, new AbortController().signal)) {}
  assert.equal(seen[0].reasoningEffort, 'high');
});
