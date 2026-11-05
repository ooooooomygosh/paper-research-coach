"""Sequential state, resumed attempts and truthful legacy interval accounting."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
import pipeline_state as state
from workflow_io import json_text, read_json, write_changed


class StateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / 'source.txt'
        self.output = self.root / 'output.txt'
        self.source.write_text('original material', encoding='utf-8')
        self.output.write_text('grounded draft', encoding='utf-8')
        # Isolate tests from unrelated code changes in the release workspace.
        self.fingerprint = patch('pipeline_state.code_fingerprint', return_value='test-code-v1')
        self.fingerprint.start()
        self.addCleanup(self.fingerprint.stop)

    def at(self, second):
        return (dt.datetime(2026, 10, 16, tzinfo=dt.timezone.utc) + dt.timedelta(seconds=second)).isoformat()

    def begin_at(self, second, task, agent=None, stage='author'):
        with patch('pipeline_state.now', return_value=self.at(second)):
            return state.begin(self.root, stage, [self.source], task_id=task)

    def end_at(self, second, attempt, status='draft-ready'):
        with patch('pipeline_state.now', return_value=self.at(second)):
            return state.end(self.root, attempt['stage'], [self.output] if status != 'failed' else [], attempt_id=attempt['attemptId'], status=status)

    def test_retry_history_keeps_failed_and_draft_ready_attempts(self):
        first = self.begin_at(0, 'chapter-1', 'worker-1')
        self.end_at(10, first, 'failed')
        second = self.begin_at(12, 'chapter-1', 'worker-2')
        self.end_at(32, second)
        with patch('pipeline_state.now', return_value=self.at(40)):
            result = state.finish(self.root)
        self.assertEqual(len(result['attempts']), 2)
        self.assertEqual(result['statusElapsedSeconds'], {'failed': 10, 'draft-ready': 20})
        self.assertEqual(result['stageElapsedSeconds']['author'], 30)
        self.assertEqual(result['observedExecutionSeconds'], 30)
        self.assertEqual(result['wallSeconds'], 40)
        self.assertEqual(result['uninstrumentedSeconds'], 10)
        self.assertTrue(result['stages'][0]['reusable'])
        self.assertNotEqual(first['attemptId'], second['attemptId'])

    def test_second_task_waits_for_current_attempt_to_finish(self):
        first = self.begin_at(0, 'part-a')
        with self.assertRaisesRegex(ValueError, 'Sequential run'):
            self.begin_at(5, 'part-b')
        self.end_at(10, first)
        second = self.begin_at(12, 'part-b')
        self.end_at(15, second)
        with patch('pipeline_state.now', return_value=self.at(20)):
            result = state.finish(self.root)
        self.assertEqual(result['observedExecutionSeconds'], 13)
        self.assertEqual(result['cumulativeTaskSeconds'], 13)
        self.assertEqual(len(result['attempts']), 2)
        self.assertEqual(result['schemaVersion'], 'learn-from-materials/pipeline-report-v1')


    def test_legacy_overlapping_attempts_remain_readable(self):
        first = self.begin_at(0, 'part-a')
        self.end_at(10, first)
        second = self.begin_at(12, 'part-b')
        self.end_at(20, second)
        root = state.state_root(self.root)
        path = root / 'attempts' / (second['attemptId'] + '.json')
        legacy = read_json(path)
        legacy.update(schemaVersion='learn-from-materials/pipeline-stage-v2', startedAt=self.at(5), agentId='historical-worker')
        write_changed(path, json_text(legacy))
        with patch('pipeline_state.now', return_value=self.at(25)):
            result = state.report(self.root)
        self.assertEqual(result['observedExecutionSeconds'], 20)
        self.assertEqual(result['cumulativeTaskSeconds'], 25)
        self.assertNotIn('maximumConcurrentAgents', result)


    def test_explicit_wait_and_uninstrumented_gap_are_distinct(self):
        first = self.begin_at(0, 'part-a')
        self.end_at(10, first)
        with patch('pipeline_state.now', return_value=self.at(20)):
            waiting = state.wait_begin(self.root, 'waiting for user choice')
        with patch('pipeline_state.now', return_value=self.at(40)):
            state.wait_end(self.root, waiting['waitId'])
        with patch('pipeline_state.now', return_value=self.at(60)):
            result = state.finish(self.root)
        self.assertEqual(result['wallSeconds'], 60)
        self.assertEqual(result['observedExecutionSeconds'], 10)
        self.assertEqual(result['explicitWaitSeconds'], 20)
        self.assertEqual(result['uninstrumentedSeconds'], 30)
        self.assertFalse(result['usage']['available'])
        self.assertEqual(result['waits'][0]['reason'], 'waiting for user choice')

    def test_wait_overlapping_work_is_not_double_subtracted_from_wall(self):
        first = self.begin_at(0, 'part-a')
        with patch('pipeline_state.now', return_value=self.at(5)):
            waiting = state.wait_begin(self.root, 'external tool wait')
        self.end_at(10, first)
        with patch('pipeline_state.now', return_value=self.at(15)):
            state.wait_end(self.root, waiting['waitId'])
        with patch('pipeline_state.now', return_value=self.at(20)):
            result = state.finish(self.root)
        self.assertEqual(result['explicitWaitSeconds'], 10)
        self.assertEqual(result['uninstrumentedSeconds'], 5)

    def test_open_attempt_is_unknown_not_continuous_observed_execution(self):
        attempt = self.begin_at(0, 'interrupted', 'worker-1')
        with patch('pipeline_state.now', return_value=self.at(3600)):
            result = state.report(self.root)
            with self.assertRaisesRegex(ValueError, 'running'):
                state.finish(self.root)
        self.assertEqual(result['observedExecutionSeconds'], 0)
        self.assertEqual(result['uninstrumentedSeconds'], 3600)
        self.assertEqual(result['unfinishedAttemptIds'], [attempt['attemptId']])

    def test_active_wait_prevents_finish_and_usage_requires_actual_values(self):
        state.wait_begin(self.root, 'user choice', wait_id='choice')
        with self.assertRaisesRegex(ValueError, 'open explicit wait'):
            state.finish(self.root)
        state.event(self.root, 'usage-reported')
        self.assertFalse(state.report(self.root)['usage']['available'])
        state.event(self.root, 'usage-reported', usage={'inputTokens': 123, 'source': 'platform-response'})
        self.assertEqual(state.report(self.root)['usage']['reportedEvents'][0]['usage']['inputTokens'], 123)

    def test_inputs_code_and_artifacts_fail_closed(self):
        first = self.begin_at(0, 'part-a')
        self.source.write_text('changed during authoring', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'changed during'):
            self.end_at(10, first)
        self.end_at(10, first, 'failed')
        second = self.begin_at(20, 'part-a')
        self.end_at(30, second)
        self.assertTrue(state.report(self.root)['stages'][0]['reusable'])
        with patch('pipeline_state.code_fingerprint', return_value='test-code-v2'):
            self.assertFalse(state.report(self.root)['stages'][0]['reusable'])
        self.output.write_text('edited output', encoding='utf-8')
        self.assertIn('artifact-changed', state.report(self.root)['stages'][0]['reasons'])
        self.source.unlink()
        self.assertIn('missing-input', state.report(self.root)['stages'][0]['reasons'])

    def test_same_task_resume_and_attempt_overwrite_are_checked(self):
        first = self.begin_at(0, 'part-a')
        repeated = self.begin_at(1, 'part-a')
        self.assertEqual(first['attemptId'], repeated['attemptId'])
        self.source.write_text('changed input', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'running attempt'):
            self.begin_at(2, 'part-a')
        self.end_at(5, first, 'failed')
        with self.assertRaisesRegex(ValueError, 'cannot be overwritten'):
            state.begin(self.root, 'author', [self.source], task_id='part-a', attempt_id=first['attemptId'])


    def test_legacy_journal_recovers_overwritten_failure_without_double_counting(self):
        root = state.state_root(self.root)
        root.mkdir()
        run = {'schemaVersion': 'learn-from-materials/pipeline-run-v1', 'runId': 'legacy', 'startedAt': self.at(0), 'finishedAt': self.at(30)}
        write_changed(root / 'run.json', json_text(run))
        events = [dict(at=self.at(0), kind='stage-start', key='author--u1', signature='old'),
                  dict(at=self.at(10), kind='stage-end', key='author--u1', status='failed', elapsedSeconds=10),
                  dict(at=self.at(12), kind='stage-start', key='author--u1', signature='old'),
                  dict(at=self.at(22), kind='stage-end', key='author--u1', status='draft-ready', elapsedSeconds=10)]
        write_changed(root / 'events.jsonl', ''.join(json.dumps(x) + '\n' for x in events))
        write_changed(root / 'stages/author--u1.json', json_text(dict(key='author--u1', stage='author', status='draft-ready', startedAt=self.at(12), endedAt=self.at(22), elapsedSeconds=10, signature='old', inputs=[], artifacts=[])))
        result = state.report(self.root)
        self.assertEqual(len(result['attempts']), 2)
        self.assertEqual(result['stageElapsedSeconds']['author'], 20)
        self.assertEqual(result['statusElapsedSeconds'], {'draft-ready': 10, 'failed': 10})
        self.assertFalse(any(x['reusable'] for x in result['attempts']))

    def test_repeated_subprocess_invocations_preserve_run_and_attempts(self):
        code = """import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import pipeline_state as s
