/* Offline diagram studio: one geometry model for cards, ports and routes. */
(function () {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const make = (tag, text, cls) => { const n=document.createElement(tag); if(text!=null)n.textContent=text; if(cls)n.className=cls; return n; };
  const svgEl = (tag, attrs) => {const n=document.createElementNS(NS,tag);Object.entries(attrs||{}).forEach(([k,v])=>n.setAttribute(k,v));return n;};
  let serial=0;
  function ordered(nodes, edges, path) {
    if(path && path.length) return [...path.map(id=>nodes.find(n=>n.id===id)).filter(Boolean),...nodes.filter(n=>!path.includes(n.id))];
    const pending=new Set(nodes.map(n=>n.id)), result=[];
    while(pending.size){
      const ready=nodes.filter(n=>pending.has(n.id)&&!edges.some(e=>e.to===n.id&&pending.has(e.from)&&e.kind!=='feedback'&&e.type!=='feedback'));
      // Cycles retain source order and explicit arrows; no invented hierarchy.
      const last=result[result.length-1];
      const degree=id=>edges.filter(e=>e.from===id||e.to===id).length;
      const near=id=>last&&edges.some(e=>(e.from===last.id&&e.to===id)||(e.to===last.id&&e.from===id));
      ready.sort((a,b)=>Number(!!near(b.id))-Number(!!near(a.id))||degree(b.id)-degree(a.id)||nodes.indexOf(a)-nodes.indexOf(b));
      const batch=[ready.length?ready[0]:nodes.find(n=>pending.has(n.id))];
      batch.forEach(n=>{pending.delete(n.id);result.push(n);});
    }
    return result;
  }
  function mount(host, options) {
    const en=options.language==='en', say=(zh,eng)=>en?eng:zh, uid='diagram-'+(++serial);
    const edges=options.edges||[], nodes=options.kind==='methodology'&&!options.mainPath?.length?options.nodes.slice():ordered(options.nodes,edges,options.mainPath), index=new Map(nodes.map((n,i)=>[n.id,i]));
    const root=make('section',null,'diagram-studio'); root.setAttribute('aria-label',options.title);
    const heading=make('div',null,'diagram-heading');
    const headingCopy=make('div');headingCopy.append(make('span',options.kind==='framework'?say('概念之间 · 逻辑相连','CONCEPTS · CONNECTIONS'):say('从理解到应用 · 全文贯通','UNDERSTAND · CONNECT · APPLY'),'diagram-kicker'),make('h3',options.title));
    const count=make('span',`${nodes.length} ${say('节点','nodes')} / ${edges.length} ${say('关系','links')}`,'diagram-count');heading.append(headingCopy,count);root.append(heading);
    const toolbar=make('div',null,'diagram-toolbar'),tools=make('div',null,'diagram-tools');
    const zoomOut=make('button','−'),zoomIn=make('button','+'),fit=make('button',say('适合宽度','Fit width')),overview=make('button',say('查看全图','Overview')),full=make('button',say('全屏查看','Full screen'));
    zoomOut.setAttribute('aria-label',say('缩小关系图','Zoom out'));zoomIn.setAttribute('aria-label',say('放大关系图','Zoom in'));
    const directionButton=make('button',say('方向演示','Show directions'));
    directionButton.setAttribute('aria-pressed','false');
    const scaleLabel=make('output','100%');[zoomOut,zoomIn,fit,overview,full,directionButton].forEach(b=>b.type='button');tools.append(zoomOut,scaleLabel,zoomIn,fit,overview,directionButton,full);
    const legend=make('p',null,'diagram-legend');
    [['source',say('材料依据','Source evidence')],['inference',say('整合推断','Inference')],['feedback',say('反馈 / 回路','Feedback')]].forEach(([kind,label])=>{const item=make('span',null,'diagram-legend-item');const swatch=make('i',null,'diagram-legend-swatch is-'+kind);swatch.setAttribute('aria-hidden','true');item.append(swatch,make('span',label));legend.append(item);});
    toolbar.append(legend,tools);root.append(toolbar);
    // Safety net: an undeclared relationship set must say so out loud instead of looking like a bare node cloud.
    if(nodes.length>1&&!edges.length){const note=make('p',say('这份页面尚未声明节点之间的关系：下面只列出卡片，没有可展开的连线。这是关系图数据缺失，不是渲染故障。','No relationships were declared for this page: the cards below are listed without any connecting links. This is missing relationship data, not a rendering fault.'),'diagram-empty');note.setAttribute('role','status');root.append(note);}
    const viewport=make('div',null,'diagram-viewport');viewport.tabIndex=0;viewport.setAttribute('aria-label',say('关系图画布，可滚动及放大','Diagram canvas; scroll and zoom'));
    const sizer=make('div',null,'diagram-sizer'),stage=make('div',null,'diagram-stage');sizer.append(stage);viewport.append(sizer);root.append(viewport);host.replaceChildren(root);
    const labelMeasure=document.createElement('canvas').getContext('2d');
    // Components keep their own source-backed topology. Allocate only the columns
    // they actually use: a single chain no longer reserves an empty three-column grid.
    const placement=new Map(),groups=[],unseen=new Set(nodes.map(n=>n.id));let totalRows=0;
    while(unseen.size){const seed=unseen.values().next().value,ids=new Set([seed]),queue=[seed];unseen.delete(seed);
      while(queue.length){const id=queue.shift();edges.filter(e=>e.from===id||e.to===id).forEach(e=>{const other=e.from===id?e.to:e.from;if(unseen.has(other)){unseen.delete(other);ids.add(other);queue.push(other);}});}
      groups.push({ids});
    }
    groups.forEach(g=>{
      const pending=nodes.filter(n=>g.ids.has(n.id)),rows=[];
      while(pending.length){let ready=pending.filter(n=>!edges.some(e=>e.to===n.id&&pending.some(p=>p.id===e.from)&&e.kind!=='feedback'&&e.type!=='feedback'));
        if(!ready.length)ready=[pending[0]]; // A source cycle keeps its recorded order.
        for(let i=0;i<ready.length;i+=3)rows.push(ready.slice(i,i+3));
        ready.forEach(n=>pending.splice(pending.indexOf(n),1));
      }
      g.rows=rows;g.cols=Math.max(1,...rows.map(row=>row.length));
    });
    const bands=[];let band=[],bandCols=0;
    groups.forEach(g=>{
      if(band.length&&bandCols+g.cols>3){bands.push(band);band=[];bandCols=0;}
      band.push(g);bandCols+=g.cols;
    });
    if(band.length)bands.push(band);
    const cols=Math.max(1,...bands.map(band=>band.reduce((sum,g)=>sum+g.cols,0)));
    bands.forEach((band,bandIndex)=>{
      const bandCols=band.reduce((sum,g)=>sum+g.cols,0),bandRows=Math.max(...band.map(g=>g.rows.length));
      let col=(cols-bandCols)/2;
      band.forEach(g=>{
        g.start=totalRows;g.end=totalRows+g.rows.length-1;
        g.rows.forEach((row,r)=>{const offset=(g.cols-row.length)/2;row.forEach((n,j)=>placement.set(n.id,{row:totalRows+r,col:col+offset+j}));});
        col+=g.cols;
      });
      totalRows+=bandRows+(bandIndex<bands.length-1?1:0);
    });
    const cw=286,gap=Math.max(128,...edges.filter(e=>e.kind!=='feedback'&&e.type!=='feedback').map(e=>labelMetrics(e.label||say('关联','Related')).width+52)),left=32,top=42,positions=new Map(),cards=new Map();
    const surfaceWidth=left*2+cols*cw+(cols-1)*gap;
    nodes.forEach((n,i)=>{
      const {row,col}=placement.get(n.id);
      const card=make('article',null,'diagram-card');card.dataset.nodeId=n.id;card.dataset.tone=String(row%3);card.style.width=cw+'px';
      const button=make('button',null,'diagram-node-button');button.type='button';button.setAttribute('aria-label',n.title);button.setAttribute('aria-pressed','false');
      const meta=make('div',null,'diagram-card-meta');
      const number=options.kind==='framework'&&Number.isInteger(n.sourceOrder)&&n.sourceOrder>0?n.sourceOrder:index.get(n.id)+1;
      if(options.showNumbers!==false)meta.append(make('span',String(number).padStart(2,'0'),'diagram-number'));
      meta.append(make('span',n.tag||say('逻辑节点','Logic node'),'diagram-tag'));
      button.title=n.title;button.append(meta,make('h4',n.title),make('p',n.summary||n.output||'','diagram-summary'));card.append(button);
      stage.append(card);cards.set(n.id,card);positions.set(n.id,{row,col,x:left+col*(cw+gap),h:0,y:0});button.onclick=()=>select(n.id);
    });
    const svg=svgEl('svg',{class:'diagram-wires',role:'group','aria-label':say('节点之间的逻辑关系','Relationships between nodes')});stage.prepend(svg);
    // Keep every relationship label above every wire and direction cue,
    // including edges created later and paths rebuilt during zoom or resize.
    const wireLayer=svgEl('g',{class:'diagram-wire-layer','aria-hidden':'true'});
    const flowLayer=svgEl('g',{class:'diagram-flow-layer','aria-hidden':'true'});
    const labelLayer=svgEl('g',{class:'diagram-label-layer'});
    svg.append(wireLayer,flowLayer,labelLayer);
    // Surfaces are painted with inline styles read from the themed palette. Stylesheet
    // backgrounds inside this page can be alpha-blended with white by the rendering path
    // (verified 2026-09-18), which turns dark cards light gray; inline button styles do not.
    const readPal=()=>{const cs=getComputedStyle(root);const t=k=>cs.getPropertyValue(k).trim();return{card:t('--dg-card'),dimCard:t('--dg-dim-card')};};
    let pal=readPal();
    const paintSurface=c=>{
      const b=c.querySelector('.diagram-node-button');
      if(b)b.style.background=c.classList.contains('is-dimmed')?pal.dimCard:pal.card;
    };
    cards.forEach(paintSurface);
    new MutationObserver(()=>{pal=readPal();cards.forEach(paintSurface);}).observe(document.body,{attributes:true,attributeFilter:['data-theme','class','style']});
    // Arrowheads read their colour from the themed CSS class, never a hard-coded fill.
    const defs=svgEl('defs');[['normal','dg-arrow-normal',15],['feedback','dg-arrow-feedback',16],['inference','dg-arrow-inference',14]].forEach(([kind,cls,size])=>{const m=svgEl('marker',{id:uid+'-'+kind,viewBox:'0 0 10 10',refX:10,refY:5,markerWidth:size,markerHeight:size,markerUnits:'userSpaceOnUse',orient:'auto'});m.append(svgEl('path',{d:'M 0 0 L 10 5 L 0 10 Z',class:cls}));defs.append(m);});svg.append(defs);
    const help=make('p',say('点击任意卡片，查看与它直接相连的卡片及关系；点击空白处恢复全图。','Click a card to see its connected cards and relationships. Click empty space to reset.'),'diagram-help');root.append(help);
    const connections=make('div',null,'diagram-connections');connections.hidden=true;connections.setAttribute('aria-live','polite');root.append(connections);
    if(options.detail){options.detail.hidden=true;}
    const groupLabels=groups.length>1?groups.map(g=>{const label=make('div',say('独立关系分支 · ','Separate branch · ')+nodes.find(n=>g.ids.has(n.id)).title,'diagram-group-label');stage.append(label);return {g,label};}):[];
    const paths=new Map(),flows=new Map(),labels=new Map();let width=surfaceWidth,height=0,scale=1,selected=null,selectedEdge=null,manualZoom=false,fitMode='width';
    const motion=window.LFMGraphMotion?.mount({root,viewport,button:directionButton,language:options.language});
    function labelMetrics(text){
      if(labelMeasure)labelMeasure.font='700 11px '+(getComputedStyle(root).getPropertyValue('--font-display').trim()||'system-ui');
      const measure=value=>labelMeasure?labelMeasure.measureText(value).width+Array.from(value).length*.11:Array.from(value).length*11.5;
      const lines=[];let line='';
      for(const character of Array.from(String(text).replace(/\s+/g,' ').trim())){
        if(line&&measure(line+character)>220){
          const space=line.lastIndexOf(' ');
          if(space>0){lines.push(line.slice(0,space));line=line.slice(space+1)+character;}
          else{lines.push(line);line=character;}
        }else line+=character;
      }
      if(line||!lines.length)lines.push(line);
      return{lines,width:Math.max(52,Math.ceil(Math.max(...lines.map(measure)))+24),height:lines.length*16+8};
    }
    function routeSegments(points){
      const simple=[];
      points.forEach(point=>{
        const last=simple[simple.length-1];
        if(last&&last.x===point.x&&last.y===point.y)return;
        const previous=simple[simple.length-2];
        if(previous&&((previous.x===last.x&&last.x===point.x&&(last.y-previous.y)*(point.y-last.y)>0)||(previous.y===last.y&&last.y===point.y&&(last.x-previous.x)*(point.x-last.x)>0)))simple.pop();
        simple.push(point);
      });
      return simple.slice(1).map((b,i)=>({a:simple[i],b,horizontal:simple[i].y===b.y,length:Math.hypot(b.x-simple[i].x,b.y-simple[i].y)}));
    }
    function pathDescription(points){return points.map((point,i)=>(i?'L ':'M ')+point.x+' '+point.y).join(' ');}
    function positionLabels(routes){
      const placed=[];
      const cardsBounds=Array.from(positions.values(),p=>({left:p.x-8,right:p.x+cw+8,top:p.y-8,bottom:p.y+p.h+8}));
      const boxFor=(x,y,r)=>({left:x-r.width/2,right:x+r.width/2,top:y-r.height/2,bottom:y+r.height/2});
      function slot(route,host){
        if(!host)return null;
        const horizontal=host.horizontal,half=(horizontal?route.width:route.height)/2;
        // A slot needs clearance in both axes. A tall vertical corridor near
        // the left edge cannot hold a wide English label inside the canvas.
        if(horizontal?host.a.y<route.height/2+8:host.a.x<route.width/2+8)return null;
        const first=horizontal?host.a.x:host.a.y,last=horizontal?host.b.x:host.b.y;
        const low=Math.max(Math.min(first,last)+half+16,8+half),high=Math.max(first,last)-half-16;
        if(low>high)return null;
        let intervals=[[low,high]];
        const subtract=(start,end)=>{intervals=intervals.flatMap(([a,b])=>{
          if(end<a||start>b)return[[a,b]];
          const result=[];if(start>a)result.push([a,start-.5]);if(end<b)result.push([end+.5,b]);
          return result.filter(([x,y])=>x<=y);
        });};
        const obstacles=[...cardsBounds,...placed];
        routes.forEach(other=>other.segments.forEach(segment=>{
          if(segment===host)return;
          obstacles.push({left:Math.min(segment.a.x,segment.b.x)-8,right:Math.max(segment.a.x,segment.b.x)+8,
            top:Math.min(segment.a.y,segment.b.y)-8,bottom:Math.max(segment.a.y,segment.b.y)+8});
        }));
        obstacles.forEach(box=>{
          if(horizontal&&host.a.y>=box.top-route.height/2&&host.a.y<=box.bottom+route.height/2)subtract(box.left-route.width/2,box.right+route.width/2);
          else if(!horizontal&&host.a.x>=box.left-route.width/2&&host.a.x<=box.right+route.width/2)subtract(box.top-route.height/2,box.bottom+route.height/2);
        });
        const middle=(first+last)/2;
        const values=intervals.map(([a,b])=>Math.max(a,Math.min(b,middle))).sort((a,b)=>Math.abs(a-middle)-Math.abs(b-middle));
        if(!values.length)return null;
        return horizontal?{x:values[0],y:host.a.y}:{x:host.a.x,y:values[0]};
      }
      function extendRoute(route){
        const source=positions.get(route.from),target=positions.get(route.to);
        const sourceRowBottom=Math.max(...Array.from(positions.values()).filter(p=>p.row===source.row).map(p=>p.y+p.h));
        const first=route.segments[0],last=route.segments[route.segments.length-1];
        const start=first.a,end=last.b;
        const exit=first.horizontal?{x:start.x+Math.sign(first.b.x-start.x)*20,y:start.y}:{x:start.x,y:start.y+Math.sign(first.b.y-start.y)*20};
        const entry=last.horizontal?{x:end.x-Math.sign(end.x-last.a.x)*20,y:end.y}:{x:end.x,y:end.y-Math.sign(end.y-last.a.y)*20};
        const exitTurn={x:exit.x,y:Math.max(exit.y,sourceRowBottom+24)};
        const entryTurn=last.horizontal?{x:entry.x,y:target.y-28}:entry;
        const rail=width+route.width/2+32;
        let points,lastRail=rail;
        if(Math.abs(entryTurn.y-exitTurn.y)<route.height+40){
          const turnY=Math.max(exitTurn.y,entryTurn.y,height)+route.height+64;
          lastRail=rail+route.width+40;
          points=[start,exit,exitTurn,{x:rail,y:exitTurn.y},{x:rail,y:turnY},{x:lastRail,y:turnY},{x:lastRail,y:entryTurn.y},entryTurn,entry,end];
          height=Math.max(height,turnY+24);
        }else points=[start,exit,exitTurn,{x:rail,y:exitTurn.y},{x:rail,y:entryTurn.y},entryTurn,entry,end];
        const description=pathDescription(points);
        paths.get(route.id).setAttribute('d',description);flows.get(route.id).setAttribute('d',description);
        route.segments=routeSegments(points);route.external=true;route.rail=rail;route.anchor=null;
        width=lastRail+route.width/2+32;
      }
      // Every label stays on its own straight segment. If a corridor is too
      // crowded, extend that edge's route and reserve a new outside segment.
      for(let attempt=0;attempt<=routes.length*2;attempt++){
        placed.length=0;routes.forEach(route=>route.anchor=null);let retry=false;
        for(const route of routes){
          const ordered=route.segments.slice().sort((a,b)=>{
            if(route.external)return Number(b.a.x===route.rail&&b.b.x===route.rail)-Number(a.a.x===route.rail&&a.b.x===route.rail)||b.length-a.length;
            return Number(b.horizontal)-Number(a.horizontal)||b.length-a.length;
          });
          let found=null;
          for(const segment of ordered){found=slot(route,segment);if(found)break;}
          if(!found){extendRoute(route);retry=true;break;}
          route.anchor=found;
          const box=boxFor(found.x,found.y,route);
          placed.push({left:box.left-8,right:box.right+8,top:box.top-8,bottom:box.bottom+8});
        }
        if(!retry)break;
      }
      routes.forEach((route,i)=>{
        // The fresh outer rail has no foreign segment beyond the canvas;
        // its middle remains a safe slot if all crowded routes were extended.
        let found=route.anchor||slot(route,route.segments.find(s=>s.a.x===route.rail&&s.b.x===route.rail));
        if(!found){extendRoute(route);found=slot(route,route.segments.find(s=>s.a.x===route.rail&&s.b.x===route.rail));}
        if(!found)return;
        route.label.setAttribute('transform',`translate(${found.x} ${found.y})`);
        const box=boxFor(found.x,found.y,route),maskId=uid+'-label-gap-'+i;
        width=Math.max(width,box.right+20);height=Math.max(height,box.bottom+20);
        const mask=svgEl('mask',{id:maskId,class:'diagram-label-gap',maskUnits:'userSpaceOnUse',maskContentUnits:'userSpaceOnUse',x:-32,y:-32,width:width+64,height:height+64});
        mask.append(svgEl('rect',{x:-32,y:-32,width:width+64,height:height+64,fill:'white'}),svgEl('rect',{x:box.left-3,y:box.top-3,width:route.width+6,height:route.height+6,rx:3,fill:'black'}));
        defs.append(mask);paths.get(route.id).setAttribute('mask','url(#'+maskId+')');flows.get(route.id).setAttribute('mask','url(#'+maskId+')');
        // Re-routing changes the measured travel used by both quiet animations.
        const path=paths.get(route.id),flow=flows.get(route.id);let length=0;
        try{length=path.getTotalLength();}catch(_){ }
        if(length>0){
          path.style.setProperty('--wire-len',length.toFixed(1));
          path.style.setProperty('--draw-dur',Math.max(360,Math.min(750,length*.45)).toFixed(0)+'ms');
          const travel=Math.max(40,length-20),head=route.feedback?34:route.inference?20:30;
          flow.style.setProperty('--flow-travel',travel.toFixed(1));flow.style.setProperty('--flow-dash',head+' '+(travel+head).toFixed(0));
        }
      });
      // Keep earlier masks large enough after any outer route expands the stage.
      defs.querySelectorAll('.diagram-label-gap').forEach(mask=>{
        mask.setAttribute('width',width+64);mask.setAttribute('height',height+64);
        mask.firstElementChild.setAttribute('width',width+64);mask.firstElementChild.setAttribute('height',height+64);
      });
    }
    // A quiet entrance is independent of selected/preview direction overlays.
    const RM=matchMedia('(prefers-reduced-motion: reduce)');
    const motionOff=()=>RM.matches||document.body.dataset.motion==='off';
    let rebuildFrame=0,visibleNow=false,io=null,hasDrawn=false;
    function applyDraw(){svg.classList.add('is-drawn','is-static');}
    function settleWires(){
      cancelAnimationFrame(rebuildFrame);
      svg.classList.remove('is-drawn');
      rebuildFrame=requestAnimationFrame(()=>{
        rebuildFrame=0;
        if(motionOff()||hasDrawn){hasDrawn=true;applyDraw();}
        else if(visibleNow)playDraw();
      });
    }
    function armDraw(){
      svg.classList.remove('is-drawn','is-flowing');
    }
    function flowCancel(){motion?.select([]);svg.classList.remove('is-flowing');}
    function startFlow(){
      motion?.select(!selected?[]:edges.filter(edge=>selectedEdge?edge.id===selectedEdge:edge.from===selected||edge.to===selected).map(edge=>edge.id));
    }
    function playDraw(){
      hasDrawn=true;
      svg.classList.remove('is-static');
      svg.classList.add('is-drawn');
    }
    function layout(initial){
      /* A display:none panel reports clientWidth 0 and offsetHeight 0 for every
         descendant. Rebuilding on those numbers wrecks the diagram: cards keep the
         height they had, but the row pitch collapses to the minimum gap, the auto
         scale collapses, and the entry/exit ports stack up. That is
         what happens when a hidden panel is switched back on — the ResizeObserver
         fires during a window where the layout is half-applied.
         Skipping the rebuild leaves the previous geometry intact, and the
         ResizeObserver will call back with real numbers a frame later. */
      if(viewport.clientWidth<=0&&!initial)return;
      const rows=totalRows,heights=Array(rows).fill(0),loads=Array(rows).fill(0);
      nodes.forEach(n=>{const p=positions.get(n.id);p.h=cards.get(n.id).offsetHeight;heights[p.row]=Math.max(heights[p.row],p.h);});
      edges.forEach(e=>{const a=positions.get(e.from),b=positions.get(e.to);if(a&&b){loads[a.row]++;loads[b.row]++;}});
      const specs=new Map(edges.map(e=>[e.id,labelMetrics(e.label||say('关联','Related'))]));
      const incoming=new Map(),outgoing=new Map();nodes.forEach(n=>{incoming.set(n.id,edges.filter(e=>e.to===n.id));outgoing.set(n.id,edges.filter(e=>e.from===n.id));});
      let y=top;const rowY=[],gaps=Array.from({length:rows},(_,r)=>Math.max(92,64+(loads[r]+(loads[r+1]||0))*8));
      edges.forEach(e=>{
        const a=positions.get(e.from),b=positions.get(e.to);if(!a||!b||b.row!==a.row+1||e.kind==='feedback'||e.type==='feedback')return;
        const sx=a.x+cw*(outgoing.get(e.from).indexOf(e)+1)/(outgoing.get(e.from).length+1),tx=b.x+cw*(incoming.get(e.to).indexOf(e)+1)/(incoming.get(e.to).length+1),spec=specs.get(e.id);
        if(Math.abs(sx-tx)>.5&&Math.abs(sx-tx)<spec.width+32)gaps[a.row]=Math.max(gaps[a.row],2*(spec.height+32)+25);
        else gaps[a.row]=Math.max(gaps[a.row],spec.height+57);
      });
      for(let r=0;r<rows;r++){rowY[r]=y;y+=heights[r]+gaps[r];}
      positions.forEach((p,id)=>{p.y=rowY[p.row];const card=cards.get(id);card.style.left=p.x+'px';card.style.top=p.y+'px';});
      paths.forEach(p=>p.remove());paths.clear();flows.forEach(q=>q.remove());flows.clear();labels.forEach(g=>g.remove());labels.clear();
      defs.querySelectorAll('.diagram-label-gap').forEach(mask=>mask.remove());
      const railLabelWidth=Math.max(52,...Array.from(specs.values(),spec=>spec.width)),railStep=railLabelWidth+40;
      let lane=0,minY=16,railCursor=surfaceWidth+24+railLabelWidth/2;const routes=[];
      edges.forEach(e=>{
        const a=positions.get(e.from),b=positions.get(e.to);if(!a||!b)return;
        const feedback=e.kind==='feedback'||e.type==='feedback';
        const spec=specs.get(e.id);
        let d,lx,ly,points,external=false,rail=null;
        if(a.row===b.row&&Math.abs(a.col-b.col)===1&&!feedback){
          const forward=b.x>a.x,sy=a.y+74,ty=b.y+74;
          const x1=forward?a.x+cw+5:a.x-5,x2=forward?b.x-12:b.x+cw+12;
          d=`M ${x1} ${sy} L ${x2} ${ty}`;
          points=[{x:x1,y:sy},{x:x2,y:ty}];
          lx=(x1+x2)/2;ly=(sy+ty)/2;
        }else{
          const oi=outgoing.get(e.from).indexOf(e),ii=incoming.get(e.to).indexOf(e);
          const sx=a.x+cw*(oi+1)/(outgoing.get(e.from).length+1),tx=b.x+cw*(ii+1)/(incoming.get(e.to).length+1);
          const sy=a.y+a.h+5,ty=b.y-12;
          if(b.row===a.row+1&&!feedback){
            const mid=(rowY[a.row]+heights[a.row]+5+ty)/2;
            d=`M ${sx} ${sy} V ${mid} H ${tx} V ${ty}`;
            points=[{x:sx,y:sy},{x:sx,y:mid},{x:tx,y:mid},{x:tx,y:ty}];
            lx=(sx+tx)/2;ly=mid;
          }else{
            const exitY=rowY[a.row]+heights[a.row]+23,entryY=ty-18;minY=Math.min(minY,entryY);
            external=true;rail=railCursor;railCursor+=railStep;lane++;
            d=`M ${sx} ${sy} V ${exitY} H ${rail} V ${entryY} H ${tx} V ${ty}`;
            points=[{x:sx,y:sy},{x:sx,y:exitY},{x:rail,y:exitY},{x:rail,y:entryY},{x:tx,y:entryY},{x:tx,y:ty}];
            lx=rail;ly=(exitY+entryY)/2;
          }
        }
      const isInference=e.evidence==='inference';
      const cls='diagram-wire'+(feedback?' is-feedback':'')+(isInference?' is-inference':'');
      const p=svgEl('path',{d,class:cls,'aria-hidden':'true','data-edge-id':e.id,'data-edge-from':e.from,'data-edge-to':e.to,'marker-end':`url(#${uid}-${feedback?'feedback':isInference?'inference':'normal'})`});
      wireLayer.append(p);paths.set(e.id,p);
      // The flow head rides a second path with identical geometry, stacked above the
      // solid line so the effect runs ON the line rather than replacing it.
      const q=svgEl('path',{d,class:'diagram-flow'+(feedback?' is-feedback':'')+(isInference?' is-inference':''),'aria-hidden':'true','data-edge-id':e.id});
      flowLayer.append(q);flows.set(e.id,q);
      const labelText=e.label||say('关联','Related');
      const labelWidth=spec.width;
      const lg=svgEl('g',{class:'diagram-edge-label'+(feedback?' is-feedback':'')+(isInference?' is-inference':''),transform:`translate(${lx} ${ly})`,'data-node-id':e.from,'data-edge-id':e.id,tabindex:'0',role:'button','aria-label':labelText+' · '+nodes.find(n=>n.id===e.from).title+' → '+nodes.find(n=>n.id===e.to).title});
      const labelTextElement=svgEl('text',{x:0,y:4,'text-anchor':'middle'});
      spec.lines.forEach((line,i)=>{const span=svgEl('tspan',{x:0,y:4+(i-(spec.lines.length-1)/2)*16});span.textContent=line;labelTextElement.append(span);});
      lg.append(svgEl('rect',{x:-labelWidth/2,y:-spec.height/2,width:labelWidth,height:spec.height,rx:10}),labelTextElement);
      lg.addEventListener('click',ev=>{ev.stopPropagation();select(e.from,e.id);});
      lg.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();select(e.from,e.id);}});
      labelLayer.append(lg);labels.set(e.id,lg);
      routes.push({id:e.id,from:e.from,to:e.to,label:lg,width:spec.width,height:spec.height,segments:routeSegments(points),external,rail,feedback,inference:isInference});
      // Geometry is measured AFTER insertion: a detached SVG path reports a bogus
      // getTotalLength() in Chromium, which would freeze the head at its minimum travel.
      let len=0;try{len=p.getTotalLength();}catch(err){len=0;}
      if(len>0){
        p.style.setProperty('--wire-len',len.toFixed(1));
        // A short stagger gives direction without making the reader wait.
        const delay=Math.min(360,(a.row*40)+(outgoing.get(e.from).indexOf(e)*20));
        p.style.setProperty('--draw-delay',delay+'ms');
        p.style.setProperty('--draw-dur',Math.max(360,Math.min(750,len*.45)).toFixed(0)+'ms');
        // The comet travels the visible length minus the arrowhead, so it never
        // collides with the tip; the dash gap is scaled off the same measured length
        // so each wire shows exactly one head in flight however long it is.
        const travel=Math.max(40,len-20);
        q.style.setProperty('--flow-travel',travel.toFixed(1));
        const head=feedback?34:isInference?20:30;
        q.style.setProperty('--flow-dash',head+' '+(travel+head).toFixed(0));
      }
      // Feedback loops and inferred links run slower — weight and pace both carry meaning.
      q.style.setProperty('--flow-dur',(feedback?2.2:isInference?1.9:1.5)+'s');
      });
      width=lane?railCursor-railStep+railLabelWidth/2+24:surfaceWidth;height=y-gaps[rows-1]+Math.max(54,gaps[rows-1]);
      positionLabels(routes);
      // Top entry corridors for return arrows are inside the canvas.
      const pad=Math.max(0,16-minY);stage.style.paddingTop='0';
      svg.setAttribute('width',width);svg.setAttribute('height',height+pad);svg.style.top=pad+'px';
      cards.forEach((card,id)=>card.style.top=(positions.get(id).y+pad)+'px');height+=pad;
      groupLabels.forEach(({g,label})=>{label.style.top=(rowY[g.start]+pad-36)+'px';const first=Array.from(g.ids)[0];label.style.left=(positions.get(first)?.x||left)+'px';});
      // Labels share their parent SVG's padding offset with the paths.
      stage.style.width=width+'px';stage.style.height=height+'px';
      if(!manualZoom){
        const byWidth=(viewport.clientWidth-24)/width;
        const byHeight=(viewport.clientHeight-24)/height;
        const minimumReadable=fitMode!=='all'&&viewport.clientWidth<820?.8:.18;
        scale=Math.max(minimumReadable,Math.min(1,fitMode==='all'?Math.min(byWidth,byHeight):byWidth))||1;
      }
      setScale(scale);if(selected)highlight(selected,selectedEdge);
      // A path rebuild must leave a complete still map after the first entrance.
      armDraw();
      settleWires();
      motion?.replace(edges.filter(edge=>paths.has(edge.id)).map(edge=>({edge,paths:[paths.get(edge.id)],overlays:[flows.get(edge.id)]})));
      startFlow();
    }
    function setScale(value){
      scale=Math.max(.18,Math.min(1.8,value));stage.style.transform=`scale(${scale})`;
      sizer.style.width=Math.max(width*scale,viewport.clientWidth)+'px';
      sizer.style.height=Math.max(height*scale,viewport.clientHeight)+'px';
      stage.style.left=Math.max(0,(viewport.clientWidth-width*scale)/2)+'px';
      stage.style.top=Math.max(0,(viewport.clientHeight-height*scale)/2)+'px';
      scaleLabel.textContent=Math.round(scale*100)+'%';
    }
    function zoomBy(delta){
      hideHover();manualZoom=true;
      const old=scale,cx=(viewport.scrollLeft+viewport.clientWidth/2-stage.offsetLeft)/old,cy=(viewport.scrollTop+viewport.clientHeight/2-stage.offsetTop)/old;
      setScale(scale+delta);
      viewport.scrollLeft=stage.offsetLeft+cx*scale-viewport.clientWidth/2;
      viewport.scrollTop=stage.offsetTop+cy*scale-viewport.clientHeight/2;
    }
    function highlight(id,edgeId){const related=new Set([id]);edges.filter(e=>edgeId?e.id===edgeId:e.from===id||e.to===id).forEach(e=>{related.add(e.from);related.add(e.to);});cards.forEach((c,k)=>{c.classList.toggle('is-selected',k===id);c.classList.toggle('is-dimmed',!!id&&!related.has(k));c.querySelector('.diagram-node-button').setAttribute('aria-pressed',String(k===id));paintSurface(c);});edges.forEach(e=>{const on=!!id&&(edgeId?e.id===edgeId:e.from===id||e.to===id);const p=paths.get(e.id);if(p){p.classList.toggle('is-active',on);p.classList.toggle('is-dimmed',!!id&&!on);}const q=flows.get(e.id);if(q){q.classList.toggle('is-active',on);q.classList.toggle('is-dimmed',!!id&&!on);}const g=labels.get(e.id);if(g){g.classList.toggle('is-active',on);g.classList.toggle('is-dimmed',!!id&&!on);}});svg.classList.toggle('is-selecting',!!id);}
    function reset(){hideHover();selected=null;selectedEdge=null;flowCancel();highlight(null);connections.hidden=true;if(options.detail)options.detail.hidden=true;}
    function select(id,edgeId){hideHover();selected=id;selectedEdge=edgeId||null;highlight(id,selectedEdge);startFlow();connections.replaceChildren();connections.hidden=false;
      const close=make('button',say('恢复全图','Show all'),'diagram-reset');close.type='button';close.onclick=reset;
      connections.append(close,make('strong',nodes.find(n=>n.id===id).title));
      const nearby=edges.filter(e=>edgeId?e.id===edgeId:e.from===id||e.to===id);
      if(!nearby.length)connections.append(make('p',say('当前材料未提供与其他卡片的明确关系。','No supported connection to another card is recorded.')));
      nearby.forEach(e=>{const row=make('button',null,'diagram-connection');row.type='button';row.append(make('span',nodes.find(n=>n.id===e.from).title+' → '+nodes.find(n=>n.id===e.to).title),make('small',e.label||e.condition||say('关联','Related')));row.onclick=()=>select(e.from===id?e.to:e.from);connections.append(row);});
      if(options.onSelect&&options.detail){options.onSelect(id,edgeId);options.detail.hidden=true;const more=make('button',say('查看详细说明与出处','Details and sources'),'diagram-more');more.type='button';more.onclick=()=>{options.detail.hidden=!options.detail.hidden;more.setAttribute('aria-expanded',String(!options.detail.hidden));};more.setAttribute('aria-expanded','false');connections.append(more);}
    }
    // Hover preview renders the very same card data as the locked detail panel.
    const hover=make('div',null,'diagram-hovercard');hover.setAttribute('aria-hidden','true');hover.tabIndex=0;document.body.append(hover);
    let hoverId=null,hoverEdgeId=null,hoverAnchor=null,hoverHideTimer=null;
    function cancelHoverHide(){clearTimeout(hoverHideTimer);hoverHideTimer=null;}
    function hideHover(){cancelHoverHide();hover.classList.remove('is-visible');hover.setAttribute('aria-hidden','true');hoverId=null;hoverEdgeId=null;hoverAnchor=null;}
    function scheduleHoverHide(){if(hoverHideTimer||!hoverId||hover.contains(document.activeElement))return;hoverHideTimer=setTimeout(hideHover,300);}
    function inHoverBridge(x,y){
      if(!hoverAnchor||!hover.classList.contains('is-visible'))return false;
      return window.LFMHoverBridge.contains(hoverAnchor.getBoundingClientRect(),hover.getBoundingClientRect(),x,y);
    }
    function showHover(id,card,edgeId=null){
      if(!options.describe)return;
      cancelHoverHide();
      if(hoverId===id&&hoverEdgeId===edgeId&&hoverAnchor===card)return;
      if(hoverId!==id||hoverEdgeId!==edgeId){hover.replaceChildren(options.describe(id,edgeId));hoverId=id;hoverEdgeId=edgeId;hover.scrollTop=0;}
      hoverAnchor=card;
      hover.classList.add('is-visible');
      hover.setAttribute('aria-hidden','false');
      motion?.preview(edges.filter(edge=>edgeId?edge.id===edgeId:edge.from===id||edge.to===id).map(edge=>edge.id));
      // Anchor once to the node. A panel that chases the pointer creates a
      // moving gap and makes a slow pointer transfer fail.
      const box=hover.getBoundingClientRect(),anchor=card.getBoundingClientRect();
      const gap=8,margin=12;
      const fitsRight=anchor.right+gap+box.width<=innerWidth-margin;
      const fitsLeft=anchor.left-gap-box.width>=margin;
      let left=fitsRight?anchor.right+gap:(fitsLeft?anchor.left-gap-box.width:anchor.right+gap);
      let top=anchor.top;
      left=Math.max(margin,Math.min(left,innerWidth-box.width-margin));
      top=Math.max(margin,Math.min(top,innerHeight-box.height-margin));
      hover.style.left=left+'px';
      hover.style.top=top+'px';
    }
    hover.addEventListener('pointerenter',cancelHoverHide);
    hover.addEventListener('pointerleave',e=>{if(!inHoverBridge(e.clientX,e.clientY))scheduleHoverHide();});
    document.addEventListener('pointermove',e=>{
      if(e.pointerType==='touch'||!hoverId)return;
      if(inHoverBridge(e.clientX,e.clientY))cancelHoverHide();
      else scheduleHoverHide();
    });
    hover.addEventListener('wheel',e=>window.LFMScrollChain.route(e,hover,viewport),{passive:false});
    viewport.addEventListener('wheel',e=>{
      if(!hover.classList.contains('is-visible')||!hoverAnchor||!inHoverBridge(e.clientX,e.clientY))return;
      window.LFMScrollChain.route(e,hover,viewport);
    },{passive:false});
    function previewTarget(target){
      const label=target.closest('.diagram-edge-label');
      if(label){showHover(label.dataset.nodeId,label,label.dataset.edgeId);return;}
      const card=target.closest('.diagram-card');
      if(card)showHover(card.dataset.nodeId,card);
    }
    stage.addEventListener('pointermove',e=>{if(e.pointerType!=='touch')previewTarget(e.target);});
    stage.addEventListener('focusin',e=>previewTarget(e.target));
    stage.addEventListener('focusout',()=>{setTimeout(()=>{if(!stage.contains(document.activeElement)&&!hover.contains(document.activeElement))scheduleHoverHide();},0);});
    hover.addEventListener('focusin',cancelHoverHide);
    hover.addEventListener('focusout',()=>{setTimeout(()=>{if(!hover.contains(document.activeElement))scheduleHoverHide();},0);});
    document.addEventListener('pointerdown',e=>{if(hoverAnchor&&!hover.contains(e.target)&&!hoverAnchor.contains(e.target))hideHover();});
    document.addEventListener('keydown',e=>{if(e.key==='Escape')hideHover();});
    document.addEventListener('lfm-panel-change',()=>{hideHover();requestAnimationFrame(()=>requestAnimationFrame(refresh));});
    window.addEventListener('scroll',hideHover,{passive:true});
    stage.addEventListener('pointerleave',e=>{if(!inHoverBridge(e.clientX,e.clientY))scheduleHoverHide();});
    viewport.addEventListener('scroll',hideHover);
    viewport.addEventListener('click',e=>{if(!e.target.closest('.diagram-card,.diagram-edge-label'))reset();});
    // Escape is layered: in fullscreen the FIRST Escape must collapse the overlay
    // (and put the studio back), and only a subsequent Escape clears a selected node.
    // The fullscreen handler is therefore registered first and marks the event handled
    // via a flag, so the selection handler below does not swallow it with
    // stopImmediatePropagation() before the overlay gets a chance to close.
    let escapeHandledByExpand=false;
    zoomOut.onclick=()=>zoomBy(-.15);zoomIn.onclick=()=>zoomBy(.15);
    fit.onclick=()=>{hideHover();fitMode='width';manualZoom=false;layout();viewport.scrollTop=0;};
    overview.onclick=()=>{hideHover();fitMode='all';manualZoom=false;layout();viewport.scrollLeft=0;viewport.scrollTop=0;};
    let placeholder=null,detailPlaceholder=null,previousScroll=null;
    function expand(){hideHover();const box=root.getBoundingClientRect(),scroll={x:window.scrollX,y:window.scrollY};const on=root.classList.toggle('is-expanded');full.textContent=on?say('退出全屏','Exit full screen'):say('全屏查看','Full screen');
      if(on){previousScroll=scroll;root.append(hover);placeholder=make('div');placeholder.style.width=box.width+'px';placeholder.style.height=box.height+'px';root.before(placeholder);document.body.append(root);root.setAttribute('aria-modal','true');root.setAttribute('role','dialog');root.dataset.previousOverflow=document.body.style.overflow;document.body.style.overflow='hidden';
        if(options.detail){detailPlaceholder=make('span');options.detail.before(detailPlaceholder);root.append(options.detail);options.detail.classList.add('diagram-expanded-detail');}
        full.focus();
      }else{document.body.append(hover);root.removeAttribute('role');root.removeAttribute('aria-modal');document.body.style.overflow=root.dataset.previousOverflow||'';placeholder.replaceWith(root);if(detailPlaceholder){detailPlaceholder.replaceWith(options.detail);options.detail.classList.remove('diagram-expanded-detail');detailPlaceholder=null;}full.focus();if(previousScroll)window.scrollTo({left:previousScroll.x,top:previousScroll.y,behavior:'instant'});previousScroll=null;}
      manualZoom=false;requestAnimationFrame(layout);
    }
    let nativeFullscreen=false,fullscreenPending=false;
    async function toggleFullscreen(){
      if(fullscreenPending)return;
      if(document.fullscreenElement===root){await document.exitFullscreen();return;}
      if(root.classList.contains('is-expanded')){expand();return;}
      expand();
      if(root.requestFullscreen){
        fullscreenPending=true;
        try{await root.requestFullscreen();nativeFullscreen=document.fullscreenElement===root;}
        catch(_){/* Keep the viewport-sized fallback when native fullscreen is unavailable. */}
        finally{fullscreenPending=false;}
      }
    }
    document.addEventListener('fullscreenchange',()=>{
      if(document.fullscreenElement===root){nativeFullscreen=true;requestAnimationFrame(layout);}
      else if(nativeFullscreen){nativeFullscreen=false;if(root.classList.contains('is-expanded'))expand();}
    });
    full.onclick=toggleFullscreen;root.addEventListener('keydown',e=>{if(!root.classList.contains('is-expanded'))return;if(e.key==='Escape'){escapeHandledByExpand=true;toggleFullscreen();e.stopPropagation();}if(e.key==='Tab'){const focusable=Array.from(root.querySelectorAll('button,[tabindex="0"],summary')).filter(n=>n.getClientRects().length);const first=focusable[0],last=focusable[focusable.length-1];if(e.shiftKey&&document.activeElement===first){e.preventDefault();last.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first.focus();}}});
    // Registered AFTER the fullscreen handler so the overlay gets Escape first.
    root.addEventListener('keydown',e=>{if(e.key!=='Escape')return;if(escapeHandledByExpand){escapeHandledByExpand=false;return;}hideHover();if(selected){reset();e.stopImmediatePropagation();}});
    /* IntersectionObserver alone can miss a panel switch at the same scroll
       position. The visibility check presents the entrance once, then restores
       a static map after tab switches and fullscreen changes. */
    const announce=()=>{
      const r=root.getBoundingClientRect();
      const on=r.height>0&&r.width>0&&r.bottom>0&&r.top<innerHeight+240;
      if(on===visibleNow)return;
      visibleNow=on;
      if(on){ if(motionOff()||hasDrawn){hasDrawn=true;applyDraw();return;} playDraw(); }
      else { motion?.refresh(); }
    };
    const observer=new ResizeObserver(()=>{if(viewport.clientWidth>0){hideHover();layout();announce();}});observer.observe(viewport);
    if('IntersectionObserver' in window){io=new IntersectionObserver(()=>announce(),{threshold:.12});io.observe(root);}
    else{visibleNow=true;playDraw();}
    // A panel switch changes visibility without moving the viewport, so it must be
    // re-announced. The ResizeObserver and the scroll listener cover the remaining
    // paths (expand/collapse, resize, and ordinary scrolling).
    document.addEventListener('visibilitychange',announce);
    window.addEventListener('scroll',announce,{passive:true});
    RM.addEventListener?.('change',()=>{armDraw();
      if(motionOff()){hasDrawn=true;applyDraw();}
      else {applyDraw();if(selected)startFlow();}});
    document.addEventListener('lfm-motion-change',()=>{
      if(motionOff()){motion?.refresh();hasDrawn=true;applyDraw();}
    });
    if(document.fonts)document.fonts.ready.then(()=>layout(true));
    requestAnimationFrame(()=>layout(true));
    /* refresh() is the external hook for a host that switches panels without
       scrolling (a tab click). The host must call it AFTER the panel is laid out —
       a double rAF is the reliable point. */
    function refresh(){ if(viewport.clientWidth<=0)return; layout(); announce(); }
    return {select,layout,root,positions,refresh,motion,destroy(){motion?.destroy();observer.disconnect();io?.disconnect();cancelAnimationFrame(rebuildFrame);hideHover();hover.remove();}};
  }
  window.LFMGraphStudio={mount,ordered};
})();
