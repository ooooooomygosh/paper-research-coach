/* Reader controls and restrained page motion. Diagram motion remains in its renderer. */
(function(){
  'use strict';
  const dataNode=document.getElementById('pageData');
  let meta={};try{meta=JSON.parse(dataNode.textContent).meta||{};}catch(_){/* valid pages always have data */}
  const en=meta.language==='en',say=(zh,english)=>en?english:zh;
  const key='lfm-motion:'+(meta.pageId||meta.knowledgeBase||meta.title||'page');
  const media=matchMedia('(prefers-reduced-motion: reduce)');
  const button=document.getElementById('motionToggle');
  let enabled=true;try{enabled=localStorage.getItem(key)!=='off';}catch(_){}
  const off=()=>media.matches||!enabled;
  const entrances=new Set();
  function entrance(panel){
    if(off()||!panel?.animate)return;
    const animation=panel.animate([{opacity:.45,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}],{duration:260,easing:'ease-out'});
    entrances.add(animation);
    animation.onfinish=animation.oncancel=()=>entrances.delete(animation);
  }
  function sync(){
    if(off()){for(const animation of entrances)animation.cancel();entrances.clear();}
    document.body.dataset.motion=off()?'off':'on';
    if(button){
      button.textContent=media.matches?say('动效：跟随系统','Motion: system'):enabled?say('动效：开','Motion: on'):say('动效：关','Motion: off');
      button.setAttribute('aria-pressed',String(!off()));button.disabled=media.matches;
    }
    document.dispatchEvent(new Event('lfm-motion-change'));
  }
  button?.addEventListener('click',()=>{enabled=!enabled;try{localStorage.setItem(key,enabled?'on':'off');}catch(_){}sync();});
  media.addEventListener?.('change',sync);sync();
  const tabs=document.querySelector('.tabs');
  if(tabs){
    const plate=document.createElement('span');plate.className='nav-active-plate';plate.setAttribute('aria-hidden','true');tabs.append(plate);
    let last=tabs.querySelector('.tab[aria-selected="true"]')?.dataset.panel;
    function update(){
      const active=tabs.querySelector('.tab[aria-selected="true"]');if(!active)return;
      plate.style.width=active.offsetWidth+'px';plate.style.transform='translateX('+active.offsetLeft+'px)';
      const id=active.dataset.panel;
      if(id!==last){
        last=id;
        const panel=document.getElementById(id);
        entrance(panel);
        document.dispatchEvent(new Event('lfm-panel-change'));
        const left=active.offsetLeft,right=left+active.offsetWidth;
        if(left<tabs.scrollLeft||right>tabs.scrollLeft+tabs.clientWidth)tabs.scrollTo({left:Math.max(0,left-(tabs.clientWidth-active.offsetWidth)/2),behavior:off()?'instant':'smooth'});
      }
    }
    requestAnimationFrame(()=>{update();tabs.classList.add('has-moving-plate');});
    new MutationObserver(()=>requestAnimationFrame(update)).observe(tabs,{attributes:true,subtree:true,attributeFilter:['aria-selected']});
    if(typeof ResizeObserver!=='undefined')new ResizeObserver(update).observe(tabs);
    window.addEventListener('resize',update,{passive:true});document.fonts?.ready.then(update);
  }
  // Animate only the established disclosures, preserving native <details> semantics.
  const running=new Map();
  function finish(item,state){if(running.get(item)!==state)return;running.delete(item);state.animation.cancel();item.open=state.open;}
  document.addEventListener('click',event=>{
    const summary=event.target.closest?.('summary');if(!summary||event.defaultPrevented)return;
    if(event.target.closest('a,button,input,select,textarea'))return;
    const detail=summary.parentElement;
    if(!detail.matches('.term-item,.chapter-conclusion,.personal-note-card,.accordion details,.assessment-preview,.unit-source-disclosure'))return;
    if(off()||!detail.animate)return;
    event.preventDefault();
    const previous=running.get(detail),opening=previous?!previous.open:!detail.open;
    const start=detail.getBoundingClientRect().height;
    if(previous){previous.animation.cancel();running.delete(detail);}
    detail.open=opening;const end=detail.getBoundingClientRect().height;detail.open=true;
    const animation=detail.animate([{height:start+'px',overflow:'hidden'},{height:end+'px',overflow:'hidden'}],{duration:220,easing:'cubic-bezier(.2,.8,.2,1)'});
    const state={animation,open:opening};running.set(detail,state);
    animation.onfinish=()=>finish(detail,state);
  });
  document.addEventListener('lfm-motion-change',()=>{if(off())for(const [item,state] of running)finish(item,state);});
})();
