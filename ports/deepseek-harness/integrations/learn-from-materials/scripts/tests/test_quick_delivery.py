"""Exercise the documented quick CLI workflow without legacy bypasses.

Inputs are synthetic teaching/observation texts. These tests establish runtime
contracts and provenance preservation, not independent semantic or visual QA.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from verify_static import verify as verify_static


class QuickDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='lfm-quick-delivery-')
        self.work = Path(self.temporary.name).resolve()

    def tearDown(self):
        self.temporary.cleanup()

    def cli(self, script, *arguments, expected=0):
        env = dict(os.environ, PYTHONUTF8='1', PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / script), *map(str, arguments)],
            cwd=self.work, env=env, capture_output=True, text=True,
            encoding='utf-8', timeout=60,
        )
        self.assertEqual(result.returncode, expected, result.stdout + '\n' + result.stderr)
        return result

    def write_json(self, path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    @staticmethod
    def set_source_ids(value, by_filename):
        if isinstance(value, dict):
            if 'sourceIds' in value:
                # The ready-model fixture uses one English original document.
                value['sourceIds'] = list(by_filename['methods-demo.txt'])
            for child in value.values():
                QuickDeliveryTests.set_source_ids(child, by_filename)
        elif isinstance(value, list):
            for child in value:
                QuickDeliveryTests.set_source_ids(child, by_filename)

    def fixture(self, language, *, descriptive=False, unreadable=False):
        en = language == 'en'
        directory = self.work / (language + ('-description' if descriptive else '-methods') + ('-unreadable' if unreadable else ''))
        directory.mkdir()
        kb = directory / 'input.learnkb'
        material = directory / 'materials'
        material.mkdir()
        page_path = ROOT / ('examples/overview-en-content.json' if en else 'scripts/tests/fixtures/methodology-zh.json')
        page = json.loads(page_path.read_text(encoding='utf-8'))
        model = page.pop('methodology')
        page.pop('methodLibrary', None)
        page['meta']['knowledgeBase'] = 'input.learnkb/INDEX.md'
        original_kb = ROOT / 'examples/methods-demo.learnkb'
        original_map = json.loads((original_kb / 'source_map.json').read_text(encoding='utf-8'))
        original_text = (original_kb / 'full_text.txt').read_text(encoding='utf-8')
        block = original_map[0]
        raw = original_text[block['start_char']:block['end_char']]
        if descriptive:
            raw = 'Field note: one observation.\nThe marker was observed once.\nNo repetition or explanation was recorded.\n'
        (material / 'methods-demo.txt').write_text(raw, encoding='utf-8')
        if unreadable:
            (material / 'image-note.txt').write_text('[Synthetic appendix: unreadable image evidence.]\n', encoding='utf-8')
        self.cli('extract.py', material, '--mode', 'text', '--ocr', 'off', '--output-dir', kb)
        blocks = json.loads((kb / 'source_map.json').read_text(encoding='utf-8'))
        by_filename = {}
        for item in blocks:
            by_filename.setdefault(Path(item['source_file']).name, []).append(item['source_id'])
        self.assertIn('methods-demo.txt', by_filename)
        self.set_source_ids(model, by_filename)

        # Save one defensible core card in each language: quick mode does not
        # need to turn every displayed concept into a reusable method card.
        library = json.loads((original_kb / 'methods.json').read_text(encoding='utf-8'))
        library['methods'] = [library['methods'][0]]
        self.set_source_ids(library, by_filename)
        if not en:
            card = library['methods'][0]
            visible = page['frameworks'][0]
            library.update(language='zh-CN', title='问题地图：核心方法卡', note='合成教学材料的核心方法。未规定的阈值保持未规定；工具不保证成功。')
            card.update(
                name=visible['name'], summary=visible['oneLine'], when=visible['when'],
                problem='问题范围不明确时，很难识别哪些信息相关。',
                prerequisites=['能够描述待解决的问题和可观察的目标。'],
                limitations=['原文没有规定通用成功保证或量化阈值。', '顺序和适用性取决于问题与现有证据。'],
                rationale='明确边界有助于判断哪些信息相关。',
                steps=[
                    {'action':'记录问题边界和相关方。', 'input':'待解决的问题。', 'output':'明确的范围与相关方清单。', 'check':'确认清单中的事项属于问题范围。'},
                    {'action':'记录约束和可观察的成功标准。', 'input':'已知约束与目标。', 'output':'约束与成功标准。', 'check':'确认成功标准可以观察。'},
                ],
                successChecks=['边界、相关方、约束和可观察的成功标准已明确。'],
                tags=['问题', '边界', '范围'],
            )
        audit = json.loads((original_kb / 'quick-audit.json').read_text(encoding='utf-8'))
        self.set_source_ids(audit, by_filename)
        audit['structure'][0].update(
            title='Method Lab core text' if en else '核心教学材料',
            note='The core teaching text and its limits were checked.' if en else '已核查核心教学正文与限制。',
        )
        audit['limitations'] = ['Core overview of a synthetic text; no claim of exhaustive research coverage.' if en else '合成材料的核心导读，不代表全量研究覆盖。']
        if unreadable:
            audit['structure'].append({
                'title':'Image appendix' if en else '图片附录',
                'sourceIds':by_filename['image-note.txt'], 'status':'unreadable',
                'note':'The image evidence was not available for review.' if en else '图片证据无法核验。',
            })
            audit['limitations'].append('Image appendix not reviewed.' if en else '图片附录未核验。')
        if descriptive:
            locator = 'methods-demo.txt · Lines 1-3'
            title = 'A single observation' if en else '一次观察记录'
            summary = 'The marker was observed once; repetition and explanation were not recorded.' if en else '标记被观察到一次，未记录重复观察或解释。'
            page['meta']['title'] = title
            page['hero'].update(eyebrow='FIELD NOTE' if en else '观察记录', title=title, lede=summary, thesis=summary)
            page['frameworks'] = [dict(page['frameworks'][0], name=title, oneLine=summary, when='Reading the observation record' if en else '阅读观察记录时', source=locator)]
            unit = page['contentUnits'][0]
            unit.update(title=title, core=summary, frameworks=[title], takeaways=[summary], source=locator)
            unit['conclusions'] = [{'title':title, 'summary':summary, 'points':[summary], 'source':locator}]
            page['contentUnits'] = [unit]
            term = page['glossary'][0]
            term.update(term='Observation' if en else '观察', definition='A recorded observation.' if en else '被记录的观察。', context=summary, related=['record' if en else '记录'], source=locator)
            page['glossary'] = [term]
            area = page['assessment']['focusAreas'][0]
            area.update(title='State the observation and its limits' if en else '说明观察及其限制', abilities=['Explain'] if en else ['解释'], source=locator)
            page['assessment']['focusAreas'] = [area]
            page['decisionRules'] = []
            page['relationships'] = []
            page['footer'] = 'Synthetic observation fixture.' if en else '合成观察记录测试材料。'
            library.update(status='none', methods=[], title=title,
                           note='The note states an observation and provides no reusable procedure.' if en else '材料只记录一次观察，没有可复用程序。')
            model.update(status='not-applicable', structure='none', title=title,
                         problem='One isolated observation provides no supported whole-material procedure.' if en else '孤立观察不足以支持整体程序。',
                         outcome='Retain the observation and its evidentiary limit.' if en else '保留观察与证据限制。',
                         note='No procedure or integrated mechanism is stated; none is invented.' if en else '原文没有给出程序或完整机制，不编造整体结构。',
                         nodes=[], edges=[], entryNodes=[], mainPath=[], constraints=[],
                         coverage=[{'unitId':unit['id'], 'nodeIds':[], 'role':'context', 'reason':'An isolated descriptive record.' if en else '孤立的描述性记录。'}])
            audit['structure'][0].update(title=title, note='The observation and missing repetition were checked.' if en else '已核查观察与缺少重复记录的限制。')
            audit['evidence'] = [{'source':locator, 'sourceIds':by_filename['methods-demo.txt'], 'quote':'The marker was observed once.', 'checked':True}]

        self.write_json(directory / 'page.json', page)
        self.write_json(kb / 'methods.json', library)
        self.write_json(kb / 'methodology.json', model)
        self.write_json(kb / 'quick-audit.json', audit)
        return {'directory':directory, 'kb':kb, 'page':page, 'library':library, 'model':model, 'audit':audit}

    def bind(self, fixture):
        directory, kb = fixture['directory'], fixture['kb']
        with_methods, ready = directory / 'page-with-methods.json', directory / 'page-ready.json'
        self.cli('methods.py', 'bind', '--library', kb / 'methods.json', '--page', directory / 'page.json', '--knowledge-base', kb, '--output', with_methods)
        self.cli('methodology.py', 'bind', '--model', kb / 'methodology.json', '--page', with_methods, '--knowledge-base', kb, '--output', ready)
        return ready

    def finalize(self, fixture, ready, *, expected=0):
        return self.cli('finalize.py', ready, '--knowledge-base', fixture['kb'], '--output-dir', fixture['directory'] / 'delivery', '--name', 'learning-quick', expected=expected)

    def assert_delivery(self, fixture, result):
        files = json.loads(result.stdout)
        page = json.loads(Path(files['page']).read_text(encoding='utf-8'))
        manifest = json.loads(Path(files['manifest']).read_text(encoding='utf-8'))
        self.assertEqual(manifest['skillVersion'], '1.1.0')
        self.assertEqual(manifest['status'], 'static-only')
        self.assertEqual(manifest['visualReview'], 'not-run')
        self.assertEqual(page['meta']['pageId'], fixture['page']['meta']['pageId'])
        self.assertEqual(page['meta']['language'], fixture['page']['meta']['language'])
        self.assertEqual(page['meta']['learningDepth'], 'quick')
        self.assertEqual(page['methodLibrary'], fixture['library'])
        self.assertEqual(page['methodology'], fixture['model'])
        self.assertEqual(verify_static(Path(files['html']))[0], [])
        with zipfile.ZipFile(files['archive']) as archive:
            self.assertIsNone(archive.testzip())
            for name in ('methods.json','patterns.md','methodology.json','methodology.md','INDEX.md','coverage-audit.md','quick-audit.json','full_text.txt','source_map.json'):
                self.assertIn('learning-quick.learnkb/' + name, archive.namelist())
            for entry in manifest['files']:
                content = archive.read(entry['path'])
                self.assertEqual(hashlib.sha256(content).hexdigest(), entry['sha256'])
                self.assertEqual(len(content), entry['bytes'])
            self.assertEqual(archive.read('learning-quick.learnkb/full_text.txt'), (fixture['kb'] / 'full_text.txt').read_bytes())
            for name in ('summary-ledger.json','coverage-audit.json','action-rule-ledger.json','content-review.json','question-bank.json'):
                self.assertNotIn('learning-quick.learnkb/' + name, archive.namelist())
            self.assertFalse(any('/.extraction-cache/' in name for name in archive.namelist()))
        return files

    def test_bilingual_extract_bind_prepare_and_formal_delivery(self):
        identities = []
        for language in ('zh-CN','en'):
            with self.subTest(language=language):
                fixture = self.fixture(language)
                ready = self.bind(fixture)
                prepared = self.cli('prepare_quick.py', ready, '--knowledge-base', fixture['kb'])
                coverage = (fixture['kb'] / 'coverage-audit.md').read_text(encoding='utf-8')
                index = (fixture['kb'] / 'INDEX.md').read_text(encoding='utf-8')
                if language == 'en':
                    self.assertIn('Quick overview validation and index generation complete', prepared.stdout)
                    self.assertIn('Scanned: ', coverage)
                    self.assertNotIn('：', coverage)
                    self.assertNotIn('快速导读', prepared.stdout)
                    self.assertIn('Focused overview, not exhaustive coverage.', index)
                else:
                    self.assertIn('快速导读校验与索引生成完成', prepared.stdout)
                    self.assertIn('已扫描：', coverage)
                    self.assertIn('核心导读，非全量知识整理。', index)
                before = {p.relative_to(fixture['kb']): hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture['kb'].rglob('*') if p.is_file()}
                self.assert_delivery(fixture, self.finalize(fixture, ready))
                after = {p.relative_to(fixture['kb']): hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture['kb'].rglob('*') if p.is_file()}
                self.assertEqual(before, after)
                self.assertEqual(fixture['model']['nodes'][0]['sources'][0]['quote'], 'When the scope is unclear, draw a problem map first')
                identities.append((fixture['page']['meta']['pageId'], [n['id'] for n in fixture['model']['nodes']], [e['id'] for e in fixture['model']['edges']]))
        self.assertEqual(identities[0], identities[1])

    def test_unreadable_status_is_localized_without_changing_audit_enums(self):
        for language in ('zh-CN','en'):
            with self.subTest(language=language):
                fixture = self.fixture(language, unreadable=True)
                ready = self.bind(fixture)
                self.cli('prepare_quick.py', ready, '--knowledge-base', fixture['kb'])
                coverage = (fixture['kb'] / 'coverage-audit.md').read_text(encoding='utf-8')
                self.assertIn('Unreadable: ' if language == 'en' else '无法读取：', coverage)
                self.assertEqual(json.loads((fixture['kb'] / 'quick-audit.json').read_text(encoding='utf-8'))['structure'][-1]['status'], 'unreadable')
                self.assert_delivery(fixture, self.finalize(fixture, ready))

    def test_descriptive_material_can_deliver_without_invented_methods(self):
        for language in ('zh-CN','en'):
            with self.subTest(language=language):
                fixture = self.fixture(language, descriptive=True)
                ready = self.bind(fixture)
                self.cli('prepare_quick.py', ready, '--knowledge-base', fixture['kb'])
                self.assert_delivery(fixture, self.finalize(fixture, ready))
                self.assertEqual(fixture['library']['methods'], [])
                self.assertEqual(fixture['model']['nodes'], [])
                self.assertEqual(fixture['model']['status'], 'not-applicable')

    def test_missing_canonical_files_stop_before_publication(self):
        for language, filename in (('en','methods.json'),('zh-CN','methodology.json')):
            with self.subTest(language=language, filename=filename):
                fixture = self.fixture(language)
                missing = fixture['kb'] / filename
                self.assertTrue(missing.resolve().is_relative_to(self.work))
                missing.unlink()
                result = self.finalize(fixture, fixture['directory'] / 'page.json', expected=2)
                self.assertIn(filename, result.stderr)
                self.assertFalse((fixture['directory'] / 'delivery').exists())

    def test_new_renderer_requires_canonical_binding_without_legacy(self):
        fixture = self.fixture('en')
        result = self.cli('render_page.py', fixture['directory'] / 'page.json', '--knowledge-base', fixture['kb'], '--output', fixture['directory'] / 'page.html', '--check-only', expected=2)
        self.assertIn('snapshot', result.stderr)
        self.assertFalse((fixture['directory'] / 'page.html').exists())
        ready = self.bind(fixture)
        self.cli('render_page.py', ready, '--knowledge-base', fixture['kb'], '--output', fixture['directory'] / 'page.html', '--check-only')

    def test_methodology_only_citation_cannot_be_omitted_from_audit(self):
        fixture = self.fixture('en')
        ready = self.bind(fixture)
        fixture['audit']['evidence'] = [e for e in fixture['audit']['evidence'] if e['source'] != 'methods-demo.txt · Lines 12']
        self.write_json(fixture['kb'] / 'quick-audit.json', fixture['audit'])
        self.cli('prepare_quick.py', ready, '--knowledge-base', fixture['kb'], expected=2)
        result = self.finalize(fixture, ready, expected=2)
        self.assertIn('Coverage validation failed', result.stderr)
        self.assertFalse((fixture['directory'] / 'delivery' / 'learning-quick.html').exists())

    def test_stale_original_text_stops_delivery(self):
        fixture = self.fixture('zh-CN')
        ready = self.bind(fixture)
        original = fixture['kb'] / 'full_text.txt'
        text = original.read_text(encoding='utf-8')
        original.write_text(text.replace('Before choosing an action', 'Before choosing any action', 1), encoding='utf-8')
        self.cli('prepare_quick.py', ready, '--knowledge-base', fixture['kb'], expected=2)
        result = self.finalize(fixture, ready, expected=2)
        self.assertIn('Source changed', result.stderr)
        self.assertFalse((fixture['directory'] / 'delivery').exists())

    def test_existing_delivery_is_preserved(self):
        fixture = self.fixture('en')
        ready = self.bind(fixture)
        self.cli('prepare_quick.py', ready, '--knowledge-base', fixture['kb'])
        output = fixture['directory'] / 'delivery'
        output.mkdir()
        existing = output / 'learning-quick.html'
        existing.write_text('Keep this prior delivery.', encoding='utf-8')
        result = self.finalize(fixture, ready, expected=2)
        self.assertIn('already exists', result.stderr)
        self.assertEqual(existing.read_text(encoding='utf-8'), 'Keep this prior delivery.')
        self.assertEqual(list(output.iterdir()), [existing])


if __name__ == '__main__':
    unittest.main()
