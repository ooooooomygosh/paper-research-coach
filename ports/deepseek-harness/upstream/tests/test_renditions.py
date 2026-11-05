"""Translated geometry must survive reload/export without leaking onto the original."""
import copy
import json

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfReader, PdfWriter

from paper_research_coach.coaching_request import Send
from paper_research_coach.exports import annotated_pdf
from paper_research_coach.renditions import inspect_pdf
from paper_research_coach.server import create_app
from paper_research_coach.store import Store
from paper_research_coach.translation import Translation


@pytest.fixture
def translated(store, paper):
    manager = Translation(store)
    folder = store.root / 'translations' / 'layout-test'
    folder.mkdir(parents=True)
    paths = {}
    for view, width in [('mono', 600), ('dual', 1200)]:
        writer = PdfWriter()
        for _ in range(4):
            writer.add_blank_page(width=width, height=800)
        path = folder / f'{view}.pdf'
        with path.open('wb') as stream:
            writer.write(stream)
        paths[view] = str(path)
    (folder / 'mapping.json').write_text('{"segments": []}')
    paths['mapping'] = str(folder / 'mapping.json')
    job = dict(id='layout-test', paper_id=paper['id'], source_version=paper['source_version'], operation_id='layout-test', state='completed', artifacts=paths)
    with store.connect() as db:
        db.execute('INSERT INTO translation_jobs VALUES (?,?,?,?)', (job['id'], paper['id'], job['operation_id'], json.dumps(job)))
    return manager.public(job), folder


def position(paper, translated, view='dual'):
    job, _ = translated
    return dict(paper_id=paper['id'], source_version=paper['source_version'], status='unresolved', page_index=None, quote='', rects=[], rendition=dict(
        job_id=job['id'], view=view, document_version=job['documents'][view]['document_version'], page_index=3, quote='', rects=[[650 if view == 'dual' else 50, 400, 900 if view == 'dual' else 300, 500]],
    ))


def test_translated_region_persists_and_exports_only_to_its_own_layout(store, paper, translated, tmp_path):
    anchor = position(paper, translated)
    note = store.put('note', dict(id='translated-note', paper_id=paper['id'], content='这里的图需要核实。', anchor=anchor, annotation_type='rectangle'))
    assert Store(store.root).get('note', note['id'])['anchor']['rendition']['rects'] == anchor['rendition']['rects']
    original = tmp_path / 'original.pdf'
    assert annotated_pdf(store, paper['id'], original)['unplaced_note_ids'] == [note['id']]
    assert not any(p.get('/Annots') for p in PdfReader(original).pages)
    dual = tmp_path / 'dual.pdf'
    assert not annotated_pdf(store, paper['id'], dual, anchor['rendition'])['unplaced_note_ids']
    annotation = PdfReader(dual).pages[3]['/Annots'][0].get_object()
    assert annotation['/Subtype'] == '/Square'
    assert annotation['/Rect'] == [650, 400, 900, 500]
    assert '这里的图需要核实。' in annotation['/Contents']
    mono = tmp_path / 'mono.pdf'
    assert annotated_pdf(store, paper['id'], mono, position(paper, translated, 'mono')['rendition'])['unplaced_note_ids'] == [note['id']]
    assert not any(p.get('/Annots') for p in PdfReader(mono).pages)


def test_rejects_foreign_out_of_bounds_and_changed_translated_geometry(store, paper, translated):
    anchor = position(paper, translated)
    for edit in ({'document_version': '0' * 64}, {'page_index': 4}, {'rects': [[-20, 0, 30, 50]]}, {'job_id': 'missing'}):
        bad = copy.deepcopy(anchor)
        bad['rendition'].update(edit)
        with pytest.raises(ValueError):
            store.put('note', dict(paper_id=paper['id'], content='bad', anchor=bad))
    other = store.put('paper', {**paper, 'id': 'other', 'revision': 0, 'title': 'Other paper'})
    bad = {**anchor, 'paper_id': other['id']}
    with pytest.raises(ValueError, match='同一篇论文'):
        store.put('note', dict(paper_id=other['id'], content='bad', anchor=bad))
    assert not store.list('note')


def test_retranslation_keeps_old_notes_but_refuses_to_reuse_their_coordinates(store, paper, translated, tmp_path):
    anchor = position(paper, translated)
    note = store.put('note', dict(paper_id=paper['id'], content='original note', anchor=anchor))
    _, folder = translated
    writer = PdfWriter()
    writer.add_blank_page(width=900, height=800)
    with (folder / 'dual.pdf').open('wb') as output:
        writer.write(output)
    with pytest.raises(ValueError, match='已改变'):
        annotated_pdf(store, paper['id'], tmp_path / 'changed.pdf', anchor['rendition'])
    assert store.get('note', note['id'])['content'] == 'original note'
    assert inspect_pdf(folder / 'dual.pdf')['document_version'] != anchor['rendition']['document_version']


def test_translated_highlight_download_through_authenticated_api(store, paper, translated):
    anchor = position(paper, translated, 'mono')
    anchor['rendition']['quote'] = 'translated selected passage'
    store.put('note', dict(paper_id=paper['id'], content='我的判断', anchor=anchor))
    with TestClient(create_app(store, token='test'), base_url='http://127.0.0.1') as client:
        headers = {'Authorization': 'Bearer test'}
        result = client.post('/api/export', headers=headers, json={'kind':'pdf', 'paper_id':paper['id'], 'rendition':anchor['rendition']})
        assert result.status_code == 200, result.text
        file = store.root / 'exports' / result.json()['download'].rsplit('/', 1)[1]
        ann = PdfReader(file).pages[3]['/Annots'][0].get_object()
        assert ann['/Subtype'] == '/Highlight'
        assert '我的判断' in ann['/Contents']
        assert client.get(result.json()['download'], headers=headers).status_code == 200


def test_legacy_anchor_serialization_does_not_change_send_fingerprints(anchor):
    body = Send(operation_id='old', content='question', anchor=anchor)
    serialized = body.fingerprint_data()['anchor']
    assert 'rendition' not in serialized
    assert json.loads(json.dumps(serialized['rects'])) == anchor['rects']
