"""Source-first relation inventories and explicit graph bindings.

Mechanical checks establish traceability/freshness, never semantic completeness
or actual reading order. No function creates semantic judgments.
"""
from __future__ import annotations
import copy
import hashlib
import json
import warnings
from pathlib import Path

SCHEMA = 'learn-from-materials/relation-ledger-v1'
TYPES = {'prerequisite','sequence','causes','supports','contrasts','part_of','applies','feedback','parallel','main','branch','contains'}
CANDIDATE = {'id','unitIds','sourceIds','evidence','from','to','type','condition','handoff','evidenceKind','note'}

def need(ok, msg):
    if not ok: raise ValueError('relation-ledger: ' + msg)
def text(v): return isinstance(v,str) and bool(v.strip())
def ids(v): return isinstance(v,list) and all(text(x) for x in v) and len(v)==len(set(v))
def exact(v, fields, label): need(isinstance(v,dict) and set(v)==set(fields),label+' fields invalid')
def read(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def digest(v): return hashlib.sha256(json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def unique(rows,key,label):
    need(isinstance(rows,list),label+' must be an array')
    result={}
    for r in rows:
        need(isinstance(r,dict) and text(r.get(key)) and r[key] not in result,label+' duplicate/missing ID')
        result[r[key]]=r
    return result

def candidate(c, corpus, allowed, units=None):
    exact(c,CANDIDATE,'candidate')
    need(all(text(c[k]) for k in ('id','from','to','condition','handoff','note')),'candidate text missing')
    need(ids(c['unitIds']) and c['unitIds'] and ids(c['sourceIds']) and c['sourceIds'],'candidate sources/units invalid')
    need(set(c['sourceIds'])<=set(allowed),'candidate sources outside search scope')
    if units is not None: need(set(c['unitIds'])<=set(units),'unknown candidate unit')
    need(c['type'] in TYPES and c['evidenceKind'] in {'material','inference'},'candidate type/evidenceKind invalid')
    used=corpus.evidence(c['evidence'],set(c['sourceIds']),c['id'])
    need(used==set(c['sourceIds']),'every candidate source requires evidence')

def validate_unit_inventory(record, corpus, publication=False):
    uid=record['unit']['id']
    covered={r['sourceId'] for r in record['sources'] if r['status']=='covered'}
    need(covered<=corpus.blocks.keys(),'unit covered source unknown')
    claims={c['id'] for c in record['claims']}
    frameworks={f['id'] for f in record['frameworks']}
    rows=unique(record['frameworkCandidates'],'id','framework candidates')
    primary=set()
    for c in rows.values():
        exact(c,{'id','name','claimIds','status','targetFrameworkId','reason'},'framework candidate')
        need(text(c['name']) and text(c['reason']) and ids(c['claimIds']) and c['claimIds'] and set(c['claimIds'])<=claims,'framework evidence/wording invalid')
        need(c['status'] in {'retained','merged','excluded','pending'},'framework disposition invalid')
        need(not publication or c['status']!='pending','pending framework candidate')
        if c['status'] in {'retained','merged'}:
            need(c['targetFrameworkId'] in frameworks,'framework target missing')
            if c['status']=='retained': primary.add(c['targetFrameworkId'])
        elif c['status']=='excluded': need(c['targetFrameworkId'] is None,'excluded framework has target')
    need(primary==frameworks or not publication,'every framework requires primary retained candidate')
    search=record['relationSearch']; exact(search,{'status','sourceIds','note'},'unit relation search')
    need(search['status'] in {'pending','searched','no-relations'} and ids(search['sourceIds']) and text(search['note']),'invalid unit search')
    need(set(search['sourceIds'])<=covered,'search includes uncovered source')
    if search['status']!='pending': need(set(search['sourceIds'])==covered,'incomplete unit search sources')
    need(not publication or search['status']!='pending','pending unit search')
    cs=unique(record['relationCandidates'],'id','local relation candidates')
    need(search['status']!='no-relations' or not cs,'no-relations search has candidates')
    for c in cs.values():
        candidate(c,corpus,covered)
        need(uid in c['unitIds'],'local candidate omits own unit')

def unit_scope(r):
    s=r['relationSearch']; uid=r['unit']['id']
    return {'id':'unit:'+uid,'kind':'unit','unitIds':[uid],'sourceIds':copy.deepcopy(s['sourceIds']),'status':s['status'],'note':s['note'],'candidateIds':[c['id'] for c in r['relationCandidates']]}

def assemble_ledger(page, records, integration):
    exact(integration,{'executionMode','integratorId','scopes','candidates','decisions','isolatedFrameworks'},'integration')
    need(integration['executionMode'] == 'sequential', 'New relation inventories use sequential execution in 1.1.0; historical parallel records are validation-only')
    return {'schemaVersion':SCHEMA,'pageId':page['meta']['pageId'],'executionMode':integration['executionMode'],'integratorId':integration['integratorId'],'scopes':[unit_scope(r) for r in records]+copy.deepcopy(integration['scopes']),'candidates':[copy.deepcopy(c) for r in records for c in r['relationCandidates']]+copy.deepcopy(integration['candidates']),'decisions':copy.deepcopy(integration['decisions']),'isolatedFrameworks':copy.deepcopy(integration['isolatedFrameworks'])}

def model(page,kb):
    p=Path(kb)/'methodology.json'
    need(p.is_file(),'canonical methodology.json missing')
    return read(p)
def graph_edges(page,m):
    result={}
    for prefix,rows in [('page:',page.get('relationships',[])),('methodology:',m.get('edges',[]))]:
        for ident,e in unique(rows,'id',prefix+'edges').items(): result[prefix+ident]=e
    return result
def all_edges(page,kb): return graph_edges(page,model(page,kb))

def validate(ledger,page,kb,records=None,publication=True):
    from unit_records import Sources
    corpus=Sources(kb)
    if records is None:
        canonical_records=[read(p) for p in sorted((Path(kb)/'unit-records').glob('*.json'))]
        by_unit={r['unit']['id']:r for r in canonical_records}
        need(len(by_unit)==len(canonical_records),'duplicate canonical unit ID')
        need(set(by_unit)=={u['id'] for u in page['contentUnits']},'canonical unit records missing/extra')
        records=[by_unit[u['id']] for u in page['contentUnits']]
    if isinstance(records,dict): records=list(records.values())
    exact(ledger,{'schemaVersion','pageId','executionMode','integratorId','scopes','candidates','decisions','isolatedFrameworks'},'ledger')
    need(ledger['schemaVersion']==SCHEMA and ledger['pageId']==page['meta']['pageId'],'schema/page mismatch')
    need(ledger['executionMode'] in {'parallel','sequential'} and text(ledger['integratorId']),'mode/integrator invalid')
    units={u['id'] for u in page['contentUnits']}
    rs={r['unit']['id']:r for r in records}
    need(len(rs)==len(records) and set(rs)==units,'records must cover exact page units')
    for r in records:
        need(r['schemaVersion']=='learn-from-materials/unit-record-v2','new relation ledger requires v2 records')
        validate_unit_inventory(r,corpus,publication)
    scopes=unique(ledger['scopes'],'id','scopes'); cs=unique(ledger['candidates'],'id','candidates')
    locals_=[c for r in records for c in r['relationCandidates']]
    need(ledger['candidates'][:len(locals_)]==locals_,'local candidates changed/reordered')
    need([s for s in ledger['scopes'] if s.get('kind')=='unit']==[unit_scope(r) for r in records],'unit scopes differ from records')
    integration_units=set()
    for s in scopes.values():
        exact(s,{'id','kind','unitIds','sourceIds','status','note','candidateIds'},'scope')
        need(s['kind'] in {'unit','integration'} and ids(s['unitIds']) and s['unitIds'] and set(s['unitIds'])<=units,'scope units invalid')
        need(ids(s['sourceIds']) and set(s['sourceIds'])<=corpus.blocks.keys() and ids(s['candidateIds']) and set(s['candidateIds'])<=cs.keys(),'scope sources/candidates invalid')
        need(s['status'] in {'searched','no-relations','pending'} and text(s['note']),'scope status/note invalid')
        need(not publication or s['status']!='pending','pending scope')
        need(s['status']!='no-relations' or not s['candidateIds'],'no-relations scope has candidates')
        if s['kind']=='integration': integration_units.update(s['unitIds'])
        relevant={row['sourceId'] for uid in s['unitIds'] for row in rs[uid]['sources']}
        need(set(s['sourceIds'])<=relevant,'scope source not relevant to declared units')
        for cid in s['candidateIds']:
            need(set(cs[cid]['unitIds'])&set(s['unitIds']) and set(cs[cid]['sourceIds'])<=set(s['sourceIds']),'candidate not supported by scope')
    if len(units)>1: need(integration_units==units,'integration scopes must cover all units')
    need({cid for s in scopes.values() for cid in s['candidateIds']}==set(cs),'candidate missing search scope')
    for c in cs.values():
        candidate(c,corpus,corpus.blocks,units)
        relevant={row['sourceId'] for uid in c['unitIds'] for row in rs[uid]['sources']}
        need(set(c['sourceIds'])<=relevant,'candidate sources unrelated to declared units')
    m=model(page,kb)
    if 'methodology' in page: need(page['methodology']==m,'inline methodology differs from canonical')
    edges=graph_edges(page,m); nodes=unique(m.get('nodes',[]),'id','methodology nodes')
    page_nodes={n['id'] for k in ('frameworks','decisionRules') for n in page.get(k,[])}
    for key,e in edges.items():
        allowed=page_nodes if key.startswith('page:') else set(nodes)
        need(e.get('from') in allowed and e.get('to') in allowed and e['from']!=e['to'],'edge endpoints invalid')
        kinds=({'prerequisite','sequence','causes','supports','contrasts','part_of','applies','feedback','parallel'} if key.startswith('page:') else {'main','branch','feedback','supports','contains','causes','prerequisite','parallel','contrasts'})
        need(e.get('type' if key.startswith('page:') else 'kind') in kinds,'invalid actual graph relation type')
    decisions=unique(ledger['decisions'],'candidateId','decisions')
    need(set(decisions)==set(cs),'every candidate needs exactly one decision')
    bound=set()
    for cid,d in decisions.items():
        exact(d,{'candidateId','status','reason','targets','detailTargets'},'decision')
        need(d['status'] in {'retained','merged','excluded','pending'} and text(d['reason']),'decision status/reason invalid')
        need(not publication or d['status']!='pending','pending decision')
        need(isinstance(d['targets'],list) and isinstance(d['detailTargets'],list),'decision destinations invalid')
        if d['status']=='excluded': need(not d['targets'] and not d['detailTargets'],'excluded candidate has destination')
        if d['status'] in {'retained','merged'}: need(d['targets'] or d['detailTargets'],'retained/merged candidate has no destination')
        seen=set()
        for t in d['targets']:
            exact(t,{'graph','edgeId','from','to'},'target')
            need(t['graph'] in {'page','methodology'},'unknown target graph')
            key=t['graph']+':'+str(t['edgeId']); need(key in edges and key not in seen,'unknown/duplicate target edge')
            seen.add(key); e=edges[key]
            need(t['from']==e['from'] and t['to']==e['to'],'target endpoint mismatch')
            actual_type=e.get('type') if t['graph']=='page' else e.get('kind')
            source_type=cs[cid]['type']
            compatible=actual_type==source_type or {actual_type,source_type} in ({'sequence','main'},{'part_of','contains'},{'applies','supports'})
            need(compatible,'candidate/edge relation types incompatible')
            original=(cs[cid]['from'],cs[cid]['to'])
            canonical_endpoints=page_nodes if t['graph']=='page' else set(nodes)
            if set(original)<=canonical_endpoints:
                reverse={actual_type,source_type}=={'part_of','contains'}
                need((t['from'],t['to'])==(original[::-1] if reverse else original),'candidate semantic direction changed')
            need(not(cs[cid]['evidenceKind']=='inference' and e.get('evidence')=='material'),'inference upgraded to material')
            bound.add(key)
        for t in d['detailTargets']:
            exact(t,{'nodeId','field','text'},'detail target')
            need(t['nodeId'] in nodes and t['field'] in {'input','action','output','check'} and text(t['text']),'invalid detail target')
            need(t['text'] in nodes[t['nodeId']].get(t['field'],''),'detail target text absent')
    need(bound==set(edges) or not publication,'actual edge lacks candidate binding')
    fs={f['id']:f for f in page.get('frameworks',[])}; degree={f:0 for f in fs}
    for e in page.get('relationships',[]):
        if e['from'] in fs and e['to'] in fs: degree[e['from']]+=1; degree[e['to']]+=1
    isolated=unique(ledger['isolatedFrameworks'],'frameworkId','isolated frameworks')
    need(set(isolated)=={f for f,n in degree.items() if n==0},'isolated framework set differs from visible graph')
    reasons=[]
    for fid,r in isolated.items():
        exact(r,{'frameworkId','scopeIds','candidateIds','reason','evidence'},'isolated framework')
        need(ids(r['scopeIds']) and r['scopeIds'] and set(r['scopeIds'])<=scopes.keys() and ids(r['candidateIds']) and set(r['candidateIds'])<=cs.keys() and text(r['reason']),'invalid isolated references')
        need(all(fs[fid]['firstUnitId'] in scopes[s]['unitIds'] for s in r['scopeIds']),'isolated scope omits first unit')
        scoped={c for s in r['scopeIds'] for c in scopes[s]['candidateIds']}
        need(set(r['candidateIds'])<=scoped,'isolated candidate outside referenced scopes')
        allowed={sid for s in r['scopeIds'] for sid in scopes[s]['sourceIds']}
        corpus.evidence(r['evidence'],allowed,'isolated '+fid); reasons.append(r['reason'])
    if len(reasons)!=len(set(reasons)): warnings.warn('Repeated isolated-framework reasons require semantic inspection',UserWarning)
    return ledger

def load_and_validate(page,kb,publication=True): return validate(read(Path(kb)/'relation-ledger.json'),page,kb,publication=publication)

def review_snapshot(page,kb):
    from unit_records import Sources
    corpus=Sources(kb); p=copy.deepcopy(page); p.setdefault('meta',{}).pop('knowledgeBase',None)
    ledger=read(Path(kb)/'relation-ledger.json'); m=model(page,kb)
    visuals={}
    def walk(v):
        if isinstance(v,dict):
            if v.get('kind')=='visual':
                corpus.evidence([v],set(corpus.blocks),'snapshot visual'); visuals[v['artifact']]=hashlib.sha256((Path(kb)/v['artifact']).read_bytes()).hexdigest()
            for x in v.values(): walk(x)
        elif isinstance(v,list):
            for x in v: walk(x)
    walk(ledger)
    return {'page':digest(p),'methodology':digest(m),'ledger':digest(ledger),'sources':{sid:digest({'block':{k:v for k,v in b.items() if k not in {'start_char','end_char'}},'text':corpus.passages[sid]}) for sid,b in sorted(corpus.blocks.items())},'visuals':visuals}

def validate_structure_review(review,page,kb,role=None):
    errors=[]
    try:
        ledger=load_and_validate(page,kb); edges=all_edges(page,kb); m=model(page,kb)
        exact(review,{'schemaVersion','role','executionMode','reviewerId','integratorId','reviewedInputs','sourceFirst','note','candidateReviews','edgeReviews','scopeReviews','isolatedReviews','scenarios','findings'},'structure review')
        need(review['schemaVersion']=='learn-from-materials/structure-review-v1' and review['role'] in {'correctness','omissions'},'review schema/role invalid')
        need(role is None or review['role']==role,'unexpected review role')
        need(review['executionMode']==ledger['executionMode'] and review['integratorId']==ledger['integratorId'] and text(review['reviewerId']),'review identities/mode invalid')
        need(review['executionMode']!='parallel' or review['reviewerId']!=review['integratorId'],'parallel reviewer equals integrator')
        need(review['reviewedInputs']==review_snapshot(page,kb),'stale structure review')
        sf=review['sourceFirst']; exact(sf,{'sourceIds','note'},'sourceFirst')
        required={sid for s in ledger['scopes'] for sid in s['sourceIds']}|{sid for c in ledger['candidates'] for sid in c['sourceIds']}
        need(ids(sf['sourceIds']) and set(sf['sourceIds'])==required and text(sf['note']) and text(review['note']),'source-first scope incomplete')
        from unit_records import Sources
        corpus=Sources(kb)
        def judgments(name,key,expected,evidence=False):
            rows=unique(review[name],key,name)
            need(set(rows)==set(expected),name+' coverage incomplete')
            for r in rows.values():
                exact(r,{key,'status','note'}|({'evidence'} if evidence else set()),name)
                need(r['status'] in {'supported','revised'} and text(r['note']),name+' unresolved judgment')
                if evidence:
                    allowed=set(expected[r[key]]['sourceIds'])
                    if allowed: corpus.evidence(r['evidence'],allowed,name)
                    else: need(r['evidence']==[], 'empty source scope must have empty evidence')
        cs={c['id']:c for c in ledger['candidates']}
        for key in ('candidateReviews','edgeReviews','scopeReviews','isolatedReviews','scenarios','findings'): need(isinstance(review[key],list),'review array invalid')
        if review['role']=='correctness':
            judgments('candidateReviews','candidateId',cs); judgments('edgeReviews','relationId',edges)
            if review['scopeReviews']: judgments('scopeReviews','scopeId',{s['id']:s for s in ledger['scopes']},True)
            if review['isolatedReviews']: judgments('isolatedReviews','frameworkId',{r['frameworkId']:r for r in ledger['isolatedFrameworks']})
        else:
            judgments('scopeReviews','scopeId',{s['id']:s for s in ledger['scopes']},True)
            judgments('isolatedReviews','frameworkId',{r['frameworkId']:r for r in ledger['isolatedFrameworks']})
            if review['candidateReviews']: judgments('candidateReviews','candidateId',cs)
            if review['edgeReviews']: judgments('edgeReviews','relationId',edges)
            need(m.get('status')!='ready' or review['scenarios'],'ready methodology needs an omission scenario')
        for f in unique(review['findings'],'id','findings').values():
            exact(f,{'id','note','candidateIds','status'},'finding')
            need(f['status']=='resolved' and text(f['note']) and ids(f['candidateIds']) and set(f['candidateIds'])<=cs.keys(),'unresolved/invalid finding')
        nodes={n['id'] for n in m.get('nodes',[])}; mids={e['id'] for e in m.get('edges',[])}
        for s in unique(review['scenarios'],'id','scenarios').values():
            exact(s,{'id','kind','sourceIds','evidence','entryNodeId','nodeIds','edgeIds','expected','observed','status'},'scenario')
            need(s['kind'] in {'application','argument','boundary'} and s['status'] in {'supported','revised'} and text(s['expected']) and text(s['observed']),'scenario judgment invalid')
            need(ids(s['sourceIds']) and set(s['sourceIds'])<=required and ids(s['nodeIds']) and s['nodeIds'] and set(s['nodeIds'])<=nodes and ids(s['edgeIds']) and set(s['edgeIds'])<=mids,'scenario references invalid')
            need(s['entryNodeId'] in m.get('entryNodes',[]) and s['entryNodeId'] in s['nodeIds'],'scenario entry invalid')
            need(corpus.evidence(s['evidence'],set(s['sourceIds']),'scenario')==set(s['sourceIds']),'scenario source lacks evidence')
            by_edge={e['id']:e for e in m.get('edges',[])}
            need(all({by_edge[e]['from'],by_edge[e]['to']}<=set(s['nodeIds']) for e in s['edgeIds']),'scenario edge endpoints absent from scenario nodes')
    except (ValueError,KeyError,TypeError,OSError,AttributeError) as exc: errors.append(str(exc))
    return errors
