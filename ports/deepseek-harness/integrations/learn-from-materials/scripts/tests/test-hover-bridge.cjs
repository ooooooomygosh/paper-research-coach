const {test}=require('node:test');
const assert=require('node:assert/strict');
const {contains}=require('../../templates/hover-bridge.js');
const a={left:100,right:200,top:100,bottom:160};
test('slow and diagonal pointer transfer stays open in either horizontal direction',()=>{
  const right={left:230,right:450,top:120,bottom:480};
  for(const [x,y] of [[180,140],[204,162],[214,182],[225,208],[270,240]]){
    assert(contains(a,right,x,y));assert(contains(right,a,x,y));
  }
});
test('vertical corridor supports overlapping-width anchors and outside movement closes',()=>{
  const below={left:70,right:350,top:190,bottom:450};
  assert(contains(a,below,185,175));assert(contains(below,a,185,175));
  assert(!contains(a,below,600,175));assert(!contains(a,below,150,30));
});
