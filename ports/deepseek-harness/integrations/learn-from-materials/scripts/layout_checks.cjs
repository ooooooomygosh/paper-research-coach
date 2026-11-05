// Pure geometry assertions shared by the browser runner and adversarial fixtures.
function checkLayout(s) {
  const errors=[];
  const finite=r=>r && ['x','y','width','height'].every(k=>Number.isFinite(r[k]));
  if(![s.viewportWidth,s.viewportHeight,s.scrollWidth].every(Number.isFinite) ||
      !finite(s.page)||!finite(s.panel)||!finite(s.nav)) return ['missing layout measurements'];
  if(s.scrollWidth>s.viewportWidth+2)errors.push('document overflows horizontally');
  if(s.page.width<Math.min(1200,s.viewportWidth-60))errors.push('page unexpectedly narrow');
  if(s.panel.width<s.page.width*.88)errors.push('active panel does not span the page');
  if(s.panel.x<s.page.x-2 || s.panel.x+s.panel.width>s.page.x+s.page.width+2)errors.push('panel outside page');
  if(Math.abs((s.page.x+s.page.width/2)-s.viewportWidth/2)>24)errors.push('page is not centered');
  if(s.navDirection!=='row')errors.push('navigation remains a vertical sidebar');
  if(s.nav.height>100)errors.push('navigation is unexpectedly tall');
  if(s.panel.y-s.nav.y-s.nav.height>80)errors.push('unexpected empty gap before active panel');
  if(s.gridColumns!==1)errors.push('unexpected implicit/explicit page column');
  return errors;
}
function checkFullscreen(s) {
  const r=s.rect;
  if(!r || ![r.x,r.y,r.width,r.height,s.viewportWidth,s.viewportHeight].every(Number.isFinite))return ['missing fullscreen measurements'];
  const errors=[];
  if(!(Math.abs(r.x)<=3 && Math.abs(r.y)<=3 && Math.abs(r.width-s.viewportWidth)<=3 && Math.abs(r.height-s.viewportHeight)<=3))errors.push('fullscreen does not fill viewport in both dimensions');
  if(Array.isArray(s.toolbarButtons)&&s.toolbarButtons.some(b=>b.x < -2||b.y < -2||b.x+b.width>s.viewportWidth+2||b.y+b.height>s.viewportHeight+2))errors.push('fullscreen toolbar control is clipped');
  if(s.graphKind==='methodology'&&s.viewportWidth<820&&(!Number.isFinite(s.renderedTitleSize)||s.renderedTitleSize<12))errors.push('narrow methodology default title is too small');
  return errors;
}
module.exports={checkLayout,checkFullscreen};
