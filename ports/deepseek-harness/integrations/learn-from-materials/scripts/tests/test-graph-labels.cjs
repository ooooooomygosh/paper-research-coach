// Exercises the production renderer with a deterministic DOM/font double.
// This checks geometry and state; it cannot attest browser paint or visual quality.
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {createDOM,pathPoints}=require('./support/memory-dom.cjs');
const root=path.resolve(__dirname,'../..');
const templates=path.join(root,'templates');
const sample=JSON.parse(fs.readFileSync(path.join(root,'examples/overview-systematic-demo.json'),'utf8')).methodology;
const kindLabel=(kind,en)=>({main:en?'Next':'接着做',branch:en?'Only when conditions are met':'满足条件才做',feedback:en?'When the test fails, revise the proposal before repeating validation':'未通过，修正方案',supports:en?'Supports':'提供支持',parallel:en?'In parallel':'并行',prerequisite:en?'Prerequisite':'先要具备'}[kind]||kind);

function mount(model,settings={}){
  const dom=createDOM(settings),host=dom.make('div','map'),detail=dom.make('div','detail');
  for(const file of ['hover-bridge.js','scroll-chain.js','graph-motion.js','graph-studio.js'])dom.run(path.join(templates,file));
  const graph=dom.context.LFMGraphStudio.mount(host,{...model,language:settings.language||'zh-CN',kind:'methodology',title:'Test',detail,describe:id=>dom.make('p',null,dom.document.createDocumentFragment()),onSelect(){}});
  dom.flush();return{dom,graph,host,detail};
}
function intersects(a,b){return a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;}
function segments(points){
  const simple=[];
  for(const p of points){const last=simple.at(-1),prev=simple.at(-2);if(last&&p.x===last.x&&p.y===last.y)continue;
    if(prev&&((prev.x===last.x&&last.x===p.x&&(last.y-prev.y)*(p.y-last.y)>0)||(prev.y===last.y&&last.y===p.y&&(last.x-prev.x)*(p.x-last.x)>0)))simple.pop();simple.push(p);}
  return simple.slice(1).map((p,i)=>({a:simple[i],b:p}));
}
function geometry(fixture){
  const {graph}=fixture,svg=graph.root.querySelector('.diagram-wires'),pad=Number.parseFloat(svg.style.top)||0;
  const cards=graph.root.querySelectorAll('.diagram-card').map(card=>({left:card.offsetLeft,right:card.offsetLeft+286,top:card.offsetTop-pad,bottom:card.offsetTop-pad+card.offsetHeight}));
  const wires=graph.root.querySelectorAll('.diagram-wire'),flows=graph.root.querySelectorAll('.diagram-flow'),labels=graph.root.querySelectorAll('.diagram-edge-label');
  assert.equal(wires.length,labels.length);assert.equal(flows.length,labels.length);
  const routes=labels.map((label,i)=>{
    const match=label.getAttribute('transform').match(/^translate\(([-\d.e]+) ([-\d.e]+)\)$/);
    assert(match,'label has a finite SVG transform');const x=Number(match[1]),y=Number(match[2]);
    const rect=label.querySelector('rect'),width=Number(rect.getAttribute('width')),height=Number(rect.getAttribute('height'));
    const box={left:x-width/2,right:x+width/2,top:y-height/2,bottom:y+height/2};
    assert(!cards.some(c=>intersects(box,c)),'label overlaps a node: '+label.dataset.edgeId);
    const route=segments(pathPoints(wires[i].getAttribute('d')));
    assert(route.every(s=>s.a.x===s.b.x||s.a.y===s.b.y),'all links remain straight or orthogonal');
    for(const s of route){const box={left:Math.min(s.a.x,s.b.x)-1,right:Math.max(s.a.x,s.b.x)+1,top:Math.min(s.a.y,s.b.y)-1,bottom:Math.max(s.a.y,s.b.y)+1};assert(!cards.some(card=>intersects(box,card)),'wire crosses a card: '+label.dataset.edgeId);}
    const host=route.find(s=>s.a.y===s.b.y?Math.abs(y-s.a.y)<.01&&box.left>=Math.min(s.a.x,s.b.x)+15.9&&box.right<=Math.max(s.a.x,s.b.x)-15.9:Math.abs(x-s.a.x)<.01&&box.top>=Math.min(s.a.y,s.b.y)+15.9&&box.bottom<=Math.max(s.a.y,s.b.y)-15.9);
    assert(host,'label has an inline slot clear of bends and arrowheads: '+label.dataset.edgeId);
    const mask=wires[i].getAttribute('mask');assert.equal(mask,flows[i].getAttribute('mask'),'flow uses the same gap');
    const maskId=mask?.match(/^url\(#(.+)\)$/)?.[1],maskElement=fixture.dom.document.getElementById(maskId);
    assert(maskElement,'every label reserves an actual wire gap');
    const hole=maskElement.children[1];assert.equal(Number(hole.getAttribute('width')),width+6);assert.equal(Number(hole.getAttribute('height')),height+6);
    assert(Number(maskElement.getAttribute('width'))>=Number(svg.getAttribute('width')),'mask covers complete canvas');
    assert.equal(wires[i].getAttribute('d'),flows[i].getAttribute('d'));
    assert(Math.abs(Number(wires[i].style['--wire-len'])-wires[i].getTotalLength())<.1,'animation follows rerouted length');
    assert(x>=width/2+7.9&&box.right<=Number(svg.getAttribute('width'))&&box.bottom<=Number(svg.getAttribute('height')),'label stays inside canvas: '+label.dataset.edgeId+' '+JSON.stringify({box,svgWidth:svg.getAttribute('width'),svgHeight:svg.getAttribute('height')}));
    for(const span of label.querySelectorAll('tspan'))assert(fixture.dom.measure(span.textContent)<=width-23,'measured label text fits its backing');
    return{box,segments:route,id:label.dataset.edgeId};
  });
  for(let i=0;i<routes.length;i++)for(let j=i+1;j<routes.length;j++)assert(!intersects(routes[i].box,routes[j].box),'labels collide: '+routes[i].id+' / '+routes[j].id);
  for(const label of routes)for(const wire of routes){if(wire===label)continue;for(const s of wire.segments){const b={left:Math.min(s.a.x,s.b.x)-2,right:Math.max(s.a.x,s.b.x)+2,top:Math.min(s.a.y,s.b.y)-2,bottom:Math.max(s.a.y,s.b.y)+2};assert(!intersects(label.box,b),'label hides another wire: '+label.id+' / '+wire.id);}}
  const layers=svg.children.filter(n=>n.tagName==='g');assert.equal(layers.at(-1).className,'diagram-label-layer','label layer paints after wires and flow');
  return wires.map(w=>w.getAttribute('d'));
}
function sampleModel(en){return{...sample,nodes:sample.nodes.map(n=>({...n,title:en?'A deliberately long node title for '+n.id:n.title,summary:n.output})),edges:sample.edges.map(e=>({...e,label:kindLabel(e.kind,en)}))};}

for(const language of ['zh-CN','en'])for(const width of [360,768,1440])for(const theme of ['warm-paper','minimal','dark']){
  test(`${language} / ${theme} / ${width}: all inline labels have clear geometry`,()=>{
    const f=mount(sampleModel(language==='en'),{language,width,theme,cardHeight:card=>card.dataset.nodeId==='m-map'?260:184});
    const before=geometry(f);f.graph.refresh();assert.deepEqual(geometry(f),before,'refresh is stable');
  });
}
test('dense branches and feedback with long labels retain every edge',()=>{
  const nodes=Array.from({length:7},(_,i)=>({id:'n'+i,title:'Node '+i}));
  const edges=[];let i=0;for(let a=0;a<7;a++)for(let b=a+1;b<7;b++)edges.push({id:'e'+i++,from:'n'+a,to:'n'+b,kind:b===a+1?'main':'branch',label:kindLabel('branch',true)});
  for(let a=1;a<7;a++)edges.push({id:'e'+i++,from:'n'+a,to:'n0',kind:'feedback',label:kindLabel('feedback',true)});
  const f=mount({nodes,edges},{language:'en',width:900,metricScale:1.4});geometry(f);assert.equal(f.graph.root.querySelectorAll('.diagram-edge-label').length,edges.length);
});
test('seeded branching, cyclic and disconnected shapes preserve safe label slots',()=>{
  let seed=90210;const rand=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/2**32;};
  for(let caseId=0;caseId<60;caseId++){
    const count=4+Math.floor(rand()*10),nodes=Array.from({length:count},(_,i)=>({id:'n'+i,title:'Measured node '+i})),edges=[];
    for(let a=0;a<count;a++)for(let b=0;b<count;b++){if(a===b||rand()>.15)continue;const kind=b<a?'feedback':rand()>.5?'main':'branch';edges.push({id:'e'+edges.length,from:'n'+a,to:'n'+b,kind,label:kindLabel(kind,true)+(caseId%3===0?' with independently recorded evidence and a long condition':'')});}
    const f=mount({nodes,edges},{language:'en',width:600,metricScale:1+caseId%3*.3,cardHeight:card=>140+Number(card.dataset.nodeId.slice(1))%3*64});
    try{geometry(f);}catch(error){error.message='shape '+caseId+': '+error.message;throw error;}
  }
});
test('a hidden panel keeps its geometry until it becomes measurable again',()=>{
  const f=mount(sampleModel(true),{language:'en'}),before=geometry(f);f.host.hidden=true;f.graph.refresh();f.host.hidden=false;f.graph.refresh();assert.deepEqual(geometry(f),before);
});
test('narrow Fit width preserves readable card scale and Overview remains available',()=>{
  const f=mount(sampleModel(true),{language:'en',width:390});
  const tools=f.graph.root.querySelector('.diagram-tools');
  const scale=()=>Number.parseInt(tools.querySelector('output').textContent,10);
  assert(scale()>=80,'narrow default does not shrink readable titles into an overview');
  const viewport=f.graph.root.querySelector('.diagram-viewport'),sizer=f.graph.root.querySelector('.diagram-sizer');
  assert(Number.parseFloat(sizer.style.width)>=viewport.clientWidth,'oversized content stays on a scrollable canvas');
  tools.querySelectorAll('button').find(n=>n.textContent==='Overview').click();
  assert(scale()<80,'Overview can still intentionally fit the complete graph');
  tools.querySelectorAll('button').find(n=>n.textContent==='Fit width').click();
  assert(scale()>=80);geometry(f);
});

test('edge selection survives renderer refresh and width/overview zoom',()=>{
  const model=sampleModel(true),edge=model.edges.find(e=>e.kind==='feedback');
  assert(edge,'fixture retains a feedback edge');
  const f=mount(model,{language:'en'}),id=edge.id;f.graph.select(edge.from,id);
  const active=()=>f.graph.root.querySelectorAll('.diagram-edge-label.is-active').map(n=>n.dataset.edgeId);
  assert.deepEqual(active(),[id]);f.graph.refresh();assert.deepEqual(active(),[id]);
  for(const name of ['Fit width','Overview']){f.graph.root.querySelectorAll('button').find(n=>n.textContent===name).click();assert.deepEqual(active(),[id]);geometry(f);}
});
for(const nativeFullscreen of [false,true])test(`fullscreen ${nativeFullscreen?'native':'fallback'} restores owner and page overflow`,async()=>{
  const f=mount(sampleModel(true),{language:'en',nativeFullscreen}),button=f.graph.root.querySelectorAll('button').find(n=>n.textContent==='Full screen');
  await button.click();f.dom.flush();assert(f.graph.root.classList.contains('is-expanded'));assert.equal(f.dom.document.body.style.overflow,'hidden');assert(f.graph.root.contains(f.dom.document.querySelector('.diagram-hovercard')));geometry(f);
  f.dom.context.scrollX=0;f.dom.context.scrollY=0;f.graph.root.dispatch('keydown',{key:'Escape'});await Promise.resolve();f.dom.flush();assert(!f.graph.root.classList.contains('is-expanded'));assert.equal(f.dom.document.body.style.overflow,'auto');assert.equal(f.graph.root.parentNode,f.host);assert.equal(f.dom.context.scrollX,24);assert.equal(f.dom.context.scrollY,480);
});
test('empty relations render a visible missing-data explanation without throwing',()=>{
  const f=mount({nodes:[{id:'a',title:'A'},{id:'b',title:'B'}],edges:[]},{language:'en'});assert(f.graph.root.querySelector('.diagram-empty').textContent.includes('No relationships'));geometry(f);
});
