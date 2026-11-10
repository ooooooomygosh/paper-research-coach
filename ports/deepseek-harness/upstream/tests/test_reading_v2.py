import pytest
from paper_research_coach import reading_v2 as v2
from paper_research_coach.store import Conflict

def session(store, paper): return store.list('session',paper['id'])[0]
def apply(store,paper,args,key='x',**kw):
    return v2.update(store,paper,session(store,paper),args,key,intent='answer',**kw)

def test_soft_navigation_and_legacy_preservation(store,paper):
    old=session(store,paper)
    apply(store,paper,{'action':'start'})
    plan=apply(store,paper,{'action':'navigate','phase':'evidence'},'n')
    assert plan['current_phase']=='evidence'
    assert plan['coverage']==[]
    assert session(store,paper)==old
    assert v2.snapshot(store,paper,old)['revision']==2

def test_bridge_restores_question_and_pause(store,paper):
    apply(store,paper,{'action':'start'})
    apply(store,paper,{'action':'task','question':'Why this baseline?'},'t')
    apply(store,paper,{'action':'bridge','bridge_kind':'concept','question':'What is baseline?'},'b')
    p=apply(store,paper,{'action':'return'},'r')
    assert p['pending_question']=='Why this baseline?'
    assert p['bridge'] is None
    assert apply(store,paper,{'action':'pause'},'p')['status']=='paused'

def test_completion_requires_actual_user_and_read_page(store,paper):
    apply(store,paper,{'action':'start'})
    args={'action':'complete','dimension':'orient','answer_quote':'my goal','page_index':0}
    with pytest.raises(ValueError): apply(store,paper,args,'a',answer='AI summary',read_pages={0})
    with pytest.raises(ValueError): apply(store,paper,args,'b',answer='my goal',read_pages=set())
    p=apply(store,paper,args,'c',answer='my goal',read_pages={0})
    assert p['coverage']==['orient']
    assert 'answer_quote' not in p['attempts'][0] # no learning consent
    assert apply(store,paper,args,'c',answer='my goal',read_pages={0})==p

def test_finish_is_depth_specific(store,paper):
    apply(store,paper,{'action':'start','depth':'skim'})
    apply(store,paper,{'action':'complete','dimension':'orient','answer_quote':'not relevant','page_index':0},'c',answer='not relevant',read_pages={0})
    assert apply(store,paper,{'action':'finish','reason':'not relevant'},'f')['status']=='completed'

def test_detours_and_stale_revisions_preserve_plan(store,paper):
    apply(store,paper,{'action':'start'})
    with pytest.raises(ValueError):
        v2.update(store,paper,session(store,paper),{'action':'navigate','phase':'judgment'},'d',intent='detour')
    with pytest.raises(Conflict):
        apply(store,paper,{'action':'pause','expected_revision':0},'p')
    assert v2.snapshot(store,paper,session(store,paper))['current_phase']=='orient'

def test_no_fake_recall(store,paper):
    apply(store,paper,{'action':'start'})
    with pytest.raises(ValueError,match='回忆'):
        apply(store,paper,{'action':'complete','dimension':'recall','answer_quote':'remember','page_index':0},'r',answer='remember',read_pages={0})


def test_ui_plan_endpoint_cannot_forge_evidence(store, paper):
    from fastapi.testclient import TestClient
    from paper_research_coach.server import create_app
    c = TestClient(create_app(store, token="test-token"), base_url="http://127.0.0.1:8765")
    headers = {"Authorization":"Bearer test-token"}
    path = "/api/reading/" + paper["id"] + "/plan"
    assert c.post(path, json={"action":"start","operation_id":"s"}, headers=headers).status_code == 200
    assert c.post(path, json={"action":"navigate","phase":"evidence","operation_id":"n","expected_revision":1}, headers=headers).json()["current_phase"] == "evidence"
    assert c.post(path, json={"action":"complete","dimension":"recall","operation_id":"fake"}, headers=headers).status_code == 400


def test_mock_coach_tools_cannot_mark_an_incomplete_understanding_round_done(store, paper):
    from test_coach import FakeRPC
    from paper_research_coach.coach import Coach
    coach = Coach(store, FakeRPC)
    state = {"conversation":{"paper_id":paper["id"]}, "stop":False,
             "answer":{"id":"a"}, "message":{"content":"I know the problem", "help_mode":"guided"},
             "read_pages":{0}, "intent":"answer"}
    coach.tool_call(state, "prc_reading_plan", {"action":"start"}, "start")
    result = coach.tool_call(state, "prc_reading_plan", {"action":"complete", "dimension":"orient", "page_index":0, "answer_quote":"I know the problem"}, "complete")
    assert result["reading_plan"]["coverage"] == ["orient"]
    result = coach.tool_call(state, "prc_reading_plan", {"action":"finish", "reason":"enough for today"}, "finish")
    assert result["reading_plan"]["status"] == "ended"
    assert session(store,paper)["reading_flow"]["completed"] == []


@pytest.mark.parametrize("stage,count,phase,task", [("model",2,"mechanism",0),("method",3,"mechanism",2),("evidence",4,"evidence",0),("recall",7,"judgment",1)])
def test_legacy_resume_preserves_return_point_without_claiming_mastery(store,paper,stage,count,phase,task):
    old = {**session(store,paper), "stage":stage, "pending_question":"Exact saved question", "next_action":"Exact next action",
           "cursor":{"page_index":1}, "reading_flow":{"status":"active", "source_version":paper["source_version"],
           "started_at":"2026-01-01T00:00:00Z", "completed":[{"step":k} for k in v2.LEGACY_KEYS[:count]]}}
    fresh=v2._fresh(paper,old)
    assert (fresh["current_phase"],fresh["current_task"]) == (phase,task)
    assert fresh["pending_question"] == "Exact saved question"
    assert fresh["legacy_return_point"]["cursor"] == {"page_index":1}
    assert fresh["legacy_return_point"]["next_action"] == "Exact next action"
    assert fresh["coverage"] == [] and fresh["attempts"] == []
    assert fresh["legacy_receipts"] == old["reading_flow"]["completed"]


def test_changed_source_does_not_reuse_old_pending_question(store,paper):
    old={**session(store,paper),"stage":"method","pending_question":"old question", "reading_flow":{"status":"active","source_version":"old-hash","completed":[]}}
    p=v2._fresh(paper,old)
    assert p["current_phase"] == "orient" and not p["pending_question"]
    assert p["legacy_return_point"]["pending_question"] == "old question"


def test_legacy_next_action_retry_is_idempotent_for_session_and_v2_plan(store,paper):
    from test_coach import FakeRPC
    from paper_research_coach.coach import Coach
    coach=Coach(store,FakeRPC)
    state={"conversation":{"paper_id":paper["id"]},"stop":False,"answer":{"id":"a"},"message":{"content":"answer"},"intent":"answer"}
    coach.tool_call(state,"prc_reading_plan",{"action":"start"},"start")
    args={"stage":"orient","next_action":"Inspect one result","pending_question":"Which result?","choices":["A","B"]}
    first=coach.tool_call(state,"prc_next_action",args,"task")
    revision=session(store,paper)["revision"]
    assert coach.tool_call(state,"prc_next_action",args,"task")==first
    assert session(store,paper)["revision"]==revision
    assert session(store,paper)["choices"]==["A","B"]
