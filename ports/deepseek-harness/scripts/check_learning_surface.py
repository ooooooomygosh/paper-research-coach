"""Optional Chrome smoke for the built DSH frontend with an isolated synthetic library.

Run from the repository root after building the DSH frontend:
PYTHONPATH=ports/deepseek-harness/upstream/src .venv312/bin/python ports/deepseek-harness/scripts/check_learning_surface.py
Set PRC_BROWSER to a Chromium executable when needed. No account/model calls.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import socket, threading, time, asyncio, json, os
from urllib.parse import urlencode
import uvicorn, httpx
from starlette.applications import Starlette
from starlette.routing import Mount
from playwright.sync_api import sync_playwright
from paper_research_coach.demo import prepare_demo
from paper_research_coach.server import create_app, session_token

root=Path(__file__).resolve().parents[3]
out=root/'artifacts/verification'
async def renderer(payload):
    return {'html':'<!doctype html><html><body><h1>Isolated learning fixture</h1><textarea id="draft">iframe draft</textarea><p>Synthetic content only; no model was called.</p></body></html>', 'warnings':[], 'meta':{'title':'Isolated learning fixture'}}
with TemporaryDirectory(prefix='prc-m2-browser-') as tmp:
    store,paper=prepare_demo(Path(tmp)); token=session_token(store)
    app=create_app(store,token,workspace_renderer=renderer)
    coach=app.state.coach
    anchor=store.list('note',paper['id'])[0]['anchor']
    draft=(root/'tests/fixtures/explainers/budget-zh.md').read_text()
    record=coach.explain_external(paper['id'],draft,question='Synthetic fixture question',anchor=anchor)
    async def status(): return {'state':'unavailable','models':[],'message':'Isolated synthetic browser fixture'}
    coach.status=status
    async def seed():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://127.0.0.1',headers={'authorization':'Bearer '+token}) as c:
            doc=(await c.post('/api/workspace/studios',json={'source':'---\ntitle: Synthetic fixture\n---\n## A Test\nSynthetic content.'})).json()
            await c.post('/api/workspace/studios/'+doc['id']+'/render')
    asyncio.run(seed())
    # Match the Harness reverse proxy: strip the public prefix before middleware.
    async def wrapper(scope,receive,send):
        scope=dict(scope)
        prefix='/paper-research-coach'
        if scope.get('path','').startswith(prefix):
            scope['path']=scope['path'][len(prefix):] or '/'
            scope['raw_path']=scope['path'].encode()
        await app(scope,receive,send)
    with socket.socket() as s: s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(wrapper,host='127.0.0.1',port=port,log_level='error',access_log=False))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    deadline=time.monotonic()+15
    while not server.started:
        if time.monotonic()>deadline: raise RuntimeError('startup timeout')
        time.sleep(.05)
    results={}
    try:
      with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('PRC_BROWSER') or ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' if Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome').exists() else None),args=['--disable-gpu'])
        page=browser.new_page(viewport={'width':1600,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(f'http://127.0.0.1:{port}/paper-research-coach/#'+urlencode({'token':token,'paper':paper['id']}))
        page.locator('.xp-card-tools button[title="放大到侧边"]').first.click()
        dialog=page.get_by_role('dialog',name='讲解面板');dialog.wait_for()
        box=dialog.get_by_label('继续追问这一处');box.fill('未发送的浏览器测试草稿')
        page.screenshot(path=str(out/'m2-large.png'))
        dialog.get_by_role('button',name='与论文对照').click()
        split=page.get_by_role('separator',name='调整论文与讲解宽度');split.wait_for()
        old=int(split.get_attribute('aria-valuenow'));split.focus();split.press('ArrowRight');assert int(split.get_attribute('aria-valuenow'))>old
        page.screenshot(path=str(out/'m2-compare.png'))
        results['wide_adjustable_split']=True
        page.set_viewport_size({'width':760,'height':900})
        tabs=page.get_by_role('group',name='论文与讲解切换');tabs.get_by_role('button',name='论文',exact=True).click()
        assert page.locator('html').get_attribute('data-learning-compare')=='paper'
        page.screenshot(path=str(out/'m2-narrow-paper.png'))
        tabs.get_by_role('button',name='讲解',exact=True).click()
        assert box.input_value()=='未发送的浏览器测试草稿'
        results['narrow_tabs_keep_draft']=True
        page.evaluate("window.__locateRequests=[]; const f=window.fetch; window.fetch=(...args)=>{ window.__locateRequests.push(String(args[0])); return f(...args); }")
        with page.expect_popup() as popup_info:
            dialog.get_by_role('button',name='在新窗口打开',exact=True).click()
        popup=popup_info.value
        popup.get_by_role('button',name='回到原文',exact=False).click()
        page.wait_for_function("window.__locateRequests.some(p=>p.includes('coach/explainer/'))")
        results['popout_uses_trusted_record_lookup']=True
        popup.close()
        page.evaluate('window.open=()=>null')
        dialog.get_by_role('button',name='在新窗口打开',exact=True).click()
        assert dialog.is_visible() and box.input_value()=='未发送的浏览器测试草稿'
        results['blocked_popout_keeps_view']=True
        dialog.focus();page.keyboard.press('Escape');assert page.locator('html').get_attribute('data-learning-compare') is None
        page.keyboard.press('Escape');assert dialog.is_visible()
        dialog.get_by_role('button',name='回到主线').click();dialog.wait_for(state='detached')
        results['escape_layers']=True
        page.wait_for_timeout(100)
        assert page.get_by_label('发给论文教练的消息').evaluate('(el)=>document.activeElement===el')
        results['focus_returns_to_composer']=True
        page.set_viewport_size({'width':1600,'height':1000})
        page.get_by_role('button',name='交互式讲解',exact=True).first.click()
        frame=page.locator('.artifact-frame iframe');frame.wait_for()
        page.wait_for_timeout(700)
        page.frame_locator('.artifact-frame iframe').locator('#draft').fill('same mounted iframe')
        handle=frame.element_handle()
        page.locator('.artifact-toolbar').get_by_role('button',name='展开讲解',exact=True).click()
        page.locator('.artifact-toolbar').get_by_role('button',name='返回工作台',exact=True).click()
        assert frame.evaluate('(el,old)=>el===old',handle)
        assert page.frame_locator('.artifact-frame iframe').locator('#draft').input_value()=='same mounted iframe'
        results['iframe_state_preserved']=True
        page.screenshot(path=str(out/'m2-iframe.png'))
        results['page_errors']=errors
        browser.close()
    finally:
        server.should_exit=True;thread.join(timeout=8)
        (out/'m2-browser-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2))
    print(json.dumps(results,ensure_ascii=False))
