"""Publication-contract regressions using explicitly synthetic reviewed data."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from finalize import finalize
from test_unit_structure_review import v3_fixture
from workflow_io import read_json, json_text, write_changed


class StructurePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.kb, self.project, self.page_path, self.page, self.units, self.global_review, self.structures, self.complete = v3_fixture(self.root, SCRIPTS.parent)

    def test_new_default_delivers_the_inventory_and_both_recorded_reviews(self):
        result = finalize(self.page_path, self.kb, self.root / 'out', 'new-contract')
        manifest = read_json(result['manifest'])
        self.assertEqual(manifest['relationReviewContract'], '1.04')
        self.assertEqual(manifest['semanticReview'], 'recorded-not-machine-proven')
        self.assertEqual(manifest['visualReview'], 'not-run')
        self.assertIn('relation-candidates', manifest['checks'])
        with zipfile.ZipFile(result['archive']) as archive:
            ledger = json.loads(archive.read('new-contract.learnkb/relation-ledger.json'))
            review = json.loads(archive.read('new-contract.learnkb/content-review.json'))
            self.assertEqual(ledger['pageId'], self.page['meta']['pageId'])
            self.assertEqual({r['role'] for r in review['structureReviews']}, {'correctness', 'omissions'})
            for item in manifest['files']:
                self.assertEqual(hashlib.sha256(archive.read(item['path'])).hexdigest(), item['sha256'])

    def test_modern_artifacts_cannot_downgrade_through_either_old_flag(self):
        for kwargs in ({'compatibility': '1.03'}, {'legacy_rule_ledger': True}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, 'cannot fall back'):
                finalize(self.page_path, self.kb, self.root / 'out', 'blocked', **kwargs)
        self.assertFalse((self.root / 'out').exists())

    def test_removed_structure_review_and_changed_decision_cannot_publish(self):
        review = copy.deepcopy(self.complete)
        review['structureReviews'] = review['structureReviews'][:1]
        write_changed(self.kb / 'content-review.json', json_text(review))
        with self.assertRaisesRegex(ValueError, 'correctness and omissions'):
            finalize(self.page_path, self.kb, self.root / 'out', 'missing-review')
        write_changed(self.kb / 'content-review.json', json_text(self.complete))
        ledger = read_json(self.kb / 'relation-ledger.json')
        ledger['decisions'][0]['reason'] += ' Changed disposition rationale.'
        write_changed(self.kb / 'relation-ledger.json', json_text(ledger))
        with self.assertRaisesRegex(ValueError, 'stale'):
            finalize(self.page_path, self.kb, self.root / 'out', 'changed-decision')

    def test_old_complete_results_need_an_explicit_compatibility_contract(self):
        # The fully reviewed 1.03 demo supplies all existing publication gates.
        old_kb = SCRIPTS.parent / 'examples/systematic-demo.learnkb'
        old_page = SCRIPTS.parent / 'examples/overview-systematic-demo.json'
        with self.assertRaises((ValueError, FileNotFoundError)):
            finalize(old_page, old_kb, self.root / 'strict', 'old-default')
        result = finalize(old_page, old_kb, self.root / 'compat', 'old-explicit', compatibility='1.03')
        manifest = read_json(result['manifest'])
        self.assertEqual(manifest['relationReviewContract'], '1.03-compatibility-not-upgraded')
        self.assertNotIn('structure-reviews', manifest['checks'])
        self.assertIn('content-review', manifest['checks'])


if __name__ == '__main__':
    unittest.main()
