"""Evidence/mapping/freshness checks; never a proof of semantic completeness."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path

SCHEMA = 'learn-from-materials/content-review-v1'
SCHEMA_V2 = 'learn-from-materials/content-review-v2'
SCHEMA_V3 = 'learn-from-materials/content-review-v3'
INPUT_FILES = ('source_map.json', 'full_text.txt', 'summary-ledger.json', 'coverage-audit.json',
               'action-rule-ledger.json', 'methods.json', 'methodology.json')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


def fingerprints(page, kb):
    """Calculate hashes only; never generate review claims or pass flags."""
    from methods import bind
    kb = Path(kb)
    canonical = bind(copy.deepcopy(page), read(kb / 'methods.json'))
    canonical['methodology'] = read(kb / 'methodology.json')
    canonical['meta'].pop('knowledgeBase', None)  # only destination changes during publication
    result = {name: hashlib.sha256((kb / name).read_bytes()).hexdigest() for name in INPUT_FILES}
    relation = kb / 'relation-ledger.json'
    if relation.is_file():
        result['relation-ledger.json'] = hashlib.sha256(relation.read_bytes()).hexdigest()
    # New authoring records also contain full unit prose. Old deliveries without
    # these records keep their existing fingerprint contract unchanged.
    for path in sorted((kb / 'unit-records').glob('*.json')):
        result[path.relative_to(kb).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    result['page'] = digest(canonical)
    return result


def text(value):
    return isinstance(value, str) and bool(value.strip())


def ids(value):
    return isinstance(value, list) and all(text(x) for x in value) and len(value) == len(set(value))


def _validate_v1(review, page, kb):
    errors = []
    kb = Path(kb).resolve()

    def need(ok, message):
        if not ok:
            errors.append(message)
        return ok

    if not isinstance(review, dict):
        return ['content-review: root must be an object']
    required = {'schemaVersion', 'pageId', 'learningDepth', 'reviewedInputs', 'unitReviews',
                'claimReviews', 'ruleReviews', 'enumeratedLists'}
    if not need(set(review) == required, 'content-review: missing or unexpected root fields'):
        return errors
    need(review['schemaVersion'] == SCHEMA, 'content-review: unsupported schema')
    need(review['pageId'] == page['meta'].get('pageId'), 'content-review: pageId mismatch')
    need(review['learningDepth'] == page['meta'].get('learningDepth') == 'systematic', 'content-review: systematic only')
    try:
        need(review['reviewedInputs'] == fingerprints(page, kb),
             'content-review: stale reviewedInputs; reread changed inputs before updating fingerprints')
        blocks, audit, ledger = (read(kb / n) for n in ('source_map.json', 'coverage-audit.json', 'summary-ledger.json'))
        raw = (kb / 'full_text.txt').read_text(encoding='utf-8')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return errors + ['content-review: invalid input: ' + str(exc)]
    try:
        candidates = read(kb / 'action-rule-ledger.json').get('candidates', [])
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return errors + ['content-review: invalid action-rule ledger: ' + str(exc)]
    return errors + validate_evidence(review, page, kb, blocks, audit, ledger, raw, candidates)


def validate_evidence(review, page, kb, blocks, audit, ledger, raw, candidates):
    """Shared v1/v2 evidence gates; caller supplies the explicit source scope."""
    errors = []
    kb = Path(kb).resolve()

    def need(ok, message):
        if not ok:
            errors.append(message)
        return ok

    if not isinstance(blocks, list) or not isinstance(audit, dict) or not isinstance(ledger, dict):
        return errors + ['content-review: invalid source map/audit/summary ledger']
    by_id, passages = {}, {}
    for b in blocks:
        if not isinstance(b, dict) or not text(b.get('source_id')):
            return errors + ['content-review: source block needs source_id']
        sid, start, end = b['source_id'], b.get('start_char'), b.get('end_char')
        if not need(sid not in by_id and type(start) is int and type(end) is int and 0 <= start <= end <= len(raw),
                    'content-review: invalid source span: ' + sid):
            continue
        by_id[sid], passages[sid] = b, raw[start:end]
        need(hashlib.sha256(passages[sid].encode('utf-8')).hexdigest() == b.get('content_sha256'),
             'content-review: source hash mismatch: ' + sid)
    unit_ids = {u['id'] for u in page.get('contentUnits', [])}
    unit_sources = {uid: set() for uid in unit_ids}
    block_claims = {}
    claims = {c['id']: c for c in ledger.get('claims', []) if isinstance(c, dict) and text(c.get('id'))}
    for block in audit.get('sourceBlocks', []):
        if not isinstance(block, dict):
            need(False, 'content-review: invalid audit block')
            continue
        if block.get('status') != 'covered':
            continue
        sid, uids, cids = block.get('sourceId'), block.get('mappedUnits'), block.get('mappedClaims')
        if not need(text(sid) and sid in by_id and ids(uids) and ids(cids), 'content-review: invalid covered block'):
            continue
        need(bool(cids) and set(cids) <= claims.keys(), 'content-review: covered block needs known claims: ' + sid)
        block_claims[sid] = set(cids)
        owners = set(uids) | {claims[c]['unitId'] for c in cids if c in claims}
        need(owners <= unit_ids, 'content-review: unknown mapped unit: ' + sid)
        for uid in owners & unit_ids:
            unit_sources[uid].add(sid)
    covered = set(block_claims)

    def evidence(entries, allowed, label):
        used = set()
        if not need(isinstance(entries, list) and bool(entries), label + ': evidence required'):
            return used
        for item in entries:
            if not isinstance(item, dict):
                need(False, label + ': evidence must be an object')
                continue
            sid, quote, kind = item.get('sourceId'), item.get('quote'), item.get('kind')
            if not need(text(sid) and sid in allowed and sid in by_id, label + ': unknown or wrong-unit source'):
                continue
            used.add(sid)
            need(text(quote), label + ': quote/transcription required')
            if kind == 'text':
                need(text(quote) and quote in passages.get(sid, ''), label + ': quote absent from source')
            elif kind == 'visual':
                relative = item.get('artifact')
                if not text(relative) or Path(relative).is_absolute():
                    need(False, label + ': visual artifact must be relative to knowledge base')
                    continue
                artifact = (kb / relative).resolve()
                safe = artifact.is_relative_to(kb) and artifact.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp'}
                if not need(safe and artifact.is_file(), label + ': missing or unsafe visual artifact'):
                    continue
                need(hashlib.sha256(artifact.read_bytes()).hexdigest() == item.get('sha256'), label + ': visual hash mismatch')
                need(text(item.get('note')), label + ': visual transcription review note required')
            else:
                need(False, label + ': evidence kind must be text or visual')
        return used

    def rows(value, key, expected, label):
        result = {}
        if not need(isinstance(value, list), label + ': must be an array'):
            return result
        for row in value:
            if not isinstance(row, dict) or not text(row.get(key)):
                need(False, label + ': invalid row')
                continue
            ident = row[key]
            need(ident not in result and ident in expected, label + ': unknown or duplicate ID: ' + ident)
            result[ident] = row
        need(set(result) == set(expected), label + ': must cover every ID exactly once')
        return result

    for uid, row in rows(review['unitReviews'], 'unitId', unit_ids, 'unitReviews').items():
        need(row.get('status') == 'completed', 'unitReviews: reread unfinished: ' + uid)
        need(ids(row.get('sourceIds')) and set(row['sourceIds']) == unit_sources.get(uid, set()), 'unitReviews: source scope mismatch: ' + uid)
        need(text(row.get('findings')), 'unitReviews: record findings or specific no-change explanation')
        evidence(row.get('evidence'), unit_sources.get(uid, set()), 'unitReviews/' + uid)
    claim_sources = {}
    for cid, row in rows(review['claimReviews'], 'claimId', claims, 'claimReviews').items():
        if cid not in claims:
            continue
        uid = claims[cid].get('unitId')
        need(row.get('status') in {'supported', 'revised'}, 'claimReviews: visible claim cannot be excluded/pending')
        need(text(row.get('note')), 'claimReviews: contextual judgement required')
        used = evidence(row.get('evidence'), unit_sources.get(uid, set()), 'claimReviews/' + cid)
        claim_sources[cid] = used
        for sid in used:
            need(cid in block_claims.get(sid, set()), 'claimReviews: evidence must map back to claim: ' + cid)
    for sid, cids in block_claims.items():
        for cid in cids:
            need(sid in claim_sources.get(cid, set()), 'content-review: mapped claim lacks evidence for block: ' + sid)
    rules = {r['id']: r for r in page.get('decisionRules', [])}
    rule_units = {c.get('targetRuleId'): c.get('unitId') for c in candidates if isinstance(c, dict) and c.get('status') == 'retained'}
    for rid, row in rows(review['ruleReviews'], 'ruleId', rules, 'ruleReviews').items():
        need(row.get('status') in {'supported', 'revised'}, 'ruleReviews: visible rule cannot be excluded/pending')
        need(text(row.get('note')), 'ruleReviews: check condition, action, reason, quantities and attribution')
        evidence(row.get('evidence'), unit_sources.get(rule_units.get(rid), set()), 'ruleReviews/' + rid)

    inventory = review['enumeratedLists']
    if not isinstance(inventory, dict):
        return errors + ['enumeratedLists: object required']
    need(inventory.get('status') == 'searched' and text(inventory.get('note')), 'enumeratedLists: search record required')
    need(ids(inventory.get('sourceIds')) and set(inventory['sourceIds']) == covered, 'enumeratedLists: search must cover all covered sources')
    lists = inventory.get('lists')
    if not isinstance(lists, list):
        return errors + ['enumeratedLists.lists: array required']
    seen_lists = set()
    for record in lists:
        if not isinstance(record, dict) or not text(record.get('id')):
            need(False, 'enumeratedLists: invalid list')
            continue
        label = 'enumeratedLists/' + record['id']
        need(record['id'] not in seen_lists, label + ': duplicate ID')
        seen_lists.add(record['id'])
        uid = record.get('unitId')
        need(uid in unit_ids, label + ': unknown unit')
        evidence(record.get('countEvidence'), unit_sources.get(uid, set()), label + '/count')
        need(text(record.get('countNote')), label + ': explain original numbering or counted headings')
        entries, count = record.get('items'), record.get('expectedCount')
        if not need(isinstance(entries, list), label + ': items must be an array'):
            continue
        need(type(count) is int and count > 0 and len(entries) == count, label + ': item count mismatch')
        seen_items = set()
        for order, entry in enumerate(entries, 1):
            if not isinstance(entry, dict):
                need(False, label + ': invalid item')
                continue
            ident = entry.get('id')
            need(text(ident) and ident not in seen_items, label + ': item ID empty or duplicate')
            if text(ident):
                seen_items.add(ident)
            need(type(entry.get('order')) is int and entry['order'] == order, label + ': original order mismatch')
            evidence(entry.get('evidence'), unit_sources.get(uid, set()), label + '/item')
            targets = entry.get('claimIds')
            if not need(ids(targets), label + ': claimIds must be unique strings'):
                continue
            disposition = entry.get('disposition')
            need(disposition in {'retained', 'merged', 'excluded'}, label + ': disposition required')
            need(text(entry.get('reason')), label + ': explain retention, merge or exclusion')
            if disposition == 'excluded':
                need(not targets, label + ': excluded item cannot claim visible targets')
            else:
                need(bool(targets) and all(t in claims and claims[t].get('unitId') == uid for t in targets), label + ': real same-unit claim targets required')
    return errors


def validate(review, page, kb):
    """Accept old complete-book reviews and scoped 1.03 unit/global reviews."""
    if isinstance(review, dict) and review.get('schemaVersion') in {SCHEMA_V2, SCHEMA_V3}:
        from unit_review import validate_complete
        return validate_complete(review, page, kb)
    if any(read(p).get('schemaVersion') == 'learn-from-materials/unit-record-v2'
           for p in (Path(kb) / 'unit-records').glob('*.json')):
        return ['content-review: v2 unit records require content-review-v3; no legacy downgrade']
    return _validate_v1(review, page, kb)


def validate_file(path, page, kb):
    try:
        return validate(read(path), page, kb)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return ['content-review: invalid record/input: ' + str(exc)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('review', type=Path, nargs='?')
    parser.add_argument('--page', type=Path, required=True)
    parser.add_argument('--knowledge-base', type=Path, required=True)
    parser.add_argument('--fingerprints', action='store_true', help='Print input hashes only, never assert completion')
    args = parser.parse_args()
    try:
        page = read(args.page)
        if args.fingerprints:
            print(json.dumps(fingerprints(page, args.knowledge_base), ensure_ascii=False, indent=2))
            return
        if not args.review:
            parser.error('review is required unless --fingerprints is used')
        errors = validate_file(args.review, page, args.knowledge_base)
        if errors:
            parser.exit(1, '\n'.join(errors) + '\n')
        print('PASS: evidence/mappings/freshness; semantic judgement remains reviewer-reported')
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    from cli_output import configure_output
    configure_output()
    main()
