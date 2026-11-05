/* Orthogonal routing for cross-links; coordinates never become canonical content. */
(function(){
  'use strict';
  function segmentClear(a,b,rects){
    return !rects.some(r=>a.x===b.x
      ? a.x>r.left&&a.x<r.right&&Math.max(a.y,b.y)>r.top&&Math.min(a.y,b.y)<r.bottom
      : a.y>r.top&&a.y<r.bottom&&Math.max(a.x,b.x)>r.left&&Math.min(a.x,b.x)<r.right);
  }
  function simplify(points){
    const out=[];
    for(const point of points){
      const last=out.at(-1),prev=out.at(-2);
      if(last&&last.x===point.x&&last.y===point.y)continue;
      if(prev&&((prev.x===last.x&&last.x===point.x&&(last.y-prev.y)*(point.y-last.y)>=0)
        ||(prev.y===last.y&&last.y===point.y&&(last.x-prev.x)*(point.x-last.x)>=0)))out.pop();
      out.push(point);
    }
    return out;
  }
  function path(points){return points.map((p,i)=>`${i?'L':'M'} ${p.x} ${p.y}`).join(' ');}
  function route(start,end,rects,bounds){
    const xs=new Set([start.x,end.x,bounds.left,bounds.right]),ys=new Set([start.y,end.y,bounds.top,bounds.bottom]);
    rects.forEach(r=>{xs.add(r.left);xs.add(r.right);ys.add(r.top);ys.add(r.bottom);});
    const x=[...xs].filter(v=>v>=bounds.left&&v<=bounds.right).sort((a,b)=>a-b);
    const y=[...ys].filter(v=>v>=bounds.top&&v<=bounds.bottom).sort((a,b)=>a-b);
    const sx=x.indexOf(start.x),sy=y.indexOf(start.y),ex=x.indexOf(end.x),ey=y.indexOf(end.y);
    if([sx,sy,ex,ey].some(v=>v<0))throw Error('Framework route endpoint outside its canvas');
    const heap=[],cost=new Map(),previous=new Map();let sequence=0;
    const key=(i,j,axis)=>`${i}:${j}:${axis}`;
    const point=(i,j)=>({x:x[i],y:y[j]});
    function push(item){let i=heap.length;heap.push(item);while(i){const p=(i-1)>>1;if(heap[p].score<=item.score)break;heap[i]=heap[p];i=p;}heap[i]=item;}
    function pop(){const first=heap[0],last=heap.pop();if(heap.length){let i=0;while(i*2+1<heap.length){let child=i*2+1;if(child+1<heap.length&&heap[child+1].score<heap[child].score)child++;if(heap[child].score>=last.score)break;heap[i]=heap[child];i=child;}heap[i]=last;}return first;}
    const first=key(sx,sy,0);cost.set(first,0);push({i:sx,j:sy,axis:0,key:first,g:0,score:0});
    let final=null;
    while(heap.length){
      const current=pop();if(cost.get(current.key)!==current.g)continue;
      if(current.i===ex&&current.j===ey){final=current.key;break;}
      for(const [di,dj,axis] of [[-1,0,1],[1,0,1],[0,-1,2],[0,1,2]]){
        const i=current.i+di,j=current.j+dj;if(i<0||j<0||i>=x.length||j>=y.length)continue;
        const a=point(current.i,current.j),b=point(i,j);if(!segmentClear(a,b,rects))continue;
        const g=current.g+Math.abs(a.x-b.x)+Math.abs(a.y-b.y)+(current.axis&&current.axis!==axis?18:0);
        const next=key(i,j,axis);if(g>=(cost.get(next)??Infinity))continue;
        cost.set(next,g);previous.set(next,current.key);
        push({i,j,axis,key:next,g,score:g+Math.abs(b.x-end.x)+Math.abs(b.y-end.y)+(sequence++)*1e-8});
      }
    }
    if(!final)throw Error('No clear framework cross-link corridor');
    const result=[];for(let id=final;id;id=previous.get(id)){const [i,j]=id.split(':').map(Number);result.push(point(i,j));}
    return simplify(result.reverse());
  }
  window.LFMFrameworkRouting={route,path,simplify,segmentClear};
})();
