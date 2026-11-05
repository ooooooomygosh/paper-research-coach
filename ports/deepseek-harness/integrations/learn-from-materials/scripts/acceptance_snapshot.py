"""Freeze explicit acceptance inputs and skill files; never approve their meaning."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from workflow_io import json_text, read_json, sha_file, write_changed

SCHEMA = 'learn-from-materials/acceptance-snapshot-v1'
ROOT = Path(__file__).resolve().parents[1]
IGNORED = {'__pycache__', '.git', '.pytest_cache', '.mypy_cache', 'node_modules'}


def _inside(path, root):
    return path == root or root in path.parents


def _inventory(path):
    if Path(path).is_symlink():
        raise ValueError('Use explicit regular acceptance inputs, not symlinks: ' + str(path))
    path = Path(path).resolve()
    if not path.exists():
        raise ValueError('Missing acceptance input: ' + str(path))
    if path.is_file():
        return {'kind': 'file', 'files': {path.name: {'sha256': sha_file(path), 'bytes': path.stat().st_size}}}
    if not path.is_dir():
        raise ValueError('Acceptance input must be a file or directory: ' + str(path))
    files = {}
    for item in sorted(path.rglob('*')):
        rel = item.relative_to(path)
        if set(rel.parts) & IGNORED or item.suffix in {'.pyc', '.pyo'}:
            continue
        if item.is_symlink():
            raise ValueError('Use explicit regular acceptance inputs, not symlinks: ' + str(item))
        if item.is_file():
            files[rel.as_posix()] = {'sha256': sha_file(item), 'bytes': item.stat().st_size}
    return {'kind': 'directory', 'files': files}


def freeze(inputs, output, skill_root=None):
    """Store once in WORK, outside watched trees. Inputs must already exist."""
    output = Path(output).resolve()
    if output.exists():
        raise ValueError('Acceptance snapshot already exists; retain it and use a new path for a new attempt')
    skill = Path(skill_root or ROOT).resolve()
    paths = [skill] + [Path(p).resolve() for p in inputs]
    if len(paths) == 1:
        raise ValueError('Supply at least one actual acceptance input in addition to the skill')
    paths = list(dict.fromkeys(paths))
    for path in paths:
        if _inside(output, path):
            raise ValueError('Snapshot output must be outside the skill and watched inputs')
    entries = [{'path': str(p), **_inventory(p)} for p in paths]
    value = {'schemaVersion': SCHEMA, 'createdAt': dt.datetime.now(dt.timezone.utc).isoformat(),
             'status': 'frozen-not-reviewed', 'entries': entries,
             'semanticReview': 'not-attested-by-snapshot',
             'scope': 'Explicit inputs and packaged skill files only; undeclared inputs are not checked.'}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation preserves an earlier freeze, including concurrent calls.
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json_text(value))
    return {'status': value['status'], 'snapshot': str(output), 'roots': len(entries),
            'files': sum(len(e['files']) for e in entries), 'semanticReview': value['semanticReview']}


def check(snapshot, output=None):
    snapshot = Path(snapshot).resolve()
    value = read_json(snapshot)
    if value.get('schemaVersion') != SCHEMA or not isinstance(value.get('entries'), list) or not value['entries']:
        raise ValueError('Invalid acceptance snapshot')
    if output:
        output = Path(output).resolve()
        if output == snapshot or any(_inside(output, Path(e['path']).resolve()) for e in value['entries']):
            raise ValueError('Check output must be outside the snapshot and watched inputs')
    differences = []
    for entry in value['entries']:
        path = Path(entry['path'])
        before = entry['files']
        try:
            after = _inventory(path)
        except (OSError, ValueError) as exc:
            differences.append({'path': str(path), 'status': 'unavailable', 'reason': str(exc)})
            continue
        if after['kind'] != entry['kind']:
            differences.append({'path': str(path), 'status': 'kind-changed'})
        for name in sorted(set(before) | set(after['files'])):
            status = 'added' if name not in before else 'removed' if name not in after['files'] else 'changed' if before[name] != after['files'][name] else None
            if status:
                differences.append({'path': str(path), 'file': name, 'status': status})
    result = {'schemaVersion': 'learn-from-materials/acceptance-check-v1',
              'snapshot': str(snapshot), 'snapshotSha256': sha_file(snapshot),
              'status': 'passed' if not differences else 'failed', 'differences': differences,
              'semanticReview': 'not-attested-by-snapshot',
              'note': 'An unchanged snapshot proves file freshness only. It does not certify tests or source review; changed inputs require inspecting the actual affected scope.'}
    if output:
        write_changed(output, json_text(result))
    return result