s.code_fingerprint = lambda _: 'sequential-fixture'
root = Path(sys.argv[2]); number = sys.argv[3]
run = s.session(root)
a = s.begin(root, 'author', [root/'source.txt'], task_id='task-' + number)
s.end(root, 'author', [root/'output.txt'], attempt_id=a['attemptId'], status='draft-ready')
print(run['runId'])
"""
        outputs = [subprocess.run([sys.executable, '-X', 'utf8', '-c', code, str(SCRIPTS), str(self.root), str(i)], capture_output=True, text=True, timeout=30) for i in range(4)]
        for result in outputs:
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len({p.stdout.strip() for p in outputs}), 1)
        with patch('pipeline_state.code_fingerprint', return_value='sequential-fixture'):
            result = state.finish(self.root)
        self.assertEqual(len(result['attempts']), 4)
        self.assertTrue(all(x['reusable'] for x in result['attempts']))
        events = state._events(state.state_root(self.root))
        self.assertEqual(sum(x['kind'] == 'run-start' for x in events), 1)


    def test_dead_lock_owner_releases_kernel_lock_and_live_lock_times_out(self):
        lockfile = self.root / 'lock'
        code = """import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from pipeline_state import locked
with locked(sys.argv[2]):
    print('locked', flush=True)
    time.sleep(60)
"""
        process = subprocess.Popen([sys.executable, '-u', '-c', code, str(SCRIPTS), str(lockfile)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            self.assertEqual(process.stdout.readline().strip(), 'locked')
            started = time.monotonic()
            with self.assertRaises(TimeoutError):
                with state.locked(lockfile, timeout=0.1):
                    self.fail('Live owner lock was stolen')
            self.assertLess(time.monotonic() - started, 2)
        finally:
            process.kill()
            process.communicate(timeout=5)
        with state.locked(lockfile, timeout=1):
            self.assertTrue(lockfile.exists())


if __name__ == '__main__':
    unittest.main()
