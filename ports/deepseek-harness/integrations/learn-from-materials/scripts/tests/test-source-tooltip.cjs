'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const {createDOM}=require('./support/memory-dom.cjs');
const root=process.env.LFM_TOOLTIP_ROOT||path.resolve(__dirname,'../..');

function setup({width=1200,height=900,language='zh-CN'}={}){
  const dom=createDOM({width,height});
  let now=0,id=0;const timers=new Map();
  dom.context.setTimeout=(fn,delay=0)=>{timers.set(++id,{fn,at:now+delay});return id;};
  dom.context.clearTimeout=id=>timers.delete(id);
  function advance(milliseconds){
    const until=now+milliseconds;
    for(let safety=0;safety<100;safety++){
      const next=[...timers].filter(([,t])=>t.at<=until).sort((a,b)=>a[1].at-b[1].at)[0];
      if(!next)break;
      const [key,timer]=next;timers.delete(key);now=timer.at;timer.fn();
    }
    now=until;
  }
  const source='book.pdf · 第1章《导论》 · PDF第3页';
  const translated='book.pdf · Chapter 1 “Introduction” · PDF p. 3';
  const data={meta:{language},contentUnits:[],sourceLabels:{[source]:translated}};
  dom.make('script','pageData').textContent=JSON.stringify(data);
  const panel=dom.make('section');panel.className='panel active';
  const view=dom.make('div','chView',panel);view.setAttribute('data-source',source);
  const target=dom.make('p',null,view);target.className='source-target';target.setAttribute('data-source',source);
  target.setAttribute('tabindex','0');target.style.left='100px';target.style.top='120px';
  target._clientWidth=250;target._clientHeight=40;
  const child=dom.make('span',null,target);
  dom.run(path.join(root,'templates/source-presentation.js'));
  dom.run(path.join(root,'templates/methodology.js'));
  const tip=dom.document.getElementById('contentSourceTooltip');
  tip._clientWidth=Math.min(420,width-24);tip._clientHeight=60;
  tip.getBoundingClientRect=()=>{
    const w=tip._clientWidth,h=Math.min(tip._clientHeight,Number.parseFloat(tip.style.maxHeight)||tip._clientHeight);
    const left=Number.parseFloat(tip.style.left)||0,top=Number.parseFloat(tip.style.top)||0;
    return{left,top,width:w,height:h,right:left+w,bottom:top+h};
  };
  const over=(node=target)=>{
    view.dispatch('pointerover',{target:node,pointerType:'mouse'});
    view.dispatch('pointermove',{target:node,pointerType:'mouse',clientX:110,clientY:130});
  };
  const out=(relatedTarget=null)=>view.dispatch('pointerout',{target,pointerType:'mouse',relatedTarget});
  const escape=()=>dom.document.dispatch('keydown',{key:'Escape'});
  return{...dom,advance,panel,view,target,child,tip,over,out,escape,source,translated};
}

