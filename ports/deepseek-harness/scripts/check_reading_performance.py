"""Isolated, synthetic long-PDF browser measurement; never opens a personal library."""
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode
import os,json,socket,threading,time,statistics
import uvicorn
from fastapi.responses import FileResponse
from playwright.sync_api import sync_playwright
from reportlab.pdfgen import canvas
from paper_research_coach.store import Store
from paper_research_coach.server import create_app,session_token
ROOT=Path(__file__).resolve().parents[3];OUT=ROOT/'artifacts/verification';OUT.mkdir(parents=True,exist_ok=True)
BASE=Path(os.environ['PRC_PERF_STATIC']) if os.environ.get('PRC_PERF_STATIC') else None
label=os.environ.get('PRC_PERF_LABEL') or ('baseline' if BASE else 'candidate')
def pct(xs,p):return round(sorted(xs)[min(len(xs)-1,int(len(xs)*p))],2) if xs else 0
with TemporaryDirectory(prefix='prc-perf-') as tmp:
    temp=Path(tmp); pdf=temp/'synthetic-180-pages.pdf'; c=canvas.Canvas(str(pdf),pagesize=(600,800))
    for i in range(180):
        c.setFont('Helvetica',10);c.drawString(40,770,f'Synthetic performance fixture page {i+1} / 180. No empirical claim.')
        for j in range(52):c.drawString(40,740-j*13,f'Line {j+1}: Evidence, mechanisms and boundary conditions for an invented research task.')
        c.showPage()
    c.save();store=Store(temp/'library');paper=store.add_paper('Synthetic performance fixture',str(pdf));token=session_token(store)
    app=create_app(store,token);coach=app.state.coach
    async def status():return {'state':'ready','models':[],'message':'Synthetic fixture: no model calls'}
    coach.status=status
    graph='---\ntitle: Synthetic graph stress\n---\n'+ '\n'.join('## '+chr(65+p)+' Graph '+str(p)+'\n```flow LR\n'+'\n'.join(f'N{p}_{i} -> N{p}_{i+1}' for i in range(29))+'\n```' for p in range(8))
    coach.explain_external(paper['id'],graph,question='Synthetic 240-node bounded diagram fixture')
    async def wrapper(scope,receive,send):
        scope=dict(scope);prefix='/paper-research-coach'
        if scope.get('path','').startswith(prefix):scope['path']=scope['path'][len(prefix):] or '/';scope['raw_path']=scope['path'].encode()
        path=scope.get('path','')
        if BASE and (path in ('/','/index.html') or path.startswith('/assets/')):
            candidate=BASE/('index.html' if path=='/' else path.lstrip('/'))
            if candidate.is_file():await FileResponse(candidate)(scope,receive,send);return
        await app(scope,receive,send)
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(wrapper,host='127.0.0.1',port=port,log_level='error',access_log=False));thread=threading.Thread(target=server.run,daemon=True);thread.start()
    while not server.started:time.sleep(.02)
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('PRC_BROWSER') or ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists() else None),args=['--disable-gpu'])
        page=browser.new_page(viewport={'width':1440,'height':1000});errors=[];writes=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda r:writes.append(r.url) if r.method in ('POST','PUT') and ('coach/send' in r.url or '/generate' in r.url) else None)
        page.add_init_script('''window.__perf={frames:[],longtasks:[],inputPaint:[],peakCanvases:0};
          new PerformanceObserver(list=>{for(const e of list.getEntries())window.__perf.longtasks.push(e.duration)}).observe({type:'longtask',buffered:true});
          let last=performance.now();function frame(t){window.__perf.frames.push(t-last);last=t;window.__perf.peakCanvases=Math.max(window.__perf.peakCanvases,document.querySelectorAll('.pdf-page canvas').length);requestAnimationFrame(frame)}requestAnimationFrame(frame);
          document.addEventListener('input',e=>{if(e.target.tagName==='TEXTAREA'){const start=performance.now();requestAnimationFrame(()=>window.__perf.inputPaint.push(performance.now()-start));}},true);''')
        start=time.monotonic();page.goto(f'http://127.0.0.1:{port}/paper-research-coach/#'+urlencode({'token':token,'paper':paper['id']}));page.locator('.pdf-page canvas').first.wait_for(timeout=30000)
        first_ms=round((time.monotonic()-start)*1000,1)
        page.evaluate('''async()=>{const e=document.querySelector('.pdf-scroll');for(let i=0;i<120;i++){e.scrollTop=(e.scrollHeight-e.clientHeight)*i/119;await new Promise(requestAnimationFrame)}}''')
        page.wait_for_timeout(300)
        canvases=page.locator('.pdf-page canvas').count();placeholders=page.locator('.pdf-page').count()
        start=time.monotonic();page.locator('.xp-card-tools button[title="放大到侧边"]').first.click();dialog=page.get_by_role('dialog',name='讲解面板');dialog.wait_for();open_ms=round((time.monotonic()-start)*1000,1)
        box=dialog.get_by_label('继续追问这一处');box.focus();page.keyboard.type('Synthetic unsent question about an evidence boundary. '*2,delay=12)
        for _ in range(4):
            dialog.get_by_role('button',name='收起讲解',exact=True).click();dialog.get_by_role('button',name='展开讲解',exact=True).click()
        dialog.get_by_role('button',name='与论文对照').click()
        divider=page.get_by_role('separator',name='调整论文与讲解宽度');divider.focus()
        for _ in range(15):divider.press('ArrowRight');divider.press('ArrowLeft')
        page.wait_for_timeout(700)
        no_action_requests=len(writes)
        async_response={'conversation_id':coach.binding(paper['id'])['conversation_id']}
        page.route('**/api/coach/send/**',lambda route:route.fulfill(status=200,json=async_response))
        dialog.get_by_role('button',name='发送追问',exact=True).click()
        page.wait_for_timeout(150)
        simulated_question_posts=len(writes)-no_action_requests
        assert no_action_requests==0 and simulated_question_posts==1
        raw=page.evaluate('window.__perf'); memory=page.evaluate('performance.memory ? performance.memory.usedJSHeapSize : null')
        result={'build':label,'pdf_pages':180,'lines_per_page':52,'diagram_nodes':240,'first_pdf_ms':first_ms,'graph_open_ms':open_ms,
                'mounted_canvases_after_scroll':canvases,'peak_canvases':raw['peakCanvases'],'page_placeholders':placeholders,
                'frame_p50_ms':pct(raw['frames'],.5),'frame_p95_ms':pct(raw['frames'],.95),'frame_max_ms':pct(raw['frames'],1),
                'longtasks_count':len(raw['longtasks']),'longtask_max_ms':pct(raw['longtasks'],1),'longtask_total_ms':round(sum(raw['longtasks']),1),
                'input_to_next_frame_p50_ms':pct(raw['inputPaint'],.5),'input_to_next_frame_p95_ms':pct(raw['inputPaint'],.95),
                'input_samples':len(raw['inputPaint']),'generation_requests_without_send':no_action_requests,'simulated_question_posts':simulated_question_posts,'upstream_model_calls':0,'js_heap_mb':round(memory/1024/1024,1) if memory else None,'page_errors':errors}
        (OUT/('performance-'+label+'.json')).write_text(json.dumps(result,indent=2));print(json.dumps(result));browser.close()
    finally:server.should_exit=True;thread.join(timeout=8)
