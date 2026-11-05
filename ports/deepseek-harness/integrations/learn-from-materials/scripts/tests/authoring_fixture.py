"""Round-trip the existing synthetic demo, not a source-review generator.

Only test/example construction uses this adapter. Draft flags remain false and
no new content-review rows or supporting judgments are generated.
"""
import copy
from pathlib import Path
import shutil

from workflow_io import read_json, json_text, write_changed


def fixture(root, skill):
    root, skill = Path(root), Path(skill)
    kb = root / 'demo.learnkb'
    shutil.copytree(skill / 'examples/systematic-demo.learnkb', kb)
    page = read_json(skill / 'examples/overview-systematic-demo.json')
    ledger = read_json(kb / 'summary-ledger.json')
    review = read_json(kb / 'content-review.json')
    audit = read_json(kb / 'coverage-audit.json')
    action = read_json(kb / 'action-rule-ledger.json')
    reviewed_claims = {x['claimId']: x for x in review['claimReviews']}
    folder = root / 'authoring'
    records = []
    for unit in page['contentUnits']:
        uid = unit['id']; mapping = {}
        def leaf(value, local):
            lid = 'display-' + uid + '-' + local.replace(':', '-')
            mapping['unit:' + uid + ':' + local] = lid
            return {'id': lid, 'text': value}
        converted = {key: unit[key] for key in ('id', 'label', 'title', 'source')}
        converted['core'] = leaf(unit['core'], 'core')
        for key, singular in [('frameworks', 'framework'), ('takeaways', 'takeaway')]:
            converted[key] = [leaf(value, singular + ':' + str(i)) for i, value in enumerate(unit[key])]
        converted['conclusions'] = [{'title': group['title'], 'source': group['source'], 'summary': leaf(group['summary'], 'conclusion:' + str(i) + ':summary'), 'points': [leaf(value, 'conclusion:' + str(i) + ':point:' + str(j)) for j, value in enumerate(group['points'])]} for i, group in enumerate(unit['conclusions'])]
        claims = []
        for claim in ledger['claims']:
            if claim['unitId'] != uid:
                continue
            evidence = copy.deepcopy(reviewed_claims[claim['id']]['evidence'])
            claims.append({key: claim[key] for key in ('id', 'kind', 'text', 'source')})
            claims[-1].update(sourceIds=list(dict.fromkeys(x['sourceId'] for x in evidence)), contentIds=[mapping[x] for x in claim['summaryRefs']], evidence=evidence)
        candidates = [copy.deepcopy(c) for c in action['candidates'] if c['unitId'] == uid]
        rules = {x['targetRuleId'] for x in candidates if x.get('targetRuleId')}
        rows = [x for x in audit['sourceBlocks'] if uid in x.get('mappedUnits', [])]
        row = next(copy.deepcopy(x) for x in action['units'] if x['unitId'] == uid)
        row.update(status='pending', reviewedSourceIds=[], note='Synthetic round-trip fixture; a fresh original-source review is still required before publication.')
        record = {'schemaVersion': 'learn-from-materials/unit-record-v1', 'unit': converted,
            'sources': [{'sourceId': x['sourceId'], 'status': x['status'], 'reason': 'Synthetic demo block assigned to this unit; fixture only.'} for x in rows],
            'claims': claims,
            'frameworks': [copy.deepcopy(x) for x in page['frameworks'] if x['firstUnitId'] == uid],
            'glossary': [copy.deepcopy(x) for x in page['glossary'] if x['firstUnitId'] == uid],
            'decisionRules': [copy.deepcopy(x) for x in page['decisionRules'] if x['id'] in rules],
            'focusAreas': [copy.deepcopy(x) for x in page['assessment']['focusAreas'] if x['unitId'] == uid],
            'sections': {'mentalModels': ['The displayed synthetic framework supplies this unit structure. ' + unit['source']],
                         'antiPatterns': ['See the original conditions and limits in the displayed conclusions; this fixture adds no outside advice. ' + unit['source']],
                         'workedExamples': ['The three-page self-authored demonstration supplies no empirical worked case. ' + unit['source']],
                         'connections': ['The canonical relation graph records cross-unit links; this fixture adds none. ' + unit['source']]},
            'ruleReview': row, 'ruleCandidates': candidates}
        path = folder / 'units' / (uid + '.json'); write_changed(path, json_text(record)); records.append(path)
    base = {k: copy.deepcopy(v) for k, v in page.items() if k not in {'contentUnits', 'frameworks', 'glossary', 'decisionRules', 'assessment', 'methodLibrary', 'methodology'}}
    project = {'schemaVersion': 'learn-from-materials/authoring-project-v1', 'page': base,
        'unitFiles': ['units/' + p.name for p in records],
        'coverage': {'sources': audit['sources'], 'finalCheck': {key: False for key in audit['finalCheck']}},
        'summaryCheck': {'sourceToSummaryComplete': False, 'summaryToSourceComplete': False, 'secondPassCompleted': False, 'missingClaimIds': [], 'orphanSummaryRefs': []},
        'actionRules': {key: copy.deepcopy(value) for key, value in action.items() if key not in {'schemaVersion', 'pageId', 'learningDepth', 'units', 'candidates'}}}
    project_file = folder / 'project.json'; write_changed(project_file, json_text(project))
    return kb, project_file, records, page
