const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const script=fs.readFileSync(path.join(__dirname,'../../templates/visual-interactions.js'),'utf8');
function setup(){
  const listeners={},animations=[],observers=[],button={disabled:false,addEventListener(_,fn){this.click=fn},setAttribute(){}};
  const animate=()=>{const a={cancelled:false,cancel(){this.cancelled=true;this.oncancel?.()}};animations.push(a);return a};
  const panels={first:{animate},second:{animate}};
  const active={dataset:{panel:'first'},offsetWidth:100,offsetLeft:0};
  const tabs={querySelector:()=>active,append(){},classList:{add(){}},clientWidth:600,scrollLeft:0};
  const media={matches:false,addEventListener(_,fn){this.change=fn}};
  const document={body:{dataset:{}},getElementById(id){return id==='pageData'?{textContent:'{"meta":{"pageId":"test"}}'}:id==='motionToggle'?button:panels[id]},querySelector:()=>tabs,createElement:()=>({style:{},setAttribute(){}}),addEventListener(name,fn){(listeners[name]??=[]).push(fn)},dispatchEvent(e){for(const fn of listeners[e.type]||[])fn(e)}};
  const sandbox={document,window:{addEventListener(){}},matchMedia:()=>media,localStorage:{getItem(){return null},setItem(){}},requestAnimationFrame:fn=>fn(),MutationObserver:class{constructor(fn){observers.push(fn)}observe(){}},Event:class{constructor(type){this.type=type}}};
  vm.runInNewContext(script,sandbox);
  return {document,button,media,animations,changePanel(){active.dataset.panel='second';observers[0]()},click(target){document.dispatchEvent({type:'click',target,defaultPrevented:false,preventDefault(){}})}};
}
test('motion off cancels an active module entrance and notifies diagram lifecycle',()=>{
  const s=setup();let changes=0;s.document.addEventListener('lfm-panel-change',()=>changes++);
  s.changePanel();assert.equal(changes,1);assert.equal(s.animations.length,1);
  s.button.click();assert(s.animations[0].cancelled);assert.equal(s.document.body.dataset.motion,'off');
});
test('rapid disclosure toggles and motion off settle to latest requested open state',()=>{
  const s=setup();const detail={open:false,matches:()=>true,getBoundingClientRect(){return {height:this.open?300:40}},animate(){const a={cancelled:false,cancel(){this.cancelled=true}};s.animations.push(a);return a}};
  const summary={parentElement:detail,closest(q){return q==='summary'?this:null}};
  s.click(summary);assert(detail.open);s.click(summary);assert(s.animations[0].cancelled);
  s.button.click();assert.equal(detail.open,false);assert(s.animations[1].cancelled);
});
test('system reduced motion cancels a running entrance and disables the toggle',()=>{
  const s=setup();s.changePanel();s.media.matches=true;s.media.change();
  assert(s.animations[0].cancelled);assert(s.button.disabled);assert.equal(s.document.body.dataset.motion,'off');
});
