import { describe, expect, it } from 'vitest';
import { studyMessage } from '../src/PaperStudy';

describe('study source navigation trust boundary', () => {
  const anchor = { paper_id: 'actual-paper', page_index: 3, source_version: 'original' };
  const study = { id: 'study-1', revision: 5, paragraphs: [{ id: 'trusted-paragraph', anchor }] };
  const data = { channel: 'prc-study-v1', id: study.id, revision: 5, anchor_id: 'trusted-paragraph' };
  it('looks up source on the host and ignores coordinates supplied by a page', () => {
    expect(studyMessage(new MessageEvent('message', { source: window, data: {...data, anchor: {paper_id: 'forged', page_index: 99}} }), window, study)).toEqual(anchor);
  });
  it('rejects other windows, stale versions and unknown paragraphs', () => {
    expect(studyMessage(new MessageEvent('message', {data}), window, study)).toBeNull();
    expect(studyMessage(new MessageEvent('message', {source: window, data: {...data, revision: 4}}), window, study)).toBeNull();
    expect(studyMessage(new MessageEvent('message', {source: window, data: {...data, anchor_id: 'forged'}}), window, study)).toBeNull();
    expect(studyMessage(new MessageEvent('message', {source: window, data: {...data, id: 'other-study'}}), window, study)).toBeNull();
  });
});
