"""Small deterministic IO helpers shared by the authoring workflow."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + '\n'


def sha_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def write_changed(path, value):
    """Replace one derived file atomically; an identical file is never rewritten."""
    path = Path(path)
    body = value if isinstance(value, bytes) else value.encode('utf-8')
    if path.is_file() and path.read_bytes() == body:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.' + path.name + '-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return True


def skill_metadata(root=None):
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    body = (root / 'SKILL.md').read_text(encoding='utf-8')
    values = {}
    for key in ('version', 'revision'):
        match = re.search(r'^  ' + key + r':\s*(.+?)\s*$', body, re.M)
        if not match:
            raise ValueError('Missing skill metadata: ' + key)
        values[key] = match[1].strip('"\'')
    return values
