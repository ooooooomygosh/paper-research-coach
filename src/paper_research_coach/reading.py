"""A paper's reading route, shared by its conversations and preserved during detours."""

from .models import now
from .store import Conflict

STEPS = (
    ("orient", "阅读目标", "确认这篇论文解决什么问题，以及本次阅读要判断什么。"),
    ("insight", "独特贡献", "把贡献与最接近的已有路线区分开，保留待核实判断。"),
    ("model", "问题设定", "核对输入、输出、可用信息、假设与代价。"),
    ("method", "方法机制", "解释关键设计为什么能解决问题，并比较一个朴素方案。"),
    ("evidence", "证据核查", "查看决定性证据、基线和替代解释，核对主张的支持范围。"),
    ("synthesis", "边界与判断", "用自己的话连起问题、机制和证据，指出适用边界。"),
    ("transfer", "研究启发", "形成一个可证伪问题，或记录不值得继续的理由。"),
    ("recall", "回忆与复习", "完成一次回忆回答与反馈，留下复习题和阅读总结。"),
)
KEYS = tuple(s[0] for s in STEPS)


def snapshot(session, paper):
    flow = session.get("reading_flow", {})
    changed = flow.get("source_version", "") != paper["source_version"]
    completed = [] if changed else flow.get("completed", [])
    status = "not_started" if changed else flow.get("status", "not_started")
    index = min(len(completed), len(STEPS) - 1)
    return {
        "status": status,
        "source_version": paper["source_version"],
        "started_at": flow.get("started_at", "") if not changed else "",
        "completed": completed,
        "current": KEYS[index],
        "label": STEPS[index][1],
        "goal": STEPS[index][2],
        "steps": [{"id": k, "label": label} for k, label, _ in STEPS],
        "needs_recheck": changed and flow.get("status", "not_started") != "not_started",
        "return_action": session.get("next_action", ""),
        "pending_question": session.get("pending_question", ""),
    }


def begin(store, paper, session, connection):
    flow = snapshot(session, paper)
    if flow["status"] != "not_started":
        return session
    store.put("paper", {**paper, "status": "reading"}, paper["revision"], origin="reading-flow", connection=connection)
    return store.put(
        "session",
        {
            **session,
            "reading_flow": {
                "status": "active",
                "source_version": paper["source_version"],
                "started_at": now(),
                "completed": [],
            },
            "stage": "orient",
            "next_action": STEPS[0][2] if flow["needs_recheck"] else session.get("next_action") or STEPS[0][2],
            "pending_question": "" if flow["needs_recheck"] else session.get("pending_question", ""),
        },
        session["revision"],
        origin="reading-flow",
        connection=connection,
    )


def complete(store, paper, session, step, evidence, page_index):
    flow = snapshot(session, paper)
    if flow["status"] != "active" or step != flow["current"]:
        raise ValueError("只能完成当前阅读步骤，不能跳过主线。")
    if store.check_source(paper["id"])["status"] != "current":
        raise Conflict("请先核实当前 PDF 来源，再记录阅读进度。")
    if not evidence.strip() or not 0 <= page_index < paper["page_count"]:
        raise ValueError("阅读步骤需要实际查看的位置和具体判断。")
    started_at = flow["started_at"] or (
        flow["completed"][0]["finished_at"] if flow["completed"] else now()
    )
    if step == "recall" and not any(
        a.get("answer", "").strip() and a.get("at", "") >= started_at
        for r in store.list("review", paper["id"])
        if not r.get("anchor") or r["anchor"]["source_version"] == paper["source_version"]
        for a in r["attempts"]
    ):
        raise ValueError("先在复习队列保存一次真实回忆回答与帮助程度，再完成跟读。")
    completed = flow["completed"] + [
        {"step": step, "evidence": evidence, "page_index": page_index, "finished_at": now()}
    ]
    finished = len(completed) == len(STEPS)
    return {
        **session,
        "reading_flow": {
            "status": "completed" if finished else "active",
            "source_version": paper["source_version"],
            "started_at": started_at,
            "completed": completed,
        },
        "stage": "recall" if finished else KEYS[len(completed)],
        "next_action": "从复习队列按期回忆这篇论文，核对尚未解决的问题。"
        if finished else STEPS[len(completed)][2],
        "pending_question": "",
    }
