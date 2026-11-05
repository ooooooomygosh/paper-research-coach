'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createDOM}=require('./support/memory-dom.cjs');
const root=path.resolve(__dirname,'../..');

function fixture(language,change){
  const data=JSON.parse(fs.readFileSync(language==='en'?path.join(root,'examples/overview-en-content.json'):path.join(__dirname,'fixtures/methodology-zh.json'),'utf8'));
  if(change)change(data);
  const before=JSON.stringify(data),dom=createDOM(),pageData=dom.make('script','pageData');pageData.textContent=JSON.stringify(data);
  const host=dom.make('section','rules'),anchor=dom.make('div',null,host);anchor.className='content-stream';
  const template=dom.make('template','wholeMethodTemplate');template.content=dom.document.createDocumentFragment();
  const whole=dom.make('section','wholeMethod',template.content);dom.make('div','methodMap',whole);dom.make('div','methodNodeDetail',whole);
  let options;
  dom.context.LFMGraphStudio={mount:(_host,config)=>{options=config;return{refresh(){}};}};
  dom.run(path.join(root,'templates/source-presentation.js'));dom.run(path.join(root,'templates/methodology.js'));dom.flush();
  assert(options,'ready methodology is mounted');assert.equal(JSON.stringify(data),before,'fixture canonical data is unchanged');
  return{data,dom,options,detail:dom.document.getElementById('methodNodeDetail')};
}

for(const language of ['zh-CN','en']){
  const en=language==='en';
  test(`${language}: node and relation details share colon headings and bracketed metadata`,()=>{
    const f=fixture(language);
    assert.equal(f.options.language,language);assert.equal(f.options.nodes.length,f.data.methodology.nodes.length);assert.equal(f.options.edges.length,f.data.methodology.edges.length);
    for(const edge of f.options.edges){const original=f.data.methodology.edges.find(e=>e.id===edge.id);for(const key of Object.keys(original))assert.equal(edge[key],original[key],'display aliases preserve canonical '+key);}
    for(const n of f.data.methodology.nodes){
      const hover=f.options.describe(n.id),headings=hover.querySelectorAll('dt');
      assert.equal(headings.length,4);for(const dt of headings)assert(dt.textContent.endsWith(en?':':'：'));
      assert.deepEqual(hover.querySelectorAll('dd').map(n=>n.textContent),['input','action','output','check'].map(k=>n[k]));
      assert(hover.textContent.includes(n.sources[0].source),'full original locator survives');
      f.options.onSelect(n.id);assert.deepEqual(f.detail.querySelectorAll('dt').map(n=>n.textContent),headings.map(n=>n.textContent));
      assert.deepEqual(f.detail.querySelectorAll('li').map(n=>n.textContent),hover.querySelectorAll('li').map(n=>n.textContent),'hover and locked relationship details agree');
      for(const li of hover.querySelectorAll('li')){
        assert(li.querySelector('strong').textContent.includes(' → '));
        const metadata=li.querySelector('small').textContent;
        assert(en?/^ \(.+\)$/.test(metadata):/^（.+）$/.test(metadata),'only relation metadata is bracketed');
      }
      if(en)assert(!/[\u3400-\u9fff]/u.test(hover.textContent),'English detail has no accidental Chinese UI strings');
    }
    const branch=f.options.edges.find(e=>e.kind==='branch');assert.equal(branch.label,en?'Only when conditions are met':'满足条件才做');
    const edgeHover=f.options.describe(branch.from,branch.id);assert.equal(edgeHover.querySelectorAll('li').length,1,'line details show only that edge');
    const buttons=f.dom.document.querySelectorAll('.action-view-button');buttons[1].click();assert(!f.dom.document.querySelector('.action-graph-view').hidden);buttons[0].click();assert(f.dom.document.querySelector('.action-graph-view').hidden);
  });
  test(`${language}: concrete feedback labels preserve ratio/time/URL punctuation`,()=>{
    const condition=en?'At 12:30 or odds 2:1, revisit https://example.test/rule':'12:30 或比例 2:1 时，重新查阅 https://example.test/rule';
    const f=fixture(language,data=>data.methodology.edges.find(e=>e.kind==='feedback').condition=condition);
    const edge=f.options.edges.find(e=>e.kind==='feedback');assert.equal(edge.label,condition);
    assert(f.options.describe(edge.from,edge.id).textContent.includes(condition));
  });
  test(`${language}: action-rule display prefixes are added exactly once`,()=>{
    for(const condition of en?['When the scope changes','the scope changes',' WHEN the scope changes ']:['当范围变化','范围变化',' 当范围变化 ']){
      const f=fixture(language,data=>data.decisionRules[0].when=condition),node=f.data.methodology.nodes[0],hover=f.options.describe(node.id);
      const displayed=hover.querySelector('.method-linked-rule').querySelector('p').textContent;
      assert.equal(displayed,/^(?:当|when\b)/i.test(condition.trim())?condition.trim():(en?'When ':'当 ')+condition.trim());
      assert(!/当\s*当|when\s+when/i.test(displayed));
      assert(hover.querySelector('.method-linked-rules').querySelector('summary').textContent.endsWith(en?')':'）'),'balanced summary parentheses');
    }
  });
  test(`${language}: non-procedural graphs describe premises without inventing a next step`,()=>{
    const f=fixture(language,data=>{data.methodology.structure='causal';data.methodology.mainPath=[];data.methodology.edges[0].kind='causes';});
    const edge=f.options.edges[0],hover=f.options.describe(edge.from,edge.id);
    assert.equal(hover.querySelector('dt').textContent,en?'Premises:':'已知条件：');
    assert(hover.textContent.includes(en?'When this relationship holds: ':'这条关系何时成立：'));
  });
  test(`${language}: every relation kind keeps its identity while displaying readable metadata`,()=>{
    const labels={main:en?'Next':'接着做',branch:en?'Only when conditions are met':'满足条件才做',supports:en?'Supports':'提供支持',contains:en?'Contains':'包含 / 属于',causes:en?'Causes':'促成 / 导致',prerequisite:en?'Prerequisite':'先要具备',parallel:en?'In parallel':'并行 / 并列',contrasts:en?'Comparison':'对比'};
    for(const kind of [...Object.keys(labels),'feedback']){
      const f=fixture(language,data=>data.methodology.edges[2].kind=kind),edge=f.options.edges[2],expected=kind==='feedback'?edge.condition.trim():labels[kind];
      assert.equal(edge.kind,kind);assert.equal(edge.label,expected);assert(f.options.describe(edge.from,edge.id).querySelector('small').textContent.includes(expected));
    }
  });
}
