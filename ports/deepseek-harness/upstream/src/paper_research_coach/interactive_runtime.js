/* Trusted renderer. All model text enters textContent; no eval or dynamic code. */
(()=>{
 const {page:p,version}=JSON.parse(document.getElementById('page-data').textContent),module=document.getElementById('module'),key='prc-interactive:'+version;
 let saved={};try{saved=JSON.parse(localStorage.getItem(key)||'{}')}catch{}
 const state={index:0,row:-1,choice:null,revealed:false,differences:false,params:Object.fromEntries(p.parameters.map(v=>[v.name,v.value]))};
 if(Number.isInteger(saved.index))state.index=Math.max(0,Math.min(p.items.length-1,saved.index));
 if(Number.isInteger(saved.row))state.row=Math.max(-1,Math.min(p.rows.length-1,saved.row));
 if(Number.isInteger(saved.choice)&&saved.choice>=0&&saved.choice<p.options.length)state.choice=saved.choice;
 state.revealed=saved.revealed===true;state.differences=saved.differences===true;
 for(const param of p.parameters){const value=saved.params?.[param.name];if(Number.isFinite(value)&&value>=param.minimum&&value<=param.maximum)state.params[param.name]=value;}
 const store=()=>{try{localStorage.setItem(key,JSON.stringify(state))}catch{}};
 function el(tag,text,cls){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;}
 function button(text,action){const node=el('button',text);node.type='button';node.addEventListener('click',action);return node;}
 const notice=text=>document.getElementById('notice').textContent=text;
 function items(){
   const nav=el('div',undefined,'nodes'),detail=el('div',undefined,'detail');
   const show=i=>{state.index=i;Array.from(nav.children).forEach((node,j)=>node.setAttribute('aria-pressed',String(i===j)));detail.replaceChildren(el('h2',p.items[i].title),el('p',p.items[i].detail));store();};
   p.items.forEach((item,i)=>nav.append(button((p.kind==='steps'?`${i+1}. `:'')+item.title,()=>show(i))));
   module.append(nav,detail);show(state.index);
   if(p.kind==='steps'){
     const controls=el('div',undefined,'steps-nav'),back=button('上一步',()=>{show(Math.max(0,state.index-1));update();}),next=button('下一步',()=>{show(Math.min(p.items.length-1,state.index+1));update();});
     const update=()=>{back.disabled=state.index===0;next.disabled=state.index===p.items.length-1;};
     controls.append(back,next);module.append(controls);nav.addEventListener('click',update);update();
   }
 }
 function comparison(){
   const label=el('label',undefined,'choice'),toggle=el('input');toggle.type='checkbox';toggle.checked=state.differences;label.append(toggle,el('span','只看存在差异的行'));
   const wrap=el('div',undefined,'table-wrap'),table=el('table'),head=el('thead'),header=el('tr'),body=el('tbody'),detail=el('p',undefined,'detail');
   ['比较项目',...p.columns].forEach(t=>header.append(el('th',t)));head.append(header);table.append(head,body);wrap.append(table);module.append(label,wrap,detail);
   const show=()=>{body.replaceChildren();p.rows.forEach((row,i)=>{
     if(state.differences&&row.values.every(v=>v===row.values[0]))return;
     const tr=el('tr');tr.dataset.selected=String(state.row===i);tr.append(el('th'));
     const choose=()=>{state.row=i;detail.textContent=row.explanation;show();store();};
     tr.firstChild.append(button(row.label,choose));row.values.forEach(t=>tr.append(el('td',t)));body.append(tr);
   });if(!body.children.length){const tr=el('tr'),td=el('td','没有符合筛选条件的差异行。');td.colSpan=p.columns.length+1;tr.append(td);body.append(tr);}};
   if(state.row>=0)detail.textContent=p.rows[state.row].explanation;
   toggle.addEventListener('change',()=>{state.differences=toggle.checked;show();store();});show();
 }
 function evidence(){
   module.append(el('h2',p.question));const choices=el('fieldset');const legend=el('legend','先记录判断，再查看参考解释');choices.append(legend);
   p.options.forEach((option,i)=>{const label=el('label',undefined,'choice'),input=el('input');input.type='radio';input.name='evidence';input.checked=state.choice===i;input.addEventListener('change',()=>{state.choice=i;store();});label.append(input,el('span',option));choices.append(label);});
   const answer=el('div',undefined,'answer');answer.append(el('small','模型参考解释 · 不是独立掌握度评定'),el('p',p.explanation),el('p','参考选项：'+p.options[p.answer]));
   answer.hidden=!state.revealed;const controls=el('div',undefined,'controls');
   controls.append(button('对照参考解释',()=>{if(state.choice===null){notice('请先选择一个判断，或使用“直接讲解”。');return;}state.revealed=true;answer.hidden=false;store();notice('已记录你的选择，参考解释已展开。');}),button('直接讲解',()=>{state.revealed=true;answer.hidden=false;store();notice('获得帮助后的回答不视为独立完成。');}));
   module.append(choices,controls,answer);
 }
 function parameters(){
   module.append(el('p','教学示意 · 不是作者实验曲线','illustrative'),el('p',p.assumptions));
   const formula={linear:'y = a·x + b',power:'y = a·xⁿ + b',exponential:'y = a·exp(k·x) + b'}[p.family];module.append(el('h2',formula));
   const controls=el('div',undefined,'controls'),outputs={};
   const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.classList.add('graph');svg.setAttribute('role','img');svg.setAttribute('aria-label',p.title+'：示意参数曲线');
   const status=el('p',undefined,'current');
   const value=(x,params)=>params.a*(p.family==='linear'?x:p.family==='power'?Math.pow(x,params.n):Math.exp(params.k*x))+params.b;
   const original=Object.fromEntries(p.parameters.map(v=>[v.name,v.value]));
   const points=()=>Array.from({length:65},(_,i)=>p.x_min+(p.x_max-p.x_min)*i/64);
   const corners=p.parameters.reduce((values,param)=>values.flatMap(v=>[param.minimum,param.maximum].map(x=>({...v,[param.name]:x}))),[{}]);
   const envelope=corners.flatMap(params=>points().map(x=>value(x,params)));
   const draw=()=>{
     const xs=points(),ys=xs.map(x=>value(x,state.params)),reference=xs.map(x=>value(x,original));
     if([...ys,...reference].some(v=>!Number.isFinite(v))){status.textContent='当前范围无法计算，请调整参数。';svg.replaceChildren();return;}
     const width=Math.max(230,Math.round(svg.getBoundingClientRect().width||560)),height=300,left=70,right=width-18,top=20,bottom=246;
     let low=Math.min(...envelope,...reference),high=Math.max(...envelope,...reference);const pad=(high-low||Math.abs(high)||1)*.1;low-=pad;high+=pad;
     const sx=x=>left+(right-left)*(x-p.x_min)/(p.x_max-p.x_min),sy=y=>bottom-(bottom-top)*(y-low)/(high-low);
     const node=(tag,attrs,text)=>{const n=document.createElementNS(ns,tag);Object.entries(attrs).forEach(([k,v])=>n.setAttribute(k,String(v)));if(text!==undefined)n.textContent=text;svg.append(n);return n;};
     const format=v=>Math.abs(v)>=1e5||(Math.abs(v)>0&&Math.abs(v)<.001)?v.toExponential(1):Number(v.toPrecision(3)).toString();
     svg.setAttribute('viewBox',`0 0 ${width} ${height}`);svg.replaceChildren();node('title',{},'实线是当前参数，虚线是初始参数；数据仅供教学探索。');
     node('rect',{x:left,y:top,width:right-left,height:bottom-top,fill:'none',stroke:'var(--line)'});
     const count=width<400?3:5;
     for(let i=0;i<count;i++){
       const x=p.x_min+(p.x_max-p.x_min)*i/(count-1),y=low+(high-low)*i/(count-1);
       node('text',{x:sx(x),y:bottom+19,'text-anchor':'middle'},format(x));node('text',{x:left-9,y:sy(y)+4,'text-anchor':'end'},format(y));
     }
     node('text',{x:(left+right)/2,y:293,'text-anchor':'middle'},p.x_label);
     node('text',{x:15,y:(top+bottom)/2,transform:`rotate(-90 15 ${(top+bottom)/2})`,'text-anchor':'middle'},p.y_label);
     const path=values=>values.map((y,i)=>`${i?'L':'M'}${sx(xs[i]).toFixed(2)},${sy(y).toFixed(2)}`).join(' ');
     node('path',{d:path(reference),fill:'none',stroke:'var(--muted)','stroke-width':1.2,'stroke-dasharray':'4 4'});
     node('path',{d:path(ys),fill:'none',stroke:'var(--accent)','stroke-width':2,'data-current-curve':''});
     status.textContent='当前参数：'+p.parameters.map(v=>v.label+' = '+format(state.params[v.name])+' '+v.unit).join('；')+'。虚线为初始参数，坐标范围覆盖所设参数空间并保持固定。';
   };
   p.parameters.forEach(param=>{const label=el('label',undefined,'parameter'),line=el('span'),output=el('output',String(state.params[param.name])),input=el('input');line.append(el('span',param.label+'（'+param.unit+'）'),output);input.type='range';input.min=param.minimum;input.max=param.maximum;input.step=(param.maximum-param.minimum)/100;input.value=state.params[param.name];input.setAttribute('aria-label',param.label);outputs[param.name]=output;input.addEventListener('input',()=>{state.params[param.name]=Number(input.value);output.textContent=Number(input.value).toPrecision(4);draw();});input.addEventListener('change',store);label.append(line,input);controls.append(label);});
   module.append(controls,svg,status);draw();if(typeof ResizeObserver==='function')new ResizeObserver(draw).observe(svg);
 }
 if(p.kind==='concepts'||p.kind==='steps')items();else if(p.kind==='comparison')comparison();else if(p.kind==='evidence')evidence();else parameters();
 const source=document.getElementById('source');source.append(el('small',p.source_label));
 if(p.source_quote)source.append(el('blockquote',p.source_quote));else source.append(el('p','此页未绑定原文，内容为模型解释。'));
 if(p.source_anchor)source.append(button('定位原文',()=>{document.dispatchEvent(new CustomEvent('prc-locate'));notice(window.parent===window?'离线页面保留来源页码；请在插件中打开对应论文。':'已请求教练定位原文。');}));
 document.getElementById('ask').addEventListener('click',()=>{
   const context=p.kind==='parameters'?JSON.stringify(state.params):p.kind==='evidence'?JSON.stringify({choice:state.choice===null?null:p.options[state.choice],reference_revealed:state.revealed}):p.kind==='comparison'?JSON.stringify({row:state.row,differences_only:state.differences}):p.items[state.index]?.title||'';
   const text=('请继续解释：'+p.title+'\n当前交互状态：'+context+'\n来源：'+p.source_label+'\n请区分原文、推断与教学假设。').slice(0,16000);
   let reply=document.getElementById('prepared-question');if(!reply){const label=el('label','可复制或带回教练的问题'),textarea=el('textarea');textarea.id='prepared-question';label.append(textarea);document.querySelector('.page-actions').after(label);reply=textarea;}reply.value=text;
   document.dispatchEvent(new CustomEvent('prc-question',{detail:{text}}));notice(window.parent===window?'已整理当前状态，请复制问题继续追问。':'已整理当前状态；请在教练输入框中确认发送。');
 });
})();
