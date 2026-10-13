"""Showcase with a real paper: "Attention Is All You Need" (Vaswani et al., 2017, arXiv:1706.03762).

The PDF is downloaded from arXiv (or passed with --pdf) into a temporary folder and never
committed. Every quoted sentence is checked against the PDF's own text before it is marked.
The coach's replies, the explainer pages and the reader's answers are scripted (a fixed demo,
not a live model), and every picture carries a "预设演示" badge that says so.

Optional developer dependencies: playwright and a Chromium installation. Not run in CI.
Usage: python scripts/capture_transformer_demo.py [--pdf attention.pdf] [--output docs/images]
"""
from __future__ import annotations

import argparse
import os
import socket
import threading
import time
import urllib.request
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

import uvicorn
from capture_showcase import demo_frame, save_demo

from paper_research_coach import reading
from paper_research_coach.models import now, uid
from paper_research_coach.server import create_app, session_token
from paper_research_coach.store import Store

ARXIV = "https://arxiv.org/pdf/1706.03762v7"
FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "explainers"
BADGE = "预设演示 · 非实时模型回复 · 论文：Vaswani et al. 2017, arXiv:1706.03762"

# Sentences the demo marks, with the page (from 0) where arXiv v7 prints them. All are checked.
QUOTES = {
    "abstract": (0, "based solely on attention mechanisms, dispensing with recurrence and convolutions entirely"),
    "softmax": (3, "pushing the softmax function into regions where it has extremely small gradients"),
    "variance": (3, "are independent random variables with mean 0 and variance 1"),
    "multihead": (4, "jointly attend to information from different representation subspaces at different positions"),
    "positions": (5, "Since our model contains no recurrence and no convolution"),
    "table1": (5, "Maximum path lengths, per-layer complexity and minimum number of sequential operations"),
}
# The reader's takeaways for the eight chapters: scripted words for the demo.
TAKEAWAYS = [
    ("orient", 0, "这次要判断：只用注意力、不用循环，能不能把翻译做得又好又快。"),
    ("insight", 1, "贡献句：以前的序列模型靠循环，很难并行；本文只用注意力；WMT 2014 翻译的 BLEU 支持到这一点。"),
    ("model", 2, "输入是源句，输出是目标句；朴素做法 RNN 要一步一步算，句子越长越慢。"),
    ("method", 3, "缩放点积注意力：用 Q 和 K 的相似度给 V 加权；除以 √d_k，softmax 才不会饱和。"),
    ("evidence", 5, "表 1：自注意力的顺序操作是 O(1)；表 2 的 BLEU 更高、训练代价更低，但主要测的是翻译。"),
    ("synthesis", 9, "只用注意力就能做强的序列转换，而且训练能并行；证据覆盖到翻译和英语句法分析，长序列的代价还没测。"),
    ("transfer", 9, "可证伪问题：序列很长时，O(n²) 的代价会不会抵消并行的好处？最小检验：同样预算下比较不同长度。"),
    ("recall", 3, "不看原文：Q·K 除以 √d_k，softmax 后乘 V；8 个头并行；位置编码补上顺序。"),
]


def fixture(name: str) -> str:
    text = (FIXTURES / f"{name}.md").read_text(encoding="utf-8")
    # Every page says it is a scripted example, in its own subtitle.
    return text.replace("\nsubtitle: ", "\nsubtitle: 预设讲解示例 · ", 1)


def fetch(pdf: Path | None, folder: Path) -> Path:
    if pdf:
        return pdf.expanduser().resolve()
    target = folder / "attention-is-all-you-need.pdf"
    request = urllib.request.Request(ARXIV, headers={"User-Agent": "paper-research-coach showcase"})
    with urllib.request.urlopen(request, timeout=60) as response:
        target.write_bytes(response.read())
    if not target.read_bytes().startswith(b"%PDF"):
        raise SystemExit("The download is not a PDF; pass --pdf with a local copy of arXiv:1706.03762v7.")
    return target