test('Blank content space never previews the whole unit citation',()=>{
  const s=setup();s.over(s.view);s.advance(500);assert.equal(s.tip.hidden,true);
});
test('Passing over a source item briefly does not obstruct reading',()=>{
  const s=setup();s.over();assert.equal(s.tip.hidden,true);s.advance(150);s.out();s.advance(500);
  assert.equal(s.tip.hidden,true);assert.equal(s.target.getAttribute('aria-describedby'),null);
});
test('Hover preview stays at its source item while the pointer moves',()=>{
  const s=setup();s.over();s.advance(300);assert.equal(s.tip.hidden,false);
  assert.equal(s.tip.style.left,'100px');assert.equal(s.tip.style.top,'168px');
  const before=[s.tip.style.left,s.tip.style.top];
  s.view.dispatch('pointermove',{target:s.child,pointerType:'mouse',clientX:333,clientY:444});
  s.over(s.child);s.advance(500);assert.deepEqual([s.tip.style.left,s.tip.style.top],before);
  assert.equal(s.tip.textContent,s.source);
});
test('Escape keeps the same source dismissed until pointer exit and re-entry',()=>{
  const s=setup();s.over();s.advance(300);s.escape();assert.equal(s.tip.hidden,true);
  s.over(s.child);s.advance(500);assert.equal(s.tip.hidden,true);
  s.out();s.advance(150);s.over();s.advance(300);assert.equal(s.tip.hidden,false);
});
test('Escape also cancels a preview that has not appeared yet',()=>{
  const s=setup();s.over();s.advance(100);s.escape();s.advance(500);assert.equal(s.tip.hidden,true);
});
test('Leaving the content closes the preview and removes its ARIA link',()=>{
  const s=setup();s.over();s.advance(300);s.out();s.advance(120);
  assert.equal(s.tip.hidden,true);assert.equal(s.target.getAttribute('aria-describedby'),null);
});
test('Keyboard focus reveals localized evidence immediately and blur closes it',()=>{
  const s=setup({language:'en'});s.target.focus();s.view.dispatch('focusin',{target:s.target});
  assert.equal(s.tip.hidden,false);assert.equal(s.tip.textContent,s.translated);
  assert.equal(s.target.getAttribute('aria-describedby'),s.tip.id);
  s.escape();s.view.dispatch('focusin',{target:s.target});assert.equal(s.tip.hidden,true);
  s.view.dispatch('focusout',{target:s.target,relatedTarget:null});
  assert.equal(s.target.getAttribute('aria-describedby'),null);
  s.view.dispatch('focusin',{target:s.target});assert.equal(s.tip.hidden,false);
});
test('Keyboard blur/refocus restores a dismissed source while the pointer stays over it',()=>{
  const s=setup();s.over();s.advance(300);s.view.dispatch('focusin',{target:s.target});
  s.escape();assert.equal(s.tip.hidden,true);
  s.view.dispatch('focusin',{target:s.target});assert.equal(s.tip.hidden,true);
  s.view.dispatch('focusout',{target:s.target,relatedTarget:null});
  s.view.dispatch('focusin',{target:s.target});assert.equal(s.tip.hidden,false);
  assert.equal(s.target.getAttribute('aria-describedby'),s.tip.id);
});

test('Touch pointer movement does not create a desktop hover preview',()=>{
  const s=setup();s.view.dispatch('pointerover',{target:s.target,pointerType:'touch'});
  s.advance(500);assert.equal(s.tip.hidden,true);
});
test('Moving onto the citation keeps it readable, including internal scrolling',()=>{
  const s=setup();s.over();s.advance(300);s.out(s.tip);s.tip.dispatch('pointerenter');s.advance(300);
  assert.equal(s.tip.hidden,false);
  s.document.dispatch('window-scroll',{target:s.tip});assert.equal(s.tip.hidden,false);
  s.tip.dispatch('pointerleave',{relatedTarget:null});s.advance(120);assert.equal(s.tip.hidden,true);
});
test('Viewport edges constrain a long preview and flip it above its source',()=>{
  const s=setup({width:390,height:400});s.target.style.left='330px';s.target.style.top='300px';
  s.tip._clientHeight=600;s.over();s.advance(300);const b=s.tip.getBoundingClientRect();
  assert.equal(s.tip.hidden,false);assert(b.left>=12&&b.right<=378);
  assert(b.top>=12&&b.bottom<=388);assert(b.bottom<=300);
});
test('External clicks and focus cancel both visible and pending previews',()=>{
  for(const event of ['click','focusin']){
    const s=setup(),tab=s.make('button');s.over();s.advance(300);
    s.document.dispatch(event,{target:tab});assert.equal(s.tip.hidden,true);
    s.over();s.advance(100);s.document.dispatch(event,{target:tab});s.advance(500);
    assert.equal(s.tip.hidden,true);
  }
});
test('Scroll, resize, hidden tab and window blur dismiss the preview',()=>{
  for(const event of ['window-scroll','window-resize','window-blur','visibilitychange']){
    const s=setup();s.over();s.advance(300);
    if(event==='visibilitychange')s.document.hidden=true;
    s.document.dispatch(event);assert.equal(s.tip.hidden,true);
    s.document.hidden=false;s.over(s.child);s.advance(500);assert.equal(s.tip.hidden,true);
  }
});
test('Replacing a unit or hiding its panel never leaves a body-level preview',()=>{
  for(const kind of ['unit','panel']){
    const s=setup();s.over();s.advance(300);
    if(kind==='panel')s.panel.hidden=true;
    const observer=kind==='panel'?s.observers[0]:s.observers[1];observer.fn();
    assert.equal(s.tip.hidden,true);assert.equal(s.target.getAttribute('aria-describedby'),null);
  }
});
