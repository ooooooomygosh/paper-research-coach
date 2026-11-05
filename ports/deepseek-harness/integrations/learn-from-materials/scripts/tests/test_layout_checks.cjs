const assert=require('node:assert/strict');
const {checkLayout,checkFullscreen}=require('../layout_checks.cjs');
const normal={viewportWidth:2105,viewportHeight:1100,scrollWidth:2105,page:{x:172.5,y:0,width:1760,height:1700},panel:{x:172.5,y:360,width:1760,height:800},nav:{x:172.5,y:280,width:1760,height:60},navDirection:'row',gridColumns:1};
assert.deepEqual(checkLayout(normal),[]);
// Screenshot-like left-column layout can have NO horizontal overflow.
const narrow=structuredClone(normal);narrow.page.width=840;narrow.page.x=20;narrow.panel.width=840;narrow.panel.x=20;narrow.nav.height=960;narrow.navDirection='column';narrow.gridColumns=2;
assert(checkLayout(narrow).includes('page unexpectedly narrow'));
assert(checkLayout(narrow).includes('navigation remains a vertical sidebar'));
assert(checkLayout(narrow).includes('unexpected implicit/explicit page column'));
const panel=structuredClone(normal);panel.panel.width=820;assert(checkLayout(panel).includes('active panel does not span the page'));
const gap=structuredClone(normal);gap.panel.y=1200;assert(checkLayout(gap).includes('unexpected empty gap before active panel'));
assert.deepEqual(checkFullscreen({viewportWidth:1440,viewportHeight:900,rect:{x:0,y:0,width:1440,height:900}}),[]);
assert(checkFullscreen({viewportWidth:1440,viewportHeight:900,rect:{x:0,y:0,width:800,height:900}}).length);
const mobile={viewportWidth:390,viewportHeight:1000,rect:{x:0,y:0,width:390,height:1000},graphKind:'methodology',renderedTitleSize:13.6,toolbarButtons:[{x:10,y:100,width:90,height:34}]};
assert.deepEqual(checkFullscreen(mobile),[]);
assert(checkFullscreen({...mobile,renderedTitleSize:3.4}).includes('narrow methodology default title is too small'));
assert(checkFullscreen({...mobile,toolbarButtons:[{x:370,y:100,width:100,height:34}]}).includes('fullscreen toolbar control is clipped'));
assert(checkLayout({}).length);
console.log('PASS: normal layout, left blank space without overflow, narrow panel, vertical navigation, implicit grid, gap and fullscreen width');
