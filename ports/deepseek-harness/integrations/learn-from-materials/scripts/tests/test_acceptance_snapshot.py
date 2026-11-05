import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from acceptance_snapshot import freeze, check
from pipeline_state import begin, end, report


class AcceptanceSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.skill = self.root / 'skill'
        self.skill.mkdir()
        (self.skill / 'SKILL.md').write_text('A skill', encoding='utf-8')
        self.kb = self.root / 'kb'
        self.kb.mkdir()
        (self.kb / 'source.txt').write_text('original', encoding='utf-8')
        self.snapshot = self.root / 'work' / 'freeze.json'

    def freeze(self):
        return freeze([self.kb], self.snapshot, self.skill)

    def test_unchanged_inputs_pass_without_approving_meaning(self):
        self.assertEqual(self.freeze()['status'], 'frozen-not-reviewed')
        self.assertEqual(check(self.snapshot)['status'], 'passed')
        self.assertEqual(check(self.snapshot)['semanticReview'], 'not-attested-by-snapshot')

    def test_added_removed_changed_and_missing_inputs_fail(self):
        self.freeze()
        (self.kb / 'source.txt').write_text('changed', encoding='utf-8')
        (self.kb / 'added.txt').write_text('new', encoding='utf-8')
        result = check(self.snapshot)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual({x['status'] for x in result['differences']}, {'added', 'changed'})
        (self.kb / 'source.txt').unlink()
        self.assertIn('removed', {x['status'] for x in check(self.snapshot)['differences']})
        (self.skill / 'SKILL.md').unlink()
        self.assertIn('removed', {x['status'] for x in check(self.snapshot)['differences']})

    def test_runtime_caches_do_not_invalidate_but_test_code_does(self):
        self.freeze()
        cache = self.skill / '__pycache__'
        cache.mkdir()
        (cache / 'x.pyc').write_bytes(b'cache')
        self.assertEqual(check(self.snapshot)['status'], 'passed')
        tests = self.skill / 'scripts' / 'tests'
        tests.mkdir(parents=True)
        (tests / 'test_new.py').write_text('pass', encoding='utf-8')
        self.assertEqual(check(self.snapshot)['status'], 'failed')

    def test_snapshot_cannot_overwrite_or_watch_its_own_outputs(self):
        self.freeze()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.freeze()
        with self.assertRaisesRegex(ValueError, 'outside'):
            freeze([self.kb], self.kb / 'freeze.json', self.skill)
        for target in (self.snapshot, self.kb / 'result.json'):
            with self.assertRaisesRegex(ValueError, 'outside'):
                check(self.snapshot, target)

    def test_cli_reports_changed_input_with_nonzero_exit(self):
        target = self.root / 'cli.json'
        cmd = [sys.executable, '-X', 'utf8', str(SCRIPTS / 'pipeline.py')]
        first = subprocess.run(cmd + ['freeze-acceptance', '--input', str(self.kb), '--output', str(target)], capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        (self.kb / 'source.txt').write_text('changed', encoding='utf-8')
        second = subprocess.run(cmd + ['check-acceptance', str(target)], capture_output=True, text=True)
        self.assertEqual(second.returncode, 2, second.stderr)
        self.assertEqual(json.loads(second.stdout)['status'], 'failed')

    def test_timing_counts_failed_attempt_and_retry_in_stage_metrics(self):
        work = self.root / 'timing'
        source = self.kb / 'source.txt'
        begin(work, 'verify', [source])
        end(work, 'verify', status='failed', error='fixture failure')
        begin(work, 'verify', [source])
        end(work, 'verify', [source])
        result = report(work)
        metrics = result['stageMetrics']['verify']
        self.assertEqual(metrics['completedAttempts'], 2)
        self.assertEqual(metrics['failedAttempts'], 1)
        self.assertEqual(metrics['retryAttempts'], 1)
        self.assertEqual(metrics['unfinishedAttempts'], 0)
        self.assertGreaterEqual(metrics['cumulativeSeconds'], metrics['observedSeconds'])


if __name__ == '__main__':
    unittest.main()
