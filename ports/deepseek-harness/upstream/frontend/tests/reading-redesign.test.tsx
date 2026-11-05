import React from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import ReadingPromptButton, { standardReadingText } from '../src/ReadingPromptButton';
import GlobalTranslation from '../src/GlobalTranslation';

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
