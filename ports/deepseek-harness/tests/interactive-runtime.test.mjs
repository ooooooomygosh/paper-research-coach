import test from 'node:test';
import assert from 'node:assert/strict';
import path from 'node:path';
import {existsSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import {spawnSync} from 'node:child_process';

const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const require=createRequire(path.join(root,'upstream/frontend/package.json'));
const {JSDOM,VirtualConsole}=require('jsdom');
const portable=path.join(root,'runtime/python/python.exe');
const python=process.env.PRC_TEST_PYTHON||(existsSync(portable)?portable:'python');
function fixture(kind){
  const value={kind,title:'Synthetic interactive explanation',summary:'Compare evidence under explicit conditions.'};
  if(['steps','concepts'].includes(kind))value.items=[{title:'Conditions',detail:'Match the budget first.'},{title:'Boundary',detail:'Keep the remaining alternatives.'}];
  if(kind==='comparison')Object.assign(value,{columns:['A','B'],rows:[{label:'Budget',values:['same','same'],explanation:'Matched.'},{label:'Data',values:['known','missing'],explanation:'Verify data coverage.'}]});
  if(kind==='evidence')Object.assign(value,{question:'What should be checked first?',options:['Budget','Universal success'],answer:0,explanation:'The reference first checks budget matching.'});
  if(kind==='parameters')Object.assign(value,{family:'linear',parameters:[{name:'a',label:'Slope',unit:'dimensionless',minimum:0,maximum:2,value:1},{name:'b',label:'Offset',unit:'dimensionless',minimum:-1,maximum:1,value:0}],assumptions:'Illustrative, not experimental data.'});
  return value;
}
function open(kind){
  const rendered=spawnSync(python,['-X','utf8','-c','import sys,json;from paper_research_coach.interactive_page import grounded_page,render_page;print(render_page(grounded_page(sys.stdin.read(),[]),"page-runtime-test"))'],{
    cwd:root,env:{...process.env,PYTHONUTF8:'1',PYTHONPATH:path.join(root,'upstream/src')},input:JSON.stringify(fixture(kind)),encoding:'utf8'});
  assert.equal(rendered.status,0,rendered.stderr);
  const errors=[],console=new VirtualConsole();console.on('jsdomError',e=>errors.push(e.message));
  const dom=new JSDOM(rendered.stdout,{url:'https://fixture.invalid',runScripts:'dangerously',virtualConsole:console});
  assert.deepEqual(errors,[]);return {dom,window:dom.window,document:dom.window.document,errors};
}
test('real parameter artifact recalculates locally and carries current values back',()=>{
  const {dom,window,document:d,errors}=open('parameters');
  const prior=d.querySelector('[data-current-curve]').getAttribute('d'),input=d.querySelector('input[aria-label=Slope]');
  input.value='1.6';input.dispatchEvent(new window.Event('input',{bubbles:true}));input.dispatchEvent(new window.Event('change',{bubbles:true}));
  assert.notEqual(d.querySelector('[data-current-curve]').getAttribute('d'),prior);
  assert.match(d.querySelector('.current').textContent,/1.6/);
  let question;d.addEventListener('prc-question',e=>question=e.detail.text);d.getElementById('ask').click();
  assert.match(question,/1.6/);assert.match(question,/教学假设/);
  assert.equal(JSON.parse(window.localStorage.getItem('prc-interactive:page-runtime-test')).params.a,1.6);
  assert.deepEqual(errors,[]);dom.window.close();
});
test('method steps and concept selections change the displayed explanation',()=>{
  for(const kind of ['steps','concepts']){
    const {dom,document:d}=open(kind);const buttons=Array.from(d.querySelectorAll('.nodes button'));
    buttons[1].click();assert.match(d.querySelector('.detail').textContent,/remaining alternatives/);
    assert.equal(buttons[1].getAttribute('aria-pressed'),'true');
    if(kind==='steps'){const back=Array.from(d.querySelectorAll('button')).find(b=>b.textContent==='上一步');back.click();assert.match(d.querySelector('.detail').textContent,/Match the budget/);}
    dom.window.close();
  }
});
test('comparison filters rows and reveals a selected reason',()=>{
  const {dom,window,document:d}=open('comparison');assert.equal(d.querySelectorAll('tbody tr').length,2);
  const toggle=d.querySelector('input[type=checkbox]');toggle.checked=true;toggle.dispatchEvent(new window.Event('change'));
  assert.equal(d.querySelectorAll('tbody tr').length,1);d.querySelector('tbody button').click();assert.match(d.querySelector('.detail').textContent,/data coverage/);dom.window.close();
});
test('evidence does not expose the reference before an explicit reveal',()=>{
  const {dom,window,document:d}=open('evidence');assert.equal(d.querySelector('.answer').hidden,true);
  assert.equal(d.querySelector('input:checked'),null);
  Array.from(d.querySelectorAll('button')).find(b=>b.textContent==='对照参考解释').click();assert.equal(d.querySelector('.answer').hidden,true);
  const choice=d.querySelector('input[type=radio]');choice.checked=true;choice.dispatchEvent(new window.Event('change'));
  Array.from(d.querySelectorAll('button')).find(b=>b.textContent==='对照参考解释').click();assert.equal(d.querySelector('.answer').hidden,false);assert.match(d.querySelector('.answer').textContent,/不是独立掌握度/);dom.window.close();
});
