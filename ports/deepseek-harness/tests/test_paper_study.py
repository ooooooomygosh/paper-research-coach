import asyncio
from types import SimpleNamespace
import pytest
from paper_research_coach.paper_study import index_pdf, validate_analysis, render_study, PaperStudy
from paper_research_coach.workspaces import WorkspaceStore, Jobs


def test_index_tracks_versions_and_scans(monkeypatch):
    monkeypatch.setattr('paper_research_coach.paper_study.PdfReader', lambda _: SimpleNamespace(pages=[SimpleNamespace(extract_text=lambda **_: '1 Introduction\n\nActual source text.'), SimpleNamespace(extract_text=lambda **_: '')]))
    paper = {'id': 'p', 'source_version': 'a', 'source_path': 'unused'}
    first, missing = index_pdf(paper)
    second, _ = index_pdf(paper)
    third, _ = index_pdf({**paper, 'source_version': 'b'})
    assert first == second and first[0]['id'] != third[0]['id']
    assert missing == [1] and first[-1]['anchor']['page_index'] == 0


def test_refuses_invented_or_ambiguous_marks():
    with pytest.raises(ValueError):
        validate_analysis({'translation': '译文', 'marks': [{'quote': 'invented', 'category': 'thesis'}]}, {'text': 'actual'})
    with pytest.raises(ValueError):
        validate_analysis({'translation': '译文', 'marks': [{'quote': 'same', 'category': 'thesis'}]}, {'text': 'same same'})


def test_export_escapes_analysis_and_keeps_note_identity():
    p = {'id': 'paragraph', 'section': 'Intro', 'text': '<actual>', 'anchor': {'page_index': 0}}
    analysis = validate_analysis({'translation': '<script>bad</script>', 'concepts': ['term']}, p)
    study = {'title': 'Title', 'source_version': 'v', 'scope': 'full', 'paragraphs': [p], 'analyses': {'paragraph': analysis}, 'unreadable_pages': []}
    document = render_study(study, [{'id': 'note-1', 'content': 'My original words', 'anchor': {'source_version': 'v', 'page_index': 0, 'quote': '<actual>'}}])
    assert '<script>bad</script>' not in document and '&lt;script&gt;bad&lt;/script&gt;' in document
    assert 'data-note-id="note-1"' in document and '#p-paragraph' in document
    assert 'src="https://' not in document and 'url(https://' not in document and 'My original words' in document


def test_partial_generation_resumes_without_repeating_saved_content(tmp_path):
    async def scenario():
        store = WorkspaceStore(tmp_path)
        jobs = Jobs(store)
        calls = []
        class Account:
            async def text(self, prompt, *args, **kwargs):
                calls.append(prompt)
                if len(calls) == 2:
                    raise ValueError('interrupted')
                if '候选核心主张' in args[0]:
                    return '{"claim":"candidate","strongest":{"paragraph_id":"a","quote":"first","reason":"evidence"},"weakest":{"paragraph_id":"b","quote":"second","reason":"check"}}'
                return '{"translation":"译文"}'
        w = SimpleNamespace(store=store, jobs=jobs, account=Account())
        service = PaperStudy(w)
        service.current = lambda *args: None
        row = store.create('study', {'paper_id': 'p', 'source_version': 'v', 'paragraphs': [{'id': 'a', 'text': 'first'}, {'id': 'b', 'text': 'second'}], 'analyses': {}, 'errors': {}})
        job = service.generate(row['id'], {})
        await jobs.tasks[job['id']]
        assert store.get('job', job['id'])['state'] == 'failed'
        assert list(store.get('study', row['id'])['analyses']) == ['a']
        retry = service.generate(row['id'], {})
        await jobs.tasks[retry['id']]
        assert store.get('job', retry['id'])['state'] == 'completed'
        assert len(calls) == 4 and 'second' in calls[2]
        await jobs.close()
    asyncio.run(scenario())


def test_long_study_summary_keeps_tail_and_resumes_saved_blocks(tmp_path):
    async def scenario():
        import json
        store = WorkspaceStore(tmp_path)
        jobs = Jobs(store)
        analyses = {str(i): validate_analysis({'translation': '译文'}, {'text': f'source {i}'}) for i in range(43)}
        row = store.create('study', {'paper_id': 'p', 'source_version': 'v', 'paragraphs': [{'id': str(i), 'text': f'source {i}'} for i in range(43)], 'analyses': analyses, 'errors': {}})
        class Account:
            calls = []
            failed = False
            async def text(self, prompt, *args, **kwargs):
                source = json.loads(prompt); self.calls.append(source)
                if 'analysis' in source[0]:
                    if source[0]['id'] == '40' and not self.failed:
                        self.failed = True; raise ValueError('transient failure')
                    first, last = source[0], source[-1]
                    strong = {'paragraph_id': first['id'], 'quote': first['text'], 'reason': 'candidate'}
                    weak = {'paragraph_id': last['id'], 'quote': last['text'], 'reason': 'check'}
                else:
                    strong, weak = source[0]['strongest'], source[-1]['weakest']
                return json.dumps({'claim': 'candidate', 'strongest': strong, 'weakest': weak})
        account = Account()
        service = PaperStudy(SimpleNamespace(store=store, jobs=jobs, account=account))
        service.current = lambda *args: None
        first = service.generate(row['id'], {}); await jobs.tasks[first['id']]
        assert len(store.get('study', row['id'])['summary_blocks']) == 1
        retry = service.generate(row['id'], {}); await jobs.tasks[retry['id']]
        final = store.get('study', row['id'])
        assert final['summary_paragraphs'] == 43
        assert final['summary']['weakest']['paragraph_id'] == '42'
        assert sum('analysis' in c[0] and c[0]['id'] == '0' for c in account.calls) == 1
        assert final['state'] == 'ready'
        await jobs.close()
    asyncio.run(scenario())
