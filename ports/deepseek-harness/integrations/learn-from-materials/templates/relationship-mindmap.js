(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const WIDTH = 228, MARGIN = 48;
  let serial=0;
  const make = (tag, cls, value) => {
    const element = document.createElement(tag);
    if (cls) element.className = cls;
    if (value !== undefined) element.textContent = value;
    return element;
  };
  const svg = (tag, cls) => {
    const element = document.createElementNS(NS, tag);
    if (cls) element.setAttribute('class', cls);
    return element;
  };

  function mount(host, options) {
    const en = options.language === 'en';
    const uid='lfm-mm-'+(++serial);
    const say = (zh, english) => en ? english : zh;
    const sourceText = options.sourceText || (value => String(value || ''));
    const nodes = [...(options.nodes || [])].sort((a,b)=>(a.sourceOrder||0)-(b.sourceOrder||0)), edges = options.edges || [];
    const byId = new Map(nodes.map(node => [node.id, node]));
    const adjacency = new Map(nodes.map(node => [node.id, []]));
    const validEdges = edges.filter(edge => byId.has(edge.from) && byId.has(edge.to));
    validEdges.forEach(edge => {
      if (!byId.has(edge.from) || !byId.has(edge.to)) return;
      adjacency.get(edge.from).push({id:edge.to, edge});
      adjacency.get(edge.to).push({id:edge.from, edge});
    });
    const order = id => byId.get(id)?.sourceOrder || nodes.findIndex(node => node.id === id) + 1;
    for (const list of adjacency.values()) list.sort((a,b) => order(a.id)-order(b.id));

    // Presentation never changes the canonical inventory. Only nodes participating
    // in actual framework links enter the graph; the rest remain searchable below.
    const graphNodes = nodes.filter(node => adjacency.get(node.id).length);
    // The forest is a layout aid; it does not change canonical edge meaning.
    const components = [], discovered = new Set();
    for (const node of graphNodes) {
      if (discovered.has(node.id)) continue;
      const component = [], pending = [node.id]; discovered.add(node.id);
      for (let i=0; i<pending.length; i++) {
        const id = pending[i]; component.push(id);
        for (const next of adjacency.get(id)) if (!discovered.has(next.id)) {
          discovered.add(next.id); pending.push(next.id);
        }
      }
      components.push(component);
    }
    function totalDistance(id, componentSize) {
      const distances = new Map([[id,0]]), queue = [id];
      for (let i=0; i<queue.length; i++) {
        const current = queue[i];
        adjacency.get(current).forEach(item => {
          if (distances.has(item.id)) return;
          distances.set(item.id, distances.get(current)+1);
          queue.push(item.id);
        });
      }
      return (componentSize-distances.size)*componentSize + [...distances.values()].reduce((sum,n)=>sum+n,0);
    }
    const roots = components.map(component => [...component].sort((a,b) =>
      totalDistance(a,component.length)-totalDistance(b,component.length)
      || adjacency.get(b).length-adjacency.get(a).length || order(a)-order(b))[0]);
    const linkedRoots = roots;
    const unlinkedIds = nodes.filter(node => !adjacency.get(node.id).length).map(node => node.id);
    const primaryRoot = linkedRoots[0] || null;
    const parent = new Map(), childEdge = new Map(), children = new Map(nodes.map(n=>[n.id,[]]));
    const side = new Map();
    for (const rootId of roots) {
      parent.set(rootId,null);
      const queue = [rootId];
      for (let i=0; i<queue.length; i++) {
        const current = queue[i];
        adjacency.get(current).forEach(({id,edge}) => {
          if (parent.has(id)) return;
          parent.set(id,current); childEdge.set(id,edge); children.get(current).push(id);
          side.set(id,current===rootId ? (edge.to===rootId?'left':'right') : side.get(current));
          queue.push(id);
        });
      }
    }
    const assignedEdges = new Set([...childEdge.values()]);
    const extraEdges = validEdges.filter(edge => !assignedEdges.has(edge));
    const expanded = new Set(roots), positions = new Map();
    let scale = 1, selected = null, selectedEdge = null;
    let span=350, branchGap=20, stageWidth=0, stageHeight=0;
    let measuredSpan=350,measuredGap=20,measurementKey='',fontEpoch=0;
    const curveSamples=new WeakMap();
    const measuredHeights=new Map(),labelSizes=new Map();
    const crossSlots=new Map(),wirePlans=new Map(),routedEdges=new Set();let routingBottom=0;
    let sectionPositions = [];

    const shell = make('section','lfm-mm'), header = make('div','lfm-mm-head');
    const heading = make('div','lfm-mm-heading');
    heading.append(make('span','lfm-mm-eyebrow',say('FRAMEWORK RELATIONSHIPS / 思维导图','FRAMEWORK RELATIONSHIPS / MIND MAP')),
      make('h3','',options.title),
      make('p','',say('图中展示有依据的框架关系。点击节点追踪直接关联；其余框架可通过下方折叠列表或搜索查看解释和出处。','The graph shows recorded framework relationships. Select a node to trace its direct links; use the collapsed list or search for other frameworks and their sources.')));
    header.append(heading);
    const tools = make('div','lfm-mm-tools');
    const search = make('input','lfm-mm-search'); search.type='search'; search.placeholder=say('搜索框架…','Search frameworks…');
    search.setAttribute('aria-label',say('搜索框架','Search frameworks'));
    search.setAttribute('aria-controls',uid+'-search-results');
    tools.append(search);
    const button = (name, action, label) => {
      const item=make('button','',name); item.type='button';
      if(label)item.setAttribute('aria-label',label);
      item.addEventListener('click',action); tools.append(item);
      return item;
    };
    const collapseButton=button(say('收起','Collapse'),()=>{expanded.clear();roots.forEach(id=>expanded.add(id));render(true);});
    const expandButton=button(say('展开全部','Expand all'),()=>{graphNodes.forEach(n=>expanded.add(n.id));render(false,primaryRoot);});
    const fitButton=button(say('适应宽度','Fit width'),()=>fit());
    button(say('清除高亮','Clear selection'),()=>{selected=null;selectedEdge=null;updateSelection();hide();});
    const zoomOutButton=button('−',()=>setScale(scale-.12),say('缩小','Zoom out'));
    const zoomInButton=button('＋',()=>setScale(scale+.12),say('放大','Zoom in'));
    const directionButton=button(say('方向演示','Show directions'),()=>{});
    directionButton.setAttribute('aria-pressed','false');
    const fullscreenButton=button(say('全屏展开','Fullscreen'),()=>toggleFullscreen());
    fullscreenButton.setAttribute('aria-pressed','false');
    header.append(tools); shell.append(header);
    const results=make('div','lfm-mm-results');results.id=uid+'-search-results';results.hidden=true;
    const searchStatus=make('p','lfm-mm-search-status');searchStatus.setAttribute('role','status');
    const resultList=make('div','lfm-mm-result-list');results.append(searchStatus,resultList);shell.append(results);

    const viewport = make('div','lfm-mm-viewport'); viewport.tabIndex=0;
    viewport.setAttribute('aria-label',say('可滚动的框架关系思维导图','Scrollable framework relationship mind map'));
    const canvas=make('div','lfm-mm-canvas'), stage=make('div','lfm-mm-stage');
    const wires=svg('svg','lfm-mm-wires'), nodeLayer=make('div','lfm-mm-nodes');
    const sectionLayer=make('div','lfm-mm-sections');
    stage.append(wires,sectionLayer,nodeLayer); canvas.append(stage); viewport.append(canvas); shell.append(viewport);
    viewport.hidden=!graphNodes.length;
    shell.classList.toggle('is-empty',!graphNodes.length);
    if(!graphNodes.length){
      shell.append(make('p','lfm-mm-empty',say('本节暂无可展示的框架关系。框架内容与出处可通过下方列表或搜索查看。','No framework relationships are recorded for this section. Use the list or search to read the frameworks and their sources.')));
      [collapseButton,expandButton,fitButton,zoomOutButton,zoomInButton,directionButton].forEach(item=>{item.disabled=true;item.hidden=true;});
    }
    const footer=make('div','lfm-mm-foot');
    const materialCount=validEdges.filter(edge=>edge.evidence==='material').length;
    if(validEdges.length)footer.append(make('span','',say(`实线：材料依据 ${materialCount} 条 · 虚线：辅助推断 ${validEdges.length-materialCount} 条`,`Solid: ${materialCount} material links · Dashed: ${validEdges.length-materialCount} inferences`)));
    const count=make('span',''); footer.append(count); shell.append(footer);
    if (extraEdges.length) shell.append(make('p','lfm-mm-extra',say(`含 ${extraEdges.length} 条交叉关系；展开相关节点后显示连线。`,`Includes ${extraEdges.length} cross-links; expand their nodes to show the wires.`)));
    const unlinked=make('details','lfm-mm-unlinked'),unlinkedList=make('div','lfm-mm-unlinked-list');
    const unlinkedDetail=make('div','lfm-mm-unlinked-detail'),unlinkedButtons=new Map();
    unlinkedDetail.id=uid+'-unlinked-detail';unlinkedDetail.hidden=true;
    unlinkedDetail.setAttribute('role','region');unlinkedDetail.tabIndex=-1;
    if(unlinkedIds.length){
      unlinked.append(make('summary','',say(`另有 ${unlinkedIds.length} 个框架未纳入关系图`,`Other frameworks outside the graph (${unlinkedIds.length})`)),
        make('p','lfm-mm-unlinked-note',say('按原文顺序列出；选择框架查看解释、适用条件和出处。未纳入本图不代表它与其他内容没有关系。','Listed in source order. Select a framework for its explanation, applicability and sources. Its absence from this graph does not establish that no relationships exist.')),
        unlinkedList,unlinkedDetail);
      for(const id of unlinkedIds){
        const node=byId.get(id),item=make('button','lfm-mm-unlinked-item',`${String(order(id)).padStart(2,'0')} · ${node.title}`);
        item.type='button';item.id=uid+'-unlinked-'+unlinkedButtons.size;
        item.setAttribute('data-framework-id',id);item.setAttribute('aria-controls',unlinkedDetail.id);item.setAttribute('aria-expanded','false');
        item.addEventListener('click',()=>reveal(node,true));unlinkedButtons.set(id,item);unlinkedList.append(item);
      }
      shell.append(unlinked);
    }
    host.replaceChildren(shell);
    const motion=window.LFMGraphMotion?.mount({root:shell,viewport,button:directionButton,language:options.language});
    const measureLayer=make('div','lfm-mm-measure');measureLayer.setAttribute('aria-hidden','true');shell.append(measureLayer);

    // Reuse exactly the source-grounded hover content supplied to the old graph.
    const hover=make('div','diagram-hovercard lfm-mm-hover');
    hover.setAttribute('aria-hidden','true');hover.tabIndex=0; document.body.append(hover);
    let hoverTimer=null,hoverAnchor=null;
    function cancelHide(){clearTimeout(hoverTimer);hoverTimer=null;}
    function inHoverBridge(x,y){return hoverAnchor&&window.LFMHoverBridge.contains(hoverAnchor.getBoundingClientRect(),hover.getBoundingClientRect(),x,y);}
    let fallbackFullscreen=false;
    function placeHover(){
      const parent=document.fullscreenElement===shell||fallbackFullscreen?shell:document.body;
      if(hover.parentNode!==parent)parent.append(hover);
    }
    function hide() {
      clearTimeout(hoverTimer); hoverTimer=null;
      hover.classList.remove('is-visible'); hover.setAttribute('aria-hidden','true');hoverAnchor=null;
    }
    function scheduleHide() {if(hoverTimer||hover.contains(document.activeElement))return;hoverTimer=setTimeout(hide,300);}
    function show(fragment,anchor) {
      clearTimeout(hoverTimer); hoverTimer=null;
      placeHover();hoverAnchor=anchor;hover.scrollTop=0;
      hover.replaceChildren(fragment); hover.classList.add('is-visible');
      hover.setAttribute('aria-hidden','false');
      const a=anchor.getBoundingClientRect(), b=hover.getBoundingClientRect(), gap=14, pad=12;
      const clamp=(value,min,max)=>Math.max(min,Math.min(value,Math.max(min,max)));
      const area=(r,s)=>Math.max(0,Math.min(r.right,s.right)-Math.max(r.left,s.left))
        *Math.max(0,Math.min(r.bottom,s.bottom)-Math.max(r.top,s.top));
      const protectedRects=[...nodeLayer.querySelectorAll('.lfm-mm-node'),...wires.querySelectorAll('.lfm-mm-edge-label')]
        .map(el=>el.getBoundingClientRect()).filter(r=>r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth);
      const candidates=[
        [a.right+gap,a.top],[a.left-b.width-gap,a.top],
        [a.left,a.bottom+gap],[a.left,a.top-b.height-gap],
        [innerWidth-b.width-pad,pad],[pad,innerHeight-b.height-pad]
      ].map(([x,y])=>{
        const left=clamp(x,pad,innerWidth-b.width-pad),top=clamp(y,pad,innerHeight-b.height-pad);
        const rect={left,top,right:left+b.width,bottom:top+b.height};
        return {left,top,score:area(rect,a)*8+protectedRects.reduce((sum,r)=>sum+area(rect,r),0)};
      });
      const best=candidates.reduce((best,item)=>item.score<best.score?item:best);
      hover.style.left=best.left+'px';hover.style.top=best.top+'px';
    }
    hover.addEventListener('pointerenter',cancelHide);
    hover.addEventListener('pointerleave',e=>{if(!inHoverBridge(e.clientX,e.clientY))scheduleHide();});
    hover.addEventListener('focusin',cancelHide);
    hover.addEventListener('focusout',()=>{setTimeout(()=>{if(!hover.contains(document.activeElement))scheduleHide();},0);});
    document.addEventListener('pointermove',e=>{if(e.pointerType==='touch'||!hoverAnchor)return;if(inHoverBridge(e.clientX,e.clientY))cancelHide();else scheduleHide();});
    document.addEventListener('pointerdown',e=>{if(hoverAnchor&&!hover.contains(e.target)&&!hoverAnchor.contains(e.target))hide();});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&(shell.contains(document.activeElement)||hoverAnchor)){hide();selected=null;selectedEdge=null;updateSelection();}});
    document.addEventListener('lfm-panel-change',()=>{hide();requestAnimationFrame(()=>requestAnimationFrame(()=>{if(host.offsetWidth)render(false);}));});
    window.addEventListener('scroll',hide,{passive:true});
    viewport.addEventListener('wheel',e=>{if(hoverAnchor&&inHoverBridge(e.clientX,e.clientY))window.LFMScrollChain.route(e,hover,viewport);},{passive:false});
    hover.addEventListener('wheel',event=>window.LFMScrollChain.route(event,hover,viewport),{passive:false});
    viewport.addEventListener('scroll',hide);
    function updateFullscreen() {
      const active=document.fullscreenElement===shell || fallbackFullscreen;
      placeHover();
      fullscreenButton.textContent=active?say('退出全屏','Exit fullscreen'):say('全屏展开','Fullscreen');
      fullscreenButton.setAttribute('aria-pressed',String(active));
      requestAnimationFrame(()=>requestAnimationFrame(()=>{if(host.offsetWidth)render(false,selected||primaryRoot);}));
    }
    function exitFallback() {
      fallbackFullscreen=false;
      shell.classList.remove('is-fullscreen');
      document.documentElement.classList.remove('lfm-mm-scroll-lock');
      updateFullscreen();
    }
    async function toggleFullscreen() {
      hide();
      if(document.fullscreenElement===shell){await document.exitFullscreen();return;}
      if(fallbackFullscreen){exitFallback();return;}
      if(shell.requestFullscreen){
        try {await shell.requestFullscreen();return;} catch (_) { /* Use the viewport-sized fallback below. */ }
      }
      fallbackFullscreen=true;
      shell.classList.add('is-fullscreen');
      document.documentElement.classList.add('lfm-mm-scroll-lock');
      updateFullscreen();
    }
    document.addEventListener('fullscreenchange',()=>{if(!fallbackFullscreen)updateFullscreen();});
    document.addEventListener('keydown',event=>{
      if(event.key!=='Escape')return;
      if(fallbackFullscreen)exitFallback();
      else if(document.fullscreenElement===shell){event.preventDefault();Promise.resolve(document.exitFullscreen()).catch(()=>{});}
      else hide();
    });
    function edgeDescription(edge) {
      const content=document.createDocumentFragment();
      content.append(make('h3','',byId.get(edge.from).title+' → '+byId.get(edge.to).title));
      content.append(make('p','lfm-mm-hover-type',`${edge.label} · ${edge.evidence==='material'?say('材料依据','Material evidence'):say('辅助理解的推断','Inference')}`));
      content.append(make('p','',edge.explanation));
      if(routedEdges.has(edge))content.append(make('p','lfm-mm-hover-type',say('局部折线：曲线候选未通过避障检查，改用保留通道；关系含义与方向保持原样。','Local orthogonal fallback: cubic candidates failed clearance checks; a reserved corridor preserves the recorded relation and direction.')));
      content.append(make('p','hover-source',say('出处：','Source: ')+sourceText(edge.source)));
      options.sourceOriginal?.(content,edge.source);
      return content;
    }

    function nodeHeight(id) {
      return measuredHeights.get(id)||72;
    }
    function measure() {
      const style=getComputedStyle(shell),rootStyle=getComputedStyle(document.documentElement);
      const key=JSON.stringify([document.body.dataset.theme,viewport.clientWidth,style.fontFamily,style.fontSize,
        style.getPropertyValue('--font-display'),rootStyle.fontSize,fontEpoch,
        graphNodes.map(node=>[node.id,node.title]),validEdges.map(edge=>edge.label)]);
      if(key===measurementKey)return;
      measureLayer.replaceChildren();measuredHeights.clear();labelSizes.clear();
      for(const node of graphNodes){
        const box=make('div',`lfm-mm-node${linkedRoots.includes(node.id)?' is-root':''}`);
        box.style.position='relative';box.style.width=WIDTH+'px';box.style.minHeight='0';
        const body=make('button','lfm-mm-select');body.style.minHeight='72px';body.tabIndex=-1;
        body.append(make('small','',`${String(order(node.id)).padStart(2,'0')} / ${say('框架','FRAMEWORK')}`),make('span','',node.title));
        box.append(body);measureLayer.append(box);
        measuredHeights.set(node.id,Math.max(72,Math.ceil(box.getBoundingClientRect().height)));
      }
      const context=document.createElement('canvas').getContext('2d');
      const probe=svg('svg'),probeGroup=svg('g','lfm-mm-edge-label'),probeText=svg('text');
      probeGroup.append(probeText);probe.append(probeGroup);measureLayer.append(probe);
      const font=getComputedStyle(probeText),fontSize=Number.parseFloat(font.fontSize)||11;
      const lineHeight=Math.ceil(fontSize*16/11);
      if(context)context.font=`${font.fontWeight||700} ${fontSize}px ${font.fontFamily||getComputedStyle(shell).getPropertyValue('--font-display')||'system-ui'}`;
      const width=text=>context?context.measureText(text).width:[...text].length*fontSize;
      for(const edge of validEdges){
        const text=edge.label||say('关联','Link'),tokens=en?text.match(/\S+\s*/g)||[text]:[...text];
        const lines=[];let line='';
        for(const token of tokens){
          if(line&&width(line+token)>168){lines.push(line.trim());line='';}
          for(const ch of token){if(line&&width(line+ch)>168){lines.push(line.trim());line='';}line+=ch;}
        }
        if(line.trim())lines.push(line.trim());if(!lines.length)lines.push(text);
        labelSizes.set(edge,{lines,lineHeight,width:Math.max(48,...lines.map(line=>width(line)+22)),height:Math.max(24,lines.length*lineHeight+10)});
      }
      measuredSpan=Math.max(350,WIDTH+Math.max(0,...[...labelSizes.values()].map(item=>item.width))+64);
      measuredGap=Math.max(20,Math.max(0,...[...labelSizes.values()].map(item=>item.height))+16);
      measurementKey=key;
      measureLayer.replaceChildren();
    }
    function visibleChildren(id) {return expanded.has(id)?children.get(id):[];}
    function branchHeight(id) {
      const list=visibleChildren(id);
      return list.length?Math.max(nodeHeight(id),list.reduce((sum,child)=>sum+branchHeight(child),0)+branchGap*(list.length-1)):nodeHeight(id);
    }
    function maxDepth(id) {return 1+Math.max(0,...visibleChildren(id).map(maxDepth));}
    function place(id,centerX,centerY,branchSide) {
      const height=nodeHeight(id);
      positions.set(id,{x:centerX-WIDTH/2,y:centerY-height/2,w:WIDTH,h:height});
      const list=visibleChildren(id);
      if (!list.length) return;
      const total=list.reduce((sum,child)=>sum+branchHeight(child),0)+branchGap*(list.length-1);
      let top=centerY-total/2;
      list.forEach(child=>{
        const size=branchHeight(child);
        place(child,centerX+(branchSide==='left'?-span:span),top+size/2,branchSide);
        top+=size+branchGap;
      });
    }
    function setScale(value) {
      const centerX=(viewport.scrollLeft+viewport.clientWidth/2)/scale,centerY=(viewport.scrollTop+viewport.clientHeight/2)/scale;
      scale=Math.max(.35,Math.min(1.4,value));
      stage.style.transform=`scale(${scale})`;
      canvas.style.width=Math.ceil(stageWidth*scale)+'px';
      canvas.style.height=Math.ceil(stageHeight*scale)+'px';
      viewport.scrollLeft=Math.max(0,centerX*scale-viewport.clientWidth/2);viewport.scrollTop=Math.max(0,centerY*scale-viewport.clientHeight/2);
    }
    function fit() {
      if (!viewport.clientWidth || !stageWidth) return;
      setScale(Math.min(1,Math.max(.65,(viewport.clientWidth-24)/stageWidth)));
      viewport.scrollLeft=0;
    }
    function focus(id) {
      const p=positions.get(id); if(!p)return;
      viewport.scrollLeft=Math.max(0,(p.x+p.w/2)*scale-viewport.clientWidth/2);
      viewport.scrollTop=Math.max(0,(p.y+p.h/2)*scale-viewport.clientHeight/2);
    }
    function splitCurve(points,t) {
      const mix=(a,b)=>({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t});
      const a=mix(points[0],points[1]),b=mix(points[1],points[2]),c=mix(points[2],points[3]);
      const d=mix(a,b),e=mix(b,c),f=mix(d,e);
      return [[points[0],a,d,f],[f,e,c,points[3]]];
    }
    function curvePath(points) {
      const [a,b,c,d]=points;
      return `M ${a.x} ${a.y} C ${b.x} ${b.y}, ${c.x} ${c.y}, ${d.x} ${d.y}`;
    }
    function wirePieces(points,width,height) {
      const center=splitCurve(points,.5)[0][3];
      const inside=t=>{
        const p=splitCurve(points,t)[0][3];
        return Math.abs(p.x-center.x)<width/2+7&&Math.abs(p.y-center.y)<height/2+7;
      };
      let outside=0,within=.5;
      for(let i=0;i<32;i++){const mid=(outside+within)/2;inside(mid)?within=mid:outside=mid;}
      const start=splitCurve(points,outside)[0];
      outside=1;within=.5;
      for(let i=0;i<32;i++){const mid=(outside+within)/2;inside(mid)?within=mid:outside=mid;}
      return [start,splitCurve(points,outside)[1]];
    }
    function wirePlan(edge,settings={}) {
      const from=positions.get(edge.from),to=positions.get(edge.to);
      const left=from.x+from.w/2<to.x+to.w/2;
      const exit=settings.exit??(left?1:-1),entry=settings.entry??(left?-1:1);
      const x1=exit===1?rightPort(edge.from):from.x,x2=(entry===1?rightPort(edge.to):to.x)+entry*8;
      const y1=from.y+from.h/2,y2=to.y+to.h/2;
      const bend=settings.reach??Math.max(64,Math.abs(x2-x1)*.52),lift=settings.lift||0;
      const points=[{x:x1,y:y1},{x:x1+exit*bend,y:y1+lift},{x:x2+entry*bend,y:y2+lift},{x:x2,y:y2}];
      const size=labelSizes.get(edge);
      return {...size,center:splitCurve(points,.5)[0][3],points,pieces:wirePieces(points,size.width,size.height)};
    }
    function labelRect(plan,pad=8) {
      return {left:plan.center.x-plan.width/2-pad,right:plan.center.x+plan.width/2+pad,
        top:plan.center.y-plan.height/2-pad,bottom:plan.center.y+plan.height/2+pad};
    }
    function intersects(a,b) {return a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top;}
    function rightPort(id) {const p=positions.get(id);return p.x+p.w+(children.get(id).length?18:0);}
    function cardRect(id,p) {return {left:p.x-6,right:rightPort(id)+6,top:p.y-6,bottom:p.y+p.h+6};}
    function segmentHits(a,b,r) {
      let enter=0,leave=1;
      for(const [start,delta,min,max] of [[a.x,b.x-a.x,r.left,r.right],[a.y,b.y-a.y,r.top,r.bottom]]){
        if(!delta){if(start<=min||start>=max)return false;continue;}
        const p=(min-start)/delta,q=(max-start)/delta;
        enter=Math.max(enter,Math.min(p,q));leave=Math.min(leave,Math.max(p,q));
        if(enter>=leave)return false;
      }
      return leave>0&&enter<1;
    }
    function curveHits(points,rect) {
      // Reject distant obstacles before sampling; share one sampled curve
      // across its remaining obstacles instead of resampling for every card.
      let sampled=curveSamples.get(points);
      if(!sampled){
        sampled={bounds:{left:Math.min(...points.map(p=>p.x)),right:Math.max(...points.map(p=>p.x)),
          top:Math.min(...points.map(p=>p.y)),bottom:Math.max(...points.map(p=>p.y))},polyline:null};
        curveSamples.set(points,sampled);
      }
      const b=sampled.bounds;
      if(b.right<rect.left||b.left>rect.right||b.bottom<rect.top||b.top>rect.bottom)return false;
      if(!sampled.polyline){
        const [a,b,c,d]=points;sampled.polyline=[a];
        for(let n=1;n<=192;n++){
          const t=n/192,u=1-t;
          sampled.polyline.push({x:u*u*u*a.x+3*u*u*t*b.x+3*u*t*t*c.x+t*t*t*d.x,
            y:u*u*u*a.y+3*u*u*t*b.y+3*u*t*t*c.y+t*t*t*d.y});
        }
      }
      for(let n=1;n<sampled.polyline.length;n++)if(segmentHits(sampled.polyline[n-1],sampled.polyline[n],rect))return true;
      return false;
    }
    function planRoutes() {
      wirePlans.clear();routedEdges.clear();
      const visible=validEdges.filter(edge=>positions.has(edge.from)&&positions.has(edge.to));
      const cards=[...positions].map(([id,p])=>({id,rect:cardRect(id,p)}));
      const bottom=Math.max(80,...cards.map(card=>card.rect.bottom))+24;
      // A fixed candidate budget applies equally to tree branches and cross-links.
      // These are genuine cubic arches, not rounded orthogonal paths.
      for(const edge of [...visible.filter(edge=>assignedEdges.has(edge)),...visible.filter(edge=>!assignedEdges.has(edge))]){
        const accepted=[...wirePlans.values()],labels=accepted.map(plan=>labelRect(plan));
        const blockers=[...labels,...cards.filter(card=>card.id!==edge.from&&card.id!==edge.to).map(card=>card.rect)];
        const from=positions.get(edge.from),to=positions.get(edge.to),forward=from.x<to.x;
        const candidates=[wirePlan(edge)];
        for(const [exit,entry] of [[forward?1:-1,forward?-1:1],[1,1],[-1,-1],[forward?-1:1,forward?1:-1]]){
          for(const lift of [0,-64,64,-144,144,-280,280]){
            candidates.push(wirePlan(edge,{exit,entry,lift,reach:Math.max(90,Math.min(260,Math.abs(from.x-to.x)*.52))}));
          }
        }
        const safe=candidates.find(plan=>{
          const rect=labelRect(plan);
          if(rect.left<12||rect.right>stageWidth-12||rect.top<60||rect.bottom>bottom)return false;
          if(plan.points.some(p=>p.x<12||p.x>stageWidth-12||p.y<60||p.y>bottom))return false;
          if(plan.pieces.some(piece=>curveHits(piece,labelRect(plan,0))))return false;
          const endpointCards=[from,to].map(p=>({left:p.x+.5,right:p.x+p.w-.5,top:p.y+.5,bottom:p.y+p.h-.5}));
          if(endpointCards.some(box=>plan.pieces.some(piece=>curveHits(piece,box))))return false;
          if([...cards.map(card=>card.rect),...labels].some(box=>intersects(rect,box)))return false;
          if(blockers.some(box=>plan.pieces.some(piece=>curveHits(piece,box))))return false;
          if(accepted.some(other=>other.pieces.some(piece=>curveHits(piece,rect))))return false;
          return true;
        });
        if(safe)wirePlans.set(edge,safe);else routedEdges.add(edge);
      }
      return visible.filter(edge=>routedEdges.has(edge));
    }
    function updateSelection() {
      const nearby=new Set(selectedEdge?[selectedEdge.from,selectedEdge.to]:selected?[selected,...adjacency.get(selected).map(item=>item.id)]:[]);
      const activeSelection=!!selected||!!selectedEdge;
      nodeLayer.querySelectorAll('.lfm-mm-node').forEach(el=>{
        const id=el.getAttribute('data-framework-id');
        el.classList.toggle('is-selected',id===selected||!!selectedEdge&&nearby.has(id));
        el.classList.toggle('is-related',activeSelection&&id!==selected&&nearby.has(id));
        el.classList.toggle('is-muted',activeSelection&&!nearby.has(id));
        el.querySelector('.lfm-mm-select')?.setAttribute('aria-pressed',String(id===selected));
      });
      unlinkedButtons.forEach((item,id)=>{
        const active=id===selected;
        item.classList.toggle('is-selected',active);item.setAttribute('aria-expanded',String(active));
      });
      unlinkedDetail.hidden=!unlinkedButtons.has(selected);
      wires.querySelectorAll('[data-edge-from]').forEach(el=>{
        const active=selectedEdge?el.getAttribute('data-edge-id')===selectedEdge.id:!!selected&&(el.getAttribute('data-edge-from')===selected||el.getAttribute('data-edge-to')===selected);
        el.classList.toggle('is-active',active);el.classList.toggle('is-muted',activeSelection&&!active);
        if(el.getAttribute('role')==='button')el.setAttribute('aria-pressed',String(active));
      });
      motion?.select(selectedEdge?[selectedEdge.id]:selected?validEdges.filter(edge=>edge.from===selected||edge.to===selected).map(edge=>edge.id):[]);
    }
    function drawWires() {
      wires.replaceChildren();
      const defs=svg('defs');
      [['material',uid+'-arrow'],['inference',uid+'-arrow-inference']].forEach(([kind,id])=>{
        const marker=svg('marker'); marker.id=id;marker.setAttribute('viewBox','0 0 10 10');
        marker.setAttribute('refX','10');marker.setAttribute('refY','5');marker.setAttribute('markerWidth','15');
        marker.setAttribute('markerHeight','15');marker.setAttribute('markerUnits','userSpaceOnUse');marker.setAttribute('orient','auto');
        const tip=svg('path');tip.setAttribute('d','M 0 0 L 10 5 L 0 10 z');tip.setAttribute('class',`lfm-mm-tip-${kind}`);
        marker.append(tip);defs.append(marker);
      }); wires.append(defs);
      const flowLayer=svg('g','lfm-mm-flow-layer'),labelLayer=svg('g','lfm-mm-label-layer'),motionEntries=[];
      const routing=window.LFMFrameworkRouting;
      const bounds={left:12,right:stageWidth-12,top:60,bottom:routingBottom};
      const obstacles=[...positions].filter(([id])=>adjacency.get(id).length).map(([id,p])=>cardRect(id,p));
      crossSlots.forEach(slot=>obstacles.push({left:slot.x-slot.width/2-8,right:slot.x+slot.width/2+8,top:slot.y-slot.height/2-8,bottom:slot.y+slot.height/2+8}));
      wirePlans.forEach((plan,edge)=>{if(!routedEdges.has(edge))obstacles.push(labelRect(plan));});
      for (const edge of validEdges) {
        const from=positions.get(edge.from),to=positions.get(edge.to);
        if (!from || !to) continue;
        const cross=!assignedEdges.has(edge);
        const y1=from.y+from.h/2,y2=to.y+to.h/2;
        const {width,height,lines,lineHeight}=labelSizes.get(edge);
        let center,paths;
        if(routedEdges.has(edge)){
          const slot=crossSlots.get(edge);center={x:slot.x,y:slot.y};
          const fromPort=rightPort(edge.from),toPort=rightPort(edge.to);
          const start={x:fromPort+6,y:y1},end={x:toPort+14,y:y2};
          const before={x:slot.x-width/2-16,y:slot.y},after={x:slot.x+width/2+16,y:slot.y};
          const prefix=routing.route(start,before,obstacles,bounds),suffix=routing.route(after,end,obstacles,bounds);
          paths=[routing.path(routing.simplify([{x:fromPort,y:y1},...prefix,{x:slot.x-width/2-7,y:slot.y}])),
            routing.path(routing.simplify([{x:slot.x+width/2+7,y:slot.y},...suffix,{x:toPort+8,y:y2}]))];
        }else{const plan=wirePlans.get(edge);center=plan.center;paths=plan.pieces.map(curvePath);}
        const entry={edge,paths:[],overlays:[]};
        paths.forEach((description,index)=>{
          const path=svg('path',`lfm-mm-wire${edge.evidence==='material'?'':' is-inference'}${cross?' is-cross':''}`);
          path.setAttribute('data-edge-id',edge.id);
          path.setAttribute('data-edge-from',edge.from);path.setAttribute('data-edge-to',edge.to);
          path.setAttribute('data-route-kind',routedEdges.has(edge)?'orthogonal-fallback':cross?'cross-curve':'tree-curve');
          if(routedEdges.has(edge))path.setAttribute('data-route-reason','No clear cubic candidate within 3 bounded layout passes (29 candidates per relation per pass); reserved obstacle-free corridor.');
          path.setAttribute('d',description);
          if(index===1)path.setAttribute('marker-end',`url(#${uid+(edge.evidence==='material'?'-arrow':'-arrow-inference')})`);
          wires.append(path);
          const flow=svg('path',`lfm-mm-flow${edge.evidence==='material'?'':' is-inference'}`);flow.setAttribute('d',description);flow.setAttribute('data-edge-id',edge.id);flow.setAttribute('aria-hidden','true');flowLayer.append(flow);entry.paths.push(path);entry.overlays.push(flow);
        });
        motionEntries.push(entry);
        const group=svg('g','lfm-mm-edge-label');group.setAttribute('tabindex','0');
        group.setAttribute('role','button');
        group.setAttribute('aria-label',`${byId.get(edge.from).title} → ${byId.get(edge.to).title}：${edge.label}`);
        group.setAttribute('transform',`translate(${center.x} ${center.y})`);
        if(edge.evidence!=='material')group.classList.add('is-inference');
        group.setAttribute('data-edge-from',edge.from);group.setAttribute('data-edge-to',edge.to);
        group.setAttribute('data-edge-id',edge.id);
        if(routedEdges.has(edge)){group.classList.add('is-route-fallback');const title=svg('title');title.textContent=say('局部折线：曲线候选未通过避障检查，使用保留通道。','Local orthogonal fallback: cubic candidates failed clearance checks; using a reserved corridor.');group.append(title);}
        const rect=svg('rect');
        rect.setAttribute('x',String(-width/2));rect.setAttribute('y',String(-height/2));
        rect.setAttribute('width',String(width));rect.setAttribute('height',String(height));rect.setAttribute('rx','10');
        const caption=svg('text');caption.setAttribute('text-anchor','middle');caption.setAttribute('dominant-baseline','central');
        lines.forEach((line,index)=>{const part=svg('tspan');part.setAttribute('x','0');part.setAttribute('y',String((index-(lines.length-1)/2)*lineHeight));part.textContent=line;caption.append(part);});
        group.append(rect,caption);
        group.addEventListener('pointerenter',()=>{show(edgeDescription(edge),group);motion?.preview([edge.id]);});
        group.addEventListener('pointerleave',scheduleHide);
        group.addEventListener('focus',()=>{show(edgeDescription(edge),group);motion?.preview([edge.id]);});
        group.addEventListener('blur',scheduleHide);
        group.addEventListener('click',()=>{selected=null;selectedEdge=edge;updateSelection();show(edgeDescription(edge),group);});
        group.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();selected=null;selectedEdge=edge;updateSelection();show(edgeDescription(edge),group);}});
        labelLayer.append(group);
      }
      wires.append(flowLayer,labelLayer);motion?.replace(motionEntries);
      shell.setAttribute('data-curved-relations',String(motionEntries.length-routedEdges.size));shell.setAttribute('data-orthogonal-fallbacks',String(routedEdges.size));shell.setAttribute('data-curve-candidates-per-pass','29');
    }
    function drawNodes() {
      nodeLayer.replaceChildren();
      for (const [id,p] of positions) {
        const node=byId.get(id),box=make('div',`lfm-mm-node${linkedRoots.includes(id)?' is-root':''}${id===selected?' is-selected':''}`);
        box.setAttribute('data-framework-id',id);
        box.style.left=p.x+'px';box.style.top=p.y+'px';box.style.width=p.w+'px';box.style.height=p.h+'px';
        const select=make('button','lfm-mm-select');select.type='button';
        select.setAttribute('aria-label',say(`查看${node.title}的解释和出处`,`View ${node.title} explanation and sources`));
        select.append(make('small','',`${String(order(id)).padStart(2,'0')} / ${say('框架','FRAMEWORK')}`),make('span','',node.title));
        select.addEventListener('click',()=>{
          selected=id;selectedEdge=null;
          updateSelection();
          show(options.describe(id),box);
        });
        box.append(select);
        if(children.get(id).length) {
          const open=expanded.has(id),toggle=make('button','lfm-mm-toggle',open?'−':'+');toggle.type='button';
          toggle.setAttribute('aria-label',`${open?say('收起','Collapse'):say('展开','Expand')}${node.title}`);
          toggle.setAttribute('aria-expanded',String(open));
          toggle.addEventListener('click',()=>{open?expanded.delete(id):expanded.add(id);render(false,id);});
          box.append(toggle);
        }
        const preview=()=>motion?.preview(validEdges.filter(edge=>edge.from===id||edge.to===id).map(edge=>edge.id));
        box.addEventListener('pointerenter',()=>{show(options.describe(id),box);preview();});
        box.addEventListener('pointerleave',scheduleHide);
        box.addEventListener('focusin',()=>{show(options.describe(id),box);preview();});
        box.addEventListener('focusout',scheduleHide);
        nodeLayer.append(box);
      }
    }
    function render(autoFit,focusId) {
      if(!graphNodes.length){
        positions.clear();nodeLayer.replaceChildren();wires.replaceChildren();sectionLayer.replaceChildren();
        stageWidth=0;stageHeight=0;stage.style.width='0px';stage.style.height='0px';
        canvas.style.width='0px';canvas.style.height='0px';
        count.textContent=say(`关系图中 0 个框架 · ${nodes.length} 个框架可在列表中查看`,`0 frameworks in graph · ${nodes.length} frameworks available in the list`);
        shell.setAttribute('data-curved-relations','0');shell.setAttribute('data-orthogonal-fallbacks','0');
        motion?.replace([]);updateSelection();return;
      }
      if(viewport.clientWidth<=0)return;
      measure();
      hide();crossSlots.clear();
      let layouts,bandTop,routedVisible,best=null,passes=0;
      // Try at most two reflows before routing unresolved tree or cross-link conflicts.
      for(let attempt=0;attempt<3;attempt++){
      span=Math.round(measuredSpan*(1+attempt*.28));branchGap=Math.round(measuredGap*(1+attempt*.6));
      positions.clear();sectionPositions=[];
      layouts=linkedRoots.map(rootId=>{
        const lists=['left','right'].map(branch=>children.get(rootId).filter(id=>side.get(id)===branch));
        const depths=lists.map(list=>Math.max(0,...list.map(maxDepth)));
        const totals=lists.map(list=>list.reduce((sum,id)=>sum+branchHeight(id),0)+branchGap*Math.max(0,list.length-1));
        return {rootId,lists,depths,totals,height:Math.max(100,...totals,nodeHeight(rootId))+48};
      });
      const leftDepth=Math.max(0,...layouts.map(item=>item.depths[0]));
      const rightDepth=Math.max(0,...layouts.map(item=>item.depths[1]));
      stageWidth=MARGIN*2+WIDTH+(leftDepth+rightDepth)*span;
      const rootX=layouts.length?MARGIN+leftDepth*span+WIDTH/2:stageWidth/2;
      bandTop=24;
      if(layouts.length){
        sectionPositions.push({top:bandTop,text:say(`已标注关系 · ${layouts.length} 组 · ${validEdges.length} 条连线`,`Linked frameworks · ${layouts.length} groups · ${validEdges.length} links`)});
        // A bounded top arch corridor lets cross-links pass above same-row cards.
        bandTop+=140;
      }
      layouts.forEach(({rootId,lists,totals,height})=>{
        const centerY=bandTop+height/2;
        positions.set(rootId,{x:rootX-WIDTH/2,y:centerY-nodeHeight(rootId)/2,w:WIDTH,h:nodeHeight(rootId)});
        lists.forEach((list,index)=>{
          const branch=index===0?'left':'right';let top=centerY-totals[index]/2;
          list.forEach(id=>{const size=branchHeight(id);place(id,rootX+(branch==='left'?-span:span),top+size/2,branch);top+=size+branchGap;});
        });
        bandTop+=height+12;
      });
      routedVisible=planRoutes();passes++;
      const conflicts=routedVisible.length;
      if(!best||conflicts<best.conflicts){
        best={conflicts,positions:new Map(positions),sections:[...sectionPositions],width:stageWidth,top:bandTop,
          plans:new Map(wirePlans),routed:new Set(routedEdges),visible:[...routedVisible]};
      }
      if(!conflicts)break;
      }
      positions.clear();best.positions.forEach((p,id)=>positions.set(id,p));sectionPositions=best.sections;
      stageWidth=best.width;bandTop=best.top;routedVisible=best.visible;
      wirePlans.clear();best.plans.forEach((p,edge)=>wirePlans.set(edge,p));routedEdges.clear();best.routed.forEach(edge=>routedEdges.add(edge));
      shell.setAttribute('data-layout-passes',String(passes));
      if(routedVisible.length){
        stageWidth+=Math.max(...routedVisible.map(edge=>labelSizes.get(edge).width))+48;
        bandTop+=12;
        for(const edge of routedVisible){const size=labelSizes.get(edge);crossSlots.set(edge,{...size,x:stageWidth/2,y:bandTop+size.height/2});bandTop+=size.height+28;}
      }
      routingBottom=bandTop+12;
      stageHeight=bandTop+24;
      stage.style.width=stageWidth+'px';stage.style.height=stageHeight+'px';
      wires.setAttribute('viewBox',`0 0 ${stageWidth} ${stageHeight}`);
      wires.setAttribute('width',String(stageWidth));wires.setAttribute('height',String(stageHeight));
      wires.style.width=stageWidth+'px';wires.style.height=stageHeight+'px';
      wires.style.maxWidth='none';wires.style.minWidth='0';wires.style.margin='0';
      sectionLayer.replaceChildren();
      sectionPositions.forEach(({top,text})=>{
        const item=make('div','lfm-mm-section',text);item.setAttribute('role','heading');item.setAttribute('aria-level','4');
        item.style.left=MARGIN+'px';item.style.top=top+'px';item.style.width=(stageWidth-MARGIN*2)+'px';sectionLayer.append(item);
      });
      drawWires();drawNodes();updateSelection();
      const visibleEdges=validEdges.filter(edge=>positions.has(edge.from)&&positions.has(edge.to)).length;
      count.textContent=say(`图中 ${positions.size} / ${graphNodes.length} 个框架 · ${visibleEdges} / ${validEdges.length} 条关系${unlinkedIds.length?` · 另 ${unlinkedIds.length} 个见列表`:''}`,`Graph: ${positions.size} / ${graphNodes.length} frameworks · ${visibleEdges} / ${validEdges.length} links${unlinkedIds.length?` · ${unlinkedIds.length} more in the list`:''}`);
      autoFit?fit():setScale(scale);
      if(focusId)focus(focusId);
    }
    function reveal(target,focusDetail=false){
      if(unlinkedButtons.has(target.id)){
        selected=target.id;selectedEdge=null;hide();unlinked.open=true;
        unlinkedDetail.replaceChildren(options.describe(target.id));
        unlinkedDetail.setAttribute('data-framework-id',target.id);
        unlinkedDetail.setAttribute('aria-labelledby',unlinkedButtons.get(target.id).id);
        updateSelection();
        if(focusDetail){unlinkedDetail.scrollIntoView?.({block:'nearest'});unlinkedDetail.focus({preventScroll:true});}
        return;
      }
      let id=target.id;
      while(id){expanded.add(id);id=parent.get(id);}
      selected=target.id;selectedEdge=null;render(false,target.id);
    }
    search.addEventListener('input',()=>{
      const query=search.value.trim().toLowerCase();resultList.replaceChildren();results.hidden=!query;
      if(!query){selected=null;selectedEdge=null;updateSelection();hide();return;}
      const matches=nodes.filter(n=>n.title.toLowerCase().includes(query)||n.summary?.toLowerCase().includes(query));
      searchStatus.textContent=say(`找到 ${matches.length} 个框架`,`Found ${matches.length} frameworks`);
      for(const node of matches){const item=make('button','lfm-mm-result',`${String(order(node.id)).padStart(2,'0')} · ${node.title}`);item.type='button';item.setAttribute('data-result-id',node.id);item.addEventListener('click',()=>reveal(node,true));resultList.append(item);}
      if(matches.length)reveal(matches[0]);else{selected=null;selectedEdge=null;updateSelection();hide();}
    });
    const refresh=()=>{if(host.offsetWidth)render(false,selected||primaryRoot);};
    document.fonts?.ready?.then(()=>{fontEpoch++;refresh();});
    document.fonts?.addEventListener('loadingdone',()=>{fontEpoch++;refresh();});
    window.addEventListener('resize',()=>{hide();if(host.offsetWidth)render(true);});
    if(typeof ResizeObserver!=='undefined'){
      let width=-1,height=-1;
      new ResizeObserver(()=>{const w=viewport.clientWidth,h=viewport.clientHeight;if(w===width&&h===height)return;width=w;height=h;hide();if(w>0)requestAnimationFrame(()=>render(false));}).observe(viewport);
    }
    render(true);
    return {refresh,hide,motion,destroy(){motion?.destroy();hide();hover.remove();}};
  }
  window.LFMMindMap={mount};
})();
