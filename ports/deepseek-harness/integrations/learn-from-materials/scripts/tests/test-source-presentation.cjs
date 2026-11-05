// Pure formatting and in-memory DOM tests. No real browser layout acceptance.
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {forPage}=require('../../templates/source-presentation.js');
const {createDOM}=require('./support/memory-dom.cjs');
const root=path.resolve(__dirname,'../..');
const raw='book.pdf · 第1章《冒险家》 · 原书第009页 · PDF第017页';
const display='book.pdf · Chapter 1 “Adventurer” · Printed p. 009 · PDF p. 017';
const data={meta:{language:'en'},sourceLabels:{[raw]:display}};

test('English presentation has exact labels and citation-container suffixes',()=>{
  const before=JSON.stringify(data),ui=forPage(data);
  assert.equal(ui.display(raw),display);
  assert.equal(ui.text('Conclusion range · '+raw),'Conclusion range · '+display);
  assert.equal(JSON.stringify(data),before);
});
test('Chinese presentation retains source label verbatim',()=>{
  const ui=forPage({...data,meta:{language:'zh-CN'}});
  assert.equal(ui.display(raw),raw);assert.equal(ui.text(raw),raw);
});
test('Fallback translates locator syntax and never invents chapter-title translations',()=>{
  const ui=forPage({meta:{language:'en'}});
  assert.equal(ui.display(raw),'book.pdf · Chapter 1《冒险家》 · Printed pp. 009 · PDF pp. 017');
  assert.equal(ui.display('材料.pdf · PDF第17页'),'材料.pdf · PDF pp. 17');
});
test('Framework and action prefixes are idempotent in English',()=>{
  const ui=forPage(data);
  for(const input of ['When reading','When When reading','Applies when: When reading'])assert.equal(ui.frameworkCondition(input),'Applies when: reading');
  assert.equal(ui.ruleCondition('When When ready'),'When ready');
  for(const input of ['Whenever ready','Before launch','After review','If supported','During review'])assert.equal(ui.ruleCondition(input),input);
});
test('Chinese conditions retain word beginnings and avoid duplicated 当',()=>{
  const ui=forPage({meta:{language:'zh-CN'}});
  assert.equal(ui.ruleCondition('当 当 图表显示上涨时'),'当 图表显示上涨时');
  for(const input of ['当前信息不足时','当地供给不足时','在信息不足时','如果信息不足'])assert.equal(ui.ruleCondition(input),input);
  assert.equal(ui.frameworkCondition('适用：适用：阅读时'),'适用：阅读时');
});
test('Original citation uses textContent in an accessible disclosure',()=>{
  const dom=createDOM(),script=dom.make('script','pageData');script.textContent=JSON.stringify(data);
  dom.run(path.join(root,'templates/source-presentation.js'));
  const host=dom.make('div');dom.context.LFMSourcePresentation.forPage(data).original(host,raw);
  assert.equal(host.querySelector('.source-original').querySelector('summary').textContent,'Original source label');
  assert.equal(host.querySelector('p').textContent,raw);
});
test('Framework line click uses the passed formatter without a free page-data variable',()=>{
  const dom=createDOM();for(const name of ['hover-bridge.js','scroll-chain.js','source-presentation.js','framework-routing.js','relationship-mindmap.js'])dom.run(path.join(root,'templates',name));
  const ui=dom.context.LFMSourcePresentation.forPage(data);
  dom.context.LFMMindMap.mount(dom.make('div'),{language:'en',title:'Map',
    nodes:[{id:'a',title:'Start'},{id:'b',title:'Next'}],
    edges:[{id:'ab',from:'a',to:'b',label:'Supports',evidence:'material',explanation:'Explained connection',source:raw}],
    sourceText:ui.text,sourceOriginal:ui.original,
    describe:id=>{const f=dom.document.createDocumentFragment();f.append(dom.make('p',null,f));return f;}});
  dom.flush();dom.document.querySelector('.lfm-mm-edge-label').click();
  const hover=dom.document.querySelector('.lfm-mm-hover');
  assert(hover.querySelector('.hover-source').textContent.includes(display));
  assert.equal(hover.querySelector('.source-original').querySelector('p').textContent,raw);
});
test('Methodology details localize citations while preserving raw evidence and IDs',()=>{
  const page=JSON.parse(fs.readFileSync(path.join(root,'examples/overview-methods-content.json'),'utf8'));
  page.sourceLabels={};
  for(const n of page.methodology.nodes)for(const s of n.sources){s.source=raw;page.sourceLabels[raw]=display;}
  for(const e of page.methodology.edges)e.source=raw;
  const before=JSON.stringify(page),dom=createDOM();dom.make('script','pageData').textContent=before;
  const host=dom.make('section','rules');dom.make('div',null,host).className='content-stream';
  const template=dom.make('template','wholeMethodTemplate');template.content=dom.document.createDocumentFragment();
  const whole=dom.make('section','wholeMethod',template.content);dom.make('div','methodMap',whole);dom.make('div','methodNodeDetail',whole);
  let options;dom.context.LFMGraphStudio={mount:(_host,value)=>{options=value;return{refresh(){}};}};
  dom.run(path.join(root,'templates/source-presentation.js'));dom.run(path.join(root,'templates/methodology.js'));dom.flush();
  const fragment=options.describe(page.methodology.nodes[0].id);
  assert(fragment.querySelector('.relation-source').textContent.includes(display));
  assert.equal(fragment.querySelector('.source-original').querySelector('p').textContent,raw);
  assert.equal(JSON.stringify(page),before);
});
