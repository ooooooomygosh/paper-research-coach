"""Scoped source-first review snapshots and final integration checks.

Snapshots and assembly are mechanical: these helpers never invent semantic
judgments, evidence quotations, reviewer identities, or completion flags.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
from pathlib import Path

from content_review import SCHEMA_V2, SCHEMA_V3, digest, fingerprints, ids, text, validate_evidence
from unit_records import Sources, compile_unit, require
from workflow_io import json_text, read_json, write_changed

UNIT_SCHEMA = 'learn-from-materials/unit-content-review-v1'
UNIT_SCHEMA_V2 = 'learn-from-materials/unit-content-review-v2'
RECORD_SCHEMA_V2 = 'learn-from-materials/unit-record-v2'
GLOBAL_SCHEMA = 'learn-from-materials/global-content-review-v1'
GLOBAL_CHECKS = {'coverage', 'crossUnitRelations', 'deduplication', 'methods', 'methodology'}


class ScopedSources(Sources):
    """Validate selected actual slices without making other units prerequisites."""
    def __init__(self, kb, source_ids):
        self.kb = Path(kb).resolve()
        self.raw = (self.kb / 'full_text.txt').read_text(encoding='utf-8')
        rows = read_json(self.kb / 'source_map.json')
        require(isinstance(rows, list), 'source_map must be an array')
        require(all(isinstance(b, dict) and text(b.get('source_id')) for b in rows), 'Invalid source map')
        mapped = {b['source_id']: b for b in rows}
        require(len(mapped) == len(rows), 'Duplicate source IDs')
        require(set(source_ids) <= mapped.keys(), 'Unknown local source ID')
        self.blocks, self.passages = {}, {}
        for sid in sorted(source_ids):
            block = mapped[sid]
            start, end = block.get('start_char'), block.get('end_char')
            require(type(start) is int and type(end) is int and 0 <= start <= end <= len(self.raw), 'Invalid source span: ' + sid)
            passage = self.raw[start:end]
            require(hashlib.sha256(passage.encode('utf-8')).hexdigest() == block.get('content_sha256'), 'Source text hash mismatch: ' + sid)
            self.blocks[sid], self.passages[sid] = block, passage


def scoped_methods(record, kb, methods=None):
    """Include node-linked and source-linked cards, including cross-unit cards."""
    if methods is None:
        path = Path(kb) / 'methods.json'
        methods = read_json(path) if path.is_file() else None
    if methods is None:
        return []
    from methods import validate_library
    validate_library(methods)
    entity_ids = {e['id'] for key in ('frameworks', 'decisionRules') for e in record.get(key, [])}
    source_ids = {r['sourceId'] for r in record['sources']}
    return sorted((copy.deepcopy(card) for card in methods['methods']
                   if card['id'] in entity_ids or any(source_ids.intersection(s['sourceIds']) for s in card['sources'])),
                  key=lambda card: card['id'])


def _context(record, kb, methods=None):
    require(isinstance(record, dict), 'Unit record must be an object')
    require(isinstance(record.get('sources'), list) and all(isinstance(r, dict) and text(r.get('sourceId')) for r in record['sources']), 'Invalid unit source rows')
    if methods is None and (Path(kb) / 'methods.json').is_file():
        methods = read_json(Path(kb) / 'methods.json')
    cards = scoped_methods(record, kb, methods)
    own_sources = {r['sourceId'] for r in record['sources']}
    source_ids = own_sources | {sid for card in cards for s in card['sources'] for sid in s['sourceIds']}
    corpus = ScopedSources(kb, source_ids)
    compiled = compile_unit(record, corpus)
    for card in cards:
        for source in card['sources']:
            require(any(source['quote'] in corpus.passages[sid] for sid in source['sourceIds']),
                    'Method evidence quote absent from associated sources: ' + card['id'])
    associations = {'libraryId': methods['libraryId'] if cards else None, 'cards': cards}
    return corpus, compiled, associations, own_sources


def snapshot(record, kb, methods=None):
    """Return dependency hashes only; a valid draft is not a reviewed draft.

    Absolute character offsets are omitted from the local dependency identity:
    inserting unrelated text before this unit need not force a reread when its
    actual passage, locator and all other source metadata remain identical.
    """
    corpus, _, cards, _ = _context(record, kb, methods)
    return _snapshot_context(record, corpus, cards)


def _snapshot_context(record, corpus, cards):
    sources = {}
    for sid, block in corpus.blocks.items():
        stable = {k: v for k, v in block.items() if k not in {'start_char', 'end_char'}}
        sources[sid] = digest({'block': stable, 'text': corpus.passages[sid]})
    return {'record': digest(record), 'sources': sources, 'methods': digest(cards)}


def validate_unit(review, record, kb, methods=None):
    """Check one authored review before or after whole-page assembly."""
    errors = []
    def need(ok, message):
        if not ok:
            errors.append('unit-review: ' + message)
        return ok
    required = {'schemaVersion', 'unitId', 'executionMode', 'authorId', 'reviewerId',
                'reviewedInputs', 'sourceFirst', 'unitReview', 'claimReviews', 'ruleReviews', 'enumeratedLists'}
    is_v2 = isinstance(record, dict) and record.get('schemaVersion') == RECORD_SCHEMA_V2
    if is_v2:
        required.add('structureReview')
    if not need(isinstance(review, dict) and set(review) == required, 'missing or unexpected fields'):
        return errors
    try:
        corpus, compiled, cards, own_sources = _context(record, kb, methods)
        uid = compiled['unit']['id']
        need(review['schemaVersion'] == (UNIT_SCHEMA_V2 if is_v2 else UNIT_SCHEMA),
             'unit record/review schema mismatch; v2 requires v2 review and vice versa')
        need(review['unitId'] == uid, 'unitId mismatch')
        need(review['executionMode'] in {'parallel', 'sequential'}, 'executionMode must be parallel/sequential')
        need(text(review['authorId']) and text(review['reviewerId']), 'authorId/reviewerId required')
        if review['executionMode'] == 'parallel':
            need(review['reviewerId'] != review['authorId'], 'parallel reviewer must differ from author')
        need(review['reviewedInputs'] == _snapshot_context(record, corpus, cards),
             'stale local snapshot; reread changed content/sources/method associations before recording a new review')
        first = review['sourceFirst']
        need(isinstance(first, dict) and set(first) == {'status', 'sourceIds', 'note'}
             and first.get('status') == 'completed' and ids(first.get('sourceIds'))
             and set(first['sourceIds']) == corpus.blocks.keys() and text(first.get('note')),
             'source-first reread must include every assigned and method-dependent source')
        need(isinstance(review['unitReview'], dict) and review['unitReview'].get('unitId') == uid,
             'unitReview must describe this unit')
        local_page = {'contentUnits': [compiled['unit']], 'decisionRules': compiled['entities']['decisionRules']}
        local_review = {key: review[key] for key in ('claimReviews', 'ruleReviews', 'enumeratedLists')}
        local_review['unitReviews'] = [review['unitReview']]
        # Retain all original claim/rule/closed-list evidence and ownership gates.
        errors += validate_evidence(local_review, local_page, kb,
                                    [b for sid, b in corpus.blocks.items() if sid in own_sources],
                                    {'sourceBlocks': compiled['sourceBlocks']}, {'claims': compiled['claims']},
                                    corpus.raw, compiled['ruleCandidates'])
        if is_v2:
            from relation_ledger import validate_unit_inventory
            validate_unit_inventory(record, corpus, publication=True)
            errors += _validate_local_structure(review['structureReview'], record, corpus)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        errors.append('unit-review: invalid record/input: ' + str(exc))
    return errors


def _validate_local_structure(review, record, corpus):
    """Check authored inventory judgments and omission evidence, never create them."""
    errors = []
    def need(ok, message):
        if not ok:
            errors.append('unit-structure-review: ' + message)
        return ok
    if not need(isinstance(review, dict) and set(review) == {'frameworkReviews', 'relationReviews', 'omissionSearch'},
                'missing or unexpected fields'):
        return errors
    for key, candidates in (('frameworkReviews', record['frameworkCandidates']),
                            ('relationReviews', record['relationCandidates'])):
        expected = {c['id'] for c in candidates}; seen = set()
        rows = review[key]
        if not need(isinstance(rows, list), key + ' must be an array'):
            continue
        for row in rows:
            if not need(isinstance(row, dict) and set(row) == {'candidateId', 'status', 'note'}, key + ': invalid row'):
                continue
            ident = row['candidateId']
            valid_id = text(ident) and ident in expected and ident not in seen
            need(valid_id, key + ': unknown or duplicate candidate')
            if valid_id:
                seen.add(ident)
            need(row['status'] in {'supported', 'revised'} and text(row['note']), key + ': explicit resolved judgment required')
        need(seen == expected, key + ': must cover every candidate including excluded exactly once')
    search = review['omissionSearch']
    covered = {r['sourceId'] for r in record['sources'] if r['status'] == 'covered'}
    if not need(isinstance(search, dict) and set(search) == {'sourceIds', 'note', 'evidence', 'findings'}, 'invalid omissionSearch fields'):
        return errors
    need(ids(search['sourceIds']) and set(search['sourceIds']) == covered and text(search['note']),
         'omission search must account for all own covered sources')
    if covered:
        try:
            corpus.evidence(search['evidence'], covered, 'unit omission search')
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            need(False, str(exc))
    else:
        need(search['evidence'] == [], 'empty covered scope requires empty evidence and specific note')
    findings = search['findings']; seen = set()
    known = {c['id'] for key in ('frameworkCandidates', 'relationCandidates') for c in record[key]}
    if need(isinstance(findings, list), 'findings must be an array'):
        for row in findings:
            if not need(isinstance(row, dict) and set(row) == {'id', 'note', 'candidateIds', 'status'}, 'invalid omission finding'):
                continue
            ident = row['id']
            need(text(ident) and ident not in seen, 'finding ID must be nonempty and unique')
            if text(ident):
                seen.add(ident)
            need(row['status'] == 'resolved' and text(row['note']), 'omission finding unresolved or unexplained')
            need(ids(row['candidateIds']) and set(row['candidateIds']) <= known, 'finding cites unknown candidates')
    return errors


def _records(page, kb):
    result = {}
    for path in sorted((Path(kb) / 'unit-records').glob('*.json')):
        record = read_json(path)
        uid = record['unit']['id']
        require(uid not in result, 'Duplicate unit record: ' + uid)
        result[uid] = record
    require(set(result) == {u['id'] for u in page['contentUnits']}, 'V2 requires one unit record per final unit')
    return {unit['id']: result[unit['id']] for unit in page['contentUnits']}


def _without_order(value):
    return {k: v for k, v in value.items() if k != 'sourceOrder'}


def _check_final_binding(page, kb, records):
    """Reject page/ledger changes that could otherwise bypass a local reread."""
    from methods import bind
    methods = read_json(Path(kb) / 'methods.json')
    corpus = Sources(kb)
    all_compiled = [compile_unit(record, corpus) for record in records.values()]
    generated = {'schemaVersion': page['schemaVersion'], 'meta': copy.deepcopy(page['meta']),
                 'contentUnits': [x['unit'] for x in all_compiled],
                 'frameworks': [e for x in all_compiled for e in x['entities']['frameworks']],
                 'decisionRules': [e for x in all_compiled for e in x['entities']['decisionRules']]}
    generated = bind(generated, methods)
    for key in ('contentUnits', 'frameworks', 'decisionRules'):
        actual, expected = ({x['id']: _without_order(x) for x in container[key]} for container in (page, generated))
        require(actual == expected and len(actual) == len(page[key]) and len(expected) == len(generated[key]), 'Final page differs from reviewed unit records: ' + key)
    for record_key, actual_rows in (('glossary', page.get('glossary', [])),
                                    ('focusAreas', page.get('assessment', {}).get('focusAreas', []))):
        expected = {e['id']: _without_order(e) for x in all_compiled for e in x['entities'][record_key]}
        actual = {e['id']: _without_order(e) for e in actual_rows}
        require(actual == expected and len(actual) == len(actual_rows)
                and len(expected) == sum(len(x['entities'][record_key]) for x in all_compiled), 'Final page differs from reviewed unit records: ' + record_key)
    ledger = read_json(Path(kb) / 'summary-ledger.json')
    expected_claims = {c['id']: _without_order(c) for x in all_compiled for c in x['claims']}
    actual_claims = {c['id']: _without_order(c) for c in ledger['claims']}
    require(actual_claims == expected_claims and len(actual_claims) == len(ledger['claims'])
            and len(expected_claims) == sum(len(x['claims']) for x in all_compiled), 'Final summary ledger differs from reviewed unit claims')
    action = read_json(Path(kb) / 'action-rule-ledger.json')
    require(action['candidates'] == [c for x in all_compiled for c in x['ruleCandidates']], 'Final rule candidates differ from reviewed unit records')
    require(action['units'] == [x['ruleReview'] for x in all_compiled], 'Final rule dispositions differ from reviewed unit records')
    if any(record.get('schemaVersion') == RECORD_SCHEMA_V2 for record in records.values()):
        from relation_ledger import validate as validate_relations
        relation = read_json(Path(kb) / 'relation-ledger.json')
        validate_relations(relation, page, kb, records=list(records.values()), publication=True)
        expected_candidates = [c for record in records.values() for c in record['relationCandidates']]
        actual_local = {c['id']: c for c in relation['candidates'] if c['id'] in {x['id'] for x in expected_candidates}}
        require(actual_local == {c['id']: c for c in expected_candidates},
                'Final relation candidates differ from reviewed unit records')
    expected_blocks = {}
    for compiled in all_compiled:
        for row in compiled['sourceBlocks']:
            sid = row['sourceId']
            current = expected_blocks.setdefault(sid, {'status': row['status'], 'mappedUnits': set(), 'mappedClaims': set()})
            require(current['status'] == row['status'], 'Conflicting local source dispositions: ' + sid)
            current['mappedUnits'].update(row['mappedUnits']); current['mappedClaims'].update(row['mappedClaims'])
    require(set(expected_blocks) == corpus.blocks.keys(), 'Unit records do not assign every source block')
    actual_blocks = read_json(Path(kb) / 'coverage-audit.json')['sourceBlocks']
    require(len(actual_blocks) == len(expected_blocks) and {r['sourceId'] for r in actual_blocks} == expected_blocks.keys(), 'Final coverage blocks differ from reviewed local sources')
    for row in actual_blocks:
        expected = expected_blocks[row['sourceId']]
        require(row['status'] == expected['status'] and set(row['mappedUnits']) == expected['mappedUnits']
                and set(row['mappedClaims']) == expected['mappedClaims'], 'Final source ownership/claim mapping differs from unit records: ' + row['sourceId'])


def cross_unit_relations(page, kb):
    """Enumerate actual page and methodology edges crossing unit ownership."""
    unit_ids = {u['id'] for u in page['contentUnits']}
    owners = {u: {u} for u in unit_ids}
    for key in ('frameworks', 'glossary'):
        for row in page.get(key, []):
            owners[row['id']] = {row['firstUnitId']}
    for row in page.get('assessment', {}).get('focusAreas', []):
        owners[row['id']] = {row['unitId']}
    for row in read_json(Path(kb) / 'action-rule-ledger.json').get('candidates', []):
        if row.get('status') == 'retained':
            owners[row['targetRuleId']] = {row['unitId']}
    result = {}
    def add(prefix, edge, mapping):
        require(edge['from'] in mapping and edge['to'] in mapping, 'Unknown relationship endpoint')
        units = mapping[edge['from']] | mapping[edge['to']]
        require(units and units <= unit_ids, 'Unknown relationship unit ownership')
        if len(units) > 1:
            key = prefix + edge['id']
            require(key not in result, 'Duplicate cross-unit relation ID')
            result[key] = {'unitIds': sorted(units), 'relation': copy.deepcopy(edge)}
    for edge in page.get('relationships', []):
        add('page:', edge, owners)
    methodology = read_json(Path(kb) / 'methodology.json')
    nodes = {n['id']: set(n['unitIds']) for n in methodology.get('nodes', [])}
    for edge in methodology.get('edges', []):
        add('methodology:', edge, nodes)
    return result


def global_snapshot(page, kb, unit_reviews):
    """Fingerprint final integrated artifacts and the actual authored reviews."""
    inputs = fingerprints(page, kb)
    dependency = Path(kb) / 'unit-dependency-map.json'
    if dependency.is_file():
        inputs['unit-dependency-map.json'] = hashlib.sha256(dependency.read_bytes()).hexdigest()
    by_unit = {}
    for row in unit_reviews:
        require(isinstance(row, dict) and text(row.get('unitId')) and row['unitId'] not in by_unit, 'Invalid/duplicate unit review')
        by_unit[row['unitId']] = digest(row)
    return {'inputs': inputs, 'unitReviews': by_unit, 'crossUnitRelations': digest(cross_unit_relations(page, kb))}


def validate_global(review, page, kb, unit_reviews):
    errors = []
    def need(ok, message):
        if not ok:
            errors.append('global-review: ' + message)
        return ok
    required = {'schemaVersion', 'reviewerId', 'status', 'reviewedInputs', 'checks', 'relationReviews'}
    if not need(isinstance(review, dict) and set(review) == required, 'missing or unexpected fields'):
        return errors
    try:
        need(review['schemaVersion'] == GLOBAL_SCHEMA and review['status'] == 'completed' and text(review['reviewerId']), 'schema, reviewerId and completion required')
        relation_path = Path(kb) / 'relation-ledger.json'
        if relation_path.is_file():
            integration = read_json(relation_path)
            if integration.get('executionMode') == 'parallel':
                need(review['reviewerId'] != integration.get('integratorId'),
                     'parallel global reviewer must differ from integrator')
        need(review['reviewedInputs'] == global_snapshot(page, kb, unit_reviews), 'stale global snapshot; inspect changed integration before recording a new review')
        checks = review['checks']
        need(isinstance(checks, dict) and set(checks) == GLOBAL_CHECKS, 'all global check categories required')
        if isinstance(checks, dict):
            for key, item in checks.items():
                need(isinstance(item, dict) and set(item) == {'status', 'note'} and item['status'] == 'completed' and text(item['note']), 'explicit integration judgment required: ' + key)
        expected = cross_unit_relations(page, kb)
        rows = review['relationReviews']
        need(isinstance(rows, list), 'relationReviews must be an array')
        seen = set()
        corpus = Sources(kb)
        owned = {u['id']: set() for u in page['contentUnits']}
        for row in read_json(Path(kb) / 'coverage-audit.json')['sourceBlocks']:
            if row.get('status') == 'covered':
                for uid in row.get('mappedUnits', []):
                    require(uid in owned, 'Unknown mapped unit')
                    owned[uid].add(row['sourceId'])
        for row in rows if isinstance(rows, list) else []:
            if not need(isinstance(row, dict) and set(row) == {'relationId', 'status', 'evidenceKind', 'note', 'evidence'}, 'invalid relation review fields'):
                continue
            ident = row['relationId']
            if not need(text(ident) and ident in expected and ident not in seen, 'unknown or duplicate actual cross-unit relation'):
                continue
            seen.add(ident)
            edge = expected[ident]
            need(row['status'] in {'supported', 'revised'} and text(row['note']), 'cross-unit relation judgment required: ' + ident)
            need(row['evidenceKind'] == edge['relation'].get('evidence') and row['evidenceKind'] in {'material', 'inference'}, 'relationship evidence attribution mismatch: ' + ident)
            allowed = set().union(*(owned[u] for u in edge['unitIds']))
            try:
                corpus.evidence(row['evidence'], allowed, ident)
            except (ValueError, TypeError, KeyError) as exc:
                need(False, str(exc))
        need(seen == expected.keys(), 'must review every actual cross-unit relation exactly once')
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        errors.append('global-review: invalid record/input: ' + str(exc))
    return errors


def validate_complete(review, page, kb):
    errors = []
    required = {'schemaVersion', 'pageId', 'learningDepth', 'executionMode', 'unitReviews', 'globalReview'}
    is_v3 = isinstance(review, dict) and review.get('schemaVersion') == SCHEMA_V3
    if is_v3:
        required.add('structureReviews')
    if not isinstance(review, dict) or set(review) != required:
        return ['content-review-v2: missing or unexpected fields']
    if review['schemaVersion'] not in {SCHEMA_V2, SCHEMA_V3} or review['pageId'] != page['meta'].get('pageId') or review['learningDepth'] != page['meta'].get('learningDepth') or review['learningDepth'] != 'systematic':
        errors.append('content-review-v2: schema/pageId/systematic mismatch')
    if review['executionMode'] not in {'parallel', 'sequential'}:
        errors.append('content-review-v2: invalid executionMode')
    try:
        records = _records(page, kb)
        new_records = [r.get('schemaVersion') == RECORD_SCHEMA_V2 for r in records.values()]
        require((is_v3 and all(new_records)) or (not is_v3 and not any(new_records)),
                'v2 unit records require content-review-v3 and v3 requires all v2 unit records; no downgrade')
        if is_v3:
            from relation_ledger import validate_structure_review
            structural = review['structureReviews']
            require(isinstance(structural, list) and len(structural) == 2 and
                    all(isinstance(r, dict) for r in structural) and
                    {r.get('role') for r in structural} == {'correctness', 'omissions'},
                    'v3 requires exactly correctness and omissions structure reviews')
            ledger = read_json(Path(kb) / 'relation-ledger.json')
            require(ledger.get('executionMode') == review['executionMode'], 'Book/ledger execution mode mismatch')
            for structural_review in structural:
                errors += validate_structure_review(structural_review, page, kb, role=structural_review['role'])
        rows = review['unitReviews']
        require(isinstance(rows, list), 'unitReviews must be an array')
        by_unit = {}
        for row in rows:
            require(isinstance(row, dict) and row.get('unitId') in records and row['unitId'] not in by_unit, 'Unknown or duplicate unit review')
            uid = row['unitId']; by_unit[uid] = row
            require(row.get('executionMode') == review['executionMode'], 'Execution mode mismatch between book and unit review')
            errors += validate_unit(row, records[uid], kb)
        require(by_unit.keys() == records.keys(), 'One review is required for every final unit')
        _check_final_binding(page, kb, records)
        # Recheck original whole-book evidence/closed-list scope after integration.
        combined = {'unitReviews': [r['unitReview'] for r in rows],
                    'claimReviews': [r for unit in rows for r in unit['claimReviews']],
                    'ruleReviews': [r for unit in rows for r in unit['ruleReviews']],
                    'enumeratedLists': {'status': rows[0]['enumeratedLists']['status'] if all(u['enumeratedLists']['status'] == rows[0]['enumeratedLists']['status'] for u in rows) else 'inconsistent',
                                        'note': '\n'.join(u['enumeratedLists']['note'] for u in rows),
                                        'sourceIds': sorted({s for u in rows for s in u['enumeratedLists']['sourceIds']}),
                                        'lists': [r for u in rows for r in u['enumeratedLists']['lists']]}}
        corpus = Sources(kb)
        errors += validate_evidence(combined, page, kb, list(corpus.blocks.values()),
                                    read_json(Path(kb) / 'coverage-audit.json'), read_json(Path(kb) / 'summary-ledger.json'),
                                    corpus.raw, read_json(Path(kb) / 'action-rule-ledger.json')['candidates'])
        errors += validate_global(review['globalReview'], page, kb, rows)
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        errors.append('content-review-v2: invalid record/input: ' + str(exc))
    return errors


def assemble_review(page, kb, unit_reviews, global_review, structure_reviews=None):
    """Combine existing authored judgments, rejecting incomplete/stale inputs."""
    mode = 'sequential'
    require(all(r.get('executionMode') == mode for r in unit_reviews),
            'New review assembly requires sequential records; historical parallel reviews are validation-only')
    records = _records(page, kb)
    is_v3 = any(r.get('schemaVersion') == RECORD_SCHEMA_V2 for r in records.values())
    require(is_v3 or not structure_reviews, 'Structure reviews require v2 unit records')
    result = {'schemaVersion': SCHEMA_V3 if is_v3 else SCHEMA_V2, 'pageId': page['meta']['pageId'], 'learningDepth': 'systematic',
              'executionMode': mode, 'unitReviews': copy.deepcopy(unit_reviews), 'globalReview': copy.deepcopy(global_review)}
    if is_v3:
        result['structureReviews'] = copy.deepcopy(structure_reviews) if structure_reviews is not None else []
    errors = validate_complete(result, page, kb)
    require(not errors, '\n'.join(errors))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for name in ('snapshot', 'check'):
        sub = commands.add_parser(name)
        sub.add_argument('--unit-record', type=Path, required=True)
        sub.add_argument('--knowledge-base', type=Path, required=True)
        sub.add_argument('--methods', type=Path, help='Optional canonical method-library fragment before final assembly')
        if name == 'check':
            sub.add_argument('--review', type=Path, required=True)
        else:
            sub.add_argument('--output', type=Path)
    for name in ('global-snapshot', 'assemble'):
        sub = commands.add_parser(name)
        sub.add_argument('--page', type=Path, required=True)
        sub.add_argument('--knowledge-base', type=Path, required=True)
        sub.add_argument('--unit-review', type=Path, action='append', required=True)
        if name == 'assemble':
            sub.add_argument('--global-review', type=Path, required=True)
            sub.add_argument('--structure-review', type=Path, action='append', default=[],
                             help='Authored correctness/omissions structure review; repeat for both roles')
            sub.add_argument('--output', type=Path, required=True)
        else:
            sub.add_argument('--output', type=Path)
    structure = commands.add_parser('structure-snapshot', help='Compute structure dependency hashes only, never judgments')
    structure.add_argument('--page', type=Path, required=True)
    structure.add_argument('--knowledge-base', type=Path, required=True)
    structure.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        if args.command in {'snapshot', 'check'}:
            record = read_json(args.unit_record)
            methods = read_json(args.methods) if args.methods else None
            if args.command == 'snapshot':
                result = snapshot(record, args.knowledge_base, methods)
            else:
                errors = validate_unit(read_json(args.review), record, args.knowledge_base, methods)
                require(not errors, '\n'.join(errors))
                print('PASS: local evidence/mappings/freshness; semantic judgment remains reviewer-reported')
                return
        elif args.command == 'structure-snapshot':
            from relation_ledger import review_snapshot
            result = review_snapshot(read_json(args.page), args.knowledge_base)
        else:
            page = read_json(args.page)
            rows = [read_json(p) for p in args.unit_review]
            result = (global_snapshot(page, args.knowledge_base, rows) if args.command == 'global-snapshot'
                      else assemble_review(page, args.knowledge_base, rows, read_json(args.global_review),
                                           structure_reviews=[read_json(p) for p in args.structure_review]))
        if args.output:
            write_changed(args.output, json_text(result))
        else:
            print(json_text(result), end='')
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    from cli_output import configure_output
    configure_output()
    main()
