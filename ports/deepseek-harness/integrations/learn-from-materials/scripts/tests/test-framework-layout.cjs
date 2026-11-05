// Runs LFMMindMap itself; memory geometry does not establish browser visual acceptance.
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
const {createDOM}=require('./support/memory-dom.cjs');
const templates=path.resolve(__dirname,'../../templates');
const node=(i,en=true)=>({id:'n'+i,sourceOrder:i,title:en?'Framework '+i:'知识框架 '+i,summary:en?'Shared evidence review':'共同证据复核',source:'Original.pdf · p. '+i});
const edge=(a,b,i,label='supports')=>({id:'e'+i,from:'n'+a,to:'n'+b,label,explanation:'Source-grounded explanation',source:'Original.pdf · p. '+i,evidence:i%3===0?'inference':'material'});
function mount(nodes,edges,settings={}){
  const dom=createDOM(settings),host=dom.make('div','framework-test');
  for(const file of ['hover-bridge.js','scroll-chain.js','graph-motion.js','framework-routing.js','relationship-mindmap.js'])dom.run(path.join(templates,file));
  const graph=dom.context.LFMMindMap.mount(host,{nodes,edges,language:settings.language||'en',title:'Framework map',describe:id=>{
    const content=dom.document.createDocumentFragment(),source=nodes.find(n=>n.id===id);
    const title=dom.make('h3',null,content);title.textContent=source.title;
    const description=dom.make('p',null,content);description.textContent=source.summary;
    const link=dom.make('a',null,content);link.setAttribute('href','#source-'+id);link.textContent=source.source;
    return content;
  },sourceText:value=>'DISPLAY '+value});
  dom.flush();return {dom,host,graph};
}
const named=(f,name)=>f.host.querySelectorAll('button').find(n=>n.textContent===name);
function full(f,en=true){named(f,en?'Expand all':'展开全部').click();f.dom.flush();}
test('cross-links try genuine cubic candidates and expose bounded fallback diagnostics',()=>{
  const nodes=[1,2,3].map(i=>node(i)),edges=[edge(1,2,1),edge(2,3,2),edge(3,1,3)];
  const f=mount(nodes,edges);full(f);geometry(f,nodes,edges);
  const shell=f.host.querySelector('.lfm-mm'),curved=f.host.querySelectorAll('.lfm-mm-wire').filter(p=>p.getAttribute('data-route-kind')==='cross-curve');
  assert(curved.length>0,'cross-links are not unconditionally sent to orthogonal routing');assert(curved.every(p=>p.getAttribute('d').includes(' C ')));
  assert(Number(shell.getAttribute('data-layout-passes'))<=3);assert.equal(shell.getAttribute('data-curve-candidates-per-pass'),'29');
  assert.equal(Number(shell.getAttribute('data-curved-relations'))+Number(shell.getAttribute('data-orthogonal-fallbacks')),edges.length);
  for(const wire of f.host.querySelectorAll('.lfm-mm-wire').filter(p=>p.getAttribute('data-route-kind')==='orthogonal-fallback'))assert(wire.getAttribute('data-route-reason'));
  const flowLayer=f.host.querySelector('.lfm-mm-flow-layer'),labelLayer=f.host.querySelector('.lfm-mm-label-layer');
  assert(f.host.querySelector('.lfm-mm-wires').children.indexOf(flowLayer)<f.host.querySelector('.lfm-mm-wires').children.indexOf(labelLayer));
  for(const e of edges){const wires=f.host.querySelectorAll('.lfm-mm-wire').filter(p=>p.dataset.edgeId===e.id),flows=f.host.querySelectorAll('.lfm-mm-flow').filter(p=>p.dataset.edgeId===e.id);assert.deepEqual(flows.map(p=>p.getAttribute('d')),wires.map(p=>p.getAttribute('d')));}
});
function sample(description){
  const tokens=description.match(/[MLC]|-?\d+(?:\.\d+)?(?:e[-+]?\d+)?/gi)||[];
  const points=[];let i=0,last;
  while(i<tokens.length){
    const op=tokens[i++].toUpperCase();
    if(op==='M'||op==='L'){
      const next={x:Number(tokens[i++]),y:Number(tokens[i++])};
      if(last&&op==='L')for(let n=1;n<64;n++)points.push({x:last.x+(next.x-last.x)*n/64,y:last.y+(next.y-last.y)*n/64});
      points.push(next);last=next;
    }else if(op==='C'){
      const b={x:Number(tokens[i++]),y:Number(tokens[i++])},c={x:Number(tokens[i++]),y:Number(tokens[i++])},d={x:Number(tokens[i++]),y:Number(tokens[i++])},a=last;
      for(let n=1;n<=128;n++){const t=n/128,u=1-t;points.push({x:u*u*u*a.x+3*u*u*t*b.x+3*u*t*t*c.x+t*t*t*d.x,y:u*u*u*a.y+3*u*u*t*b.y+3*u*t*t*c.y+t*t*t*d.y});}last=d;
    }else throw Error('Unexpected path command '+op);
  }
  return points;
}
function geometry(f,nodes,edges){
  const ids=new Set(nodes.map(n=>n.id));edges=edges.filter(e=>ids.has(e.from)&&ids.has(e.to));
  const connected=new Set(edges.flatMap(e=>[e.from,e.to]));
  const boxes=f.host.querySelectorAll('.lfm-mm-node').map(el=>({id:el.getAttribute('data-framework-id'),left:el.offsetLeft,top:el.offsetTop,right:el.offsetLeft+el.clientWidth,bottom:el.offsetTop+el.offsetHeight}));
  const labels=f.host.querySelectorAll('.lfm-mm-edge-label');
  assert.deepEqual(boxes.map(b=>b.id).sort(),[...connected].sort(),'only connected frameworks enter the canvas');
  const list=f.host.querySelectorAll('.lfm-mm-unlinked-item').map(item=>item.getAttribute('data-framework-id'));
  assert.deepEqual(list,[...nodes].sort((a,b)=>(a.sourceOrder||0)-(b.sourceOrder||0)).filter(n=>!connected.has(n.id)).map(n=>n.id),'all other frameworks remain in source order outside the canvas');
  assert.deepEqual([...boxes.map(b=>b.id),...list].sort(),[...ids].sort(),'graph and list preserve the canonical framework inventory');
  assert.equal(labels.length,edges.length);
  for(let i=0;i<boxes.length;i++)for(let j=i+1;j<boxes.length;j++)assert(!(boxes[i].left<boxes[j].right&&boxes[i].right>boxes[j].left&&boxes[i].top<boxes[j].bottom&&boxes[i].bottom>boxes[j].top),'node overlap');
  const paths=f.host.querySelectorAll('.lfm-mm-wire');
  assert.equal(paths.length,edges.length*2);
  for(const e of edges){
    const own=paths.filter(p=>p.getAttribute('data-edge-id')===e.id);assert.equal(own.length,2);
    assert.equal(own.filter(p=>p.getAttribute('marker-end')).length,1);
    assert(own.every(p=>p.getAttribute('data-edge-from')===e.from&&p.getAttribute('data-edge-to')===e.to));
    for(const p of own){
      const points=sample(p.getAttribute('d'));
      assert(boxes.filter(b=>b.id!==e.from&&b.id!==e.to).every(b=>points.every(pt=>pt.x<=b.left||pt.x>=b.right||pt.y<=b.top||pt.y>=b.bottom)),'wire crosses a foreign card');
    }
    const start=sample(own[0].getAttribute('d'))[0],end=sample(own[1].getAttribute('d')).at(-1);
    for(const [pt,id,target] of [[start,e.from,false],[end,e.to,true]]){
      const card=boxes.find(b=>b.id===id);
      assert.equal(pt.y,(card.top+card.bottom)/2);
      const ports=target?[card.left-8,card.right+8,card.right+26]:[card.left,card.right,card.right+18];
      assert(ports.some(x=>Math.abs(pt.x-x)<.01),target?'arrow tip needs an 8px gap at the actual target port':'wrong source port');
    }
  }
  const labelBounds=[];
  for(const label of labels){
    const [x,y]=label.getAttribute('transform').match(/-?\d+(?:\.\d+)?(?:e[-+]?\d+)?/gi).map(Number),rect=label.querySelector('rect');
    const bounds={left:x+Number(rect.getAttribute('x')),right:x+Number(rect.getAttribute('x'))+Number(rect.getAttribute('width')),top:y+Number(rect.getAttribute('y')),bottom:y+Number(rect.getAttribute('y'))+Number(rect.getAttribute('height'))};
    assert(boxes.every(b=>!(bounds.left<b.right&&bounds.right>b.left&&bounds.top<b.bottom&&bounds.bottom>b.top)),'label/card overlap');
    assert(labelBounds.every(b=>!(bounds.left<b.right&&bounds.right>b.left&&bounds.top<b.bottom&&bounds.bottom>b.top)),'label/label overlap');labelBounds.push(bounds);
    for(const p of paths){const hit=sample(p.getAttribute('d')).find(pt=>pt.x>bounds.left&&pt.x<bounds.right&&pt.y>bounds.top&&pt.y<bounds.bottom);assert(!hit,`wire under ${label.getAttribute('data-edge-id')}: ${p.getAttribute('data-edge-id')} ${JSON.stringify({bounds,hit,path:p.getAttribute('d')})}`);}
  }
}

