#!/usr/bin/env python3
"""Portable source-grounded authoring, early checks, checkpoints and timing.

This orchestrates deterministic work. It never calls a model, installs packages,
authors review results, or replaces finalize.py's publication gates.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from workflow_io import read_json, json_text, write_changed, skill_metadata
from unit_records import Sources, compile_unit, assemble
from pipeline_state import begin, end, report, finish, stage_key, state_root, file_entries, signature, inspect_state, STAGES, event, wait_begin, wait_end


def preflight(inputs=()):
    root = Path(__file__).resolve().parents[1]
    required = ['SKILL.md', 'scripts/extract.py', 'scripts/finalize.py', 'scripts/content_review.py', 'scripts/unit_review.py', 'scripts/relation_ledger.py', 'scripts/acceptance_snapshot.py', 'references/material-processing.md', 'references/learning-page-workflow.md', 'references/page-update-workflow.md', 'references/relation-ledger.md', 'references/content-contract.md', 'references/systematic-workflow.md', 'templates/relationship-mindmap.js', 'templates/framework-routing.js', 'templates/graph-motion.js']
    errors = ['Missing skill file: ' + p for p in required if not (root / p).is_file()]
    if sys.version_info < (3, 10):
        errors.append('Python 3.10+ is required')
    for path in inputs:
        if not Path(path).is_file():
            errors.append('Missing source input: ' + str(path))
    optional = {name: importlib.util.find_spec(name) is not None for name in ('pypdf', 'PyPDF2', 'pdfminer', 'PIL', 'pytesseract')}
    tools = {name: shutil.which(name) for name in ('node', 'pdftotext', 'pdftoppm', 'tesseract', 'swift')}
    result = {'schemaVersion': 'learn-from-materials/pipeline-preflight-v1', 'skill': skill_metadata(root), 'platform': platform.system(), 'pythonVersion': platform.python_version(), 'optionalPackages': optional, 'tools': tools, 'errors': errors, 'status': 'passed' if not errors else 'failed', 'limits': ['OCR/native-vision and browser availability require an actual capability probe; optional-package absence does not imply unreadability.', 'No dependencies were installed. Missing browser verification must remain not-run.']}
    return result


def validate_unit(path, kb):
    compiled = compile_unit(read_json(path), Sources(kb))
    return {'status': 'draft-valid', 'unitId': compiled['unit']['id'], 'claims': len(compiled['claims']), 'sources': len(compiled['sourceBlocks']), 'semanticReview': 'not-attested-by-schema-or-quote-match'}


def checkpoint(path, kb, work_dir):
    """Recover a surviving, validated authoring record without certifying meaning."""
    result = validate_unit(path, kb)
    inputs = [Path(kb) / 'source_map.json', Path(kb) / 'full_text.txt']
    key = stage_key('author', result['unitId'])
    state = state_root(work_dir) / 'stages' / (key + '.json')
    if state.is_file():
        prior = read_json(state)
        if prior['status'] == 'running' and prior['signature'] != signature('author', file_entries(inputs)):
            raise ValueError('Surviving stage used different sources/code; inspect it before accepting the draft')
    begin(work_dir, 'author', inputs, result['unitId'])
    return {**result, 'checkpoint': end(work_dir, 'author', [path], result['unitId'], status='draft-ready')}


def run_command(args):
    command = list(args.command)
    if command and command[0] == '--':
        command.pop(0)
    if not command:
        raise ValueError('Supply an explicit executable and arguments after --')
    if args.stage in {'author', 'review'} and args.reuse:
        raise ValueError('Automatic command reuse is for mechanical stages; use explicit source review/checkpoint handling for author/review')
    key = stage_key(args.stage, args.unit_id)
    state = state_root(args.work_dir) / 'stages' / (key + '.json')
    expected = signature(args.stage, file_entries(args.input), command)
    if args.reuse and state.is_file():
        prior = read_json(state)
        inspected = inspect_state(prior)
        if inspected['reusable'] and prior['signature'] == expected:
            event(args.work_dir, 'stage-reuse', key=key)
            return {'returnCode': 0, 'reused': True, 'stage': inspected}
    if state.is_file() and read_json(state).get('status') == 'running':
        raise ValueError('Command stage is already running; explicitly end an abandoned stage as failed before retrying')
    identity = {'task_id': args.task_id, 'attempt_id': args.attempt_id}
    prior = begin(args.work_dir, args.stage, args.input, args.unit_id, command, **identity)
    try:
        completed = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', shell=False)
        if completed.returncode:
            result = end(args.work_dir, args.stage, (), args.unit_id, status='failed', error=completed.stderr[-3000:], **identity)
        else:
            result = end(args.work_dir, args.stage, args.artifact, args.unit_id, **identity)
        return {'returnCode': completed.returncode, 'reused': False, 'stage': result, 'stdoutTail': completed.stdout[-4000:], 'stderrTail': completed.stderr[-3000:]}
    except (OSError, ValueError) as exc:
        # Keep artifacts from a failed command; recovery validates them explicitly.
        if read_json(state).get('status') == 'running':
            end(args.work_dir, args.stage, (), args.unit_id, status='failed', error=str(exc), **identity)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest='operation', required=True)
    p = subs.add_parser('preflight'); p.add_argument('--input', action='append', default=[], type=Path); p.add_argument('--output', type=Path)
    p = subs.add_parser('validate-unit'); p.add_argument('record', type=Path); p.add_argument('--knowledge-base', '-k', required=True, type=Path)
    p = subs.add_parser('assemble'); p.add_argument('project', type=Path); p.add_argument('--knowledge-base', '-k', required=True, type=Path); p.add_argument('--output-page', required=True, type=Path)
    p = subs.add_parser('checkpoint'); p.add_argument('record', type=Path); p.add_argument('--knowledge-base', '-k', required=True, type=Path); p.add_argument('--work-dir', required=True, type=Path)
    p = subs.add_parser('freeze-acceptance'); p.add_argument('--input', action='append', required=True, type=Path); p.add_argument('--output', required=True, type=Path)
    p = subs.add_parser('check-acceptance'); p.add_argument('snapshot', type=Path); p.add_argument('--output', type=Path)
    for name in ('status', 'resume', 'finish'):
        p = subs.add_parser(name); p.add_argument('--work-dir', required=True, type=Path); p.add_argument('--output', type=Path)
    for name in ('begin', 'end', 'run'):
        p = subs.add_parser(name); p.add_argument('--work-dir', required=True, type=Path); p.add_argument('--stage', choices=STAGES, required=True); p.add_argument('--unit-id')
        p.add_argument('--task-id'); p.add_argument('--attempt-id')
        if name in ('begin', 'run'):
            p.add_argument('--input', action='append', default=[], type=Path)
        if name == 'begin':
            p.add_argument('--model-label')
        if name in ('end', 'run'):
            p.add_argument('--artifact', action='append', default=[], type=Path)
        if name == 'end':
            p.add_argument('--status', choices=('succeeded', 'draft-ready', 'failed'), default='succeeded'); p.add_argument('--error')
        if name == 'run':
            p.add_argument('--reuse', action='store_true'); p.add_argument('command', nargs=argparse.REMAINDER)
    p = subs.add_parser('wait-begin'); p.add_argument('--work-dir', required=True, type=Path); p.add_argument('--reason', required=True); p.add_argument('--wait-id'); p.add_argument('--task-id')
    p = subs.add_parser('wait-end'); p.add_argument('--work-dir', required=True, type=Path); p.add_argument('--wait-id', required=True)
    args = parser.parse_args()
    try:
        if args.operation == 'preflight':
            result = preflight(args.input)
            if args.output:
                write_changed(args.output, json_text(result))
        elif args.operation == 'validate-unit':
            result = validate_unit(args.record, args.knowledge_base)
        elif args.operation == 'assemble':
            result = assemble(args.project, args.knowledge_base, args.output_page)
        elif args.operation == 'checkpoint':
            result = checkpoint(args.record, args.knowledge_base, args.work_dir)
        elif args.operation == 'freeze-acceptance':
            from acceptance_snapshot import freeze
            result = freeze(args.input, args.output)
        elif args.operation == 'check-acceptance':
            from acceptance_snapshot import check
            result = check(args.snapshot, args.output)
        elif args.operation == 'begin':
            result = begin(args.work_dir, args.stage, args.input, args.unit_id, model_label=args.model_label, task_id=args.task_id, attempt_id=args.attempt_id)
        elif args.operation == 'end':
            result = end(args.work_dir, args.stage, args.artifact, args.unit_id, status=args.status, error=args.error, task_id=args.task_id, attempt_id=args.attempt_id)
        elif args.operation == 'run':
            result = run_command(args)
        elif args.operation == 'wait-begin':
            result = wait_begin(args.work_dir, args.reason, args.wait_id, task_id=args.task_id)
        elif args.operation == 'wait-end':
            result = wait_end(args.work_dir, args.wait_id)
        else:
            result = finish(args.work_dir) if args.operation == 'finish' else report(args.work_dir)
            if args.output:
                write_changed(args.output, json_text(result))
        print(json_text(result), end='')
        if result.get('status') == 'failed' or result.get('returnCode', 0):
            return 2
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    from cli_output import configure_output
    configure_output()
    sys.exit(main())
