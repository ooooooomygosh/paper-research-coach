import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from finalize import finalize
from methodology import validate, markdown, edge_label
from methodology_ui import overview_markup
from render_page import render
from verify_static import verify as verify_static


class BilingualMethodologyTests(unittest.TestCase):
    def setUp(self):
        self.page = json.loads((ROOT / 'examples/overview-en-content.json').read_text(encoding='utf-8'))
        self.kb = ROOT / 'examples/methods-demo.learnkb'

    def pages(self):
        yield self.page
        zh = json.loads((ROOT / 'scripts/tests/fixtures/methodology-zh.json').read_text(encoding='utf-8'))
        yield zh

    def test_both_models_keep_original_evidence_and_valid_references(self):
        originals = self.page['methodology']
        for page in self.pages():
            with self.subTest(language=page['meta']['language']):
                model = page['methodology']
                validate(model, page, self.kb)
                self.assertEqual([n['id'] for n in model['nodes']], [n['id'] for n in originals['nodes']])
                self.assertEqual([n['sources'] for n in model['nodes']], [n['sources'] for n in originals['nodes']])
                self.assertEqual([(e['id'], e['from'], e['to'], e['kind'], e['source']) for e in model['edges']],
                                 [(e['id'], e['from'], e['to'], e['kind'], e['source']) for e in originals['edges']])

    def test_bilingual_render_roundtrip_retains_graph_content(self):
        for page in self.pages():
            before = copy.deepcopy(page)
            with self.subTest(language=page['meta']['language']), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / 'page.html'
                render(page, output, Path(temporary) / 'page.md')
                errors, _, embedded = verify_static(output)
                self.assertEqual(errors, [])
                self.assertEqual(embedded['methodology'], page['methodology'])
                self.assertEqual(embedded['meta']['pageId'], page['meta']['pageId'])
                self.assertEqual(page, before)
                for node in page['methodology']['nodes']:
                    for key in ('input', 'action', 'output', 'check'):
                        self.assertIn(node[key], markdown(page['methodology']))

    def test_markdown_and_fallback_use_same_localized_relations(self):
        for page in self.pages():
            model = page['methodology']
            with self.subTest(language=model['language']):
                text, fallback = markdown(model), overview_markup(page)
                for edge in model['edges']:
                    label = edge_label(edge, model['language'])
                    self.assertIn(label, text)
                    self.assertIn(label, fallback)
                    self.assertIn(edge['source'], text)
                self.assertIn('Only when conditions are met' if model['language'] == 'en' else '满足条件才做', text)
                self.assertIn('Input: ' if model['language'] == 'en' else '输入：', text)
                self.assertNotIn('(branch;', text)

    def test_english_complete_delivery_uses_v1_metadata_and_preserves_source(self):
        before = {p.relative_to(self.kb): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.kb.rglob('*') if p.is_file()}
        with tempfile.TemporaryDirectory() as temporary:
            result = finalize(ROOT / 'examples/overview-en-content.json', self.kb, Path(temporary) / 'out', 'english', compatibility='1.03')
            manifest = json.loads(Path(result['manifest']).read_text(encoding='utf-8'))
            self.assertEqual(manifest['skillVersion'], '1.1.0')
            self.assertEqual(manifest['skillRevision'], 'release')
            self.assertEqual(manifest['visualReview'], 'not-run')
            with zipfile.ZipFile(result['archive']) as archive:
                self.assertIsNone(archive.testzip())
                page = json.loads(archive.read('english.page.json'))
                self.assertEqual(page['meta']['language'], 'en')
                self.assertEqual(page['meta']['pageId'], self.page['meta']['pageId'])
                self.assertEqual(page['methodology'], self.page['methodology'])
                self.assertIn('Only when conditions are met', archive.read('english.learnkb/methodology.md').decode('utf-8'))
        after = {p.relative_to(self.kb): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.kb.rglob('*') if p.is_file()}
        self.assertEqual(after, before)


if __name__ == '__main__':
    unittest.main()
