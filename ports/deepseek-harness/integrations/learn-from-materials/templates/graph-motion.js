/* Shared, bounded direction cues. Geometry and semantic direction belong to renderers. */
(function(){
  'use strict';
  const symmetric=edge=>edge.directed===false||['contrasts','contrast','comparison','parallel','compares'].includes(edge.type||edge.kind);
  function mount({root,viewport,button,language}){
    const reduced=matchMedia('(prefers-reduced-motion: reduce)');
    const listeners=[],animations=new Set();let entries=[],selected=new Set(),timer=null,previewTimer=null,demo=false,cursor=0,destroyed=false;
    const listen=(target,name,fn,opts)=>{target.addEventListener(name,fn,opts);listeners.push(()=>target.removeEventListener?.(name,fn,opts));};
    const off=()=>destroyed||reduced.matches||document.body.dataset.motion==='off'||document.hidden;
    function inView(element){
      if(!element?.getClientRects().length)return false;
      const r=element.getBoundingClientRect(),v=viewport.getBoundingClientRect();
      return r.width+r.height>0&&r.bottom>=Math.max(0,v.top)&&r.top<=Math.min(innerHeight,v.bottom)&&r.right>=Math.max(0,v.left)&&r.left<=Math.min(innerWidth,v.right);
    }
    const visible=()=>!off()&&inView(root)&&inView(viewport);
    function clear(){
      clearTimeout(timer);clearTimeout(previewTimer);timer=previewTimer=null;
      animations.forEach(animation=>animation.cancel());animations.clear();
      entries.forEach(entry=>{entry.overlays.forEach(path=>path.classList.remove('is-direction-cue'));entry.paths.forEach(path=>path.classList.remove('is-symmetric-preview'));});
      root.classList.remove('is-direction-playing');
    }
    function paintSymmetric(){entries.forEach(entry=>entry.paths.forEach(path=>path.classList.toggle('is-symmetric-highlight',symmetric(entry.edge)&&selected.has(entry.edge.id))));}
    function play(batch){
      if(!visible())return;
      root.classList.add('is-direction-playing');
      batch.forEach(entry=>{
        if(symmetric(entry.edge))return;
        const lengths=entry.paths.map(path=>{try{return path.getTotalLength();}catch(_){return 0;}}),total=lengths.reduce((a,b)=>a+b,0);
        if(!total)return;
        let elapsed=0;const duration=entry.edge.kind==='feedback'||entry.edge.type==='feedback'?2100:1700;
        entry.overlays.forEach((path,index)=>{
          const length=lengths[index],head=Math.min(32,Math.max(12,length*.12));
          path.classList.add('is-direction-cue');path.style.strokeDasharray=`${head} ${length+head*2}`;
          if(path.animate){
            const animation=path.animate([
              {strokeDashoffset:head,opacity:0},{strokeDashoffset:head-(length+head)*.08,opacity:.9,offset:.08},
              {strokeDashoffset:head-(length+head)*.92,opacity:.9,offset:.92},{strokeDashoffset:-length,opacity:0}
            ],{duration:duration*length/total,delay:duration*elapsed/total,easing:'linear',iterations:1,fill:'none'});
            animations.add(animation);animation.onfinish=()=>{animations.delete(animation);path.classList.remove('is-direction-cue');};
          }
          elapsed+=length;
        });
      });
    }
    function candidates(ids){return entries.filter(entry=>!symmetric(entry.edge)&&(!ids||ids.has(entry.edge.id))&&entry.paths.some(inView));}
    function tick(){
      clear();if(!visible())return;
      const eligible=candidates(demo?null:selected);
      if(eligible.length){const batch=Array.from({length:Math.min(3,eligible.length)},(_,i)=>eligible[(cursor+i)%eligible.length]);cursor=(cursor+batch.length)%eligible.length;play(batch);}
      if(demo||selected.size)timer=setTimeout(tick,2800);
    }
    function refresh(){clear();paintSymmetric();if(visible()&&(demo||selected.size))tick();}
    function updateButton(){if(button){button.setAttribute('aria-pressed',String(demo));button.disabled=off();button.textContent=demo?(language==='en'?'Stop directions':'停止方向演示'):(language==='en'?'Show directions':'方向演示');}}
    if(button)listen(button,'click',()=>{demo=!demo;cursor=0;updateButton();refresh();});
    listen(document,'lfm-motion-change',()=>{updateButton();refresh();});
    listen(document,'visibilitychange',()=>{updateButton();refresh();});
    listen(reduced,'change',()=>{updateButton();refresh();});
    listen(document,'lfm-panel-change',()=>{clear();requestAnimationFrame(()=>requestAnimationFrame(refresh));});
    listen(viewport,'scroll',refresh,{passive:true});listen(window,'scroll',refresh,{passive:true});
    let observer=null,detachObserver=null;
    if(typeof IntersectionObserver!=='undefined'){observer=new IntersectionObserver(refresh,{threshold:0});observer.observe(root);}
    if(typeof MutationObserver!=='undefined'){detachObserver=new MutationObserver(()=>{if('isConnected' in root&&!root.isConnected)destroy();});detachObserver.observe(document.body,{childList:true,subtree:true});}
    function destroy(){if(destroyed)return;clear();destroyed=true;observer?.disconnect();detachObserver?.disconnect();listeners.splice(0).forEach(remove=>remove());}
    updateButton();
    return {
      replace(next){clear();entries=next;refresh();},
      select(ids){selected=new Set(ids);cursor=0;refresh();},
      preview(ids){if(!visible())return;clear();const wanted=new Set(ids);entries.filter(entry=>wanted.has(entry.edge.id)&&symmetric(entry.edge)).forEach(entry=>entry.paths.forEach(path=>path.classList.add('is-symmetric-preview')));play(candidates(wanted).slice(0,3));previewTimer=setTimeout(refresh,2300);},
      refresh,destroy,
      state(){return{demo,selected:[...selected],running:animations.size,maxBatch:3};}
    };
  }
  window.LFMGraphMotion={mount,symmetric};
})();
