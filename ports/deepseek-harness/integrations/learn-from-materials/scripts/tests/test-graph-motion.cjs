'use strict';
// Lifecycle/semantic tests for the production helper; not browser paint QA.
const {test}=require('node:test'),assert=require('node:assert/strict'),path=require('node:path');
const {createDOM}=require('./support/memory-dom.cjs');
function fixture({count=5,reduced=false}={}){
  const dom=createDOM({reducedMotion:reduced}),root=dom.make('section','root'),viewport=dom.make('div','view',root),button=dom.make('button','directions',root);
  const timers=new Map(),animations=[];let serial=0;
  const media={matches:reduced,events:[],addEventListener(_,fn){this.events.push(fn);},removeEventListener(_,fn){this.events=this.events.filter(x=>x!==fn);},change(value){this.matches=value;this.events.forEach(fn=>fn());}};
  Object.assign(dom.context,{matchMedia:()=>media,setTimeout:fn=>{timers.set(++serial,fn);return serial;},clearTimeout:id=>timers.delete(id)});
  dom.Element.prototype.animate=function(frames,options){const a={path:this,frames,options,cancelled:false,cancel(){this.cancelled=true;}};animations.push(a);return a;};
  dom.run(path.resolve(__dirname,'../../templates/graph-motion.js'));
  const entries=Array.from({length:count},(_,i)=>{
    const base=dom.make('path',null,viewport),flow=dom.make('path',null,viewport);
    const d=i%2?'M 400 30 L 10 30':'M 10 30 L 400 30';base.setAttribute('d',d);flow.setAttribute('d',d);
    base.setAttribute('stroke-dasharray',i%2?'7 6':'none');base.setAttribute('marker-end','url(#solid-arrow)');
    return{edge:{id:'e'+i,from:i%2?'right':'left',to:i%2?'left':'right',type:'supports'},paths:[base],overlays:[flow]};
  });
  const graph=dom.context.LFMGraphMotion.mount({root,viewport,button,language:'en'});graph.replace(entries);
  function advance(){const pending=[...timers];timers.clear();pending.forEach(([,fn])=>fn());dom.flush();}
  return{dom,root,viewport,button,media,entries,graph,animations,timers,advance};
}
test('idle has no moving edges; selection repeats in batches of at most three',()=>{
  const f=fixture();assert.equal(f.animations.length,0);f.graph.select(f.entries.map(e=>e.edge.id));
  assert.equal(f.animations.length,3);assert(f.animations.every(a=>a.options.iterations===1));
  const first=f.animations.slice();f.advance();assert(first.every(a=>a.cancelled));assert.equal(f.animations.length,6);
  f.graph.select([]);const count=f.animations.length;f.advance();assert.equal(f.animations.length,count);assert.equal(f.timers.size,0);
});
test('hover gives one pass then returns to an idle map',()=>{
  const f=fixture();f.graph.preview(['e1']);assert.equal(f.animations.length,1);f.advance();assert.equal(f.animations.length,1);assert.equal(f.timers.size,0);
});
test('direction demo is opt-in, batches visible relations, and stops completely',()=>{
  const f=fixture({count:7});f.entries[0].paths[0].style.top='2000px';f.button.click();
  assert.equal(f.button.getAttribute('aria-pressed'),'true');assert.equal(f.animations.length,3);assert(!f.animations.some(a=>a.path===f.entries[0].overlays[0]));
  f.advance();assert.equal(f.animations.length,6);f.button.click();assert.equal(f.button.getAttribute('aria-pressed'),'false');assert(f.animations.every(a=>a.cancelled));assert.equal(f.timers.size,0);
});
test('global motion off and reduced motion cancel then resume a retained selection',()=>{
  const f=fixture();f.graph.select(['e1']);f.dom.document.body.dataset.motion='off';f.dom.document.dispatch('lfm-motion-change');
  assert(f.animations.every(a=>a.cancelled));assert.equal(f.timers.size,0);assert(f.button.disabled);
  f.dom.document.body.dataset.motion='on';f.dom.document.dispatch('lfm-motion-change');assert.equal(f.animations.length,2);assert(!f.button.disabled);
  f.media.change(true);assert.equal(f.timers.size,0);assert(f.animations.every(a=>a.cancelled));f.media.change(false);assert.equal(f.animations.length,3);
});
test('document/viewport visibility pause cues without discarding selected IDs',()=>{
  const f=fixture();f.graph.select(['e0']);f.dom.document.hidden=true;f.dom.document.dispatch('visibilitychange');assert(f.animations[0].cancelled);assert.equal(f.timers.size,0);
  f.dom.document.hidden=false;f.dom.document.dispatch('visibilitychange');assert.equal(f.animations.length,2);
  f.viewport.style.top='2000px';f.graph.refresh();assert.equal(f.timers.size,0);f.viewport.style.top='0';f.graph.refresh();assert.equal(f.animations.length,3);
});
test('contrasts and parallel relations highlight together without a one-way cue',()=>{
  const f=fixture({count:2});f.entries[0].edge.type='contrasts';f.entries[1].edge.type='parallel';f.graph.select(['e0','e1']);assert.equal(f.animations.length,0);
  assert(f.entries.every(e=>e.paths[0].classList.contains('is-symmetric-highlight')));
  f.graph.select([]);f.graph.preview(['e0','e1']);assert.equal(f.animations.length,0);assert(f.entries.every(e=>e.paths[0].classList.contains('is-symmetric-preview')));f.advance();assert(f.entries.every(e=>!e.paths[0].classList.contains('is-symmetric-preview')));
});
test('reverse edges use unchanged canonical geometry; overlays move from start to end',()=>{
  const f=fixture({count:2}),before=f.entries.map(e=>[e.paths[0].getAttribute('d'),e.paths[0].getAttribute('stroke-dasharray'),e.paths[0].getAttribute('marker-end')]);
  f.graph.select(['e1']);const a=f.animations[0];assert.equal(a.path.getAttribute('d'),'M 400 30 L 10 30');assert(a.frames[0].strokeDashoffset>a.frames.at(-1).strokeDashoffset);
  f.graph.refresh();assert.deepEqual(f.entries.map(e=>[e.paths[0].getAttribute('d'),e.paths[0].getAttribute('stroke-dasharray'),e.paths[0].getAttribute('marker-end')]),before);
});
test('split wire pieces play sequentially along their own exact geometry',()=>{
  const f=fixture({count:1}),entry=f.entries[0],base=f.dom.make('path',null,f.viewport),flow=f.dom.make('path',null,f.viewport);base.setAttribute('d','M 500 30 L 700 30');flow.setAttribute('d',base.getAttribute('d'));entry.paths.push(base);entry.overlays.push(flow);f.graph.replace([entry]);f.graph.select(['e0']);
  assert.equal(f.animations.length,2);assert.equal(f.animations[0].options.delay,0);assert(f.animations[1].options.delay>0);assert.equal(flow.getAttribute('d'),base.getAttribute('d'));
});
test('rebuilding replaces overlay objects and retains selected edge identity',()=>{
  const f=fixture({count:1});f.graph.select(['e0']);const old=f.animations[0],next=f.dom.make('path',null,f.viewport);next.setAttribute('d',f.entries[0].paths[0].getAttribute('d'));f.entries[0].overlays=[next];f.graph.replace(f.entries);
  assert(old.cancelled);assert.equal(f.animations.at(-1).path,next);assert.deepEqual([...f.graph.state().selected],['e0']);
});
test('destroy cancels timers/animations and removes direction listeners',()=>{
  const f=fixture();f.button.click();f.graph.destroy();assert(f.animations.every(a=>a.cancelled));assert.equal(f.timers.size,0);const count=f.animations.length;f.button.click();f.dom.document.dispatch('lfm-motion-change');f.media.change(true);f.advance();assert.equal(f.animations.length,count);
});
