// Opt-in only where browser access is permitted. Never use this to bypass a
// browser policy refusal. Uses existing installations; missing runtime is not-run.
// node scripts/verify-layout.cjs final.html report.json
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {pathToFileURL}=require('node:url');
const {checkLayout,checkFullscreen}=require('./layout_checks.cjs');
const widths=[390,819,820,821,980,981,1024,1039,1040,1041,1440,2105,820,1440];
const themes=['warm-paper','minimal','dark'];
const tabs=['frameworks','content','glossary','rules','practice','notes'];
const [htmlArg,reportArg]=process.argv.slice(2);
if(!htmlArg||!reportArg){console.error('Usage: node verify-layout.cjs final.html report.json');process.exit(2);}
const html=path.resolve(htmlArg),reportPath=path.resolve(reportArg);
if(fs.existsSync(reportPath)){console.error('Report already exists; choose a new report path');process.exit(2);}
if(!/\.html?$/i.test(html)||!fs.existsSync(html)){console.error('Expected an existing HTML file');process.exit(2);}
const report={schemaVersion:'learn-from-materials/layout-review-v1',htmlSha256:crypto.createHash('sha256').update(fs.readFileSync(html)).digest('hex'),
  status:'not-run',checks:[],fullscreen:[],screenshots:[],errors:[],note:'Automated geometry only; screenshots still require visual inspection.'};
function save(){fs.writeFileSync(reportPath,JSON.stringify(report,null,2)+'\n',{flag:'wx'});}
(async()=>{
  let chromium,browser;
  try{({chromium}=require('playwright'));browser=await chromium.launch({headless:true,...(process.env.LFM_BROWSER_CHANNEL?{channel:process.env.LFM_BROWSER_CHANNEL}:{})});}
  catch(e){report.note='Browser check not run: '+String(e.message).split('\n')[0];save();process.exitCode=2;return;}
  const shots=reportPath+'.shots';
  try{
    fs.mkdirSync(shots); // fail rather than overwrite prior screenshots
    const url=pathToFileURL(html).href;
    const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block',reducedMotion:'reduce'});
    await context.route('**/*',r=>{const u=r.request().url();if(u===url||/^(data:|blob:)/.test(u))return r.continue();report.errors.push('blocked external request');return r.abort();});
    await context.addInitScript(()=>{
      window.WebSocket=class{constructor(){throw new Error('WebSocket disabled');}};
      window.EventSource=class{constructor(){throw new Error('EventSource disabled');}};
    });
    const page=await context.newPage();
    context.on('page',other=>{if(other!==page)other.close().catch(()=>{});});
    page.on('pageerror',e=>report.errors.push(e.message));
    await page.goto(url,{waitUntil:'domcontentloaded'});
    const data=JSON.parse(await page.locator('#pageData').textContent());
    const available={frameworks:data.frameworks.length>0,rules:data.methodology?.status==='ready'};
    if(await page.locator('#guideSkip').isVisible())await page.locator('#guideSkip').click();
    async function measureLayout(){
      await page.evaluate(()=>window.scrollTo(0,0));
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      return page.evaluate(()=>{
        const rect=n=>{if(!n)return null;const r=n.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height};};
        const root=document.querySelector('.page'),nav=document.querySelector('.tabs');
        return {viewportWidth:innerWidth,viewportHeight:innerHeight,scrollWidth:document.documentElement.scrollWidth,
          page:rect(root),panel:rect(document.querySelector('.panel.active')),nav:rect(nav),
          navDirection:nav?getComputedStyle(nav).flexDirection:null,
          gridColumns:root?getComputedStyle(root).gridTemplateColumns.trim().split(/\s+/).length:0};
      });
    }
    let shotNumber=0;
    async function shot(label){
      const file=path.join(shots,String(++shotNumber).padStart(3,'0')+'-'+label+'.png');
      await page.screenshot({path:file});
      report.screenshots.push({path:path.relative(path.dirname(reportPath),file).split(path.sep).join('/'),sha256:crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')});
    }
    for(const theme of themes){
      await page.selectOption('#themePicker',theme);
      for(const width of widths){
        await page.setViewportSize({width,height:1000});
        for(const tab of tabs){
          await page.locator('#tab-'+tab).click();
          const measurements=await measureLayout();
          const errors=checkLayout(measurements);
          report.checks.push({theme,width,tab,measurements,errors});
          if(errors.length)report.errors.push(`${theme}/${width}/${tab}: ${errors.join('; ')}`);
          if(errors.length||width===1440||width===2105||width===390)await shot(`${theme}-${width}-${tab}`);
        }
      }
      for(const width of [390,1440,2105]){
        await page.setViewportSize({width,height:1000});
        for(const [name,selector] of [['frameworks','#frameworks .lfm-mm'],['rules','.diagram-studio.is-expanded']]){
          if(!available[name]){report.fullscreen.push({theme,width,module:name,status:'not-applicable',errors:[]});continue;}
          if(name==='rules'){
            await page.locator('#tab-rules').click();
            await page.locator('#rules .action-view-button').nth(1).click();
            await page.locator('#rules .diagram-tools button').last().click();
          }else{
            await page.locator('#tab-frameworks').click();
            await page.locator('#frameworks .relation-tools button').nth(1).click();
            await page.locator('#frameworks .lfm-mm .lfm-mm-tools button').filter({hasText:/全屏展开|Fullscreen/}).click();
          }
          await page.waitForTimeout(150);
          const measurements=await page.locator(selector).evaluate(n=>{
            const rect=e=>{const r=e.getBoundingClientRect();return{x:r.x,y:r.y,width:r.width,height:r.height};};
            const stage=n.querySelector('.diagram-stage'),title=n.querySelector('.diagram-card h4');
            const scale=stage?Number((stage.style.transform.match(/scale\(([^)]+)\)/)||[])[1]):null;
            return{rect:rect(n),viewportWidth:innerWidth,viewportHeight:innerHeight,
              graphKind:stage?'methodology':'framework',
              renderedTitleSize:title&&scale?parseFloat(getComputedStyle(title).fontSize)*scale:null,
              toolbarButtons:[...n.querySelectorAll('.diagram-tools button,.lfm-mm-tools button')].map(rect)};
          });
          const errors=checkFullscreen(measurements);
          await shot(`${theme}-${width}-${name}-fullscreen`);
          if(name==='frameworks')await page.locator('#frameworks .lfm-mm .lfm-mm-tools button').filter({hasText:/退出全屏|Exit fullscreen/}).click();
          else await page.locator('.diagram-studio.is-expanded .diagram-tools button').last().click();
          await page.waitForFunction(()=>!document.fullscreenElement&&!document.querySelector('.is-expanded,.lfm-mm.is-fullscreen'));
          const restored=await measureLayout();
          errors.push(...checkLayout(restored).map(e=>'after fullscreen: '+e));
          report.fullscreen.push({theme,width,module:name,measurements,restored,errors});
          if(errors.length)report.errors.push(`${theme}/${width}/${name}/fullscreen: ${errors.join('; ')}`);
          await shot(`${theme}-${width}-${name}-restored`);
        }
      }
    }
    report.status=report.errors.length?'failed':'passed';
    await context.close();
  }catch(e){report.status='failed';report.errors.push(String(e.message));}
  finally{await browser.close();save();}
  console.log(report.status+': '+reportPath);process.exitCode=report.status==='passed'?0:1;
})().catch(e=>{console.error(e);process.exitCode=1;});
