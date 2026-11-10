import asyncio
import json
from pathlib import Path
import httpx
from reportlab.pdfgen import canvas
from paper_research_coach.server import create_app
from paper_research_coach.store import Store
from paper_research_coach.workspaces import WorkspaceStore


def make_pdf(path, blank=False):
    c = canvas.Canvas(str(path), pagesize=(600, 800))
    if not blank:
        c.drawString(60, 720, '1 Introduction')
        c.drawString(60, 680, 'Synthetic evidence checks an alternative explanation.')
    c.showPage(); c.save()


def test_authenticated_study_source_validation_and_shared_note_conflicts(tmp_path):
    async def run():
        store = Store(tmp_path / 'data')
        path = tmp_path / 'paper.pdf'; make_pdf(path)
        paper = store.add_paper('Synthetic paper', str(path))
        blank = tmp_path / 'blank.pdf'; make_pdf(blank, True)
        scan = store.add_paper('No text', str(blank))
        app = create_app(store, 'secret')
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url='http://127.0.0.1') as c:
            assert (await c.get('/api/workspace/studies')).status_code == 401
            c.headers['authorization'] = 'Bearer secret'
            no_text = await c.post('/api/workspace/studies', json={'paper_id': scan['id'], 'scope': 'full'})
            assert no_text.status_code == 400
            row = (await c.post('/api/workspace/studies', json={'paper_id': paper['id'], 'scope': 'full'})).json()
            assert row['paragraphs'] and 'page_images' not in row
            anchor = row['paragraphs'][0]['anchor']
            note = {'id': 'shared-note', 'paper_id': paper['id'], 'author': 'user', 'provenance': 'USER', 'content': 'Exact learner thought', 'anchor': anchor}
            def commit(content, expected, operation):
                return {'operation_id': operation, 'mutations': [{'kind': 'note', 'data': {**note, 'content': content}, 'expected_revision': expected}]}
            saved = (await c.post('/api/commit', json=commit('Exact learner thought', 0, 'create-note'))).json()['records'][0]
            read = (await c.get('/api/workspace/studies/' + row['id'])).json()
            assert read['notes'][0]['id'] == saved['id']
            assert (await c.post('/api/commit', json=commit('First edit', saved['revision'], 'edit-one'))).status_code == 200
            assert (await c.post('/api/commit', json=commit('Concurrent edit', saved['revision'], 'edit-two'))).status_code == 409
            route = '/api/workspace/studies/' + row['id'] + '/notes/' + saved['id']
            assert (await c.put(route, json={'operation_id':'scope-stale', 'revision':1, 'content':'stale'})).status_code == 409
            assert (await c.put(route, json={'operation_id':'scope-edit', 'revision':2, 'content':'First edit scoped'})).status_code == 200
            foreign = {**note, 'id':'foreign-note', 'paper_id':scan['id'], 'anchor':None}
            assert (await c.post('/api/commit', json={'operation_id':'foreign-create','mutations':[{'kind':'note','data':foreign,'expected_revision':0}]})).status_code == 200
            attack = '/api/workspace/studies/' + row['id'] + '/notes/foreign-note'
            assert (await c.put(attack, json={'operation_id':'scope-attack','revision':1,'content':'forged'})).status_code == 400
            exported = await c.get('/api/workspace/studies/' + row['id'] + '/html')
            assert 'data:image/png;base64,' in exported.text
            assert 'First edit' in exported.text and 'data-note-id="shared-note"' in exported.text
            path.write_bytes(path.read_bytes()+b'\n%new-version')
            rejected = await c.post('/api/workspace/studies/' + row['id'] + '/generate', json={})
            assert rejected.status_code == 400
        await app.state.workspace.close()
    asyncio.run(run())


def test_cancel_and_restart_preserve_completed_paragraphs(tmp_path):
    async def run():
        store = Store(tmp_path / 'data')
        app = create_app(store, 'secret')
        w = app.state.workspace
        row = w.store.create('study', {'paper_id': 'p', 'source_version': 'v', 'paragraphs': [{'id': 'a', 'text': 'first'}, {'id': 'b', 'text': 'second'}], 'analyses': {}, 'errors': {}})
        from paper_research_coach.paper_study import PaperStudy
        service = PaperStudy(w); service.current = lambda *args: None
        waiting = asyncio.Event()
        class Account:
            calls = 0
            async def text(self, *args, **kwargs):
                self.calls += 1
                if self.calls > 1:
                    waiting.set(); await asyncio.Event().wait()
                return '{"translation":"译文"}'
        w.account = Account()
        pending = service.generate(row['id'], {})
        await asyncio.wait_for(waiting.wait(), 2)
        await w.jobs.cancel(pending['id'])
        reopened = WorkspaceStore(w.store.root)
        assert list(reopened.get('study', row['id'])['analyses']) == ['a']
        assert reopened.get('job', pending['id'])['state'] == 'cancelled'
        await w.close()
    asyncio.run(run())
