import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync, writeFileSync, readFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import path from 'node:path';
import {renderExplainer} from '../host/studio-renderer.mjs';
import {createModelBridge} from '../host/index.js';

const source = `---
title: 学习一个判断过程
---
先确认条件，再检验证据。
## A 判断流程
\`\`\`flow
问题 -> 证据: 检查
证据 -> 结论: 比较
\`\`\`
## B 试着判断
\`\`\`ask
下一步要做什么？
* 核对原文 | 先找依据
- 直接推广结论 | 可能遗漏条件
\`\`\`
`;

test('real private entry renders an interactive standalone artifact', async t => {
  const bridge = createModelBridge({}, 'test-render-secret');
  await new Promise(resolve => bridge.listen(0, '127.0.0.1', resolve));
  t.after(() => { bridge.closeAllConnections(); bridge.close(); });
  const response = await fetch(`http://127.0.0.1:${bridge.address().port}/render-html`, {method: 'POST', headers: {authorization: 'Bearer test-render-secret'}, body: JSON.stringify({source})});
  assert.equal(response.status, 200);
  const artifact = await response.json();
  const target = path.join(mkdtempSync(path.join(tmpdir(), 'prc-studio-')), 'explainer.html');
  writeFileSync(target, artifact.html);
  assert.match(readFileSync(target, 'utf8'), /class="am-ask"/);
  assert.match(artifact.html, /sha256-/);
  assert.match(artifact.html, /<svg/);
  assert.equal(artifact.meta.theme, 'paper');
});

test('drafts cannot embed arbitrary host images or code files', async () => {
  await assert.rejects(renderExplainer({source: '---\ntitle: Test\n---\n## A Image\n![image](C:/private/image.png)'}), /不读取|内联图片/);
  await assert.rejects(renderExplainer({source: '---\ntitle: Test\n---\n## A Code\n```js src=private.js\n```'}), /不从草稿路径读取/);
});

test('renderer keeps upstream support for math and sortable tables', async () => {
  const result = await renderExplainer({source: '---\ntitle: Evidence\n---\n## A Formula\n$x^2$\n\n| Item | Value |\n|---|---|\n| A | 1 |\n\n{table sort filter}\n'});
  assert.match(result.html, /<math/);
  assert.ok(result.html.includes('<table') && result.html.includes('data-am-table'));
});
