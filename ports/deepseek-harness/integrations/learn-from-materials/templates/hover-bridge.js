/* Pointer corridor shared by both explanation popovers. */
(function(root){
  function contains(a,b,x,y,pad=8){
    const inside=r=>x>=r.left-pad&&x<=r.right+pad&&y>=r.top-pad&&y<=r.bottom+pad;
    if(inside(a)||inside(b))return true;
    if(b.left>=a.right)return x>=a.right-pad&&x<=b.left+pad&&y>=Math.min(a.top,b.top)-pad&&y<=Math.max(a.bottom,b.bottom)+pad;
    if(a.left>=b.right)return x>=b.right-pad&&x<=a.left+pad&&y>=Math.min(a.top,b.top)-pad&&y<=Math.max(a.bottom,b.bottom)+pad;
    return x>=Math.min(a.left,b.left)-pad&&x<=Math.max(a.right,b.right)+pad&&y>=Math.min(a.bottom,b.bottom)-pad&&y<=Math.max(a.top,b.top)+pad;
  }
  root.LFMHoverBridge={contains};
  if(typeof module!=='undefined')module.exports={contains};
})(typeof window!=='undefined'?window:globalThis);
