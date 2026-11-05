#!/usr/bin/env python3
"""Read-only checks for an unpacked skill release; no installs or network calls."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
import re
from urllib.parse import unquote

from workflow_io import skill_metadata


def verify(root):
    root = Path(root).resolve()
    errors = []
    try:
        metadata = skill_metadata(root)
        version = metadata['version']
        if not re.fullmatch(r'\d+\.\d+\.\d+', version):
            errors.append('Release version must use major.minor.patch')
    except (OSError, ValueError, KeyError) as exc:
        return {'status': 'failed', 'errors': ['Invalid SKILL.md metadata: ' + str(exc)]}
    required = ('SKILL.md', 'README.md', 'README_CN.md', 'CHANGELOG.md', 'LICENSE.md', 'NOTICE.md',
                'scripts/extract.py', 'scripts/finalize.py', 'scripts/pipeline.py',
                'scripts/unit_review.py', 'scripts/relation_ledger.py',
                'references/systematic-workflow.md', 'templates/graph-motion.js',
                'examples/method-lab-synthetic.pdf')
    for name in required:
        if not (root / name).is_file():
            errors.append('Missing release file: ' + name)
    retired = ('scripts/parallel_workflow.py', 'references/parallel-workflow.md', 'assets/parallel-policy.json',
               'scripts/tests/execution_choice_fixture.py', 'scripts/tests/test_parallel_workflow.py',
               'scripts/tests/test_global_structure_queue.py', 'scripts/tests/test_preparse_choice.py')
    for name in retired:
        if (root / name).exists():
            errors.append('Retired execution module remains: ' + name)
    forbidden_imports = {'parallel_workflow', 'execution_choice_fixture'}
    for path in (root / 'scripts').rglob('*.py'):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8-sig'))
            for node in ast.walk(tree):
                imported = [a.name.split('.')[0] for a in node.names] if isinstance(node, ast.Import) else [node.module.split('.')[0]] if isinstance(node, ast.ImportFrom) and node.module else []
                if forbidden_imports.intersection(imported):
                    errors.append('Broken retired import in ' + path.relative_to(root).as_posix())
        except (SyntaxError, UnicodeError) as exc:
            errors.append('Invalid Python source: ' + path.relative_to(root).as_posix() + ': ' + str(exc))
    for name in ('README.md', 'README_CN.md'):
        path = root / name
        if not path.exists():
            continue
        content = path.read_text(encoding='utf-8')
        if 'version-' + version + '-blue' not in content or 'learn-from-materials-' + version + '.zip' not in content:
            errors.append('Version/install filename mismatch in ' + name)
    changelog = root / 'CHANGELOG.md'
    if changelog.exists() and not re.search(r'^## ' + re.escape(version) + r'\b', changelog.read_text(encoding='utf-8'), re.M):
        errors.append('Missing current release changelog entry')
    docs = [root / 'SKILL.md', root / 'README.md', root / 'README_CN.md', *(root / 'references').glob('*.md')]
    for path in docs:
        if not path.is_file():
            continue
        content = path.read_text(encoding='utf-8')
        if 'parallel-workflow.md' in content or '--agent-id' in content:
            errors.append('Current instructions retain a removed execution dependency: ' + path.relative_to(root).as_posix())
        for target in re.findall(r'(?<!!)\[[^\]\n]+\]\(([^)\n]+)\)', content):
            target = target.strip().strip('<>').split('#')[0]
            if not target or re.match(r'^[A-Za-z][A-Za-z\d+.-]*:', target):
                continue
            if not (path.parent / unquote(target)).exists():
                errors.append('Broken documentation link: ' + path.relative_to(root).as_posix() + ' -> ' + target)
    return {'status': 'passed' if not errors else 'failed', 'version': version,
            'revision': metadata['revision'], 'archiveName': 'learn-from-materials-' + version + '.zip',
            'errors': errors, 'scope': 'Package structure, metadata, Python syntax/imports and documentation links; not semantic or visual acceptance.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    result = verify(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else result['status'].upper() + ': release ' + result.get('version', 'unknown') + ('\n' + '\n'.join(result['errors']) if result['errors'] else ''))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    from cli_output import configure_output
    configure_output()
    raise SystemExit(main())
