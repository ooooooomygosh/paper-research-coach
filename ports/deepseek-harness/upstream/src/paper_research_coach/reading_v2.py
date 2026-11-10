"""Goal-based reading plans, separate from immutable legacy eight-step receipts."""
from __future__ import annotations
import json
from contextlib import nullcontext
from .models import now
from .store import Conflict

PHASES = (
    ("orient", "判断是否值得读", ("说出本次要判断的问题", "说出作者声称改变什么，并决定是否继续")),
    ("mechanism", "理解关键机制", ("举一个输入输出的例子", "指出一个关键条件", "解释一个设计怎样解决困难")),
    ("evidence", "核查证据与边界", ("认清一张图表的比较条件", "核查一个关键结果", "检查一种替代解释或边界")),
    ("judgment", "形成并回忆自己的判断", ("用自己的话说明主张和支持范围", "合上材料回忆，再确定下一步")),
)
KEYS = tuple(p[0] for p in PHASES)
DEPTHS = ("skim", "understand", "reconstruct")

def _schema(db):
    db.execute("CREATE TABLE IF NOT EXISTS reading_plans_v2(paper_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, data TEXT NOT NULL)")
    db.execute("CREATE TABLE IF NOT EXISTS reading_plan_operations(id TEXT PRIMARY KEY, result TEXT NOT NULL)")

LEGACY_KEYS = ("orient", "insight", "model", "method", "evidence", "synthesis", "transfer", "recall")
LEGACY_PHASES = {"orient":("orient",0), "insight":("orient",1), "model":("mechanism",0),
                 "method":("mechanism",2), "evidence":("evidence",0), "synthesis":("judgment",0),
                 "transfer":("judgment",0), "recall":("judgment",1), "talk":("judgment",1)}

def _fresh(paper, session):
    legacy = session.get("reading_flow", {})
    receipts = legacy.get("completed", [])
    same_source = not legacy.get("source_version") or legacy["source_version"] == paper["source_version"]
    prefix = [r.get("step") for r in receipts] == list(LEGACY_KEYS[:len(receipts)]) and len(receipts) <= 8
    step = session.get("stage", "orient")
    if same_source and prefix and legacy.get("status") == "active" and receipts:
        step = LEGACY_KEYS[min(len(receipts),7)]
    phase, task = LEGACY_PHASES.get(step, ("orient",0)) if same_source else ("orient",0)
    pending = session.get("pending_question", "") if same_source else ""
    status = "not_started"
    if same_source and (legacy.get("status") == "active" or pending or step not in ("orient", "insight")):
        status = "active"
    if same_source and legacy.get("status") == "completed" and prefix and len(receipts) == 8:
        phase, task, status = "judgment", 1, "completed"
    return dict(plan_version=2, paper_id=paper["id"], source_version=paper["source_version"], revision=0,
                depth=session.get("depth", "understand"), goal=session.get("goal", ""), status=status,
                current_phase=phase, current_task=task, pending_question=pending,
                phases=[dict(id=k, label=l, tasks=list(t)) for k,l,t in PHASES], coverage=[], attempts=[],
                legacy_receipts=receipts, legacy_source_version=legacy.get("source_version", ""),
                legacy_return_point={"stage":session.get("stage", "orient"), "cursor":session.get("cursor"),
                    "pending_question":session.get("pending_question", ""), "next_action":session.get("next_action", "")},
                bridge=None, return_point=None,
                started_at=legacy.get("started_at", "") if same_source else "", updated_at=session.get("updated_at", ""))

def snapshot(store, paper, session):
    with store.connect() as db:
        # Snapshot polling must not create schemas or modify user state.
        exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='reading_plans_v2'").fetchone()
        row = db.execute("SELECT data FROM reading_plans_v2 WHERE paper_id=?", (paper["id"],)).fetchone() if exists else None
    plan = json.loads(row[0]) if row else _fresh(paper, session)
    if plan["source_version"] != paper["source_version"]:
        return {**plan, "status":"stale", "needs_recheck":True}
    return plan