for(const en of [true,false]){
  const language=en?'en':'zh-CN';
  test(language+': sparse groups keep all relations and move unlinked frameworks to a collapsed list',()=>{
    const nodes=Array.from({length:20},(_,i)=>node(i+1,en));
    const edges=[edge(2,12,1),edge(15,12,2),edge(3,9,3),edge(10,7,4)];
    const f=mount(nodes,edges,{language,width:1440});full(f,en);geometry(f,nodes,edges);
    assert(Number.parseFloat(f.host.querySelector('.lfm-mm-stage').style.height)<1600);
    assert.equal(f.host.querySelectorAll('.lfm-mm-node').length,7);
    assert.equal(f.host.querySelectorAll('.lfm-mm-unlinked-item').length,13);
    assert(!f.host.querySelector('.lfm-mm-unlinked').open,'the list starts collapsed and Expand all does not open it');
    assert(!f.host.querySelector('.lfm-mm-canvas').contains(f.host.querySelector('.lfm-mm-unlinked')));
    assert(!f.host.textContent.includes(en?'RELATION CENTER':'关系中心'));
    const snapshots=JSON.stringify({nodes,edges});f.graph.refresh();f.dom.flush();assert.equal(JSON.stringify({nodes,edges}),snapshots);
  });
  test(language+': one node and all-unlinked datasets retain every framework without a blank canvas',()=>{
    for(const total of [1,13,100]){
      const nodes=Array.from({length:total},(_,i)=>node(i+1,en)),f=mount(nodes,[],{language,width:1440});
      geometry(f,nodes,[]);assert.equal(Number.parseFloat(f.host.querySelector('.lfm-mm-stage').style.height),0);
      assert(f.host.querySelector('.lfm-mm-viewport').hidden);
      assert(f.host.querySelector('.lfm-mm-empty'));
      assert(named(f,en?'Expand all':'展开全部').disabled);
      assert(!f.host.querySelector('.lfm-mm-unlinked').open);
    }
  });
  test(language+': measured enlarged titles and multiline labels leave genuine gaps',()=>{
    const nodes=[node(1,en),node(2,en),node(3,en)];nodes[1].title=(en?'Manufacturing constraints and engineering dependencies ':'制造限制与工程依赖关系').repeat(4);
    const edges=[edge(1,2,1,(en?'Prerequisite with a reviewed source and an explicit applicability limit ':'明确使用前提、来源与适用条件').repeat(2)),edge(1,3,2)];
    const f=mount(nodes,edges,{language,metricScale:2});full(f,en);geometry(f,nodes,edges);
    assert(f.host.querySelectorAll('tspan').length>edges.length);
  });
  test(language+': all matching frameworks are searchable and numbered consistently',()=>{
    const nodes=Array.from({length:12},(_,i)=>node(i+1,en)),f=mount(nodes,[],{language});
    const search=f.host.querySelector('input');search.focus();search.value=en?'framework':'框架';search.dispatch('input');f.dom.flush();
    assert.equal(f.host.querySelectorAll('.lfm-mm-result').length,12);
    assert.equal(f.dom.document.activeElement,search,'typing does not move keyboard focus');
    f.host.querySelectorAll('.lfm-mm-result')[11].click();f.dom.flush();
    const selected=f.host.querySelector('.lfm-mm-unlinked-item.is-selected'),detail=f.host.querySelector('.lfm-mm-unlinked-detail');
    assert.equal(selected.getAttribute('data-framework-id'),'n12');
    assert(selected.textContent.includes('12 ·'));assert.equal(selected.getAttribute('aria-expanded'),'true');
    assert(f.host.querySelector('.lfm-mm-unlinked').open);assert(!detail.hidden);
    assert.equal(detail.getAttribute('aria-labelledby'),selected.id);assert(detail.textContent.includes(nodes[11].source));
    assert.equal(detail.querySelector('a').getAttribute('href'),'#source-n12');
    assert.equal(f.dom.document.activeElement,detail,'explicit selection moves focus to readable source details');
    assert.equal(f.host.querySelectorAll('.lfm-mm-node').length,0,'search does not inject isolated nodes into the canvas');
    search.value='missing-unique-token';search.dispatch('input');assert.equal(f.host.querySelectorAll('.lfm-mm-result').length,0);assert.equal(f.host.querySelectorAll('.lfm-mm-unlinked-item.is-selected').length,0);assert(detail.hidden);
    search.value='';search.dispatch('input');assert(f.host.querySelector('.lfm-mm-results').hidden);
  });
  test(language+': direct neighbors and edge endpoints have distinct selection states',()=>{
    const nodes=[1,2,3,4].map(i=>node(i,en)),edges=[edge(1,2,1),edge(2,3,2)],f=mount(nodes,edges,{language});full(f,en);
    f.host.querySelectorAll('.lfm-mm-node').find(n=>n.getAttribute('data-framework-id')==='n1').querySelector('button').click();
    assert.equal(f.host.querySelectorAll('.lfm-mm-node.is-muted').length,1);
    f.host.querySelectorAll('.lfm-mm-edge-label')[1].dispatch('keydown',{key:'Enter'});
    assert.equal(f.host.querySelectorAll('.lfm-mm-node.is-selected').length,2);
    assert.equal(f.host.querySelectorAll('.lfm-mm-edge-label.is-active').length,1);
    named(f,en?'Clear selection':'清除高亮').click();assert.equal(f.host.querySelectorAll('.lfm-mm-node.is-muted').length,0);
  });
}
test('cycles, dense cross-links and disconnected groups retain labels and arrow direction',()=>{
  for(const total of [3,6,10]){
    const nodes=Array.from({length:total+3},(_,i)=>node(i+1)),edges=[];
    for(let a=1;a<=total;a++)for(let b=1;b<=total;b++)if(a!==b&&(a+b)%3===0)edges.push(edge(a,b,edges.length+1));
    const f=mount(nodes,edges);full(f);geometry(f,nodes,edges);
    named(f,'Collapse').click();f.dom.flush();full(f);geometry(f,nodes,edges);
  }
});
test('narrow all-unlinked views use the list without a large graph viewport',()=>{
  const nodes=Array.from({length:12},(_,i)=>node(i+1)),f=mount(nodes,[],{width:390});
  geometry(f,nodes,[]);
  assert(f.host.querySelector('.lfm-mm-viewport').hidden);assert.equal(f.host.querySelectorAll('.lfm-mm-node').length,0);
  assert.equal(f.host.querySelectorAll('.lfm-mm-unlinked-item').length,12);
  assert.equal(Number.parseFloat(f.host.querySelector('.lfm-mm-stage').style.width),0);
});
test('unlinked list preserves source order, source links and keyboard selection across graph refresh',()=>{
  const nodes=[node(7),node(3),node(1),node(5),node(2)],edges=[edge(1,2,1)],original=JSON.stringify({nodes,edges}),f=mount(nodes,edges);
  full(f);geometry(f,nodes,edges);
  const items=f.host.querySelectorAll('.lfm-mm-unlinked-item'),list=f.host.querySelector('.lfm-mm-unlinked');
  assert.deepEqual(items.map(n=>n.getAttribute('data-framework-id')),['n3','n5','n7']);
  list.open=true;items[1].click();
  const detail=f.host.querySelector('.lfm-mm-unlinked-detail');
  assert(!detail.hidden);assert.equal(detail.querySelector('a').getAttribute('href'),'#source-n5');
  f.graph.refresh();f.dom.flush();full(f);
  assert.equal(detail.getAttribute('data-framework-id'),'n5');assert(!detail.hidden);
  assert.equal(items[1].getAttribute('aria-expanded'),'true');
  f.host.querySelector('.lfm-mm-select').click();
  assert(detail.hidden);assert.equal(items[1].getAttribute('aria-expanded'),'false');
  assert.equal(JSON.stringify({nodes,edges}),original,'rendering and selection never mutate source inventory or evidence');
});
test('edges with missing endpoints do not promote isolated frameworks into the canvas',()=>{
  const nodes=[node(1),node(2)],edges=[{...edge(1,2,1),to:'missing'}],f=mount(nodes,edges);
  geometry(f,nodes,edges);assert(f.host.querySelector('.lfm-mm-viewport').hidden);
  assert.equal(f.host.querySelectorAll('.lfm-mm-unlinked-item').length,2);
});
test('empty framework inventories render a concise empty state without exceptions',()=>{
  const f=mount([],[]);geometry(f,[],[]);
  assert(f.host.querySelector('.lfm-mm-empty'));assert(f.host.querySelector('.lfm-mm-viewport').hidden);
  assert.equal(f.host.querySelectorAll('.lfm-mm-unlinked-item').length,0);
});
test('all-unlinked fullscreen retains inline details, source links and theme identity',()=>{
  for(const theme of ['warm-paper','minimal','dark']){
    const nodes=[node(1),node(2)],f=mount(nodes,[],{theme});
    f.host.querySelectorAll('.lfm-mm-unlinked-item')[1].click();named(f,'Fullscreen').click();f.dom.flush();
    assert(!f.host.querySelector('.lfm-mm-unlinked-detail').hidden);assert(f.host.querySelector('.lfm-mm-viewport').hidden);
    assert.equal(f.host.querySelector('.lfm-mm-unlinked-detail').querySelector('a').getAttribute('href'),'#source-n2');
    named(f,'Exit fullscreen').click();f.dom.flush();geometry(f,nodes,[]);
    assert.equal(f.dom.document.body.dataset.theme,theme);
  }
});
for(const nativeFullscreen of [false,true])test((nativeFullscreen?'native':'fallback')+' fullscreen, panel return and source details preserve graph state',()=>{
  const nodes=[node(1),node(2),node(3)],edges=[edge(1,2,1),edge(2,3,2)],f=mount(nodes,edges,{nativeFullscreen});full(f);
  named(f,'Fullscreen').click();f.dom.flush();assert.equal(named(f,'Exit fullscreen').getAttribute('aria-pressed'),'true');
  named(f,'Exit fullscreen').click();f.dom.flush();assert.equal(named(f,'Fullscreen').getAttribute('aria-pressed'),'false');
  f.host.hidden=true;f.graph.refresh();f.dom.flush();f.host.hidden=false;f.graph.refresh();f.dom.flush();geometry(f,nodes,edges);
  const label=f.host.querySelector('.lfm-mm-edge-label');label.dispatch('focus');
  assert(f.dom.document.querySelector('.lfm-mm-hover').textContent.includes('DISPLAY Original.pdf'));
});
test('Escape programmatically exits native framework fullscreen and preserves graph',async()=>{
  const nodes=[node(1),node(2)],edges=[edge(1,2,1)],f=mount(nodes,edges,{nativeFullscreen:true});full(f);
  named(f,'Fullscreen').click();f.dom.flush();assert(f.dom.document.fullscreenElement);
  f.dom.document.dispatch('keydown',{key:'Escape'});await Promise.resolve();f.dom.flush();
  assert.equal(f.dom.document.fullscreenElement,null);geometry(f,nodes,edges);
});

