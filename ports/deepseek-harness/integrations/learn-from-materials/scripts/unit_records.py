"""Compile explicit source-first unit records; never infer facts or review results."""
from __future__ import annotations

import copy
import hashlib
import re
from pathlib import Path

from workflow_io import read_json, json_text, write_changed
from verify_coverage import stable_source_key, SUMMARY_CLAIM_KINDS

UNIT_SCHEMA = 'learn-from-materials/unit-record-v1'
PROJECT_SCHEMA = 'learn-from-materials/authoring-project-v1'
UNIT_SCHEMA_V2 = 'learn-from-materials/unit-record-v2'
PROJECT_SCHEMA_V2 = 'learn-from-materials/authoring-project-v2'
IDENTIFIER = re.compile(r'^[A-Za-z][A-Za-z0-9_-]*$')
ENTITY_KEYS = ('frameworks', 'glossary', 'decisionRules', 'focusAreas')
SECTION_KEYS = ('mentalModels', 'antiPatterns', 'workedExamples', 'connections')
ENTITY_FIELDS = {
    'frameworks': ({'id', 'name', 'oneLine', 'when', 'firstUnitId', 'source'}, {'sourceOrder'}),
    'glossary': ({'id', 'term', 'category', 'definition', 'context', 'related', 'units', 'firstUnitId', 'source'}, {'fullName', 'zhMeaning', 'sourceOrder'}),
    'decisionRules': ({'id', 'when', 'do', 'because', 'source'}, set()),
    'focusAreas': ({'id', 'title', 'unitId', 'abilities', 'source'}, set()),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


class Sources:
    """Load a source corpus once for all unit validations in a build."""
    def __init__(self, kb):
        self.kb = Path(kb).resolve()
        self.raw = (self.kb / 'full_text.txt').read_text(encoding='utf-8')
        blocks = read_json(self.kb / 'source_map.json')
        require(isinstance(blocks, list), 'source_map must be an array')
        self.blocks = {}
        self.passages = {}
        for block in blocks:
            sid = block.get('source_id')
            start, end = block.get('start_char'), block.get('end_char')
            require(text(sid) and sid not in self.blocks, 'Duplicate/missing source ID')
            require(type(start) is int and type(end) is int and 0 <= start <= end <= len(self.raw), 'Invalid source span: ' + sid)
            passage = self.raw[start:end]
            require(hashlib.sha256(passage.encode('utf-8')).hexdigest() == block.get('content_sha256'), 'Source text hash mismatch: ' + sid)
            self.blocks[sid] = block
            self.passages[sid] = passage

    def evidence(self, items, allowed, label):
        require(isinstance(items, list) and items, label + ': evidence required')
        used = set()
        for item in items:
            require(isinstance(item, dict), label + ': evidence must be an object')
            sid = item.get('sourceId')
            require(sid in allowed and sid in self.blocks, label + ': unknown or wrong-unit source')
            require(text(item.get('quote')), label + ': exact quote/transcription required')
            if item.get('kind') == 'text':
                require(item['quote'] in self.passages[sid], label + ': quote absent from source')
            elif item.get('kind') == 'visual':
                relative = item.get('artifact')
                require(text(relative) and not Path(relative).is_absolute(), label + ': relative image path required')
                image = (self.kb / relative).resolve()
                require(image.is_relative_to(self.kb) and image.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'} and image.is_file(), label + ': missing/unsafe image')
                require(hashlib.sha256(image.read_bytes()).hexdigest() == item.get('sha256') and text(item.get('note')), label + ': visual evidence hash/note mismatch')
            else:
                raise ValueError(label + ': evidence kind must be text or visual')
            used.add(sid)
        return used


def compile_unit(record, corpus):
    allowed = {'schemaVersion', 'unit', 'sources', 'claims', 'sections', 'ruleReview', 'ruleCandidates', *ENTITY_KEYS}
    modern = isinstance(record, dict) and record.get('schemaVersion') == UNIT_SCHEMA_V2
    if modern:
        allowed |= {'frameworkCandidates', 'relationSearch', 'relationCandidates'}
    require(isinstance(record, dict) and not set(record) - allowed, 'Unknown unit-record fields')
    require(record.get('schemaVersion') in {UNIT_SCHEMA, UNIT_SCHEMA_V2}, 'Unsupported unit-record schema')
    unit = record.get('unit')
    require(isinstance(unit, dict) and set(unit) == {'id', 'label', 'title', 'source', 'core', 'frameworks', 'takeaways', 'conclusions'}, 'unit fields must match the authoring contract')
    uid = unit['id']
    require(isinstance(uid, str) and IDENTIFIER.fullmatch(uid), 'Invalid unit ID')
    require(all(text(unit.get(k)) for k in ('label', 'title', 'source')), uid + ': label/title/source required')
    source_rows = record.get('sources')
    require(isinstance(source_rows, list) and source_rows, uid + ': source rows required')
    source_ids, covered_ids = set(), set()
    for row in source_rows:
        require(isinstance(row, dict) and set(row) == {'sourceId', 'status', 'reason'}, uid + ': source rows require sourceId/status/reason')
        sid = row['sourceId']
        require(sid in corpus.blocks and sid not in source_ids, uid + ': duplicate/unknown source ID')
        require(row['status'] in {'covered', 'no-content', 'duplicate', 'unreadable'} and text(row['reason']), uid + ': explicit source status/reason required')
        source_ids.add(sid)
        if row['status'] == 'covered':
            covered_ids.add(sid)
    refs, leaves = {}, {}

    def leaf(item, target):
        require(isinstance(item, dict) and set(item) == {'id', 'text'}, uid + ': display leaves require only id/text')
        lid = item['id']
        require(isinstance(lid, str) and IDENTIFIER.fullmatch(lid) and lid not in refs and text(item['text']), uid + ': invalid/duplicate display ID')
        refs[lid], leaves[lid] = 'unit:' + uid + ':' + target, item['text']
        return item['text']

    display = {key: unit[key] for key in ('id', 'label', 'title', 'source')}
    display['core'] = leaf(unit['core'], 'core')
    for key, singular in (('frameworks', 'framework'), ('takeaways', 'takeaway')):
        require(isinstance(unit[key], list) and unit[key], uid + ': nonempty ' + key + ' required')
        display[key] = [leaf(item, singular + ':' + str(i)) for i, item in enumerate(unit[key])]
    require(isinstance(unit['conclusions'], list) and unit['conclusions'], uid + ': conclusions required')
    display['conclusions'] = []
    for i, group in enumerate(unit['conclusions']):
        require(isinstance(group, dict) and set(group) == {'title', 'source', 'summary', 'points'} and text(group['title']) and text(group['source']), uid + ': conclusion fields invalid')
        require(isinstance(group['points'], list) and group['points'], uid + ': conclusion points required')
        prefix = 'conclusion:' + str(i) + ':'
        display['conclusions'].append({'title': group['title'], 'source': group['source'], 'summary': leaf(group['summary'], prefix + 'summary'), 'points': [leaf(item, prefix + 'point:' + str(j)) for j, item in enumerate(group['points'])]})
    sections = record.get('sections')
    require(isinstance(sections, dict) and set(sections) == set(SECTION_KEYS), uid + ': all four descriptive sections are required')
    require(all(isinstance(sections[k], list) and sections[k] and all(text(v) for v in sections[k]) for k in SECTION_KEYS), uid + ': provide section content or an explicit material-specific absence reason')
    claims, by_source, by_leaf = [], {sid: [] for sid in covered_ids}, {lid: [] for lid in refs}
    seen_claims = set()
    require(isinstance(record.get('claims'), list) and record['claims'], uid + ': claims required')
    for claim in record['claims']:
        require(isinstance(claim, dict) and set(claim) == {'id', 'kind', 'text', 'source', 'sourceIds', 'contentIds', 'evidence'}, uid + ': claim fields invalid')
        cid = claim['id']
        require(isinstance(cid, str) and IDENTIFIER.fullmatch(cid) and cid not in seen_claims, uid + ': duplicate/invalid claim ID')
        seen_claims.add(cid)
        require(claim['kind'] in SUMMARY_CLAIM_KINDS and text(claim['text']) and text(claim['source']), cid + ': kind/text/source invalid')
        sids, lids = claim['sourceIds'], claim['contentIds']
        require(isinstance(sids, list) and sids and len(sids) == len(set(sids)) and set(sids) <= covered_ids, cid + ': claim sources must be covered by this unit')
        require(isinstance(lids, list) and lids and len(lids) == len(set(lids)) and set(lids) <= refs.keys(), cid + ': unknown/repeated display ID')
        used = corpus.evidence(claim['evidence'], set(sids), cid)
        require(set(sids) == used, cid + ': each declared source needs evidence')
        claims.append({'id': cid, 'unitId': uid, 'kind': claim['kind'], 'text': claim['text'], 'source': claim['source'], 'summaryRefs': [refs[lid] for lid in lids]})
        for sid in sids:
            by_source[sid].append(cid)
        for lid in lids:
            by_leaf[lid].append(claim['source'])
    require(all(by_source.values()), uid + ': covered block without a claim; record a justified non-content status instead')
    require(all(by_leaf.values()), uid + ': visible content without source claims')
    def source_for(item):
        return '; '.join(dict.fromkeys(by_leaf[item['id']]))
    display['sourceDetails'] = {'core': source_for(unit['core']), 'frameworks': [source_for(x) for x in unit['frameworks']], 'takeaways': [source_for(x) for x in unit['takeaways']], 'conclusions': [{'summary': source_for(g['summary']), 'points': [source_for(x) for x in g['points']]} for g in unit['conclusions']]}
    entities = {}
    for key in ENTITY_KEYS:
        values = record.get(key)
        require(isinstance(values, list), uid + ': ' + key + ' must be an array')
        seen = set()
        for value in values:
            require(isinstance(value, dict) and isinstance(value.get('id'), str) and IDENTIFIER.fullmatch(value['id']) and value['id'] not in seen, uid + ': invalid/duplicate entity ID in ' + key)
            required, optional = ENTITY_FIELDS[key]
            require(required <= value.keys() and not value.keys() - required - optional, uid + ': missing/unknown entity fields in ' + key)
            require(all(text(value[name]) for name in required - {'related', 'units', 'abilities'}), uid + ': nonempty entity text required in ' + key)
            if key in ('frameworks', 'glossary'):
                require(value['firstUnitId'] == uid, uid + ': put canonical entities in their first introducing unit')
            for name in ('related', 'units', 'abilities'):
                if name in value:
                    require(isinstance(value[name], list) and value[name] and all(text(x) for x in value[name]), uid + ': nonempty ' + name + ' array required')
            if key == 'glossary':
                require(uid in value['units'], uid + ': glossary units must include its introducing unit')
            if key == 'focusAreas':
                require(value['unitId'] == uid and set(value['abilities']) <= {'记忆', '解释', '应用', '迁移', 'Recall', 'Explain', 'Apply', 'Transfer'}, uid + ': assessment unit/abilities invalid')
            seen.add(value['id'])
        entities[key] = copy.deepcopy(values)
    review = record.get('ruleReview')
    require(isinstance(review, dict) and set(review) == {'unitId', 'status', 'reviewedSourceIds', 'note'} and review['unitId'] == uid, uid + ': explicit ruleReview required')
    require(review['status'] in {'pending', 'reviewed', 'no-rules'} and text(review['note']), uid + ': ruleReview status/note invalid')
    require(isinstance(review['reviewedSourceIds'], list) and len(review['reviewedSourceIds']) == len(set(review['reviewedSourceIds'])) and set(review['reviewedSourceIds']) <= covered_ids, uid + ': invalid rule review sources')
    if review['status'] != 'pending':
        require(set(review['reviewedSourceIds']) == covered_ids, uid + ': completed rule review must include every covered block')
    candidates = record.get('ruleCandidates')
    require(isinstance(candidates, list), uid + ': ruleCandidates array required')
    for candidate in candidates:
        require(isinstance(candidate, dict) and candidate.get('unitId') == uid, uid + ': wrong-unit rule candidate')
        sids = candidate.get('sourceIds')
        require(isinstance(sids, list) and sids and set(sids) <= covered_ids and text(candidate.get('quote')), uid + ': invalid candidate evidence')
        require(any(candidate['quote'] in corpus.passages[sid] for sid in sids), uid + ': candidate quote absent')
    audit = [{'sourceId': row['sourceId'], 'status': row['status'], 'reason': row['reason'], 'mappedUnits': [uid] if row['status'] == 'covered' else [], 'mappedClaims': by_source.get(row['sourceId'], [])} for row in source_rows]
    if modern:
        from relation_ledger import validate_unit_inventory
        validate_unit_inventory(record, corpus, publication=False)
    return {'unit': display, 'claims': claims, 'sourceBlocks': audit, 'entities': entities, 'ruleReview': copy.deepcopy(review), 'ruleCandidates': copy.deepcopy(candidates), 'leafIds': list(refs), 'sections': sections}


def unit_markdown(compiled, language='en'):
    unit, entities = compiled['unit'], compiled['entities']
    titles = {'Core Idea': '核心思想', 'Frameworks Introduced': '本章框架', 'Key Concepts': '关键概念', 'Mental Models': '结构与因果关系', 'Anti-patterns': '反例与错误做法', 'Worked Example': '材料案例', 'Key Takeaways': '行动要点', 'Expandable Conclusions': '完整展开结论', 'Connects To': '前后联系', 'Source Range': '原文范围'}
    def heading(title):
        return '## ' + (titles[title] + ' / ' + title if language == 'zh-CN' else title)
    lines = ['# ' + unit['title'], '', heading('Core Idea'), '', unit['core'], '', heading('Frameworks Introduced'), '']
    lines += ['- ' + x for x in unit['frameworks']]
    for item in entities['frameworks']:
        lines += ['', '### ' + item['name'], '', item['oneLine'], '', item['when'], '', item['source']]
    lines += ['', heading('Key Concepts'), '']
    lines += ['- ' + x['term'] + (' (' + x['fullName'] + ')' if x.get('fullName') else '') + (' · ' + x['zhMeaning'] if x.get('zhMeaning') else '') + ': ' + x['definition'] + ' — ' + x['context'] + ' (' + x['source'] + ')' for x in entities['glossary']]
    for key, heading in [('mentalModels', 'Mental Models'), ('antiPatterns', 'Anti-patterns'), ('workedExamples', 'Worked Example')]:
        lines += ['', '## ' + (titles[heading] + ' / ' + heading if language == 'zh-CN' else heading), ''] + ['- ' + x for x in compiled['sections'][key]]
    lines += ['', '## ' + (titles['Key Takeaways'] + ' / Key Takeaways' if language == 'zh-CN' else 'Key Takeaways'), ''] + ['- ' + x for x in unit['takeaways']]
    lines += ['', '## ' + (titles['Expandable Conclusions'] + ' / Expandable Conclusions' if language == 'zh-CN' else 'Expandable Conclusions'), '']
    for group in unit['conclusions']:
        lines += ['### ' + group['title'], '', group['summary'], ''] + ['- ' + x for x in group['points']] + ['', group['source'], '']
    lines += ['## ' + (titles['Connects To'] + ' / Connects To' if language == 'zh-CN' else 'Connects To'), ''] + ['- ' + x for x in compiled['sections']['connections']] + ['', '## ' + (titles['Source Range'] + ' / Source Range' if language == 'zh-CN' else 'Source Range'), '', unit['source'], '']
    return '\n'.join(lines)


def checked_unit_exports(page, kb):
    """Bind new records to their displayed units and deterministically export prose."""
    kb = Path(kb)
    files = sorted((kb / 'unit-records').glob('*.json'))
    if not files:
        return {}
    corpus = Sources(kb)
    expected = {u['id']: u for u in page['contentUnits']}
    exports, seen = {}, set()
    for path in files:
        item = compile_unit(read_json(path), corpus)
        uid = item['unit']['id']
        require(uid not in seen and uid in expected and item['unit'] == expected[uid], 'Missing/stale unit-record snapshot: ' + uid)
        seen.add(uid)
        exports['units/' + uid + '.md'] = unit_markdown(item, page['meta'].get('language', 'zh-CN'))
    require(seen == expected.keys(), 'New authoring deliveries require records for every unit')
    return exports


def assemble(project_file, kb, output_page):
    """Build existing contracts from explicit records; publication stays gated."""
    project_file, kb = Path(project_file).resolve(), Path(kb).resolve()
    project = read_json(project_file)
    modern = isinstance(project, dict) and project.get('schemaVersion') == PROJECT_SCHEMA_V2
    fields = {'schemaVersion', 'page', 'unitFiles', 'coverage', 'summaryCheck', 'actionRules'} | ({'relations'} if modern else set())
    require(isinstance(project, dict) and set(project) == fields, 'Authoring project fields invalid')
    require(project['schemaVersion'] in {PROJECT_SCHEMA, PROJECT_SCHEMA_V2}, 'Unsupported authoring-project schema')
    page = copy.deepcopy(project['page'])
    forbidden = {'contentUnits', 'frameworks', 'glossary', 'decisionRules', 'assessment', 'methodLibrary', 'methodology'}
    require(not set(page) & forbidden, 'Project page must not duplicate generated content or canonical method snapshots')
    require(page.get('schemaVersion') == '4.3' and page.get('meta', {}).get('learningDepth') == 'systematic' and page['meta'].get('mode') == 'overview', 'Unit compilation is for new schema-4.3 systematic overviews')
    require(isinstance(project['unitFiles'], list) and project['unitFiles'], 'unitFiles required in original material order')
    corpus = Sources(kb)
    compiled, records, paths = [], [], []
    for name in project['unitFiles']:
        require(text(name) and not Path(name).is_absolute(), 'unitFiles must use relative paths')
        path = (project_file.parent / name).resolve()
        require(path.is_relative_to(project_file.parent) and path not in paths, 'Unsafe or repeated unit file')
        record = read_json(path)
        require((record.get('schemaVersion') == UNIT_SCHEMA_V2) == modern, 'Do not mix unit/project contract versions')
        compiled.append(compile_unit(record, corpus)); records.append(record); paths.append(path)
    seen_units, seen_claims, seen_leaves, seen_entities = set(), set(), set(), set()
    page.update(contentUnits=[], frameworks=[], glossary=[], decisionRules=[], assessment={'focusAreas': []})
    claims, block_rows = [], {}
    for item in compiled:
        uid = item['unit']['id']
        require(uid not in seen_units, 'Duplicate unit ID: ' + uid); seen_units.add(uid)
        require(not seen_claims.intersection(x['id'] for x in item['claims']), 'Duplicate claim IDs across units')
        require(not seen_leaves.intersection(item['leafIds']), 'Display IDs must be unique across units')
        seen_claims.update(x['id'] for x in item['claims']); seen_leaves.update(item['leafIds'])
        page['contentUnits'].append(item['unit']); claims.extend(item['claims'])
        for key in ENTITY_KEYS:
            for value in item['entities'][key]:
                require(value['id'] not in seen_entities, 'Entity IDs must be globally unique; explicitly merge equivalent entries before compiling: ' + value['id'])
                seen_entities.add(value['id'])
                (page['assessment']['focusAreas'] if key == 'focusAreas' else page[key]).append(value)
        for row in item['sourceBlocks']:
            sid = row['sourceId']
            if sid not in block_rows:
                block_rows[sid] = copy.deepcopy(row)
            else:
                target = block_rows[sid]
                require(target['status'] == row['status'], 'Conflicting source dispositions: ' + sid)
                for key in ('mappedUnits', 'mappedClaims'):
                    target[key] = list(dict.fromkeys(target[key] + row[key]))
                if row['reason'] not in target['reason']:
                    target['reason'] += '; ' + row['reason']
    require(set(block_rows) == corpus.blocks.keys(), 'Every source block needs an explicit disposition; missing: ' + ', '.join(sorted(corpus.blocks.keys() - block_rows.keys())[:8]))
    for key in ('frameworks', 'glossary'):
        for index, value in enumerate(page[key], 1):
            value['sourceOrder'] = index
    for index, claim in enumerate(claims, 1):
        claim['sourceOrder'] = index
    rows = [block_rows[sid] for sid in corpus.blocks]
    summary = {'schemaVersion': 'knowledge-learning-assistant-summary-ledger/v1', 'claims': claims, 'exclusions': [{'source': corpus.blocks[r['sourceId']].get('locator', r['sourceId']), 'reason': r['reason']} for r in rows if r['status'] != 'covered'], 'finalCheck': copy.deepcopy(project['summaryCheck'])}
    coverage = copy.deepcopy(project['coverage'])
    require(set(coverage) == {'sources', 'finalCheck'}, 'coverage must explicitly supply sources/finalCheck')
    coverage.update(schemaVersion='1.1', learningDepth='systematic', sourceBlocks=rows)
    ledger = copy.deepcopy(project['actionRules'])
    require(not {'units', 'candidates'} & set(ledger), 'Action-rule units/candidates come from unit records')
    ledger.update(schemaVersion='learn-from-materials/action-rule-ledger-v2', pageId=page['meta']['pageId'], learningDepth='systematic', units=[x['ruleReview'] for x in compiled], candidates=[c for x in compiled for c in x['ruleCandidates']])
    dependencies = []
    for row in rows:
        sid = row['sourceId']; block = corpus.blocks[sid]
        derived = []
        for item in compiled:
            if item['unit']['id'] not in row['mappedUnits']:
                continue
            for key, prefix in [('frameworks', 'framework'), ('glossary', 'term'), ('decisionRules', 'rule'), ('focusAreas', 'assessment')]:
                derived.extend(prefix + ':' + v['id'] for v in item['entities'][key])
        dependencies.append({'sourceKey': stable_source_key(block), 'contentHash': block['content_sha256'], 'unitIds': row['mappedUnits'], 'claimIds': row['mappedClaims'], 'derivedRefs': list(dict.fromkeys(derived))})
    # Existing binders remain the only source of page method-card snapshots.
    from methods import bind, validate_library
    from methodology import validate as validate_methodology
    from render_page import validate
    from delivery import check_canonical
    page = bind(page, validate_library(read_json(kb / 'methods.json'), kb))
    page['methodology'] = read_json(kb / 'methodology.json')
    validate_methodology(page['methodology'], page, kb)
    validate(page)
    exports = check_canonical(page, kb, include_units=False)
    writes = {Path(output_page): json_text(page), kb / 'summary-ledger.json': json_text(summary), kb / 'coverage-audit.json': json_text(coverage), kb / 'action-rule-ledger.json': json_text(ledger), kb / 'unit-dependency-map.json': json_text({'schemaVersion': 'learn-from-materials/unit-dependency-map-v1', 'pageId': page['meta']['pageId'], 'entries': dependencies})}
    if modern:
        from relation_ledger import assemble_ledger, validate as validate_relations
        relations = assemble_ledger(page, records, project['relations'])
        validate_relations(relations, page, kb, records=records, publication=False)
        writes[kb / 'relation-ledger.json'] = json_text(relations)
    for record, item in zip(records, compiled):
        uid = item['unit']['id']
        writes[kb / 'units' / (uid + '.md')] = unit_markdown(item, page['meta'].get('language', 'zh-CN'))
        writes[kb / 'unit-records' / (uid + '.json')] = json_text(record)
    en = page['meta'].get('language') == 'en'
    def label(zh, english):
        return english if en else zh
    index = ['# ' + page['meta']['title'], ''] + ['- [' + x['unit']['title'] + '](units/' + x['unit']['id'] + '.md)' for x in compiled]
    index += ['', '- [' + label('整体方法论', 'Whole-material methodology') + '](methodology.md)', '- [' + label('可复用方法卡', 'Reusable methods') + '](patterns.md)', '- [' + label('术语', 'Glossary') + '](glossary.md)', '- [' + label('覆盖审计', 'Coverage audit') + '](coverage-audit.md)', '']
    writes[kb / 'INDEX.md'] = '\n'.join(index)
    terms = ['# ' + label('术语', 'Glossary'), '']
    for item in page['glossary']:
        terms += ['## ' + item['term'], '', item['definition'], '', item['context'], '']
        for key, title in [('fullName', label('英文全称', 'Full name')), ('zhMeaning', label('中文含义', 'Chinese meaning'))]:
            if item.get(key): terms += [title + ': ' + item[key], '']
        terms += [label('分类', 'Category') + ': ' + item['category'], label('相关概念', 'Related') + ': ' + ', '.join(item['related']), label('关联单元', 'Units') + ': ' + ', '.join(item['units']), '', item['source'], '']
    writes[kb / 'glossary.md'] = '\n'.join(terms)
    writes[kb / 'cheatsheet.md'] = '# ' + label('框架与行动规则', 'Frameworks and action rules') + '\n\n' + '\n\n'.join('## ' + x['name'] + '\n\n' + x['oneLine'] + '\n\n' + x['when'] + '\n\n' + x['source'] for x in page['frameworks']) + '\n\n' + '\n\n'.join(x['when'] + ' → ' + x['do'] + '\n\n' + x['because'] + '\n\n' + x['source'] for x in page['decisionRules']) + '\n'
    writes[kb / 'practice.md'] = '# ' + label('学习自检考点', 'Assessment focus areas') + '\n\n' + '\n\n'.join('## ' + x['title'] + '\n\n' + x['unitId'] + ' · ' + ', '.join(x['abilities']) + '\n\n' + x['source'] for x in page['assessment']['focusAreas']) + '\n'
    audit_md = ['# ' + label('覆盖审计', 'Coverage audit'), '', label('映射由脚本组装；语义复核另有独立记录。', 'Structural mappings are compiled; semantic review is recorded separately.'), '']
    for source in coverage['sources']:
        audit_md += ['## ' + source['filename'], '', source['status'] + ': ' + source['reason'], '']
    for row in rows:
        audit_md += ['- ' + row['sourceId'] + ' · ' + row['status'] + ' · ' + ', '.join(row['mappedUnits']) + ' · ' + row['reason']]
    for item in compiled:
        audit_md += ['', '## ' + item['unit']['title'] + ': ' + label('方法候选', 'Method candidates'), '', item['ruleReview']['note']]
        for candidate in item['ruleCandidates']:
            audit_md += ['- ' + candidate['id'] + ' → ' + str(candidate.get('targetRuleId')) + ' · ' + candidate.get('status', 'pending') + ' · ' + candidate.get('reason', '')]
    writes[kb / 'coverage-audit.md'] = '\n'.join(audit_md) + '\n'
    for name, content in exports.items():
        writes[kb / name] = content
    # Validate the entire assembled object before committing any derived output.
    changed = [str(path) for path, content in writes.items() if write_changed(path, content)]
    return {'page': str(Path(output_page).resolve()), 'units': len(compiled), 'claims': len(claims), 'changedFiles': changed, 'status': 'assembled-not-published', 'semanticReview': 'not-attested-by-compiler'}
