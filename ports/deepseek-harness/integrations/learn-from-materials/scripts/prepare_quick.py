"""Validate quick content, then derive compact indexes without model rewrites."""
import argparse
from pathlib import Path
from render_page import validate
from verify_coverage import load_json
from verify_quick import verify_quick


def prepare(page: Path, kb: Path) -> None:
    data = load_json(page)
    validate(data)
    en = data['meta'].get('language') == 'en'
    if data['meta']['learningDepth'] != 'quick':
        raise ValueError('prepare_quick only accepts quick mode' if en else 'prepare_quick 仅用于 quick 模式')
    errors = verify_quick(data, kb)
    if errors:
        raise ValueError('\n'.join(errors))
    audit = load_json(kb / 'quick-audit.json')
    index = ['# ' + data['meta']['title'], '',
             'Focused overview, not exhaustive coverage.' if en else '核心导读，非全量知识整理。',
             'Original: full_text.txt; Sources: source_map.json; Limits: coverage-audit.md' if en else '原文：full_text.txt；出处：source_map.json；限制：coverage-audit.md',
             'No question bank is prebuilt here. Check existing questions in the selected scope when starting a quiz.' if en else '题库未在此步骤预建；启动测验时检查所选范围原题。', '']
    for unit in data.get('contentUnits', []):
        index.extend(['## ' + unit['id'] + ' · ' + unit['title'], unit['core'], unit['source'], ''])
    (kb / 'INDEX.md').write_text('\n'.join(index), encoding='utf-8')
    lines = ['# Quick overview coverage' if en else '# 快速导读范围说明', '', *audit['limitations'], '']
    statuses = {'scanned': 'Scanned', 'unreadable': 'Unreadable'} if en else {'scanned': '已扫描', 'unreadable': '无法读取'}
    separator = ': ' if en else '：'
    for group in audit['structure']:
        lines.extend(['## ' + group['title'], statuses[group['status']] + separator + group['note'], ''])
    (kb / 'coverage-audit.md').write_text('\n'.join(lines), encoding='utf-8')


if __name__ == '__main__':
    from cli_output import configure_output
    configure_output()
    parser = argparse.ArgumentParser()
    parser.add_argument('page', type=Path)
    parser.add_argument('--knowledge-base', '-k', type=Path, required=True)
    args = parser.parse_args()
    try:
        prepare(args.page, args.knowledge_base)
    except (ValueError, OSError) as exc:
        parser.exit(2, str(exc) + '\n')
    en = load_json(args.page)['meta'].get('language') == 'en'
    print('Quick overview validation and index generation complete' if en else '快速导读校验与索引生成完成')
