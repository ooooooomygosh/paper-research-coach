"""Sequential checkpoints and measured wall-clock intervals, never semantic proof.

Attempts retain every retry; stages remains a latest-attempt compatibility view.
Kernel locks are automatically released if their owning process crashes.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import hashlib
import json
import os
import re
import time
import uuid
from pathlib import Path

from workflow_io import read_json, json_text, write_changed, sha_file

STAGES = ('preflight', 'extract', 'author', 'assemble', 'review', 'render', 'verify', 'deliver')
KEY = re.compile(r'^[A-Za-z][A-Za-z0-9_-]*$')
ATTEMPT = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$')
ROOT = Path(__file__).resolve().parents[1]


@contextlib.contextmanager
def locked(lock_path, timeout=30):
    """Exclusive OS advisory lock at an explicit file path; not recursive.

    Cooperating writers use the same path. A leftover file is harmless; a live
    lock is never stolen, and acquisition has a bounded timeout.
    """
    path = Path(lock_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    stream = path.open('a+b')
    acquired = False
    try:
        while True:
            try:
                stream.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('Timed out waiting for pipeline lock: ' + str(path))
                time.sleep(min(0.05, max(0, deadline - time.monotonic())))
        # Lock first, initialize second. Concurrent first writers must not write
        # the byte before owning it. Windows permits locking beyond EOF.
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b'0')
            stream.flush()
        yield
    finally:
        if acquired:
            stream.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
        stream.close()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _time(value):
    stamp = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Pipeline timestamps require a timezone')
    return stamp


def seconds(start, end):
    return round(max(0, (_time(end) - _time(start)).total_seconds()), 6)


def code_fingerprint(stage):
    names = {
        'extract': ('scripts/extract.py', 'scripts/extractor', 'scripts/workflow_io.py'),
        'author': ('SKILL.md', 'references', 'scripts/unit_records.py', 'scripts/relation_ledger.py'),
        'assemble': ('scripts/unit_records.py', 'scripts/relation_ledger.py', 'scripts/methods.py', 'scripts/methodology.py', 'scripts/render_page.py', 'scripts/localization.py', 'scripts/workflow_io.py'),
        'review': ('references', 'scripts/content_review.py', 'scripts/unit_review.py', 'scripts/relation_ledger.py', 'scripts/unit_records.py', 'scripts/action_rules.py', 'scripts/verify_coverage.py', 'scripts/methods.py', 'scripts/methodology.py'),
    }.get(stage, ('scripts', 'templates'))
    files = set()
    for name in names:
        path = ROOT / name
        files.update([path] if path.is_file() else (p for p in path.rglob('*') if p.is_file() and p.suffix in {'.py', '.js', '.css', '.html', '.md'} and not {'__pycache__', 'tests'} & set(p.parts)))
    checkpoint_code = ROOT / 'scripts/pipeline_state.py'
    if checkpoint_code.is_file():
        files.add(checkpoint_code)  # Checkpoint semantics affect every cache.
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.relative_to(ROOT).as_posix().encode('utf-8') + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def file_entries(paths):
    result = []
    for path in paths:
        path = Path(path).resolve()
        if not path.is_file():
            raise ValueError('Missing checkpoint file: ' + str(path))
        result.append({'path': str(path), 'sha256': sha_file(path)})
    return result


def stage_key(stage, unit_id=None):
    if stage not in STAGES or unit_id is not None and not KEY.fullmatch(unit_id):
        raise ValueError('Invalid stage or unit ID')
    return stage + ('--' + unit_id if unit_id else '')


def state_root(work_dir):
    return Path(work_dir).resolve() / '.pipeline'


def _append(root, kind, at=None, **fields):
    value = {'at': at or now(), 'kind': kind, **fields}
    with (root / 'events.jsonl').open('a', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + '\n')
        stream.flush()
        os.fsync(stream.fileno())
    return value


def _session(root, model_label=None):
    path = root / 'run.json'
    if path.is_file():
        value = read_json(path)
        if value.get('finishedAt'):
            raise ValueError('Run is already finished; choose a new work directory for a new timed run')
        if model_label and value.get('modelLabel') not in (None, model_label):
            raise ValueError('Model label changed inside one run')
        if model_label and not value.get('modelLabel'):
            value['modelLabel'] = model_label
            write_changed(path, json_text(value))
        return value
    value = {'schemaVersion': 'learn-from-materials/pipeline-run-v2', 'runId': str(uuid.uuid4()), 'startedAt': now(), 'finishedAt': None, 'modelLabel': model_label, 'timerBoundary': 'first-recorded-event-to-finish; unbracketed gaps remain unknown'}
    write_changed(path, json_text(value))
    _append(root, 'run-start', at=value['startedAt'], runId=value['runId'])
    return value


def session(work_dir, model_label=None):
    root = state_root(work_dir)
    with locked(root / 'state.lock'):
        return _session(root, model_label)


def event(work_dir, kind, **fields):
    root = state_root(work_dir)
    with locked(root / 'state.lock'):
        _session(root)
        return _append(root, kind, **fields)


def signature(stage, inputs, command=None):
    payload = {'stage': stage, 'inputs': inputs, 'codeSha256': code_fingerprint(stage), 'command': command or []}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode('utf-8')).hexdigest()


def inspect_state(value):
    reasons = []
    try:
        inputs = file_entries(x['path'] for x in value['inputs'])
        if signature(value['stage'], inputs, value.get('command')) != value['signature']:
            reasons.append('input-or-relevant-code-changed')
    except (OSError, ValueError, KeyError, TypeError):
        reasons.append('missing-input')
    try:
        if file_entries(x['path'] for x in value.get('artifacts', [])) != value.get('artifacts', []):
            reasons.append('artifact-changed')
    except (OSError, ValueError, KeyError, TypeError):
        reasons.append('missing-artifact')
    reusable = value.get('status') in {'succeeded', 'draft-ready'} and bool(value.get('artifacts')) and not reasons and not value.get('timingOnly')
    return {name: value.get(name) for name in ('key', 'stage', 'unitId', 'attemptId', 'taskId', 'agentId', 'status', 'startedAt', 'endedAt', 'elapsedSeconds')} | {'reusable': reusable, 'reasons': reasons, 'semanticReview': 'not-proven-by-checkpoint'}


def _attempt_id(value=None):
    value = value or ('a' + uuid.uuid4().hex)
    if not isinstance(value, str) or not ATTEMPT.fullmatch(value):
        raise ValueError('Invalid attempt/wait ID')
    return value


def _identity(value):
    if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 256):
        raise ValueError('Agent/task identity must be a nonempty string of at most 256 characters')
    return value


def _attempts(root):
    values = [read_json(p) for p in sorted((root / 'attempts').glob('*.json'))]
    ids = {x.get('attemptId') for x in values}
    for path in sorted((root / 'stages').glob('*.json')):
        value = read_json(path)
        if not value.get('attemptId') or value['attemptId'] not in ids:
            values.append(value)
    return values


def _archive_legacy(root, value):
    if not value.get('attemptId'):
        value = {**value, 'attemptId': _attempt_id(), 'legacyImported': True}
        write_changed(root / 'attempts' / (value['attemptId'] + '.json'), json_text(value))
        write_changed(root / 'stages' / (value['key'] + '.json'), json_text(value))
    return value


def begin(work_dir, stage, inputs, unit_id=None, command=None, model_label=None, *, task_id=None, attempt_id=None):
    root = state_root(work_dir)
    key = stage_key(stage, unit_id)
    task_id = _identity(task_id)
    with locked(root / 'state.lock'):
        _session(root, model_label)
        entries = file_entries(inputs)
        sig = signature(stage, entries, command)
        running_elsewhere = [x for x in _attempts(root) if x['status'] == 'running'
                             and (x['key'] != key or x.get('taskId') != task_id)]
        if running_elsewhere:
            raise ValueError('Sequential run already has a running attempt; finish or fail it before starting another task')
        candidates = [_archive_legacy(root, x) for x in _attempts(root) if x['key'] == key]
        if attempt_id:
            _attempt_id(attempt_id)
            existing = [x for x in _attempts(root) if x.get('attemptId') == attempt_id]
            if existing:
                prior = existing[0]
                if prior['key'] == key and prior['status'] == 'running' and prior['signature'] == sig and prior.get('taskId') == task_id:
                    return prior
                raise ValueError('Attempt ID already exists and cannot be overwritten')
        running = [x for x in candidates if x['status'] == 'running' and x.get('taskId') == task_id]
        if running:
            if len(running) == 1 and running[0]['signature'] == sig and not attempt_id:
                return running[0]
            raise ValueError('Task already has a running attempt; finish or fail it before restarting')
        value = {'schemaVersion': 'learn-from-materials/pipeline-stage-v3', 'key': key, 'stage': stage, 'unitId': unit_id, 'attemptId': _attempt_id(attempt_id), 'taskId': task_id, 'status': 'running', 'startedAt': now(), 'inputs': entries, 'signature': sig, 'command': command or [], 'artifacts': []}
        write_changed(root / 'attempts' / (value['attemptId'] + '.json'), json_text(value))
        write_changed(root / 'stages' / (key + '.json'), json_text(value))
        _append(root, 'stage-start', at=value['startedAt'], key=key, signature=sig, attemptId=value['attemptId'], taskId=task_id)
        return value


def end(work_dir, stage, artifacts=(), unit_id=None, status='succeeded', error=None, *, task_id=None, attempt_id=None):
    root = state_root(work_dir)
    key = stage_key(stage, unit_id)
    if status not in {'succeeded', 'draft-ready', 'failed'}:
        raise ValueError('Invalid stage result')
    _identity(task_id)
    if attempt_id:
        _attempt_id(attempt_id)
    with locked(root / 'state.lock'):
        _session(root)
        candidates = [x for x in _attempts(root) if x['key'] == key and x['status'] == 'running' and (attempt_id is None or x.get('attemptId') == attempt_id) and (task_id is None or x.get('taskId') == task_id)]
        if len(candidates) != 1:
            raise ValueError('End requires one matching running attempt; specify attempt_id for ambiguous tasks')
        value = _archive_legacy(root, candidates[0])
        if status != 'failed':
            if signature(stage, file_entries(x['path'] for x in value['inputs']), value.get('command')) != value['signature']:
                raise ValueError('Inputs/code changed during this stage; rerun it')
            if not artifacts:
                raise ValueError('Successful stages require actual output artifacts')
        value.update(status=status, endedAt=now(), artifacts=file_entries(artifacts), error=error)
        value['elapsedSeconds'] = seconds(value['startedAt'], value['endedAt'])
        write_changed(root / 'attempts' / (value['attemptId'] + '.json'), json_text(value))
        latest = root / 'stages' / (key + '.json')
        if not latest.is_file() or read_json(latest).get('attemptId') == value['attemptId']:
            write_changed(latest, json_text(value))
        _append(root, 'stage-end', at=value['endedAt'], key=key, status=status, elapsedSeconds=value['elapsedSeconds'], attemptId=value['attemptId'], taskId=value.get('taskId'))
        return inspect_state(value)


def wait_begin(work_dir, reason, wait_id=None, *, task_id=None):
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError('An explicit wait reason is required')
    root = state_root(work_dir)
    with locked(root / 'state.lock'):
        _session(root)
        value = {'waitId': _attempt_id(wait_id), 'reason': reason, 'taskId': _identity(task_id), 'startedAt': now(), 'endedAt': None}
        path = root / 'waits' / (value['waitId'] + '.json')
        if path.exists():
            raise ValueError('Wait ID already exists')
        write_changed(path, json_text(value))
        _append(root, 'wait-start', at=value['startedAt'], **value)
        return value


def wait_end(work_dir, wait_id):
    root = state_root(work_dir)
    wait_id = _attempt_id(wait_id)
    with locked(root / 'state.lock'):
        _session(root)
        path = root / 'waits' / (wait_id + '.json')
        value = read_json(path)
        if value.get('endedAt'):
            raise ValueError('Wait is already ended')
        value['endedAt'] = now()
        value['elapsedSeconds'] = seconds(value['startedAt'], value['endedAt'])
        write_changed(path, json_text(value))
        _append(root, 'wait-end', at=value['endedAt'], **value)
        return value


def _events(root):
    path = root / 'events.jsonl'
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def _legacy_event_attempts(events, attempts):
    """Recover overwritten 1.02 timing history without inventing cache evidence."""
    pending, recovered = {}, []
    for index, item in enumerate(events):
        if item.get('attemptId') or not item.get('key'):
            continue
        if item['kind'] == 'stage-start':
            if item['key'] in pending:
                recovered.append(pending[item['key']])
            pending[item['key']] = {'key': item['key'], 'stage': item['key'].split('--')[0], 'startedAt': item['at'], 'signature': item.get('signature'), 'attemptId': 'legacy-event-' + str(index), 'status': 'running', 'timingOnly': True}
        elif item['kind'] == 'stage-end' and item['key'] in pending:
            record = pending.pop(item['key'])
            record.update(status=item['status'], endedAt=item['at'], elapsedSeconds=item.get('elapsedSeconds', seconds(record['startedAt'], item['at'])))
            recovered.append(record)
    recovered.extend(pending.values())
    # Match each physical legacy snapshot to at most one journal interval. A
    # quick retry can start within a second of its predecessor and must survive.
    for actual in attempts:
        candidates = [(abs((_time(actual['startedAt']) - _time(x['startedAt'])).total_seconds()), i)
                      for i, x in enumerate(recovered) if actual['key'] == x['key']
                      and actual.get('status') == x['status'] and actual.get('signature') == x.get('signature')]
        if candidates:
            distance, index = min(candidates)
            if distance < 1:
                recovered.pop(index)
    return recovered


def _interval(start, end, lower, upper):
    a, b = max(_time(start), lower), min(_time(end), upper)
    return (a, b) if b > a else None


def _union(intervals):
    merged = []
    for a, b in sorted(x for x in intervals if x):
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


def _duration(intervals):
    return round(sum((b - a).total_seconds() for a, b in intervals), 6)


def _report(root):
    run = read_json(root / 'run.json')
    events = _events(root)
    attempts = _attempts(root)
    attempts += _legacy_event_attempts(events, attempts)
    start = min((x['at'] for x in events), key=_time) if events else run['startedAt']
    stop = run.get('finishedAt') or now()
    lower, upper = _time(start), _time(stop)
    completed = [x for x in attempts if x.get('endedAt') and x['status'] in {'succeeded', 'draft-ready', 'failed'}]
    intervals = [i for x in completed if (i := _interval(x['startedAt'], x['endedAt'], lower, upper))]
    execution = _union(intervals)
    waits = [read_json(p) for p in sorted((root / 'waits').glob('*.json'))]
    explicit_wait = _union([_interval(x['startedAt'], x.get('endedAt') or stop, lower, upper) for x in waits])
    known_wait_ids = {x['waitId'] for x in waits}
    pending = {}
    for item in events:
        wid = item.get('waitId')
        if not wid or wid in known_wait_ids:
            continue
        if item['kind'] == 'wait-start':
            pending[wid] = item['at']
        elif item['kind'] == 'wait-end' and wid in pending:
            explicit_wait = _union(explicit_wait + [_interval(pending.pop(wid), item['at'], lower, upper)])
    explicit_wait = _union(explicit_wait + [_interval(x, stop, lower, upper) for x in pending.values()])
    covered = _union(execution + explicit_wait)
    wall = seconds(start, stop)
    stage_totals, status_totals = {}, {}
    for value in completed:
        elapsed = seconds(value['startedAt'], value['endedAt'])
        stage_totals[value['stage']] = round(stage_totals.get(value['stage'], 0) + elapsed, 6)
        status_totals[value['status']] = round(status_totals.get(value['status'], 0) + elapsed, 6)
    stage_metrics = {}
    for stage in STAGES:
        all_stage = [x for x in attempts if x['stage'] == stage]
        if not all_stage:
            continue
        done = [x for x in completed if x['stage'] == stage]
        counts = {}
        for value in all_stage:
            counts[value['key']] = counts.get(value['key'], 0) + 1
        stage_metrics[stage] = {
            'completedAttempts': len(done),
            'failedAttempts': sum(x['status'] == 'failed' for x in done),
            'unfinishedAttempts': sum(x['status'] == 'running' for x in all_stage),
            'retryAttempts': sum(max(0, n - 1) for n in counts.values()),
            'cumulativeSeconds': stage_totals.get(stage, 0),
            'observedSeconds': _duration(_union([_interval(x['startedAt'], x['endedAt'], lower, upper) for x in done])),
        }
    usage = [x for x in events if x['kind'] == 'usage-reported' and isinstance(x.get('usage'), dict) and x['usage']]
    return {**run, 'schemaVersion': 'learn-from-materials/pipeline-report-v1', 'runSchemaVersion': run['schemaVersion'], 'timingStartedAt': start, 'wallSeconds': wall,
            'stages': [inspect_state(read_json(p)) for p in sorted((root / 'stages').glob('*.json'))],
            'attempts': [inspect_state(x) for x in attempts], 'waits': waits,
            'stageElapsedSeconds': stage_totals, 'statusElapsedSeconds': status_totals,
            'stageMetrics': stage_metrics,
            'observedExecutionSeconds': _duration(execution), 'cumulativeTaskSeconds': _duration(intervals),
            'explicitWaitSeconds': _duration(explicit_wait), 'uninstrumentedSeconds': round(max(0, wall - _duration(covered)), 6),
            'unfinishedAttemptIds': [x.get('attemptId', x['key']) for x in attempts if x['status'] == 'running'],
            'usage': {'available': bool(usage), 'reportedEvents': usage},
            'note': 'Observed execution is the union of completed stage brackets, including draft-ready and failed attempts; it includes model/tool waits inside those brackets, not CPU time. Cumulative task effort sums brackets and can exceed wall time. Explicit waits can overlap stage brackets. Uninstrumented time is unknown, not assumed idle. Open attempts are excluded from measured execution. Checkpoint reuse never proves semantic review.'}


def report(work_dir):
    root = state_root(work_dir)
    with locked(root / 'state.lock'):
        return _report(root)


def finish(work_dir):
    root = state_root(work_dir)
    with locked(root / 'state.lock'):
        result = _report(root)
        if result['unfinishedAttemptIds']:
            raise ValueError('Cannot finish a run with running stages')
        if any(not read_json(p).get('endedAt') for p in (root / 'waits').glob('*.json')):
            raise ValueError('Cannot finish a run with an open explicit wait')
        path = root / 'run.json'
        run = read_json(path)
        if not run.get('finishedAt'):
            run['finishedAt'] = now()
            write_changed(path, json_text(run))
            _append(root, 'run-finish', at=run['finishedAt'])
        return _report(root)
