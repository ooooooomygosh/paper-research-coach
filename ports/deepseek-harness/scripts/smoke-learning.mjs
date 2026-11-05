/** Real signed-in-account verification. Inputs below are synthetic teaching text. */
import assert from 'node:assert/strict';
import {writeFileSync} from 'node:fs';
import path from 'node:path';

export async function smokeLearning({origin, cookie, pkg}) {
  const base = origin + '/paper-research-coach/api/workspace';
  const request = async (endpoint = '', body, method = body === undefined ? 'GET' : 'POST', raw = false) => {
    const response = await fetch(base + endpoint, {method, headers: {cookie, origin, ...(raw ? {'content-type': 'application/octet-stream'} : body === undefined ? {} : {'content-type': 'application/json'})}, body: body === undefined ? undefined : raw ? body : JSON.stringify(body)});
    const text = await response.text();
    assert.ok(response.ok, `${endpoint}: HTTP ${response.status}: ${text.slice(0, 800)}`);
    return JSON.parse(text);
  };
  async function wait(job) {
    const deadline = Date.now() + 600000;
    let previous = '';
    while (['queued', 'running'].includes(job.state) && Date.now() < deadline) {
      await new Promise(resolve => setTimeout(resolve, 1500));
      job = await request('/jobs/' + job.id);
      const stage = `${job.stage}:${job.done}/${job.total}`;
      if (stage !== previous) { console.log(JSON.stringify({test: 'live-learning-progress', kind: job.kind, stage, state: job.state})); previous = stage; }
    }
    assert.equal(job.state, 'completed', JSON.stringify({state: job.state, message: job.message, stage: job.stage}));
    return job;
  }
  const kb = await request('/kbs', {title: '合成资料 · 学习功能验收', depth: 'systematic'});
  const texts = [
    ['evidence.md', '# 证据阅读法\n\n证据阅读法包含三个步骤。第一步提出一个可核对的问题，输入是阅读目标，输出是具体的问题句。第二步回到材料寻找直接依据，输入是问题，输出是逐字引文及其位置。第三步核对依据是否真的支持结论，输入是引文和结论，输出是支持、部分支持或不支持的判断。每一步都应留下可以复查的记录。\n\n这种方法适用于核查文本材料中的主张。它不负责判断图像里未提取的细节，也不能证明研究结论普遍正确。若材料没有给出足够依据，应写明信息不足。'],
    ['practice.txt', '间隔复习是一种学习安排：完成首次阅读后，隔一段时间尝试回忆要点，再回到原文核对。检验产出是自己复述的内容和原文之间的差异。复习的目标是发现忘记或误解之处。这里没有给定固定的间隔天数，也没有提供改善分数的保证。\n\n复习记录应区分“已经看过”和“能够解释”。选择题只能反映一次具体作答，不等于已经掌握整个主题。']
  ];
  for (const [name, text] of texts) await request(`/kbs/${kb.id}/materials?filename=${encodeURIComponent(name)}`, Buffer.from(text), 'POST', true);
  await wait(await request(`/kbs/${kb.id}/build`, {resume: false}));
  let detail = await request('/kbs/' + kb.id);
  assert.ok(detail.page.contentUnits.length >= 2);
  assert.equal(detail.coverage.processed_blocks, detail.coverage.total_blocks);
  assert.ok(detail.questions.length >= 2);
  const methods = await request('/methods');
  assert.ok(methods.methods.some(entry => entry.kb_id === kb.id));
  const unit = detail.page.contentUnits[0], question = detail.questions[0];
  await request(`/kbs/${kb.id}/progress`, {unit_id: unit.id, completed: true, note: '合成验收：可以用自己的话复述。', version: detail.viewing.version}, 'PUT');
  const attempt = await request(`/kbs/${kb.id}/attempts`, {question_id: question.id, answer: question.correct, version: detail.viewing.version});
  assert.equal(attempt.correct, true);
  await wait(await request(`/kbs/${kb.id}/ask`, {question: '证据阅读法有哪些步骤？这种方法有什么限制？', version: detail.viewing.version}));
  detail = await request('/kbs/' + kb.id);
  const answer = detail.chat.filter(turn => turn.role === 'assistant').at(-1);
  assert.ok(answer.content.length > 20);
  assert.ok(answer.citations.length);
  for (const citation of answer.citations) {
    const source = await request(`/kbs/${kb.id}/sources/${citation.block_id}?version=${detail.viewing.version}`);
    assert.ok(source.text.includes(citation.quote));
  }
  const studio = await request('/studios', {question: '用一个流程图和一个互动选择题解释证据阅读法，保留适用条件和局限。', context: {kb_id: kb.id, version: detail.viewing.version}});
  await wait(await request(`/studios/${studio.id}/generate`, {}));
  const page = await request('/studios/' + studio.id);
  for (const [kind, record] of [['kb', detail], ['studio', page]]) {
    const document = await fetch(base + `/view/${kind}/${record.id}`, {headers: {cookie}});
    assert.equal(document.status, 200);
    assert.match(document.headers.get('content-security-policy'), /sandbox allow-scripts/);
    assert.doesNotMatch(document.headers.get('content-security-policy'), /allow-same-origin/);
    const html = await document.text();
    assert.match(html, /prc-workspace-v1/);
    assert.match(html, /Content-Security-Policy/);
    assert.ok(html.length > 10000);
  }
  const output = {provider: 'deepseek-account', inputs: 'synthetic', kb_id: kb.id, studio_id: studio.id, units: detail.page.contentUnits.length, methods: methods.methods.filter(entry => entry.kb_id === kb.id).length, questions: detail.questions.length, citations: answer.citations.length, processing: detail.coverage, studioVersion: page.published.version};
  writeFileSync(path.join(pkg, '.test-learning-result.json'), JSON.stringify(output, null, 2));
  console.log(JSON.stringify({test: 'live-account-two-features', ...output}));
}