def badge(page):
    page.add_init_script(f"""addEventListener('DOMContentLoaded', () => {{
        const tag = document.createElement('div');
        tag.textContent = {BADGE!r};
        tag.style.cssText = 'position:fixed;left:12px;bottom:10px;z-index:99999;padding:3px 10px;border-radius:999px;' +
          'background:#203229d9;color:#fbfbf7;font:600 12px/1.5 system-ui,sans-serif;pointer-events:none';
        document.body.append(tag);
    }});""")


def say(coach, conversation, role, content, **extra):
    message = {"id": extra.pop("id", uid()), "conversation_id": conversation, "role": role, "content": content,
               "status": "completed", "created_at": now(), "actions": [], **extra}
    coach.save_message(message)
    return message


def set_flow(store, paper, chapters: int, **session_fields):
    session = store.list("session", paper["id"])[0]
    if session["reading_flow"]["status"] == "not_started":
        with store.connect() as db:
            session = reading.begin(store, paper, session, db)
    done = [{"step": k, "evidence": "预设演示", "page_index": p, "finished_at": now(), "takeaway": t}
            for k, p, t in TAKEAWAYS[:chapters]]
    flow = {**session["reading_flow"], "completed": done, "status": "completed" if chapters == 8 else "active"}
    stage = TAKEAWAYS[min(chapters, 7)][0]
    return store.put("session", {**session, "reading_flow": flow, "stage": stage, **session_fields}, session["revision"])


