"""Observable sequential entry, historical review compatibility and removal gates."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from content_review import validate
from benchmark_pipeline import run_once
from pipeline import preflight
from relation_ledger import review_snapshot
from test_unit_structure_review import v3_fixture
from unit_records import assemble
from unit_review import global_snapshot
from verify_release import verify
from workflow_io import read_json, write_changed, json_text


class SequentialReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_direct_extraction_needs_no_execution_choice_file(self):
        source = self.root / 'source.txt'
        source.write_text('1. Scope\nRecord an observable success criterion.', encoding='utf-8')
        output = self.root / 'kb'
        result = subprocess.run([sys.executable, str(SCRIPTS/'extract.py'), str(source), '--output-dir', str(output), '--ocr', 'off'], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        blocks = read_json(output/'source_map.json')
        self.assertTrue(blocks and all(x.get('source_id') and x.get('content_sha256') for x in blocks))
        self.assertIn('observable success', (output/'full_text.txt').read_text(encoding='utf-8'))
        self.assertFalse((self.root/'execution-choice.json').exists())
        self.assertEqual(preflight([source])['status'], 'passed')
        self.assertNotIn('workload', preflight([source]))

    def test_removed_argument_has_actionable_error_before_output(self):
        source = self.root/'source.txt';source.write_text('Example', encoding='utf-8')
        output = self.root/'out'
        result = subprocess.run([sys.executable,str(SCRIPTS/'extract.py'),str(source),'--output-dir',str(output),'--execution-choice','old.json'],capture_output=True,text=True)
        self.assertEqual(result.returncode,2)
        self.assertIn('removed in 1.1.0', result.stderr)
        self.assertFalse(output.exists())

    def test_new_relation_assembly_rejects_parallel_without_overwriting_page(self):
        kb, project_path, page_path, *_ = v3_fixture(self.root, SCRIPTS.parent)
        before = page_path.read_bytes()
        project = read_json(project_path)
        project['relations']['executionMode'] = 'parallel'
        write_changed(project_path,json_text(project))
        with self.assertRaisesRegex(ValueError,'sequential execution'):
            assemble(project_path,kb,page_path)
        self.assertEqual(page_path.read_bytes(), before)

    def test_historical_parallel_review_is_validated_without_rewriting_identity(self):
        kb, _, _, page, reviews, global_review, structures, complete = v3_fixture(self.root,SCRIPTS.parent)
        ledger = read_json(kb/'relation-ledger.json');ledger['executionMode']='parallel'
        write_changed(kb/'relation-ledger.json',json_text(ledger))
        complete = copy.deepcopy(complete);complete['executionMode']='parallel'
        for row in complete['unitReviews']:
            row['executionMode']='parallel'
        for row in complete['structureReviews']:
            row['executionMode']='parallel';row['reviewedInputs']=review_snapshot(page,kb)
        complete['globalReview']['reviewedInputs']=global_snapshot(page,kb,complete['unitReviews'])
        self.assertEqual(validate(complete,page,kb),[])
        invalid=copy.deepcopy(complete)
        invalid['structureReviews'][0]['reviewerId']=ledger['integratorId']
        self.assertTrue(validate(invalid,page,kb))
        self.assertEqual(read_json(kb/'relation-ledger.json')['executionMode'],'parallel')

    def test_release_is_self_consistent(self):
        result = verify(SCRIPTS.parent)
        self.assertEqual(result['errors'],[])

    def test_benchmark_captures_unicode_diagnostics_under_windows_code_page(self):
        extractor = self.root/'diagnostic.py'
        extractor.write_text("import sys\nprint('中文诊断', file=sys.stderr)\n",encoding='utf-8')
        with patch.dict(os.environ, {'PYTHONIOENCODING':'cp936'}):
            result = run_once(extractor, [], self.root/'output', no_cache=False)
        self.assertEqual(result['returnCode'],0)
        self.assertIn('中文诊断',result['stderrTail'])


if __name__=='__main__':
    unittest.main()
