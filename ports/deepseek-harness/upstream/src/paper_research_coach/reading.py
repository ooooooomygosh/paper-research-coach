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

# The method each step applies, sent with every mainline turn so the model
# coaches by it without having to look it up (see references/questions.md).
GUIDES = {
    "orient": "先问清这次要判断什么、读多深（速读/精读/研读）。建议非线性顺序：题目摘要、结论、只看图表，几分钟内决定是否值得继续；不值得就记录停止理由，这也是有效结果。",
    "insight": "用引言五问（讲什么、解决什么问题、为何有趣、真正新在哪、巧在哪）读开头；对照最接近的前作，形成暂定贡献句“已有路线在X下受Y限制；本文改变Z；证据E支持到B”，缺项留空。分开作者声称与证据。",
    "model": "核对输入、输出、决策时可用的信息、假设与代价。先请用户说出一个朴素解法，再看它为什么不够。",
    "method": "一次只讲清一个因果环节：关键设计怎样克服困难，与朴素方案比差在哪。按用户的实际回答决定示范、共同完成或只给提示。",
    "evidence": "看图表前先请用户预测能区分两种解释的结果，再查看真实证据。每次只问一条批判问题：基线与预算是否匹配，数据是否足以支撑、收集与解读是否合理，有无更有说服力的数据集。",
    "synthesis": "请用户先用自己的话说出这篇的贡献，再核对；指出结论在什么条件下失效。可用三句话：改变了什么、最强证据覆盖到哪、什么结果会让我改变判断。",
    "transfer": "创造性阅读：好的 idea 是什么、作者没想到什么、如果现在做能做什么。请用户先答，再收敛为可证伪问题、强简单基线、最小检验和推翻条件；或记录不值得继续的理由。",
    "recall": "请用户不看原文回忆机制和证据边界，再核对并给反馈；提议写半页评述；创建一道复习题。",
}


# What "done" means for each step, shown to the reader on the task card and sent to the coach.
CHECKS = {
    "orient": "说出这次要判断什么、读多深，并决定继续读还是停下（停下也写明理由）。",
    "insight": "写出暂定贡献句：已有路线在 X 下受 Y 限制；本文改变 Z；证据 E 支持到 B。",
    "model": "说出输入、输出、可用信息和一个关键假设，并说出朴素解法为什么不够。",
    "method": "用自己的话讲清一个关键设计怎样克服困难（一个因果环节）。",
    "evidence": "先预测，再对照真实图表：说出最强证据支持到哪、还缺什么。",
    "synthesis": "用三句话说出：改变了什么、证据覆盖到哪、什么结果会改变判断。",
    "transfer": "写出一个可证伪问题（含简单基线和最小检验），或写明不值得继续的理由。",
    "recall": "不看原文完成一次回忆回答，并留下一道复习题。",
}
# Where each step usually looks in a paper (Carr/Keshav order: abstract, conclusion, figures first).
LOOKS = {
    "orient": "题目、摘要、结论和主图",
    "insight": "引言里的问题陈述和贡献列表，以及最接近的一篇前作",
    "model": "问题定义，或方法开头的符号与设定",
    "method": "方法总图和核心模块的描述",
    "evidence": "主结果表、关键图和消融实验",
    "synthesis": "讨论、局限和结论",
    "transfer": "局限与未来工作",
    "recall": "先不看原文；回忆后再对照",
}
# Three levels of reading (沈向洋/华刚): how deep each step goes.
DEPTHS = {
    "skim": "速读：每步只抓一句结论，图表看大意；读者可以随时停。",
    "understand": "精读：每步核对一处原文证据。",
    "reconstruct": "研读：每步追问推导与实验细节，请读者试着自己推一步。",
}


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
        "choices": session.get("choices", []) if session.get("pending_question") else [],
        "check": CHECKS[KEYS[index]],
        "look": LOOKS[KEYS[index]],
        "depth": session.get("depth", "understand"),
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


def complete(store, paper, session, step, evidence, page_index, takeaway=""):
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
    entry = {"step": step, "evidence": evidence, "page_index": page_index, "finished_at": now()}
    if takeaway.strip():
        entry["takeaway"] = " ".join(takeaway.split())[:400]
    completed = flow["completed"] + [entry]
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
        "choices": [],
    }


PLAIN = "写法：短句、主动语态、一个词一个意思、先说结论，像同事当面讲；术语第一次出现时用一句话解释，不用空话。"


def turn_guide(flow, intent):
    """One compact, step-specific coaching card for this turn."""
    if not flow or flow.get("status") not in ("active", "completed"):
        return ""
    index = KEYS.index(flow["current"]) + 1
    where = f"第 {index}/{len(KEYS)} 步「{flow['label']}」"
    if flow["status"] == "completed":
        return "【主线】八步已完成。可回顾总结、安排复习，或讨论新问题；不要重新开始一轮。" + PLAIN
    if intent == "detour":
        return (
            f"【插话】主线停在{where}，本轮不推进也不完成步骤。读者在问一个具体问题。\n"
            "概念、机制、公式、图表、流程、对比或技术细节：调用 prc_explain，在讲解面板里讲（先读 branch 参考）；"
            "聊天里只写一两句要点，不要重复整页。只是一个词的译法或一句话能答完的是非题：直接在聊天里答。"
            "要读者看某几句原文时，用 prc_show 标出来。\n"
            "卡点若妨碍当前判断，用最小例子讲清；不妨碍就简短回答，建议先记下。答完不必催促回主线，面板里有“回到主线”。" + PLAIN
        )
    current = flow["current"]
    lines = [
        f"【本轮主线】{where}。本步目标：{flow['goal']}",
        "方法要点：" + GUIDES[current],
        "读法：" + DEPTHS.get(flow.get("depth", "understand"), DEPTHS["understand"]),
        "完成标准：" + CHECKS[current],
    ]
    if flow.get("pending_question"):
        lines.append("当前问题：" + flow["pending_question"][:250])
    if intent == "answer":
        lines.append(
            "系统判断这条是对当前问题的回答：先引用其原话核对对错与依据，再决定是否完成本步。"
            "读者要提示或要讲解时，按请求给，本步不算独立完成。"
            "若它其实是另一个具体问题，就当插话处理：用 prc_explain 的面板讲解（place=panel），不完成步骤，也不改动当前问题。"
        )
    lines.append(
        "像布置一个小任务那样带读：\n"
        f"1. 先找原文，通常在「{LOOKS[current]}」。用 prc_find 或 prc_read_page 找到，再用 prc_show 标出 1–3 句（逐字复制）；回复里用 ①②③ 指代，不整段粘贴。\n"
        "2. 给读者一件事做：一个问题或一个预测，用 prc_next_action 保存为待答问题；是选择或预测时，附 2–4 个短选项（choices）。\n"
        "3. 机制、流程、对比或证据表适合画图：可调用一次 prc_explain，图解会嵌在主线对话里。要读者先预测或先回忆的步骤，等读者答完再给图。\n"
        "4. 回答有原文依据就完成本步（prc_complete_reading_step，takeaway 写一句收获，尽量用读者原话），并在同一条回复里布置下一步的第一件事，不要以“还想了解什么”结尾。"
    )
    lines.append("一轮只推进一个动作、至多一个思考任务。界面已显示当前步骤，回复里不必复述步骤编号。" + PLAIN)
    return "\n".join(lines)
