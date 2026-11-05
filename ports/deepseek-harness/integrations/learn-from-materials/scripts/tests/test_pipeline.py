import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from workflow_io import read_json, json_text, write_changed
from unit_records import Sources, compile_unit, assemble
from pipeline import validate_unit, checkpoint, preflight
from pipeline_state import begin, end, report, inspect_state, finish, code_fingerprint
from content_review import fingerprints, validate_file
from delivery import check_canonical
from finalize import finalize
from authoring_fixture import fixture


class AuthoringTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kb, self.project, self.records, self.original = fixture(self.root, SCRIPTS.parent)

    def test_round_trip_preserves_every_visible_string_and_source(self):
        target = self.root / 'page.json'
        result = assemble(self.project, self.kb, target)
        actual = read_json(target)
        for before, after in zip(self.original['contentUnits'], actual['contentUnits']):
            self.assertEqual(before, {k: v for k, v in after.items() if k != 'sourceDetails'})
            self.assertTrue(after['sourceDetails']['core'])
        for key in ('frameworks', 'glossary', 'decisionRules', 'assessment', 'relationships'):
            self.assertEqual(self.original[key], actual[key])
        self.assertEqual(result['status'], 'assembled-not-published')
        self.assertFalse(read_json(self.kb / 'summary-ledger.json')['finalCheck']['secondPassCompleted'])
        self.assertEqual(read_json(self.kb / 'action-rule-ledger.json')['units'][0]['status'], 'pending')
        self.assertTrue(any('stale' in x for x in validate_file(self.kb / 'content-review.json', actual, self.kb)))

    def test_source_reviewed_synthetic_fixture_can_complete_new_delivery(self):
        # Integration fixture only: reuse its existing reviewed source claims;
        # production assembly never creates these semantic acknowledgements.
        original_action = read_json(SCRIPTS.parent / 'examples/systematic-demo.learnkb/action-rule-ledger.json')
        for path in self.records:
            record = read_json(path)
            record['ruleReview'] = next(x for x in original_action['units'] if x['unitId'] == record['unit']['id'])
            write_changed(path, json_text(record))
        project = read_json(self.project)
        project['coverage']['finalCheck'] = read_json(SCRIPTS.parent / 'examples/systematic-demo.learnkb/coverage-audit.json')['finalCheck']
        project['summaryCheck'] = read_json(SCRIPTS.parent / 'examples/systematic-demo.learnkb/summary-ledger.json')['finalCheck']
        write_changed(self.project, json_text(project))
        target = self.root / 'page.json'; assemble(self.project, self.kb, target)
        review = read_json(self.kb / 'content-review.json')
        review['reviewedInputs'] = fingerprints(read_json(target), self.kb)
        write_changed(self.kb / 'content-review.json', json_text(review))
        result = finalize(target, self.kb, self.root / 'delivery', 'new-authoring', compatibility='1.03')
        self.assertEqual(Path(result['methodologyExport']).read_bytes(), Path(result['methodology']).read_bytes())
        self.assertEqual(read_json(result['manifest'])['skillVersion'], '1.1.0')

    def test_insertion_keeps_stable_content_ids_and_rebuilds_numeric_refs(self):
        record = read_json(self.records[0]); old_id = record['unit']['takeaways'][0]['id']
        record['unit']['takeaways'].insert(0, {'id': 'display-inserted', 'text': record['unit']['takeaways'][0]['text']})
        original = next(c for c in record['claims'] if old_id in c['contentIds'])
        original['contentIds'].append('display-inserted')
        result = compile_unit(record, Sources(self.kb))
        compiled = next(c for c in result['claims'] if c['id'] == original['id'])
        self.assertIn('unit:u01:takeaway:1', compiled['summaryRefs'])
        self.assertIn('unit:u01:takeaway:0', compiled['summaryRefs'])

    def test_bad_quote_unknown_display_and_unmapped_blocks_fail(self):
        for mutation in ('quote', 'display', 'unmapped'):
            with self.subTest(mutation=mutation):
                record = read_json(self.records[0])
                if mutation == 'quote': record['claims'][0]['evidence'][0]['quote'] = 'NEVER WRITTEN IN THE ORIGINAL'
                if mutation == 'display': record['claims'][0]['contentIds'] = ['invented-display']
                if mutation == 'unmapped': record['claims'] = []
                with self.assertRaises(ValueError): compile_unit(record, Sources(self.kb))

    def test_repeat_assembly_does_not_rewrite_unchanged_files(self):
        target = self.root / 'page.json'; assemble(self.project, self.kb, target)
        before = {p: p.stat().st_mtime_ns for p in [target, self.kb / 'units/u01.md', self.kb / 'summary-ledger.json']}
        result = assemble(self.project, self.kb, target)
        self.assertEqual(result['changedFiles'], [])
        self.assertEqual(before, {p: p.stat().st_mtime_ns for p in before})

    def test_unit_prose_is_canonical_and_covered_by_review_fingerprint(self):
        target = self.root / 'page.json'; assemble(self.project, self.kb, target)
        page = read_json(target); before = fingerprints(page, self.kb)
        record_path = self.kb / 'unit-records/u01.json'; record = read_json(record_path)
        record['sections']['workedExamples'][0] += ' Changed.'; write_changed(record_path, json_text(record))
        self.assertNotEqual(before, fingerprints(page, self.kb))
        self.assertIn('Changed.', check_canonical(page, self.kb)['units/u01.md'])
        record['unit']['core']['text'] += ' Changed.'; write_changed(record_path, json_text(record))
        with self.assertRaisesRegex(ValueError, 'snapshot'): check_canonical(page, self.kb)

    def test_missing_global_source_disposition_is_not_silently_completed(self):
        project = read_json(self.project); project['unitFiles'].pop(); write_changed(self.project, json_text(project))
        with self.assertRaisesRegex(ValueError, 'Every source block'): assemble(self.project, self.kb, self.root / 'page.json')
        self.assertFalse((self.root / 'page.json').exists())

    def test_failed_author_can_recover_valid_draft_without_review_attestation(self):
        inputs = [self.kb / 'source_map.json', self.kb / 'full_text.txt']
        begin(self.root, 'author', inputs, 'u01')
        end(self.root, 'author', unit_id='u01', status='failed', error='simulated interrupted generation')
        result = checkpoint(self.records[0], self.kb, self.root)
        self.assertEqual(result['status'], 'draft-valid')
        self.assertEqual(result['checkpoint']['status'], 'draft-ready')
        self.assertTrue(report(self.root)['stages'][0]['reusable'])
        self.assertIn('not-attested', result['semanticReview'])


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root / 'input.txt'; self.artifact = self.root / 'output.txt'
        self.source.write_text('source', encoding='utf-8'); self.artifact.write_text('output', encoding='utf-8')

    def test_modified_source_and_output_are_not_reusable(self):
        begin(self.root, 'render', [self.source]); end(self.root, 'render', [self.artifact])
        self.assertTrue(report(self.root)['stages'][0]['reusable'])
        self.artifact.write_text('changed', encoding='utf-8')
        self.assertFalse(report(self.root)['stages'][0]['reusable'])
        self.source.unlink()
        self.assertIn('missing-input', report(self.root)['stages'][0]['reasons'])

    def test_template_change_invalidates_render_but_not_author(self):
        (self.root / 'templates').mkdir(); (self.root / 'scripts').mkdir(); (self.root / 'references').mkdir()
        (self.root / 'SKILL.md').write_text('stable content contract', encoding='utf-8')
        template = self.root / 'templates/map.js'; template.write_text('version one', encoding='utf-8')
        with patch('pipeline_state.ROOT', self.root):
            author, render = code_fingerprint('author'), code_fingerprint('render')
            template.write_text('version two', encoding='utf-8')
            self.assertEqual(author, code_fingerprint('author')); self.assertNotEqual(render, code_fingerprint('render'))

    def test_finish_preserves_total_wall_boundary_and_rejects_active_stage(self):
        begin(self.root, 'render', [self.source])
        with self.assertRaisesRegex(ValueError, 'running'): finish(self.root)
        end(self.root, 'render', [self.artifact]); result = finish(self.root)
        self.assertTrue(result['finishedAt']); self.assertGreaterEqual(result['wallSeconds'], 0)
        with self.assertRaisesRegex(ValueError, 'finished'): begin(self.root, 'verify', [self.source])

    def test_reuse_skips_command_only_when_all_inputs_and_outputs_match(self):
        counter = self.root / 'counter.txt'
        code = 'from pathlib import Path; p=Path(r"' + str(counter) + '"); p.write_text(str(int(p.read_text())+1) if p.exists() else "1")'
        command = [sys.executable, str(SCRIPTS / 'pipeline.py'), 'run', '--work-dir', str(self.root), '--stage', 'render', '--input', str(self.source), '--artifact', str(counter), '--reuse', '--', sys.executable, '-c', code]
        for _ in range(2):
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(counter.read_text(), '1')
        self.source.write_text('new source', encoding='utf-8')
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr); self.assertEqual(counter.read_text(), '2')

    def test_failed_command_keeps_surviving_files_and_reports_failed(self):
        command = [sys.executable, str(SCRIPTS / 'pipeline.py'), 'run', '--work-dir', str(self.root), '--stage', 'assemble', '--input', str(self.source), '--artifact', str(self.artifact), '--', sys.executable, '-c', 'raise SystemExit(7)']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2); self.assertTrue(self.artifact.is_file())
        self.assertEqual(report(self.root)['stages'][0]['status'], 'failed')
        self.assertFalse(report(self.root)['stages'][0]['reusable'])

    def test_preflight_does_not_install_or_require_optional_packages(self):
        result = preflight([self.source]); self.assertEqual(result['status'], 'passed')
        self.assertEqual(result['skill']['version'], '1.1.0')


if __name__ == '__main__':
    unittest.main()
