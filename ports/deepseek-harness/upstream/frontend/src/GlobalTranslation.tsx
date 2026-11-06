import { useEffect, useRef, useState } from 'react';
import { TranslationTools } from './ReadingTools';
import TranslationLibrary from './TranslationLibrary';
import Icon from './Icon';
import type { Row } from './api';

export default function GlobalTranslation({ paper, papers, job, readableJob, reload, onClose, onRead }: {
  paper?: Row; papers: Row[]; job: any; readableJob: any; reload: () => void;
  onClose: () => void; onRead: (paperId: string) => void;
}) {
  const [mode, setMode] = useState(paper ? 'paper' : 'batch');
  const closeButton = useRef<HTMLButtonElement>(null), close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    closeButton.current?.focus();
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { event.preventDefault(); close.current(); } };
    document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('keydown', escape); if (previous?.isConnected) previous.focus(); };
  }, []);
  return <aside className="global-translation" aria-label="翻译与后台队列">
    <header><h2>翻译</h2><button ref={closeButton} type="button" aria-label="关闭翻译面板" onClick={onClose}><Icon name="close" /></button></header>
    <nav className="global-translation-tabs" aria-label="翻译范围">
      <button type="button" disabled={!paper} aria-pressed={mode === 'paper'} onClick={() => setMode('paper')}>当前论文</button>
      <button type="button" aria-pressed={mode === 'batch'} onClick={() => setMode('batch')}>批量后台翻译</button>
    </nav>
    <p className="small muted">切换页面或关闭面板后任务继续；退出 Harness 会保存进度，重启可恢复。</p>
    {mode === 'paper' && paper ? <TranslationTools key={paper.id + paper.source_version} paper={paper} job={job} readableJob={readableJob} reload={reload} open />
      : <TranslationLibrary papers={papers} onUpdate={reload} onRead={onRead} />}
  </aside>;
}
