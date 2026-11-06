import template from './assets/standard-reading.txt?raw';
import Icon from './Icon';

export function standardReadingText(paper?: { title?: string; source_version?: string }, page?: number) {
  const context = paper ? `当前文献：${paper.title || '未命名论文'}\n来源版本：${paper.source_version || '待核实'}\n当前 PDF 物理页：${(page || 0) + 1}\n\n` : '';
  return context + template;
}

export function downloadReadingPrompt(paper?: { title?: string; source_version?: string }, page?: number) {
  const url = URL.createObjectURL(new Blob([standardReadingText(paper, page)], { type: 'text/plain;charset=utf-8' }));
  const link = document.createElement('a');
  link.href = url; link.download = 'PaperResearchCoach-标准阅读提示.txt';
  document.body.append(link); link.click(); link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ReadingPromptButton({ paper, page }: { paper?: { title?: string; source_version?: string }; page?: number }) {
  return <button type="button" onClick={() => downloadReadingPrompt(paper, page)} title="一键导出七环节与证据阅读提示；不调用模型">
    <Icon name="download" />标准阅读
  </button>;
}
