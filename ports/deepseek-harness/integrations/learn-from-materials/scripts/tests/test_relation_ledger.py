import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import relation_ledger as rl
from unit_records import Sources

class RelationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup); self.kb=Path(self.tmp.name)
        raw='value determines price; stop credit at limit'
        self.write('full_text.txt',raw,False)
        self.write('source_map.json',[{'source_id':'s1','start_char':0,'end_char':len(raw),'content_sha256':hashlib.sha256(raw.encode()).hexdigest()}])
        self.ev=[{'sourceId':'s1','kind':'text','quote':'value determines price'}]
        self.c={'id':'c1','unitIds':['u1'],'sourceIds':['s1'],'evidence':self.ev,'from':'value','to':'price','type':'supports','condition':'customer value established','handoff':'pricing input','evidenceKind':'material','note':'value is the stated pricing input'}
        self.record={'schemaVersion':'learn-from-materials/unit-record-v2','unit':{'id':'u1'},'sources':[{'sourceId':'s1','status':'covered'}],'claims':[{'id':'claim1'}],'frameworks':[{'id':'f1'},{'id':'f2'}],'frameworkCandidates':[{'id':'fc1','name':'value','claimIds':['claim1'],'status':'retained','targetFrameworkId':'f1','reason':'independent input'},{'id':'fc2','name':'price','claimIds':['claim1'],'status':'retained','targetFrameworkId':'f2','reason':'independent decision'}],'relationSearch':{'status':'searched','sourceIds':['s1'],'note':'searched value to pricing reasoning'},'relationCandidates':[self.c]}
        self.edge={'id':'e1','from':'f1','to':'f2','type':'supports','evidence':'material'}
        self.page={'meta':{'pageId':'p','knowledgeBase':'old'},'contentUnits':[{'id':'u1'}],'frameworks':[{'id':'f1','firstUnitId':'u1'},{'id':'f2','firstUnitId':'u1'}],'relationships':[self.edge]}
        self.model={'status':'not-applicable','nodes':[],'edges':[],'entryNodes':[]}
        self.write('methodology.json',self.model)
        self.integration={'executionMode':'sequential','integratorId':'author','scopes':[],'candidates':[],'decisions':[{'candidateId':'c1','status':'retained','reason':'stated dependency','targets':[{'graph':'page','edgeId':'e1','from':'f1','to':'f2'}],'detailTargets':[]}],'isolatedFrameworks':[]}
        self.ledger=rl.assemble_ledger(self.page,[self.record],self.integration)
        (self.kb/'unit-records').mkdir(); self.write('unit-records/u1.json',self.record)
        self.write('relation-ledger.json',self.ledger)
    def write(self,name,obj,js=True): (self.kb/name).write_text(json.dumps(obj) if js else obj,encoding='utf-8')
    def validate(self,ledger=None,publication=True): return rl.validate(ledger or self.ledger,self.page,self.kb,records=[self.record],publication=publication)
    def test_duplicate_canonical_unit_id_rejected(self):
        self.write('unit-records/duplicate.json',self.record)
        with self.assertRaisesRegex(ValueError,'duplicate canonical unit ID'): rl.load_and_validate(self.page,self.kb)
    def test_positive_no_legacy_audits_required(self): self.assertEqual(self.validate(),self.ledger)
    def test_candidate_not_discovered_by_assembly(self):
        x=copy.deepcopy(self.record); x['relationCandidates']=[]
        result=rl.assemble_ledger(self.page,[x],self.integration)
        self.assertEqual(result['candidates'],[])
        with self.assertRaises(ValueError): rl.validate(result,self.page,self.kb,[x])
    def test_missing_binding_and_reversed_endpoint(self):
        for change in ['missing','reverse']:
            x=copy.deepcopy(self.ledger)
            if change=='missing': x['decisions'][0].update(status='excluded',targets=[])
            else: x['decisions'][0]['targets'][0]['from']='f2'
            with self.assertRaises(ValueError): self.validate(x)
    def test_inference_cannot_upgrade(self):
        self.record['relationCandidates'][0]['evidenceKind']='inference'; self.ledger['candidates'][0]['evidenceKind']='inference'
        with self.assertRaises(ValueError): self.validate()
    def test_pending_draft_not_publication(self):
        self.ledger['decisions'][0]['status']='pending'
        self.validate(publication=False)
        with self.assertRaises(ValueError): self.validate()
    def test_duplicate_candidates_and_wrong_quote(self):
        x=copy.deepcopy(self.ledger); x['candidates'].append(copy.deepcopy(x['candidates'][0]))
        with self.assertRaises(ValueError): self.validate(x)
        self.record['relationCandidates'][0]['evidence'][0]['quote']='invented'
        with self.assertRaises(ValueError): self.validate()
    def test_isolation_requires_source_review(self):
        self.page['relationships']=[]; self.ledger['decisions'][0].update(status='excluded',targets=[])
        with self.assertRaises(ValueError): self.validate()
        self.ledger['isolatedFrameworks']=[{'frameworkId':f,'scopeIds':['unit:u1'],'candidateIds':['c1'],'reason':'specific finding '+f,'evidence':self.ev} for f in ['f1','f2']]
        self.validate()
        self.ledger['isolatedFrameworks'][0]['scopeIds']=['missing']
        with self.assertRaises(ValueError): self.validate()
    def test_two_units_require_explicit_integration_scope(self):
        r2=copy.deepcopy(self.record); r2['unit']['id']='u2'; r2['frameworks']=[]; r2['frameworkCandidates']=[]; r2['relationCandidates']=[]; r2['relationSearch']['status']='no-relations'
        self.page['contentUnits'].append({'id':'u2'})
        ledger=rl.assemble_ledger(self.page,[self.record,r2],self.integration)
        with self.assertRaises(ValueError): rl.validate(ledger,self.page,self.kb,[self.record,r2])
        ledger['scopes'].append({'id':'cross-products','kind':'integration','unitIds':['u1','u2'],'sourceIds':['s1'],'status':'no-relations','note':'source search found no additional cross-unit condition','candidateIds':[]})
        rl.validate(ledger,self.page,self.kb,[self.record,r2])
    def test_detail_target_and_type_direction(self):
        self.model={'status':'ready','nodes':[{'id':'n1','input':'value','action':'pricing','output':'quote','check':'market'}],'edges':[],'entryNodes':['n1']}; self.write('methodology.json',self.model)
        self.ledger['decisions'][0]['detailTargets']=[{'nodeId':'n1','field':'input','text':'invented'}]
        with self.assertRaises(ValueError): self.validate()
        self.ledger['decisions'][0]['detailTargets'][0]['text']='value'; self.validate()
        self.record['relationCandidates'][0]['type']='causes'; self.ledger['candidates'][0]['type']='causes'
        with self.assertRaises(ValueError): self.validate()
    def test_containment_direction_reverses(self):
        self.record['relationCandidates'][0].update({'from':'f2','to':'f1','type':'contains'})
        self.ledger['candidates'][0].update({'from':'f2','to':'f1','type':'contains'})
        self.page['relationships'][0]['type']='part_of'; self.validate()
        self.record['relationCandidates'][0].update({'from':'f1','to':'f2'})
        self.ledger['candidates'][0].update({'from':'f1','to':'f2'})
        with self.assertRaises(ValueError): self.validate()
    def test_visual_hash_and_safe_path(self):
        image=self.kb/'chart.png'; image.write_bytes(b'fixture')
        visual={'sourceId':'s1','kind':'visual','quote':'transcribed figure','artifact':'chart.png','sha256':hashlib.sha256(b'fixture').hexdigest(),'note':'original diagram reading'}
        self.record['relationCandidates'][0]['evidence']=[visual]; self.ledger['candidates'][0]['evidence']=[visual]
        self.validate(); self.write('relation-ledger.json',self.ledger)
        rl.review_snapshot(self.page,self.kb)
        image.write_bytes(b'changed')
        with self.assertRaises(ValueError): self.validate()
    def test_framework_pending_and_primary_requirement(self):
        self.record['frameworkCandidates'][0]['status']='pending'
        self.validate(publication=False)
        with self.assertRaises(ValueError): self.validate()
    def test_merged_candidate_still_requires_review(self):
        c=copy.deepcopy(self.c); c['id']='c2'; self.record['relationCandidates'].append(c)
        self.ledger=rl.assemble_ledger(self.page,[self.record],self.integration)
        d=copy.deepcopy(self.ledger['decisions'][0]); d.update(candidateId='c2',status='merged',reason='same dependency with additional source wording'); self.ledger['decisions'].append(d)
        self.validate(); self.write('unit-records/u1.json',self.record); self.write('relation-ledger.json',self.ledger)
        self.assertTrue(rl.validate_structure_review(self.review(),self.page,self.kb))
    def review(self,role='correctness'):
        return {'schemaVersion':'learn-from-materials/structure-review-v1','role':role,'executionMode':'sequential','reviewerId':'reviewer','integratorId':'author','reviewedInputs':rl.review_snapshot(self.page,self.kb),'sourceFirst':{'sourceIds':['s1'],'note':'reread original value/pricing reasoning'},'note':'checked direction and evidence','candidateReviews':[{'candidateId':'c1','status':'supported','note':'value is stated as input'}] if role=='correctness' else [],'edgeReviews':[{'relationId':'page:e1','status':'supported','note':'input to decision'}] if role=='correctness' else [],'scopeReviews':[{'scopeId':'unit:u1','status':'supported','note':'checked remaining passage','evidence':self.ev}] if role=='omissions' else [],'isolatedReviews':[],'scenarios':[],'findings':[]}
    def test_review_roles_and_excluded_coverage(self):
        for role in ['correctness','omissions']: self.assertEqual(rl.validate_structure_review(self.review(role),self.page,self.kb,role),[])
        r=self.review(); r['candidateReviews']=[]
        self.assertTrue(rl.validate_structure_review(r,self.page,self.kb))
        r=self.review(); r['reviewerId']='author'
        self.assertEqual(rl.validate_structure_review(r,self.page,self.kb),[])
    def test_snapshot_destination_stable_graph_and_source_changes_stale(self):
        before=rl.review_snapshot(self.page,self.kb); self.page['meta']['knowledgeBase']='new'
        self.assertEqual(before,rl.review_snapshot(self.page,self.kb))
        r=self.review(); self.page['relationships'][0]['explanation']='changed meaning'
        self.assertTrue(rl.validate_structure_review(r,self.page,self.kb))
        self.write('full_text.txt','corrupted',False)
        with self.assertRaises(ValueError): rl.review_snapshot(self.page,self.kb)
    def test_omission_ready_scenario_requires_real_nodes(self):
        self.model={'status':'ready','nodes':[{'id':'n1','input':'value','action':'price','output':'quote','check':'market'}],'edges':[],'entryNodes':['n1']}; self.write('methodology.json',self.model)
        r=self.review('omissions'); self.assertTrue(rl.validate_structure_review(r,self.page,self.kb))
        r['scenarios']=[{'id':'case1','kind':'boundary','sourceIds':['s1'],'evidence':self.ev,'entryNodeId':'n1','nodeIds':['n1'],'edgeIds':[],'expected':'value feeds price','observed':'node preserves this input','status':'supported'}]
        self.assertEqual(rl.validate_structure_review(r,self.page,self.kb),[])
        r['scenarios'][0]['nodeIds']=['invented']; self.assertTrue(rl.validate_structure_review(r,self.page,self.kb))

if __name__=='__main__': unittest.main()
