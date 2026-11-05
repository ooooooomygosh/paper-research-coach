/* Citation labels are presentation only. Raw locators and evidence are retained. */
(function(root){
  'use strict';
  function forPage(data){
    const en=data?.meta?.language==='en',labels=data?.sourceLabels||{};
    const keys=Object.keys(labels).sort((a,b)=>b.length-a.length);
    function display(raw){
      raw=String(raw||'');if(!en)return raw;
      if(Object.prototype.hasOwnProperty.call(labels,raw))return labels[raw];
      return raw.replace(/原书\s*第\s*([\d–—\-\s]+)页/g,'Printed pp. $1')
        .replace(/PDF\s*第\s*([\d–—\-\s]+)页/g,'PDF pp. $1')
        .replace(/第\s*(\d+)\s*章/g,'Chapter $1');
    }
    function text(value){
      value=String(value||'');if(!en)return value;
      if(Object.prototype.hasOwnProperty.call(labels,value))return labels[value];
      // Only call on citation containers, never on quotations or prose.
      for(const key of keys)if(value.endsWith(key))return value.slice(0,-key.length)+labels[key];
      return display(value);
    }
    function original(parent,raw){
      if(!en||display(raw)===raw)return;
      const detail=document.createElement('details');detail.className='source-original';
      const heading=document.createElement('summary');heading.textContent='Original source label';
      const body=document.createElement('p');body.textContent=raw;detail.append(heading,body);parent.append(detail);
    }
    function frameworkCondition(value){
      value=String(value||'').trim();
      return en?'Applies when: '+value.replace(/^(?:(?:applies\s+when\b|when\b)\s*[:：]?\s*)+/i,''):'适用：'+value.replace(/^(?:适用\s*[:：]\s*)+/,'');
    }
    function ruleCondition(value){
      value=String(value||'').trim();
      if(!en){
        if(/^(?:在|如果|若|一旦|每当|只要|除非|等到|当[前地日年月时场事期下])/.test(value))return value;
        const prefix=value.match(/^(当\s*)/);
        return prefix?prefix[1]+value.slice(prefix[0].length).replace(/^(?:当(?![前地日年月时场事期下])\s*)+/,''):'当 '+value;
      }
      const prefix=value.match(/^(when\b\s*[:：]?\s*)/i);
      if(prefix)return prefix[1]+value.slice(prefix[0].length).replace(/^(?:when\b\s*[:：]?\s*)+/i,'');
      return /^(?:if|before|after|during|in|on|once|unless|while|whenever)\b/i.test(value)?value:'When '+value;
    }
    return {display,text,original,frameworkCondition,ruleCondition};
  }
  root.LFMSourcePresentation={forPage};
  if(typeof module!=='undefined'&&module.exports)module.exports={forPage};
})(typeof globalThis!=='undefined'?globalThis:window);