test('all theme identities and canonical inputs survive render refresh',()=>{
  for(const theme of ['warm-paper','minimal','dark']){
    const nodes=[node(1),node(2)],edges=[edge(1,2,1)],original=JSON.stringify({nodes,edges}),f=mount(nodes,edges,{theme});
    f.graph.refresh();f.dom.flush();geometry(f,nodes,edges);assert.equal(JSON.stringify({nodes,edges}),original);assert.equal(f.dom.document.body.dataset.theme,theme);
  }
});
test('deterministic mixed graphs retain clear labels/cards across languages and widths',()=>{
  let seed=28461;const random=()=>{seed=(1664525*seed+1013904223)>>>0;return seed/2**32;};
  for(let scenario=0;scenario<18;scenario++){
    const en=scenario%2===0,total=4+scenario%8,nodes=Array.from({length:total+2},(_,i)=>node(i+1,en)),edges=[];
    nodes[1].title=(en?'Detailed framework with manufacturing dependencies ':'具有制造依赖条件的详细框架').repeat(2+scenario%3);
    for(let a=1;a<=total;a++)for(let b=1;b<=total;b++)if(a!==b&&random()<.2){
      const label=en?'Reviewed applicability with conditions':'已核对的适用条件';edges.push(edge(a,b,edges.length+1,scenario%3===0?label.repeat(3):label));
    }
    const f=mount(nodes,edges,{language:en?'en':'zh-CN',width:[390,820,1440][scenario%3],metricScale:scenario%4===0?2:1});full(f,en);geometry(f,nodes,edges);
  }
});
test('bundled canonical framework graphs run through the actual renderer',()=>{
  for(const name of ['overview-methods-content.json','overview-current-zh.json','overview-systematic-demo.json']){
    const page=JSON.parse(fs.readFileSync(path.join(templates,'../examples',name),'utf8'));
    const nodes=page.frameworks.map(n=>({...n,title:n.name,summary:n.oneLine})),ids=new Set(nodes.map(n=>n.id));
    const edges=page.relationships.filter(e=>ids.has(e.from)&&ids.has(e.to)).map(e=>({...e,label:e.type}));
    const f=mount(nodes,edges,{language:page.meta.language||'zh-CN'});full(f,page.meta.language==='en');geometry(f,nodes,edges);
  }
});
