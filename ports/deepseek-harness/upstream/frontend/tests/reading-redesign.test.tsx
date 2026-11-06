import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ReadingPromptButton, { standardReadingText } from '../src/ReadingPromptButton';
import GlobalTranslation from '../src/GlobalTranslation';
import InteractiveStudio from '../src/InteractiveStudio';
import ArtifactFrame from '../src/ArtifactFrame';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); localStorage.clear(); });

it('exports the attributed reading guide in one click without an account request', () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  const create = vi.fn(() => 'blob:reading');
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: create });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  render(<ReadingPromptButton paper={{ title: 'Synthetic paper', source_version: 'v2' }} page={3} />);
  fireEvent.click(screen.getByRole('button', { name: '标准阅读' }));
  expect(click).toHaveBeenCalledOnce(); expect(create).toHaveBeenCalledOnce();
  expect(fetch).not.toHaveBeenCalled();
  const text = standardReadingText({ title: 'Synthetic paper', source_version: 'v2' }, 3);
  expect(text).toContain('当前 PDF 物理页：4'); expect(text).toContain('Ow8fw2HtEiixDgkWlkbckdvHnef');
  expect(text).toContain('docs/METHOD.md'); expect(text).toContain('不按篇数');
});

it('opens the existing batch queue from the global panel without starting translation', async () => {
  const requests: { path: string; method?: string }[] = [];
  vi.stubGlobal('fetch', vi.fn(async (path: string, init?: any) => {
    requests.push({ path, method: init?.method });
    const data = path.endsWith('coach/status') ? { models: [] }
      : path.endsWith('translation/settings') ? { model: 'deepseek', component: { ready: true } }
      : { data: [], papers: {} };
    return { ok: true, json: async () => data };
  }));
  const close = vi.fn();
  render(<GlobalTranslation papers={[]} job={null} readableJob={null} reload={vi.fn()} onClose={close} onRead={vi.fn()} />);
  await screen.findByRole('region', { name: '后台批量翻译' });
  await waitFor(() => expect(requests.some(r => r.path.endsWith('translation/jobs'))).toBe(true));
  expect(requests.some(r => r.method === 'POST')).toBe(false);
  fireEvent.click(screen.getByRole('button', { name: '关闭翻译面板' }));
  expect(close).toHaveBeenCalledOnce();
  expect(requests.some(r => /stop|cancel/.test(r.path))).toBe(false);
});

it('explicitly selects account-generated components and binds a source version', async () => {
  let row: any = { id: 's1', revision: 1, title: 'Synthetic', question: 'Explain', source: '', presentation: 'document', language: 'zh', theme: 'paper', template: 'doc', context: {}, history: [] };
  const writes: any[] = [];
  vi.stubGlobal('fetch', vi.fn(async (path: string, init?: any) => {
    const value = init?.body && JSON.parse(init.body);
    if (init?.method === 'PUT') { writes.push(value); row = { ...row, ...value }; }
    if (path.endsWith('/generate')) writes.push({ generation: true });
    return { ok: true, json: async () => row };
  }));
  render(<InteractiveStudio id="s1" jobs={[]} kbs={[]} page={2} paper={{ id: 'p', source_version: 'v2' }} reload={vi.fn()} report={vi.fn()} />);
  await screen.findByLabelText('讲解形式');
  fireEvent.change(screen.getByLabelText('讲解形式'), { target: { value: 'components' } });
  fireEvent.click(screen.getByRole('button', { name: '使用当前论文页' }));
  fireEvent.click(screen.getByRole('button', { name: '生成交互式讲解' }));
  await waitFor(() => expect(writes.some(v => v.generation)).toBe(true));
  expect(writes[0].presentation).toBe('components');
  expect(writes[0].context).toMatchObject({ paper_id: 'p', source_version: 'v2', page_index: 2 });
});

it('locates the selected publication through its callback, ignoring message-supplied anchors', () => {
  const locate = vi.fn(), fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  render(<ArtifactFrame kind="studio" id="s1" version="v1" title="Synthetic page" onQuestion={vi.fn()} onLocate={locate} report={vi.fn()} />);
  const frame = screen.getByTitle('Synthetic page') as HTMLIFrameElement;
  window.dispatchEvent(new MessageEvent('message', { source: frame.contentWindow, data: { channel: 'prc-workspace-v1', scope: { id: 's1', type: 'studio' }, kind: 'locate', anchor: { paper_id: 'arbitrary' } } }));
  expect(locate).toHaveBeenCalledWith(); expect(fetch).not.toHaveBeenCalled();
  window.dispatchEvent(new MessageEvent('message', { source: frame.contentWindow, data: { channel: 'prc-workspace-v1', scope: { id: 'another', type: 'studio' }, kind: 'locate' } }));
  expect(locate).toHaveBeenCalledTimes(1);
});

it('brings a page question into the collapsed composer without sending it', async () => {
  const fetch = vi.fn(async () => ({ ok: true, json: async () => ({ id: 's1', revision: 1, title: 'Saved explanation', question: 'Earlier question', source: '', presentation: 'components', language: 'zh', context: {}, history: [], published: { version: 'v1', title: 'Saved page', format: 'components' } }) }));
  vi.stubGlobal('fetch', fetch);
  render(<InteractiveStudio id="s1" jobs={[]} kbs={[]} page={0} reload={vi.fn()} report={vi.fn()} />);
  const frame = await screen.findByTitle('Saved page') as HTMLIFrameElement;
  const question = screen.getByLabelText('交互式讲解问题');
  Object.defineProperty(question, 'scrollIntoView', { value: vi.fn(), configurable: true });
  expect(question.closest('details')?.open).toBe(false);
  window.dispatchEvent(new MessageEvent('message', { source: frame.contentWindow, data: { channel: 'prc-workspace-v1', scope: { id: 's1', type: 'studio' }, kind: 'question', text: 'Explain the current slope = 2' } }));
  await waitFor(() => expect(document.activeElement).toBe(question));
  expect(question.closest('details')?.open).toBe(true);
  expect((question as HTMLTextAreaElement).value).toContain('slope = 2');
  expect(fetch).toHaveBeenCalledOnce();
});