def update(store, paper, session, args, operation_id, *, read_pages=(), answer="", intent="detour", connection=None):
    action = args.get("action")
    allowed = {"start", "navigate", "task", "complete", "pause", "resume", "finish", "bridge", "return"}
    if action not in allowed:
        raise ValueError("未知阅读动作")
    with (nullcontext(connection) if connection is not None else store.connect()) as db:
        if not db.in_transaction: db.execute("BEGIN IMMEDIATE")
        _schema(db)
        prior = db.execute("SELECT result FROM reading_plan_operations WHERE id=?", (operation_id,)).fetchone()
        if prior:
            return json.loads(prior[0])
        row = db.execute("SELECT revision,data FROM reading_plans_v2 WHERE paper_id=?", (paper["id"],)).fetchone()
        plan = json.loads(row[1]) if row else _fresh(paper, session)
        if plan["source_version"] != paper["source_version"]:
            if action != "start":
                raise Conflict("材料已换版，请开始新计划；旧记录保留待核查")
            old = plan
            plan = _fresh(paper, session)
            plan["previous_plan"] = old
        expected = args.get("expected_revision")
        if expected is not None and expected != plan["revision"]:
            raise Conflict("阅读计划已更新，请重新读取")
        if intent == "detour" and action in {"task", "complete", "finish", "navigate"}:
            raise ValueError("当前是局部提问，保留主线问题与进度")
        if action == "start":
            depth = args.get("depth", plan["depth"])
            if depth not in DEPTHS: raise ValueError("无效阅读深度")
            plan.update(depth=depth, goal=args.get("goal", plan["goal"]), status="active", started_at=plan["started_at"] or now())
        elif action == "navigate":
            if args.get("phase") not in KEYS: raise ValueError("无效阶段")
            plan.update(current_phase=args["phase"], current_task=0, pending_question="", status="active", started_at=plan["started_at"] or now())
        elif action == "task":
            question = args.get("question", "").strip()
            if not question: raise ValueError("需要一个明确的任务")
            plan["pending_question"] = question[:2000]
        elif action == "complete":
            if plan["status"] != "active": raise ValueError("请先继续当前阅读计划")
            quote = args.get("answer_quote", "").strip()
            page = args.get("page_index")
            if not quote or quote not in answer: raise ValueError("依据须逐字来自本轮用户回答")
            if store.check_source(paper["id"])["status"] != "current":
                raise Conflict("请先核实当前材料版本")
            if page not in read_pages: raise ValueError("先实际读取该页再记录依据")
            if not 0 <= page < paper.get("page_count", 0): raise ValueError("页码超出材料范围")
            dimension = args.get("dimension")
            if dimension not in ("orient","insight","model","method","evidence","synthesis","transfer","recall"):
                raise ValueError("无效证据维度")
            if dimension == "recall" and not any(
                a.get("answer", "").strip() and a.get("at", "") >= plan["started_at"]
                for review in store.list("review", paper["id"])
                if not review.get("anchor") or review["anchor"].get("source_version") == paper["source_version"]
                for a in review.get("attempts", [])):
                raise ValueError("先保存本轮真实回忆回答，再记录回忆覆盖")
            entry = dict(page_index=page, dimension=dimension, at=now())
            if session.get("learning_consent"):
                entry.update(answer_quote=quote, assistance=args.get("assistance", "guided"))
            plan["attempts"].append(entry)
            if dimension not in plan["coverage"]: plan["coverage"].append(dimension)
            plan["current_task"] += 1
            plan["pending_question"] = ""
        elif action == "pause": plan["status"] = "paused"
        elif action == "resume": plan["status"] = "active"
        elif action == "finish":
            reason = args.get("reason", "").strip()
            if not reason: raise ValueError("请保留结束理由")
            coverage = set(plan["coverage"])
            required = {"orient"} if plan["depth"] == "skim" else {"method", "evidence", "synthesis", "recall"}
            if plan["depth"] == "reconstruct": required.add("transfer")
            plan.update(status="completed" if required <= coverage else "ended", end_reason=reason)
        elif action == "bridge":
            kind = args.get("bridge_kind")
            if kind not in ("language", "concept", "formula", "argument"): raise ValueError("无效补桥类型")
            if not plan["bridge"]:
                plan["return_point"] = {k: plan[k] for k in ("current_phase", "current_task", "pending_question")}
            plan["bridge"] = dict(kind=kind, question=args.get("question", ""), at=now())
        elif action == "return":
            if plan["return_point"]: plan.update(plan["return_point"])
            plan.update(bridge=None, return_point=None)
        plan["revision"] = (row[0] if row else 0) + 1
        plan["updated_at"] = now()
        encoded = json.dumps(plan, ensure_ascii=False)
        db.execute("INSERT OR REPLACE INTO reading_plans_v2 VALUES (?,?,?)", (paper["id"], plan["revision"], encoded))
        db.execute("INSERT INTO reading_plan_operations VALUES (?,?)", (operation_id, encoded))
        return plan

def guide(plan, intent):
    phase = next((p for p in PHASES if p[0] == plan["current_phase"]), PHASES[0])
    task = phase[2][plan["current_task"]] if plan["current_task"] < len(phase[2]) else "核查剩余疑问，或选择下一个阶段"
    if plan["status"] in ("not_started", "stale"): return ""
    return ("\n【四阶段软引导 v2】当前建议：" + task + "\n" + json.dumps({k: plan[k] for k in ("plan_version", "revision", "status", "depth", "goal", "current_phase", "current_task", "pending_question", "coverage", "bridge")}, ensure_ascii=False) +
            "\n使用 prc_reading_plan 管理当前目标。四阶段可以跳转、暂放；旧八步仅作覆盖证据，勿调用旧完成工具来凑进度。"
            "继续时先复用已保存目标、待答问题与最近真实回答，必要时读取对话；不要重复入门、重置目标或要求重译。"
            "每轮一个认知动作，贡献先记作者主张，读完机制与证据再核实。卡住仅补一个必要背景，用另一例示范后返回。"
            "用户要直接讲解就立即讲；当前是局部提问时保留主线问题。帮助偏好不等于能力；点击弄懂和AI文本不算用户表现。"
            "recall 必须有本轮真实回忆作答；已看解答的复述须记受助。研究拓展只在需要时进行。")