def capture(output: Path, pdf: Path | None, executable: str | None) -> dict:
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="prc-transformer-") as directory:
        root = Path(directory)
        (root / "source").mkdir()
        source = fetch(pdf, root / "source")
        store = Store(root / "library")
        paper = store.add_paper(
            "Attention Is All You Need", str(source), authors="Vaswani, Shazeer, Parmar, Uszkoreit, Jones, Gomez, Kaiser, Polosukhin",
            year="2017", url="https://arxiv.org/abs/1706.03762", status="reading",
            goal="判断只用注意力的模型是否真的又好又快",
        )
        store.set_setting("active-paper", paper["id"])
        token = session_token(store)
        app = create_app(store, token)
        coach = app.state.coach

        async def preview_status():
            return {"state": "unavailable", "models": [], "skill": "paper-research-coach",
                    "message": "展示使用预设对话，未发起模型请求。"}
        coach.status = preview_status
        conversation = coach.binding(paper["id"])["conversation_id"]

        # Check every quote against the PDF before anything is drawn. A miss stops the script.
        focus = {}
        for key, (page_index, quote) in QUOTES.items():
            focus[key], _ = coach.focus_action(paper["id"], page_index, [quote], "看这里")
        report = {"pdf_pages": paper["page_count"], "quotes_checked": len(QUOTES)}

        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False, log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        deadline = time.monotonic() + 15
        while not server.started:
            if not thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("The local showcase server did not start.")
            time.sleep(0.05)
        url = f"http://127.0.0.1:{port}/#" + urlencode({"token": token, "paper": paper["id"]})
        errors: list[str] = []
        frames, durations = [], []

        def frame(page, caption, hold=2800):
            frames.append(demo_frame(page, caption))
            durations.append(hold)

        try:
            with sync_playwright() as playwright:
                options = {"headless": True, "args": ["--disable-gpu"]}
                if executable:
                    options["executable_path"] = executable
                browser = playwright.chromium.launch(**options)

                def open_page(ratio="0.56", width=1440, height=1000):
                    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
                    page.add_init_script(f"localStorage.setItem('prc-pane-ratio', '{ratio}')")
                    badge(page)
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    return page

                # ---- Scene A: a side quest, "why divide by √d_k?", while chapter 4 is under way.
                set_flow(store, paper, 3, pending_question="", next_action="读 3.2.1 节，说清缩放点积注意力的一个因果环节。")
                anchor = focus["softmax"]["anchor"]
                question = "为什么注意力里要除以 √d_k？不除会怎样？"
                say(coach, conversation, "assistant", "**预设带读示例 · 非实时模型回复**\n\n第 4 章：方法机制。先读 3.2.1 节，看懂一个因果环节就行。",
                    intent="follow", step="method")
                say(coach, conversation, "user", question, intent="detour", step="method", anchor={**anchor, "rects": []})
                page = open_page()
                page.goto(url)
                page.locator(".pdf-page[data-page-index='0'] canvas").wait_for()
                page.get_by_text(question).first.wait_for()
                page.wait_for_timeout(600)
                frame(page, "读到第 4 页，插一句：为什么要除以 √d_k？", 2600)
                # The coach marks the sentence and draws the answer as a page inside the conversation.
                reply = uid()
                record = coach.save_explainer(paper["id"], conversation, fixture("transformer-scaled-attention"), message_id=reply,
                                              question=question, anchor=anchor)
                show = {**focus["softmax"], "id": "focus:" + reply, "label": "第 4 页 · softmax 会饱和", "note": "softmax 会饱和"}
                variance = focus["variance"]
                show["marks"] = show["marks"] + [{**variance["marks"][0], "n": 2}]
                show["anchor"] = {**show["anchor"], "rects": show["anchor"]["rects"] + variance["anchor"]["rects"]}
                say(coach, conversation, "assistant", "**预设带读示例 · 非实时模型回复**\n\n① 是原因，② 是脚注 4 的推理。讲解页在下面，主线停在第 4 章，弄懂了就回来。",
                    id=reply, intent="detour", step="method", actions=[show, coach.explainer_action(record)])
                card = page.locator(".xp-card").first
                card.locator(".xp-grid").wait_for()
                page.locator(".coach-mark").first.wait_for()
                page.wait_for_timeout(900)
                card.evaluate("e => e.scrollIntoView({block: 'start'})")
                page.wait_for_timeout(500)
                page.screenshot(animations="disabled", path=str(output / "transformer-side-quest.png"))
                frame(page, "PDF 翻到第 4 页标出 ①②；讲解页直接在对话里展开", 3200)
                card.locator(".xp-section").nth(1).scroll_into_view_if_needed()
                page.wait_for_timeout(400)
                frame(page, "每一块都能单独追问：“点积为什么会变大”", 2600)
                # A follow-up on panel B becomes page 2 of the same side quest.
                follow = "B「点积为什么会变大」这一块我没看懂，请换个说法，或者举一个小例子。"
                say(coach, conversation, "user", follow, intent="detour", step="method", branch_id=record["id"])
                second_id = uid()
                second = coach.save_explainer(paper["id"], conversation, FOLLOW_UP, message_id=second_id, branch_id=record["id"],
                                              question=follow)
                say(coach, conversation, "assistant", "**预设带读示例 · 非实时模型回复**\n\n换成一个具体的数：见第 2 页。",
                    id=second_id, intent="detour", step="method", actions=[coach.explainer_action(second)])
                page.get_by_role("button", name="支线 · 第 2 页 用 d_k = 64 算一遍", exact=False).first.wait_for()
                cards = page.locator(".xp-card")
                cards.last.locator(".xp-grid").wait_for()
                page.wait_for_timeout(700)
                cards.last.evaluate("e => e.scrollIntoView({block: 'start'})")
                page.wait_for_timeout(400)
                frame(page, "没看懂就追问那一块：同一条支线的第 2 页", 2800)
                quest = page.get_by_role("group", name="支线任务").first
                quest.get_by_role("button", name="我弄懂了").click()
                quest.get_by_label("用一句话写下你弄懂了什么（可以不写）").fill(
                    "维度大时点积的方差是 d_k，除以 √d_k 把它拉回 1，softmax 才不会只盯一个位置。")
                quest.get_by_role("button", name="记下，支线完成").click()
                page.get_by_text("支线完成：已弄懂").first.wait_for()
                page.get_by_text("支线完成：已弄懂").first.scroll_into_view_if_needed()
                page.wait_for_timeout(500)
                page.screenshot(animations="disabled", path=str(output / "transformer-side-quest-done.png"))
                frame(page, "弄懂了：用自己的话记一句，支线完成", 2800)
                page.close()

                # Two more side quests from chapter 4, for the quest log and the journey tree.
                for name, key, ask, status, mine in (
                    ("transformer-multihead", "multihead", "为什么要 8 个头，一个头不够吗？", "parked", ""),
                    ("transformer-positions", "positions", "没有循环，模型怎么知道词的顺序？", "done",
                     "把不同频率的正弦和余弦加到词向量上，位置就写进去了。"),
                ):
                    mid = uid()
                    say(coach, conversation, "user", ask, intent="detour", step="method", anchor={**focus[key]["anchor"], "rects": []})
                    side = coach.save_explainer(paper["id"], conversation, fixture(name), message_id=mid, question=ask,
                                                anchor=focus[key]["anchor"])
                    say(coach, conversation, "assistant", "**预设带读示例 · 非实时模型回复**\n\n讲解页在下面。", id=mid, intent="detour",
                        step="method", actions=[coach.explainer_action(side)])
                    coach.set_quest(side["id"], status, mine)

                # ---- Scene B: the mainline, chapter 5, Table 1 on page 6.
                say(coach, conversation, "user", "（预设）Q 和 K 算相似度，除以 √d_k 后做 softmax，再给 V 加权。", intent="answer", step="method")
                say(coach, conversation, "assistant", "**预设带读示例 · 非实时模型回复**\n\n对，这就是一个完整的因果环节。第 4 章完成。",
                    intent="answer", step="method", completed_step={"step": "method", "label": "方法机制", "takeaway": TAKEAWAYS[3][2], "page_index": 3})
                task = {"question": "先猜：三种层里，哪一种连接任意两个位置的路径最短？", "choices": ["自注意力", "循环", "卷积"]}
                set_flow(store, paper, 4, pending_question=task["question"], choices=task["choices"],
                         next_action="对照表 1，说出自注意力在哪一列占优、代价在哪一列。")
                main_id = uid()
                figure = coach.save_explainer(paper["id"], conversation, fixture("transformer-table1"), message_id=main_id, origin="mainline")
                mark = {**focus["table1"], "id": "focus:" + main_id, "label": "第 6 页 · 表 1", "note": "表 1"}
                say(coach, conversation, "assistant",
                    "**预设带读示例 · 非实时模型回复**\n\n第 5 章：证据核查。① 是表 1 的标题，这张表比较三种层的代价。\n\n先别看数字，**猜一猜**：哪一种连接任意两个位置的路径最短？",
                    id=main_id, intent="follow", step="evidence", task=task, actions=[mark, coach.explainer_action(figure)])
                page = open_page(ratio="0.58")
                page.goto(url)
                card = page.locator(".quest-card").last
                card.wait_for()
                page.get_by_role("figure", name="图解：表 1：三种层的代价").wait_for()
                card.get_by_title("在 PDF 里看这一句").first.click()
                page.locator(".coach-mark").first.wait_for()
                page.wait_for_timeout(900)
                card.evaluate("e => e.scrollIntoView({block: 'start'})")
                page.wait_for_timeout(400)
                page.screenshot(animations="disabled", path=str(output / "transformer-mainline.png"))
                frame(page, "回到主线：第 5 章，PDF 翻到表 1，先猜再看", 3000)
                page.emulate_media(color_scheme="dark")
                page.wait_for_timeout(300)
                page.screenshot(animations="disabled", path=str(output / "transformer-mainline-dark.png"))
                page.emulate_media(color_scheme="light")
                page.get_by_role("button", name="任务日志").first.click()
                log = page.get_by_role("dialog", name="任务日志")
                log.get_by_text("我的收获：维度大时").wait_for()
                page.wait_for_timeout(400)
                page.screenshot(animations="disabled", path=str(output / "transformer-quest-log.png"))
                frame(page, "任务日志：主线 8 章，每章下挂着它的支线", 2800)
                page.close()

                # ---- Scene C: the whole reading as a tree, after all eight chapters.
                say(coach, conversation, "user", "自注意力：每个位置都直接看所有位置。", intent="answer", step="evidence")
                say(coach, conversation, "assistant", "**预设带读示例 · 非实时模型回复**\n\n对，表 1 第一行的最长路径是 O(1)。代价是每层 O(n²·d)，序列很长时会变贵。",
                    intent="answer", step="evidence")
                for step, words, reply in (
                    ("synthesis", "改变了：不用循环也能做强的翻译。证据到翻译和句法分析。如果长文档上明显变差，我会改判断。",
                     "三句话都有了，而且说出了什么会让你改判断。"),
                    ("recall", "Q·K 除以 √d_k，softmax 后乘 V；8 个头；位置编码。", "回忆完整。复习题已经留下。"),
                ):
                    say(coach, conversation, "user", words, intent="answer", step=step)
                    say(coach, conversation, "assistant", "**预设带读示例 · 非实时模型回复**\n\n" + reply, intent="answer", step=step)
                set_flow(store, paper, 8, pending_question="", choices=[], next_action="")
                say(coach, conversation, "assistant", "**预设带读示例 · 非实时模型回复**\n\n八章都读完了。复盘树里是这一路的全部记录。",
                    intent="answer", step="recall",
                    completed_step={"step": "recall", "label": "回忆与复习", "takeaway": TAKEAWAYS[7][2], "page_index": 3})
                tree = open_page(width=1100, height=1400)
                tree.goto(url)  # signs this browser in, as the reading window does before it opens the tree
                tree.locator(".coach-panel").wait_for()
                tree.goto(f"http://127.0.0.1:{port}/#" + urlencode({"journey": paper["id"]}))
                tree.reload()
                tree.get_by_text("我的核心判断").wait_for()
                tree.wait_for_timeout(600)
                tree.screenshot(animations="disabled", path=str(output / "transformer-journey.png"), full_page=False)
                tree.emulate_media(color_scheme="dark")
                tree.wait_for_timeout(300)
                tree.screenshot(animations="disabled", path=str(output / "transformer-journey-dark.png"))
                tree.emulate_media(color_scheme="light")
                tree.set_viewport_size({"width": 1440, "height": 1000})
                tree.wait_for_timeout(300)
                frame(tree, "读完以后：一棵复盘树，主线、支线、原话和收获都在", 3400)
                tree.close()
                browser.close()
            save_demo(frames, output / "demo-transformer.webp", durations=durations)
        finally:
            server.should_exit = True
            thread.join(timeout=10)
        assert not errors, errors
        report.update(frames=len(frames), browser_errors=errors, dialogue="scripted, not live AI")
        return report


# Page 2 of the √d_k side quest: the reader did not follow panel B, so the coach uses one number.
FOLLOW_UP = """---
title: 用 d_k = 64 算一遍
subtitle: 预设讲解示例 · 接着第 1 页的 B
---
先说结论：64 个随机乘积加起来，结果常常在 ±8 左右，而不是 ±1。softmax 看到 ±8 这样的差距，几乎把全部权重给最大的那一个。

## 一个小例子 {span=2}
```flow LR
(64 对 q_i·k_i) -> 相加: 每项方差 1
相加 -> *点积: 方差 64，标准差 8
*点积 -> 除以 8
除以 8 -> (标准差回到 1)
```

## softmax 看到的差距
| 两个分数 | softmax 给大的那个 |
|---|---|
| 1 和 0 | 约 73% |
| 8 和 0 | no 约 99.97% |
"""


def main():
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--pdf", type=Path, help="a local copy of arXiv:1706.03762v7 (otherwise downloaded)")
    cli.add_argument("--output", type=Path, default=Path("docs/images"))
    cli.add_argument("--chromium", default=os.environ.get("CHROMIUM_PATH"))
    args = cli.parse_args()
    print(capture(args.output, args.pdf, args.chromium))


if __name__ == "__main__":
    main()
