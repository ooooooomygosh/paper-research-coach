import {renderDoc, loadMath} from '../integrations/answer-me-with-html/prc-renderer.mjs';

export async function renderExplainer({source, theme = 'paper', template = 'doc', language = 'zh'}) {
  if (typeof source !== 'string' || !source.trim() || source.length > 250_000) throw new Error('讲解草稿为空或超过页面大小限制。');
  if (!['paper', 'blueprint', 'shadcn'].includes(theme)) throw new Error('不支持的讲解主题。');
  if (!['doc', 'sheet'].includes(template)) throw new Error('不支持的讲解版式。');
  await loadMath(source);
  const {html, warnings, stats, meta} = renderDoc(source, {theme, template, lang: language, style: '80'});
  return {html, warnings, stats, meta};
}
