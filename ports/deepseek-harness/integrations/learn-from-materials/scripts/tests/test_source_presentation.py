"""Citation display tests. These do not attest a real browser render."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from source_presentation import (SOURCE_LABELS, canonical_sources, display_source,
                                 framework_condition, original_disclosure,
                                 rule_condition, validate_labels)
from render_page import render
from verify_static import verify
from verify_coverage import collect_sources

RAW = 'book.pdf · 第1章《冒险家》 · 原书第009页 · PDF第017页'
DISPLAY = 'book.pdf · Chapter 1 “Adventurer” · Printed p. 009 · PDF p. 017'


class SourcePresentationTests(unittest.TestCase):
    def page(self, **changes):
        data = {'meta': {'language': 'en'}, 'source': RAW,
                'sourceLabels': {RAW: DISPLAY}}
        data.update(changes)
        return data

    def errors(self, data, complete=True):
        errors = []
        validate_labels(data, errors, require_complete=complete)
        return errors

    def test_exact_reviewed_label_is_valid_and_nonmutating(self):
        data = self.page()
        before = copy.deepcopy(data)
        self.assertEqual(self.errors(data), [])
        self.assertEqual(data, before)

    def test_unknown_nonstring_or_empty_label_rejected(self):
        for labels in ({'not a citation': DISPLAY}, {42: DISPLAY}, {RAW: ''}, {RAW: None}, []):
            with self.subTest(labels=labels):
                self.assertTrue(self.errors(self.page(sourceLabels=labels)))

    def test_changed_page_chapter_and_filename_rejected(self):
        for label in (DISPLAY.replace('017', '018'), DISPLAY.replace('Chapter 1', 'Chapter 2'),
                      DISPLAY.replace('book.pdf', 'other.pdf')):
            with self.subTest(label=label):
                self.assertTrue(self.errors(self.page(sourceLabels={RAW: label})))

    def test_swapped_printed_and_pdf_pages_rejected(self):
        label = 'book.pdf · Chapter 1 “Adventurer” · Printed p. 017 · PDF p. 009'
        self.assertTrue(any('assignments' in x for x in self.errors(self.page(sourceLabels={RAW: label}))))

    def test_missing_or_untranslated_title_rejected_for_new_english_delivery(self):
        self.assertTrue(self.errors(self.page(sourceLabels={})))
        self.assertTrue(self.errors(self.page(sourceLabels={RAW: DISPLAY.replace('Adventurer', '冒险家')})))
        self.assertEqual(self.errors(self.page(sourceLabels={}), complete=False), [])

    def test_chinese_page_does_not_require_english_labels(self):
        self.assertEqual(self.errors(self.page(meta={'language': 'zh-CN'}, sourceLabels={})), [])

    def test_filename_and_numeric_locator_only_need_no_title_translation(self):
        data = {'meta': {'language': 'en'}, 'source': '材料.pdf · PDF第17页'}
        self.assertEqual(self.errors(data), [])
        self.assertEqual(display_source(data['source'], 'en'), '材料.pdf · PDF pp. 17')

    def test_chinese_filename_with_spaces_and_middle_dot_is_retained(self):
        raw = '埃隆·马斯克 传.pdf · 第1章《冒险家》 · PDF第17页'
        label = '埃隆·马斯克 传.pdf · Chapter 1 “Adventurer” · PDF p. 17'
        self.assertEqual(self.errors(self.page(source=raw, sourceLabels={raw:label})), [])
        self.assertTrue(self.errors(self.page(source=raw, sourceLabels={raw:label.replace('埃隆·马斯克 传.pdf','Biography.pdf')})))
        self.assertEqual(self.errors({'meta':{'language':'en'},'source':'埃隆·马斯克 传.pdf · PDF第17页'}), [])

    def test_display_labels_are_not_new_evidence(self):
        data = self.page()
        self.assertEqual(canonical_sources(data), {RAW})
        self.assertEqual(collect_sources(data), [RAW])
        self.assertEqual(collect_sources({'sourceLabels': {'source': 'fake evidence'}}), [])

    def test_display_and_original_disclosure_keep_chinese_original(self):
        token = SOURCE_LABELS.set({RAW: DISPLAY})
        try:
            self.assertEqual(display_source(RAW, 'en'), DISPLAY)
            self.assertEqual(display_source(RAW, 'zh-CN'), RAW)
            self.assertIn(RAW, original_disclosure(RAW, 'en'))
            self.assertEqual(original_disclosure(RAW, 'zh-CN'), '')
        finally:
            SOURCE_LABELS.reset(token)

    def test_label_markup_is_escaped(self):
        token = SOURCE_LABELS.set({'<script>': 'English label'})
        try:
            html = original_disclosure('<script>', 'en')
            self.assertIn('<p>&lt;script&gt;</p>', html)
            self.assertNotIn('<script>', html)
        finally:
            SOURCE_LABELS.reset(token)

    def test_framework_prefix_is_idempotent(self):
        for value in ('When reading', 'When When reading', 'Applies when: When reading'):
            self.assertEqual(framework_condition(value, 'en'), 'Applies when: reading')
        self.assertEqual(framework_condition('适用：适用：阅读时', 'zh-CN'), '适用：阅读时')

    def test_rule_prefix_is_idempotent_and_keeps_time_phrases(self):
        self.assertEqual(rule_condition('When When ready', 'en'), 'When ready')
        self.assertEqual(rule_condition('当 当 图表显示上涨时', 'zh-CN'), '当 图表显示上涨时')
        for value in ('Whenever ready', 'Before launch', 'After review', 'If supported', 'In production'):
            self.assertEqual(rule_condition(value, 'en'), value)
        for value in ('当前信息不足时', '当地供给不足时', '在信息不足时', '如果信息不足'):
            self.assertEqual(rule_condition(value, 'zh-CN'), value)

    def test_roundtrip_localizes_ui_but_keeps_ids_quotes_and_raw_sources(self):
        data = json.loads((ROOT / 'examples/overview-methods-content.json').read_text(encoding='utf-8'))
        original = copy.deepcopy(data)
        labels = {}

        def translate_sources(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    if key in {'source', 'locator'} and isinstance(value, str):
                        raw = value + ' · 测试标题'
                        labels[raw] = value + ' · Test heading'
                        node[key] = raw
                    else:
                        translate_sources(value)
            elif isinstance(node, list):
                for item in node:
                    translate_sources(item)

        translate_sources(data)
        data['sourceLabels'] = labels
        first = next(iter(labels))
        labels[first] = '<img src=x> ' + labels[first]
        before = copy.deepcopy(data)
        with tempfile.TemporaryDirectory() as temporary:
            html = Path(temporary) / 'page.html'
            md = Path(temporary) / 'page.md'
            render(data, html, md)
            errors, _, embedded = verify(html)
            self.assertEqual(errors, [])
            self.assertEqual(embedded, before)
            self.assertEqual(data, before)
            self.assertEqual(embedded['meta']['pageId'], original['meta']['pageId'])
            self.assertEqual([x['id'] for x in embedded['methodology']['nodes']],
                             [x['id'] for x in original['methodology']['nodes']])
            for x, y in zip(embedded['methodology']['nodes'], original['methodology']['nodes']):
                self.assertEqual([s['quote'] for s in x['sources']], [s['quote'] for s in y['sources']])
            text = html.read_text(encoding='utf-8')
            self.assertIn('source-original', text)
            self.assertIn('source-label-index', text)
            self.assertIn('&lt;img src=x&gt;', text)
            self.assertNotIn('<img src=x>', text)
            self.assertIn('Original source labels', md.read_text(encoding='utf-8'))
            for raw, label in labels.items():
                from html import escape
                self.assertIn(escape(label), text)
                self.assertIn(raw, md.read_text(encoding='utf-8'))

    def test_final_layout_layer_has_content_sized_tabs_and_fixed_badges(self):
        css = (ROOT / 'templates/reader-layout.css').read_text(encoding='utf-8')
        self.assertIn('width:max-content', css)
        self.assertIn('flex:0 0 26px', css)
        self.assertIn('height:auto;max-height:none', css)
        self.assertIn('overflow-wrap:anywhere', css)
        self.assertIn('.source-target,.chapter-conclusion,.ch-view', css)


if __name__ == '__main__':
    unittest.main()
