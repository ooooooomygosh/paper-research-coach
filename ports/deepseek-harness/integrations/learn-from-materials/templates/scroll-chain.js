/* Keep wheel input inside the floating explanation. Boundary wheel is consumed. */
(function(){
  'use strict';
  function consume(element,axis,delta){
    if(!element||!delta)return 0;
    const vertical=axis==='y',prop=vertical?'scrollTop':'scrollLeft';
    const maximum=Math.max(0,vertical?element.scrollHeight-element.clientHeight:element.scrollWidth-element.clientWidth);
    const before=element[prop],next=Math.max(0,Math.min(maximum,before+delta));
    if(next===before)return 0;
    element[prop]=next;
    return element[prop]-before;
  }
  function transfer(targets,dx,dy){
    let x=dx,y=dy;
    for(const target of new Set(targets.filter(Boolean))){
      x-=consume(target,'x',x);y-=consume(target,'y',y);
      if(!x&&!y)break;
    }
    return {x,y,moved:x!==dx||y!==dy};
  }
  function forward(event,targets,pageHeight=800,pageWidth=1000){
    if(event.ctrlKey||event.metaKey||!event.cancelable)return false;
    const unitY=event.deltaMode===1?40:event.deltaMode===2?pageHeight:1;
    const unitX=event.deltaMode===1?40:event.deltaMode===2?pageWidth:1;
    let dx=event.deltaX*unitX,dy=event.deltaY*unitY;
    if(event.shiftKey&&!dx){dx=dy;dy=0;}
    const result=transfer(targets,dx,dy);
    if(result.moved){event.preventDefault();event.stopPropagation();}
    return result.moved;
  }
  function route(event,hover,viewport){
    if(event.ctrlKey||event.metaKey||!event.cancelable)return false;
    const targets=[];
    const scrollable=element=>/auto|scroll/.test(getComputedStyle(element).overflowY+' '+getComputedStyle(element).overflowX);
    let inner=event.target instanceof Element?event.target:null;
    if(inner&&hover.contains(inner)){
      for(;inner&&inner!==hover;inner=inner.parentElement)if(scrollable(inner))targets.push(inner);
    }
    targets.push(hover);
    const unitY=event.deltaMode===1?40:event.deltaMode===2?(hover.clientHeight||viewport.clientHeight):1;
    const unitX=event.deltaMode===1?40:event.deltaMode===2?(hover.clientWidth||viewport.clientWidth):1;
    let dx=event.deltaX*unitX,dy=event.deltaY*unitY;
    if(event.shiftKey&&!dx){dx=dy;dy=0;}
    if(!dx&&!dy)return false;
    // Never chain to the viewport, parent containers, or document. Once the
    // floating card reaches an edge, the remaining wheel delta is discarded.
    const result=transfer(targets,dx,dy);
    event.preventDefault();
    event.stopPropagation();
    return result.moved||!!(dx||dy);
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={consume,transfer,forward,route};
  if(typeof window!=='undefined')window.LFMScrollChain={route};
})();
