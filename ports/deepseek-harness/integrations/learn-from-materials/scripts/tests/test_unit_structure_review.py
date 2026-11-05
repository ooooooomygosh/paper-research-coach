"""Synthetic 1.04 mutation fixture only; never a production review generator.

The pre-existing authored Method Lab demo supplies the source claims and their
reviewed judgments. Structural judgments here are explicit test assertions about
that invented material, not an approval mechanism for arbitrary input books.
"""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
from authoring_fixture import fixture
from content_review import SCHEMA_V3, fingerprints, validate
from unit_records import assemble
from unit_review import (GLOBAL_CHECKS, GLOBAL_SCHEMA, UNIT_SCHEMA_V2, assemble_review,
                         cross_unit_relations, global_snapshot, snapshot, validate_unit)
from workflow_io import read_json, json_text, write_changed
import relation_ledger as rl


def v3_fixture(root, skill):
    root = Path(root)
    kb, project_path, paths, original = fixture(root, skill)
    old = read_json(kb / 'content-review.json')
    action = read_json(kb / 'action-rule-ledger.json')
    project = read_json(project_path)
    project['schemaVersion'] = 'learn-from-materials/authoring-project-v2'
    project['coverage']['finalCheck'] = read_json(kb / 'coverage-audit.json')['finalCheck']
    project['summaryCheck'] = read_json(kb / 'summary-ledger.json')['finalCheck']
    records = []
    for path in paths:
        r = read_json(path); uid = r['unit']['id']
        r['schemaVersion'] = 'learn-from-materials/unit-record-v2'
        r['ruleReview'] = next(copy.deepcopy(x) for x in action['units'] if x['unitId'] == uid)
        r['frameworkCandidates'] = [dict(id='inventory-'+f['id'], name=f['name'],
            claimIds=[r['claims'][0]['id']], status='retained', targetFrameworkId=f['id'],
            reason='Synthetic original unit explicitly introduces this named framework.') for f in r['frameworks']]
        r['relationSearch'] = dict(status='searched', sourceIds=[x['sourceId'] for x in r['sources'] if x['status']=='covered'],
                                   note='Synthetic local passage was read; global decisions below preserve its stated application and feedback links.')
        # Local and integration candidates remain distinguishable so the final
        # binding mutation can detect an edited canonical ledger.
        r['relationCandidates'] = []
        records.append(r); write_changed(path, json_text(r))
    methodology = read_json(kb / 'methodology.json')
    # Fixed synthetic relation inventory, based on the existing authored demo.
    specs = [('page','map-rule',0), ('page','evidence-rule',1), ('page','action-rule',2),
             ('page','feedback-evidence',2), ('page','feedback-map',2), ('page','map-evidence',0),
             ('methodology','e-map-evidence',0), ('methodology','e-evidence-test',1),
             ('methodology','e-direct-test',2), ('methodology','e-return-evidence',2),
             ('methodology','e-return-map',2)]
    candidates, decisions = [], []
    for graph, ident, source_unit in specs:
        edge = next(e for e in (original['relationships'] if graph=='page' else methodology['edges']) if e['id']==ident)
        r = records[source_unit]; ev = copy.deepcopy(r['claims'][0]['evidence'])
        c = dict(id='candidate-'+graph+'-'+ident, unitIds=[r['unit']['id']],
                 sourceIds=list(dict.fromkeys(e['sourceId'] for e in ev)), evidence=ev,
                 **{'from':edge['from'], 'to':edge['to']}, type=edge.get('type',edge.get('kind')),
                 condition='Synthetic demo condition retained in original edge.', handoff='The original concept supports the displayed next use.',
                 evidenceKind=edge['evidence'], note='Synthetic fixture checks this exact authored demo relation, not automatic graph extraction.')
        candidates.append(c)
        decisions.append(dict(candidateId=c['id'],status='retained',reason='The fixed synthetic relation is displayed with its original direction and attribution.',
                              targets=[dict(graph=graph,edgeId=ident,**{'from':edge['from'],'to':edge['to']})],detailTargets=[]))
    records[0]['relationCandidates'] = [candidates.pop(0)]
    write_changed(paths[0], json_text(records[0]))
    source_ids = sorted({s['sourceId'] for r in records for s in r['sources'] if s['status']=='covered'})
    project['relations'] = dict(executionMode='sequential',integratorId='fixture-integrator',
        scopes=[dict(id='integration:demo',kind='integration',unitIds=[r['unit']['id'] for r in records],
                     sourceIds=source_ids,status='searched',note='All three invented passages were checked for application and feedback handoffs.',
                     candidateIds=[c['id'] for c in candidates])],candidates=candidates,decisions=decisions,isolatedFrameworks=[])
    write_changed(project_path,json_text(project))
    page_path=root/'page.json';assemble(project_path,kb,page_path);page=read_json(page_path)
    reviews=[]
    for r in records:
        uid=r['unit']['id']; claim_ids={c['id'] for c in r['claims']};rule_ids={x['id'] for x in r['decisionRules']}
        s=snapshot(r,kb);covered=[x['sourceId'] for x in r['sources'] if x['status']=='covered']
        enum=copy.deepcopy(old['enumeratedLists']);enum['sourceIds']=covered;enum['lists']=[x for x in enum['lists'] if x['unitId']==uid]
        reviews.append(dict(schemaVersion=UNIT_SCHEMA_V2,unitId=uid,executionMode='sequential',authorId='fixture-author',reviewerId='fixture-local-reviewer',
            reviewedInputs=s,sourceFirst=dict(status='completed',sourceIds=list(s['sources']),note='Synthetic source passage reread before fixture judgments.'),
            unitReview=next(copy.deepcopy(x) for x in old['unitReviews'] if x['unitId']==uid),
            claimReviews=[copy.deepcopy(x) for x in old['claimReviews'] if x['claimId'] in claim_ids],
            ruleReviews=[copy.deepcopy(x) for x in old['ruleReviews'] if x['ruleId'] in rule_ids],enumeratedLists=enum,
            structureReview=dict(frameworkReviews=[dict(candidateId=c['id'],status='supported',note='The invented passage names this framework.') for c in r['frameworkCandidates']],
                relationReviews=[dict(candidateId=c['id'],status='supported',note='The fixed unclear-scope passage applies its named map to its corresponding action rule.') for c in r['relationCandidates']],
                omissionSearch=dict(sourceIds=covered,note='Synthetic passage has its named framework; local and integration inventories account for the relations.',
                evidence=copy.deepcopy(r['claims'][0]['evidence']),findings=[]))))
    global_review=dict(schemaVersion=GLOBAL_SCHEMA,reviewerId='fixture-independent-global',status='completed',reviewedInputs=global_snapshot(page,kb,reviews),
                       checks={k:dict(status='completed',note='Fixed synthetic integration checked for '+k) for k in GLOBAL_CHECKS},relationReviews=[])
    for ident, row in cross_unit_relations(page,kb).items():
        local=next(r for r in reviews if r['unitId'] in row['unitIds'])
        global_review['relationReviews'].append(dict(relationId=ident,status='supported',evidenceKind=row['relation']['evidence'],
            note='Synthetic authored relation preserves this handoff and evidence attribution.',evidence=copy.deepcopy(local['unitReview']['evidence'])))
    ledger=read_json(kb/'relation-ledger.json');struct=[]
    for role in ['correctness','omissions']:
        structural=dict(schemaVersion='learn-from-materials/structure-review-v1',role=role,executionMode='sequential',reviewerId='fixture-independent-'+role,
            integratorId='fixture-integrator',reviewedInputs=rl.review_snapshot(page,kb),sourceFirst=dict(sourceIds=source_ids,note='Read every invented source passage for this fixture role.'),
            note='Synthetic comparison of the authored graph with its original invented reasoning.',
            candidateReviews=[],edgeReviews=[],scopeReviews=[],isolatedReviews=[],scenarios=[],findings=[])
        if role=='correctness':
            structural['candidateReviews']=[dict(candidateId=c['id'],status='supported',note='Fixed demo candidate supports the exact displayed relation.') for c in ledger['candidates']]
            structural['edgeReviews']=[dict(relationId=e,status='supported',note='Original demo edge direction and attribution are unchanged.') for e in rl.all_edges(page,kb)]
        else:
            for scope in ledger['scopes']:
                evidence=[]
                for sid in scope['sourceIds']:
                    evidence.append(copy.deepcopy(next(e for r in records for c in r['claims'] for e in c['evidence'] if e['sourceId']==sid)))
                structural['scopeReviews'].append(dict(scopeId=scope['id'],status='supported',note='The entire fixed scope was compared, including possible feedback.',evidence=evidence))
            structural['scenarios']=[dict(id='demo-application',kind='application',sourceIds=source_ids,
                evidence=[copy.deepcopy(next(e for r in records for c in r['claims'] for e in c['evidence'] if e['sourceId']==sid)) for sid in source_ids],
                entryNodeId='m-map',nodeIds=['m-map','m-evidence','m-test'],edgeIds=['e-map-evidence','e-evidence-test'],
                expected='Unclear scope can be mapped before an evidence check and a low-cost test.',
                observed='The fixed methodology preserves mapping, evidence inputs and the test; its optional path remains explicitly inferred.',status='supported')]
        struct.append(structural)
    complete=assemble_review(page,kb,reviews,global_review,structure_reviews=struct)
    write_changed(kb/'content-review.json',json_text(complete))
    return kb,project_path,page_path,page,reviews,global_review,struct,complete


class UnitStructureReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.kb,self.project,self.page_path,self.page,self.reviews,self.global_review,self.struct,self.complete=v3_fixture(self.root,SCRIPTS.parent)

    def test_v3_complete_and_destination_stability(self):
        self.assertEqual(self.complete['schemaVersion'],SCHEMA_V3)
        self.assertEqual(validate(self.complete,self.page,self.kb),[])
        self.page['meta']['knowledgeBase']='other-delivery/INDEX.md'
        self.assertEqual(validate(self.complete,self.page,self.kb),[])

    def test_required_roles_and_honest_sequential_global_reread(self):
        for replacement in [[],self.struct[:1],[self.struct[0],self.struct[0]]]:
            r=copy.deepcopy(self.complete);r['structureReviews']=replacement
            self.assertTrue(any('exactly correctness and omissions' in e for e in validate(r,self.page,self.kb)))
        r=copy.deepcopy(self.complete);r['globalReview']['reviewerId']='fixture-integrator'
        self.assertEqual(validate(r,self.page,self.kb),[])

    def test_no_schema_downgrade(self):
        r=copy.deepcopy(self.complete);r['schemaVersion']='learn-from-materials/content-review-v2';r.pop('structureReviews')
        self.assertTrue(any('no downgrade' in e for e in validate(r,self.page,self.kb)))
        record=read_json(self.kb/'unit-records/u01.json');review=copy.deepcopy(self.reviews[0]);review['schemaVersion']='learn-from-materials/unit-content-review-v1';review.pop('structureReview')
        self.assertTrue(validate_unit(review,record,self.kb))

    def test_framework_omission_and_source_scope_are_required(self):
        record=read_json(self.kb/'unit-records/u01.json')
        r=copy.deepcopy(self.reviews[0]);r['structureReview']['frameworkReviews']=[]
        self.assertTrue(any('every candidate' in e for e in validate_unit(r,record,self.kb)))
        r=copy.deepcopy(self.reviews[0]);r['structureReview']['omissionSearch']['sourceIds']=[]
        self.assertTrue(any('all own covered' in e for e in validate_unit(r,record,self.kb)))
        r=copy.deepcopy(self.reviews[0]);r['structureReview']['omissionSearch']['findings']=[dict(id='pending',note='not resolved',candidateIds=[],status='pending')]
        self.assertTrue(any('unresolved' in e for e in validate_unit(r,record,self.kb)))

    def test_relation_inventory_changes_cannot_be_hash_refreshed_away(self):
        before=fingerprints(self.page,self.kb)
        ledger=read_json(self.kb/'relation-ledger.json')
        next(c for c in ledger['candidates'] if c['id']=='candidate-page-evidence-rule')['note']+=' changed'
        write_changed(self.kb/'relation-ledger.json',json_text(ledger))
        self.assertNotEqual(before,fingerprints(self.page,self.kb))
        changed=copy.deepcopy(self.complete);changed['globalReview']['reviewedInputs']=global_snapshot(self.page,self.kb,self.reviews)
        self.assertTrue(any('stale' in e for e in validate(changed,self.page,self.kb)))

    def test_local_candidate_cannot_be_edited_only_in_ledger(self):
        from unit_review import _check_final_binding, _records
        ledger=read_json(self.kb/'relation-ledger.json')
        local=next(c for c in ledger['candidates'] if c['id']=='candidate-page-map-rule')
        local['condition']='Invented changed condition, absent from reviewed local inventory.'
        write_changed(self.kb/'relation-ledger.json',json_text(ledger))
        with self.assertRaises(ValueError):
            _check_final_binding(self.page,self.kb,_records(self.page,self.kb))

    def test_excluded_local_candidates_still_need_judgment(self):
        record=read_json(self.kb/'unit-records/u01.json')
        c=copy.deepcopy(record['frameworkCandidates'][0]);c.update(id='excluded-frame',status='excluded',targetFrameworkId=None,reason='Synthetic phrase is equivalent background, not a distinct framework.')
        record['frameworkCandidates'].append(c)
        r=copy.deepcopy(self.reviews[0]);r['reviewedInputs']=snapshot(record,self.kb)
        self.assertTrue(any('every candidate' in e for e in validate_unit(r,record,self.kb)))
        r['structureReview']['frameworkReviews'].append(dict(candidateId='excluded-frame',status='supported',note='Checked source; exclusion does not remove an independent framework.'))
        self.assertEqual(validate_unit(r,record,self.kb),[])
        r['structureReview']['relationReviews']=[]
        self.assertTrue(any('every candidate' in e for e in validate_unit(r,record,self.kb)))

    def test_structure_snapshot_cli_only_hashes(self):
        result=subprocess.run([sys.executable,str(SCRIPTS/'unit_review.py'),'structure-snapshot','--page',str(self.page_path),'--knowledge-base',str(self.kb)],capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        snap=json.loads(result.stdout);self.assertEqual(snap,rl.review_snapshot(self.page,self.kb))
        self.assertNotIn('candidateReviews',snap);self.assertNotIn('status',snap)


if __name__=='__main__':unittest.main()
