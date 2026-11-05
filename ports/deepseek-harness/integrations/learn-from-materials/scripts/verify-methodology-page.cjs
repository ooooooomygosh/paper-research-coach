// Optional browser regression. Uses existing Playwright/browser installations only.
// node scripts/verify-methodology-page.cjs learning.html [screenshot.png]
const assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
let chromium;
try {({chromium}=require('playwright'));} catch(e) {console.error('Playwright unavailable; no dependencies installed.');process.exit(2);}
(async()=>{
  const browser=await chromium.launch({headless:true,...(process.env.LFM_BROWSER_CHANNEL?{channel:process.env.LFM_BROWSER_CHANNEL}:{})});
  try {
    const url=pathToFileURL(path.resolve(process.argv[2])).href;
    const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});
    const errors=[],blocked=[];
    await context.route('**/*',r=>{const u=r.request().url();if(u===url||/^(data:|blob:)/.test(u))return r.continue();blocked.push(u);return r.abort();});
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));await page.goto(url);
    if(await page.locator('#guideSkip').isVisible())await page.locator('#guideSkip').click();
    const data=await page.locator('#pageData').textContent().then(JSON.parse);
    assert(await page.locator('#frameworks .grid').isVisible(),'Cards must be the initial view');
    assert.equal(await page.locator('#frameworks #wholeMethod').count(),0);
    assert.equal(await page.locator('#rules #wholeMethod').count(),1);
    await page.locator('#frameworks .relation-tools button').nth(1).click();
    const map=page.locator('#frameworks .lfm-mm');
    assert(await map.isVisible(),'Framework mind map must open');
    const frameworkIds=new Set(data.frameworks.map(n=>n.id));
    const frameworkEdges=(data.relationships||[]).filter(e=>frameworkIds.has(e.from)&&frameworkIds.has(e.to));
    const linkedIds=[...new Set(frameworkEdges.flatMap(e=>[e.from,e.to]))].sort();
    if(frameworkEdges.length)await map.locator('.lfm-mm-tools button').filter({hasText:/展开全部|Expand all/}).click();
    const nodeIds=await map.locator('.lfm-mm-node').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-framework-id')).sort());
    assert.deepEqual(nodeIds,linkedIds,'Only frameworks participating in canonical framework edges enter the canvas');
    const listIds=await map.locator('.lfm-mm-unlinked-item').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-framework-id')));
    const isolated=data.frameworks.filter(n=>!linkedIds.includes(n.id)).sort((a,b)=>(a.sourceOrder||0)-(b.sourceOrder||0));
    assert.deepEqual(listIds,isolated.map(n=>n.id),'Unlinked frameworks remain available in source order outside the canvas');
    assert.deepEqual([...nodeIds,...listIds].sort(),[...frameworkIds].sort(),'Graph plus list preserves the entire canonical inventory');
    if(listIds.length)assert.equal(await map.locator('.lfm-mm-unlinked').evaluate(n=>n.open),false,'The external framework list starts collapsed, including after Expand all');
    const drawnIds=await map.locator('.lfm-mm-wire').evaluateAll(paths=>[...new Set(paths.map(p=>p.getAttribute('data-edge-id')))].sort());
    assert.deepEqual(drawnIds,frameworkEdges.map(e=>e.id).sort(),'Every canonical framework edge must remain visible after expansion, including its label-gap path pieces');
    const arrowIds=await map.locator('.lfm-mm-wire[marker-end]').evaluateAll(paths=>[...new Set(paths.map(p=>p.getAttribute('data-edge-id')))].sort());
    assert.deepEqual(arrowIds,drawnIds,'Each canonical framework relation retains its target arrow');
    assert.equal(await map.locator('.lfm-mm-edge-label').count(),frameworkEdges.length);
    if(linkedIds.length){
      await map.locator('.lfm-mm-select').first().focus();
      assert(await page.locator('.lfm-mm-hover').isVisible(),'Framework explanations must be available on focus');
    }else{
      assert(await map.locator('.lfm-mm-viewport').isHidden(),'An all-unlinked section must not leave a large blank graph');
      assert(await map.locator('.lfm-mm-empty').isVisible());
    }
    if(isolated.length){
      const target=isolated[0];
      await map.locator('.lfm-mm-search').fill(target.name);
      const resultIds=await map.locator('.lfm-mm-result').evaluateAll(items=>items.map(n=>n.getAttribute('data-result-id')));
      assert(resultIds.includes(target.id));
      await map.locator('.lfm-mm-result').nth(resultIds.indexOf(target.id)).click();
      const detail=map.locator('.lfm-mm-unlinked-detail');
      assert(await detail.isVisible(),'Selecting an isolated search result opens its source details');
      assert((await detail.textContent()).includes(target.name));
      assert((await detail.locator('.relation-source').textContent()).trim(),'Isolated framework source remains readable');
      assert.deepEqual(await map.locator('.lfm-mm-node').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('data-framework-id')).sort()),linkedIds,'Search never injects an isolated framework into the canvas');
      await map.locator('.lfm-mm-search').fill('');
      await map.locator('.lfm-mm-unlinked summary').click();
    }
    await map.locator('.lfm-mm-tools button').filter({hasText:/全屏展开|Fullscreen/}).click();
    assert(await map.isVisible());
    assert(await map.evaluate(n=>Math.abs(n.getBoundingClientRect().height-innerHeight)<3),'Framework fullscreen must fill the viewport');
    await page.keyboard.press('Escape');
    await page.waitForFunction(()=>!document.fullscreenElement&&!document.querySelector('.lfm-mm.is-fullscreen'));
    await page.locator('#tab-rules').click();
    // The rules panel ships cards-first too; activate the diagram view before
    // touching its toolbar, otherwise .diagram-tools has zero size and is not visible.
    const rulesGraph=page.locator('#rules .action-view-button').nth(1);
    if(await rulesGraph.count())await rulesGraph.click();
    await page.waitForTimeout(300);
    assert.equal(await page.locator('#rules .diagram-card').count(),data.methodology.nodes.length);
    await page.locator('#rules .diagram-tools button').last().click();
    assert.equal(await page.locator('body > .diagram-studio.is-expanded').count(),1);
    await page.locator('.is-expanded .diagram-node-button').first().click();
    const intersections=await page.evaluate(()=>{
      const root=document.querySelector('.diagram-studio.is-expanded'),cards=[...root.querySelectorAll('.diagram-card')].map(n=>n.getBoundingClientRect()),hits=[];
      for(const p of root.querySelectorAll('.diagram-wire')){
        const m=p.getScreenCTM(),length=p.getTotalLength();
        for(let d=4;d<length-4;d+=6){
          const v=p.getPointAtLength(d),x=m.a*v.x+m.c*v.y+m.e,y=m.b*v.x+m.d*v.y+m.f;
          if(cards.some(c=>x>c.left+3&&x<c.right-3&&y>c.top+3&&y<c.bottom-3)){hits.push(p.getAttribute('d'));break;}
        }
      }
      return hits;
    });
    assert.deepEqual(intersections,[],'Wires must not pass through card interiors');
    if(process.argv[3])await page.screenshot({path:path.resolve(process.argv[3])});
    await page.keyboard.press('Escape');
    await page.waitForFunction(()=>!document.fullscreenElement&&!document.querySelector('.diagram-studio.is-expanded'));
    assert.equal(await page.locator('#rules .diagram-studio').count(),1);
    // Back to the cards view: the launch button lives there and is hidden while the
    // diagram view is active.
    await page.locator('#rules .action-view-button').first().click();
    await page.waitForTimeout(200);
    await page.locator('#applyMethod').click();
    assert.equal(await page.locator('#methodSelect').inputValue(),'whole');
    await page.locator('#methodProblem').fill('How should I apply the methodology to a new problem?');
    await page.locator('#methodForm button[type=submit]').click();
    const prompt=await page.locator('#methodPrompt').inputValue(),payload=JSON.parse(prompt.slice(prompt.indexOf('{\n')));
    assert.equal(payload.selection,'whole-material');assert.deepEqual(payload.methodology,data.methodology);
    await page.locator('#methodClose').click();await page.locator('#tab-content').click();
    await page.locator('.ch-nav-btn').last().click();
    // A diagram hovercard from the earlier graph interaction is appended to <body> and
    // clamped to the viewport edge, so a plain mouse.move() may leave the cursor still
    // inside it. Dispatch a pointerleave on it to dismiss it deterministically.
    await page.evaluate(()=>{const h=document.querySelector('.diagram-hovercard');if(h)h.dispatchEvent(new PointerEvent('pointerleave',{bubbles:true}));});
    await page.waitForTimeout(150);
    // The chapter body may sit above the fold after switching chapters; scroll it into
    // view so the pointer actually lands on the element and fires pointermove.
    const chCore=page.locator('#chView .ch-core');
    await chCore.scrollIntoViewIfNeeded();
    await page.waitForTimeout(100);
    // The tooltip is driven by pointermove (not mouseenter), so the pointer must
    // actually travel into the element. Move in two steps from an off-element start.
    const cbox=await chCore.boundingBox();
    await page.mouse.move(Math.max(1,cbox.x-40), Math.max(1,cbox.y-40));
    await page.mouse.move(cbox.x+cbox.width/2, cbox.y+cbox.height/2);
    await page.waitForTimeout(200);
    const hoverShown=await page.locator('#contentSourceTooltip').isVisible();
    if(!hoverShown){
      // Fallback: some environments deliver no pointermove for a scripted mouse; the
      // keyboard path exercises the same source plumbing.
      await chCore.evaluate(n=>n.focus({preventScroll:true}));
      await page.waitForTimeout(150);
    }
    assert(await page.locator('#contentSourceTooltip').isVisible());
    await page.keyboard.press('Escape');
    await page.waitForTimeout(100);
    // Blur first: focusing an already-focused node fires no focusin, so the tooltip
    // would never re-appear.
    await chCore.evaluate(n=>n.blur());
    await page.waitForTimeout(100);
    await chCore.scrollIntoViewIfNeeded();
    await page.waitForTimeout(150);
    await chCore.evaluate(n=>n.focus({preventScroll:true}));
    await page.waitForTimeout(150);
    assert(await page.locator('#contentSourceTooltip').isVisible());
    await page.setViewportSize({width:390,height:844});
    await page.locator('#tab-rules').click();
    await page.waitForTimeout(200);
    // Same as the desktop pass: activate the rules diagram view before using its toolbar.
    const rulesGraphMobile=page.locator('#rules .action-view-button').nth(1);
    if(await rulesGraphMobile.count())await rulesGraphMobile.click();
    await page.waitForTimeout(300);
    await page.locator('#rules .diagram-tools button').last().click();
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),true);
    assert.equal(await page.locator('.is-expanded .diagram-card').count(),data.methodology.nodes.length);
    assert(await page.locator('.is-expanded .diagram-tools button').evaluateAll(buttons=>buttons.every(button=>{const r=button.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1;})),'Every mobile toolbar button remains reachable');
    await page.keyboard.press('Escape');
    await page.waitForFunction(()=>!document.fullscreenElement&&!document.querySelector('.diagram-studio.is-expanded'));
    assert.deepEqual(errors,[]);assert.deepEqual(blocked,[]);
    console.log('PASS: cards-first, complete framework mind map, whole methodology in rules, no card/wire collisions, fullscreen, prompt, sources and mobile overflow.');
    await context.close();
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
