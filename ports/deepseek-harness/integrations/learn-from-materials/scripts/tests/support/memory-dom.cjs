// Deterministic DOM double for renderer behavior. It is NOT browser visual QA.
'use strict';
const fs=require('node:fs');
const vm=require('node:vm');

function pathPoints(description){
  const tokens=String(description).match(/[MLHV]|-?\d+(?:\.\d+)?(?:e[-+]?\d+)?/gi)||[];
  const result=[];let i=0,x=0,y=0;
  while(i<tokens.length){
    const op=tokens[i++].toUpperCase();
    if(op==='M'||op==='L'){x=Number(tokens[i++]);y=Number(tokens[i++]);}
    else if(op==='H')x=Number(tokens[i++]);
    else if(op==='V')y=Number(tokens[i++]);
    else throw Error('Unsupported path command '+op);
    result.push({x,y});
  }
  return result;
}

function createDOM(options={}){
  const frames=[],timers=new Map(),observers=[];let timerId=0;
  const measure=text=>Array.from(String(text)).reduce((sum,c)=>sum+(/[\u2e80-\uffff]/u.test(c)?11:/[MW@]/.test(c)?8.5:c===' '?3.5:6),0)*(options.metricScale||1);
  let document;
  class Element{
    constructor(tag){
      this.tagName=tag;this.children=[];this.attributes={};this.dataset={};this.events={};this.hidden=false;this.parentNode=null;this._text='';this.className='';
      this.scrollLeft=0;this.scrollTop=0;this.scrollHeight=1200;this.scrollWidth=1200;
      this.style={setProperty(k,v){this[k]=String(v);},getPropertyValue(k){return this[k]||'';}};
      this.classList={contains:c=>this.className.split(/\s+/).includes(c),add:(...cs)=>{cs.forEach(c=>{if(!this.classList.contains(c))this.className=(this.className+' '+c).trim();});},remove:(...cs)=>{this.className=this.className.split(/\s+/).filter(c=>!cs.includes(c)).join(' ');},toggle:(c,force)=>{const on=force===undefined?!this.classList.contains(c):!!force;this.classList[on?'add':'remove'](c);return on;}};
    }
    set textContent(value){this._text=String(value);this.replaceChildren();}
    get textContent(){return this._text+this.children.map(n=>n.textContent).join('');}
    get parentElement(){return this.parentNode;}
    get firstElementChild(){return this.children[0]||null;}
    get childElementCount(){return this.children.length;}
    setAttribute(k,v){this.attributes[k]=String(v);if(k==='class')this.className=String(v);if(k==='id')this.id=String(v);if(k.startsWith('data-'))this.dataset[k.slice(5).replace(/-([a-z])/g,(_,c)=>c.toUpperCase())]=String(v);}
    getAttribute(k){return k==='class'?this.className:this.attributes[k]??null;}
    removeAttribute(k){delete this.attributes[k];}
    append(...nodes){nodes.forEach(n=>{if(typeof n==='string'){const text=new Element('#text');text.textContent=n;n=text;}if(n.tagName==='#fragment'){this.append(...n.children.slice());return;}n.remove();n.parentNode=this;this.children.push(n);});}
    prepend(...nodes){nodes.reverse().forEach(n=>{n.remove();n.parentNode=this;this.children.unshift(n);});}
    replaceChildren(...nodes){this.children.forEach(n=>n.parentNode=null);this.children=[];this.append(...nodes);}
    insertBefore(n,reference){if(!reference){this.append(n);return;}const i=this.children.indexOf(reference);if(i<0)throw Error('Reference is not a child');n.remove();n.parentNode=this;this.children.splice(i,0,n);}
    before(n){this.parentNode.insertBefore(n,this);}
    replaceWith(n){const parent=this.parentNode;parent.insertBefore(n,this);this.remove();}
    remove(){if(this.parentNode){const list=this.parentNode.children;list.splice(list.indexOf(this),1);this.parentNode=null;}}
    cloneNode(deep){const n=new Element(this.tagName);n.className=this.className;n._text=this._text;n.id=this.id;n.attributes={...this.attributes};n.dataset={...this.dataset};if(deep)n.append(...this.children.map(c=>c.cloneNode(true)));return n;}
    all(){return this.children.flatMap(n=>[n,...n.all()]);}
    matches(selector){return selector.split(',').some(part=>{
      part=part.trim();const attr=part.match(/\[([^=\]]+)(?:=["']?([^"'\]]*)["']?)?\]/);
      if(attr&&(this.getAttribute(attr[1])===null||(attr[2]!==undefined&&this.getAttribute(attr[1])!==attr[2])))return false;
      part=part.replace(/\[[^\]]*\]/g,'');const id=part.match(/#([\w-]+)/);if(id&&this.id!==id[1])return false;
      const classes=[...part.matchAll(/\.([\w-]+)/g)];if(classes.some(m=>!this.classList.contains(m[1])))return false;
      const tag=part.match(/^[\w-]+/);return !tag||this.tagName.toLowerCase()===tag[0].toLowerCase();
    });}
    querySelectorAll(selector){return this.all().filter(n=>n.matches(selector));}
    querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
    closest(selector){let n=this;while(n){if(n.matches(selector))return n;n=n.parentNode;}return null;}
    contains(n){while(n){if(n===this)return true;n=n.parentNode;}return false;}
    addEventListener(name,fn){(this.events[name]||=[]).push(fn);}
    removeEventListener(name,fn){this.events[name]=(this.events[name]||[]).filter(f=>f!==fn);}
    dispatch(name,extra={}){const event={target:this,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.stopped=true;},stopImmediatePropagation(){this.immediate=true;},...extra};for(const fn of this.events[name]||[]){fn(event);if(event.immediate)break;}return event;}
    click(){return this.onclick?.({target:this,stopPropagation(){},preventDefault(){}})??this.dispatch('click');}
    focus(){document.activeElement=this;}
    get invisible(){let n=this;while(n){if(n.hidden)return true;n=n.parentNode;}return false;}
    get clientWidth(){return this.invisible?0:this._clientWidth??(this.classList.contains('diagram-viewport')||this.classList.contains('lfm-mm-viewport')?options.width||1200:Number.parseFloat(this.style.width)||640);}
    get clientHeight(){return this.invisible?0:this._clientHeight??(this.classList.contains('diagram-viewport')||this.classList.contains('lfm-mm-viewport')?options.height||700:500);}
    get offsetWidth(){return this.clientWidth;}
    get offsetHeight(){
      if(this.invisible)return 0;
      if(this.classList.contains('diagram-card'))return options.cardHeight?.(this)||176;
      if(this.classList.contains('lfm-mm-node')){
        if(this.style.height)return Number.parseFloat(this.style.height);
        const title=this.querySelector('span')?.textContent||'';
        return Math.max(Number.parseFloat(this.style.minHeight)||72,options.frameworkHeight?.(this)||40+Math.ceil(measure(title)/(this.clientWidth-34))*23);
      }
      return this.clientHeight;
    }
    get offsetLeft(){return Number.parseFloat(this.style.left)||0;}
    get offsetTop(){return Number.parseFloat(this.style.top)||0;}
    getBoundingClientRect(){const width=this.clientWidth,height=this.offsetHeight,left=this.offsetLeft,top=this.offsetTop;return{left,top,right:left+width,bottom:top+height,width,height};}
    getClientRects(){return this.invisible?[]:[this.getBoundingClientRect()];}
    getTotalLength(){const points=pathPoints(this.getAttribute('d'));return points.slice(1).reduce((sum,p,i)=>sum+Math.hypot(p.x-points[i].x,p.y-points[i].y),0);}
    getContext(){return{font:'',measureText:text=>({width:measure(text)})};}
  }
  document=new Element('#document');document.documentElement=new Element('html');document.body=new Element('body');document.append(document.documentElement);document.documentElement.append(document.body);document.body.dataset.theme=options.theme||'warm-paper';document.body.style.overflow='auto';document.activeElement=document.body;
  document.createElement=tag=>new Element(tag);document.createElementNS=(_,tag)=>new Element(tag);document.createDocumentFragment=()=>new Element('#fragment');document.getElementById=id=>document.all().find(n=>n.id===id)||null;
  const sandbox={document,Element,HTMLElement:Element,console,innerWidth:options.width||1200,innerHeight:options.height||900,
    getComputedStyle:n=>({getPropertyValue:k=>k==='--font-display'?'system-ui':k==='--dg-card'?document.body.dataset.theme+'-card':k==='--dg-dim-card'?document.body.dataset.theme+'-dim':'',overflowY:n.style.overflowY||'auto',overflowX:n.style.overflowX||'auto',lineHeight:'20px'}),
    requestAnimationFrame:fn=>{frames.push(fn);return frames.length;},cancelAnimationFrame(){},setTimeout:fn=>{timers.set(++timerId,fn);return timerId;},clearTimeout:id=>timers.delete(id),
    MutationObserver:class{constructor(fn){this.fn=fn;observers.push(this);}observe(){}disconnect(){}},
    ResizeObserver:class{constructor(fn){this.fn=fn;observers.push(this);}observe(){}disconnect(){}},
    matchMedia:()=>({matches:options.reducedMotion??true,addEventListener(){}})
  };
  sandbox.window=sandbox;sandbox.scrollX=24;sandbox.scrollY=480;sandbox.scrollTo=position=>{sandbox.scrollX=position.left;sandbox.scrollY=position.top;};sandbox.addEventListener=(name,fn)=>document.addEventListener('window-'+name,fn);
  if(options.nativeFullscreen){Element.prototype.requestFullscreen=async function(){document.fullscreenElement=this;document.dispatch('fullscreenchange');};document.exitFullscreen=async()=>{document.fullscreenElement=null;document.dispatch('fullscreenchange');};}
  const context=vm.createContext(sandbox);
  return{document,context,Element,measure,observers,
    run:file=>vm.runInContext(fs.readFileSync(file,'utf8'),context,{filename:file}),
    flush(){let count=0;while(frames.length){if(++count>1000)throw Error('Animation frame loop');frames.shift()();}},
    make(tag,id,parent=document.body){const n=new Element(tag);if(id)n.setAttribute('id',id);parent.append(n);return n;}
  };
}
module.exports={createDOM,pathPoints};
