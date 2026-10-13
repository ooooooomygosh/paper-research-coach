"""Capture the real built UI with synthetic source and explicitly scripted dialogue.

Optional developer dependencies: playwright; a Chromium installation. No AI request,
personal-library access or telemetry. Images are layout examples, not model evidence.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import threading
import time
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

import uvicorn
from paper_research_coach.demo import prepare_demo
from paper_research_coach.server import create_app, session_token


def capture(output: Path, executable: str | None = None) -> None:
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="prc-showcase-") as directory:
        store, paper = prepare_demo(Path(directory))
        token = session_token(store)
        app = create_app(store, token)
        coach = app.state.coach
        conversation = coach.binding(paper["id"])["conversation_id"]
        anchor = store.list("note", paper["id"])[0]["anchor"]
        messages = [
            ("user", "【预设读者问题】这里没有误差条。这个提升会不会只是因为测量次数更多？", anchor),
            ("assistant", "**预设带读示例 · 非实时模型回复**\n\n先看第 2 页：两组都是 **20 次观测**。这排除了“只是测量更多”这个解释，但还不能证明时机选择稳定有效。\n\n原文同时写着：*No error bars, repeated runs or trajectory details are reported.*\n\n我们现在只核对一个问题：**还缺什么证据，才能相信这 2 个单位的差距？**", anchor),
        ]
        for index, (role, content, source) in enumerate(messages):
            coach.save_message({"id": f"showcase-{index}", "conversation_id": conversation,
                                "role": role, "content": content, "status": "completed",
                                "anchor": source, "intent": "detour"})
        # A scripted branch explainer, labelled as such in its own subtitle.
        draft = (Path(__file__).resolve().parents[1] / "tests/fixtures/explainers/budget-zh.md").read_text(encoding="utf-8")
        coach.explain_external(paper["id"], draft.replace("subtitle: 先对齐预算，再比较效果", "subtitle: 预设讲解示例 · 非实时模型回复"),
                               question="这个提升会不会只是因为测量次数更多？", anchor=anchor)

        async def preview_status():
            return {"state": "unavailable", "models": [], "skill": "paper-research-coach",
                    "message": "展示使用预设对话，未发起模型请求。"}
        coach.status = preview_status
        # Ask the OS for a free loopback port; never stop an unrelated service.
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
                                              access_log=False, log_level="error"))
        thread = threading.Thread(target=server.run, daemon=True)
        thread.start()
        try:
            deadline = time.monotonic() + 15
            while not server.started:
                if not thread.is_alive() or time.monotonic() > deadline:
                    raise RuntimeError("The local showcase server did not start.")
                time.sleep(0.05)
            with sync_playwright() as playwright:
                # Software rendering avoids black PDF captures on headless macOS GPUs.
                options = {"headless": True, "args": ["--disable-gpu"]}
                if executable:
                    options["executable_path"] = executable
                browser = playwright.chromium.launch(**options)
                page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=1)
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.add_init_script("window.cspViolations = []; document.addEventListener('securitypolicyviolation', e => window.cspViolations.push(e.violatedDirective))")
                page.goto(f"http://127.0.0.1:{port}/#" + urlencode({"token": token, "paper": paper["id"]}))
                page.get_by_text("预设带读示例 · 非实时模型回复", exact=True).wait_for()
                page.locator(".pdf-page[data-page-index='1'] canvas").wait_for()
                page.wait_for_timeout(700)
                page.screenshot(animations="disabled", path=str(output / "reading.png"))
                # Verify the rendered fixture, not just the existence of a canvas.
                assert page.locator(".textLayer").first.text_content().strip()
                from PIL import Image
                with Image.open(output / "reading.png") as shot:
                    assert min(shot.convert("RGB").getpixel((30, 90))) > 230, "PDF paper is not visible"
                # The same scene in the dark theme, for the README's <picture> element.
                page.emulate_media(color_scheme="dark")
                page.wait_for_timeout(300)
                page.screenshot(animations="disabled", path=str(output / "reading-dark.png"))
                page.emulate_media(color_scheme="light")
                passage = page.locator(".textLayer span").filter(has_text="Both policies receive 20 observations per episode.")
                passage.evaluate("""e => {
                    const range = document.createRange(); range.selectNodeContents(e);
                    const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
                    e.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
                }""")
                selected = page.get_by_role("dialog", name="原文选区", exact=True)
                selected.wait_for()
                assert "Both policies receive" in selected.inner_text()
                page.get_by_label("关闭译文", exact=True).click()
                page.evaluate("window.getSelection().removeAllRanges()")
                assert page.evaluate("window.cspViolations") == []
                divider = page.get_by_role("separator", name="调整 PDF 与对话宽度")
                original_ratio = int(divider.get_attribute("aria-valuenow"))
                divider.focus()
                divider.press("ArrowLeft")
                assert int(divider.get_attribute("aria-valuenow")) < original_ratio
                divider.press("ArrowRight")
                assert int(divider.get_attribute("aria-valuenow")) == original_ratio
                page.locator(".pdf-page[data-page-index='1'] canvas").wait_for()
                # Page input is a draft: typing does not navigate; Escape cancels.
                cursor = page.get_by_label("阅读页码", exact=True)
                before = cursor.input_value()
                scrolled = page.locator(".pdf-scroll").evaluate("e => e.scrollTop")
                cursor.fill("3")
                page.wait_for_timeout(200)
                assert page.locator(".pdf-scroll").evaluate("e => e.scrollTop") == scrolled
                cursor.press("Escape")
                assert cursor.input_value() == before
                # Exercise real native dialog focus containment and restoration.
                page.get_by_label("更多阅读工具", exact=True).click()
                page.get_by_role("button", name="更多", exact=True).click()
                opener = page.get_by_role("button", name="论文信息与版本", exact=True)
                opener.click()
                dialog = page.get_by_role("dialog", name="论文信息与版本", exact=True)
                for _ in range(22):
                    page.keyboard.press("Tab")
                    assert dialog.evaluate("d => d.contains(document.activeElement)")
                page.keyboard.press("Escape")
                assert opener.evaluate("e => e === document.activeElement")
                page.keyboard.press("Escape")
                assert page.get_by_label("更多阅读工具", exact=True).evaluate("e => e === document.activeElement")
                # Branch explainer: a question answered beside the paper; one click returns to the mainline.
                branch = browser.new_page(viewport={"width": 1440, "height": 1000})
                branch.add_init_script("localStorage.setItem('prc-pane-ratio', '0.58')")  # a wider conversation for the picture
                branch.goto(f"http://127.0.0.1:{port}/#" + urlencode({"token": token, "paper": paper["id"]}))
                card = branch.locator(".xp-card-toggle").filter(has_text="为什么这个比较不公平").first
                card.wait_for()
                branch.wait_for_timeout(500)
                assert card.get_attribute("aria-expanded") == "false", "an old explainer page must stay folded on load"
                assert not branch.get_by_role("dialog", name="讲解面板").count()
                card.click()
                branch.locator(".xp-card .xp-grid").wait_for()
                branch.locator(".xp-card").first.evaluate("e => e.scrollIntoView({block: 'start'})")
                branch.wait_for_timeout(600)
                branch.screenshot(animations="disabled", path=str(output / "branch-card.png"))
                branch.get_by_role("button", name="放大到侧边").first.click()
                panel = branch.get_by_role("dialog", name="讲解面板")
                panel.wait_for()
                panel.get_by_text("预设讲解示例 · 非实时模型回复").wait_for()  # the content has loaded
                assert panel.get_by_role("img", name="流程图：", exact=False).count()
                branch.wait_for_timeout(500)
                branch.screenshot(animations="disabled", path=str(output / "branch.png"))
                branch.emulate_media(color_scheme="dark")
                branch.wait_for_timeout(300)
                branch.screenshot(animations="disabled", path=str(output / "branch-dark.png"))
                branch.emulate_media(color_scheme="light")
                panel.get_by_role("button", name="回到主线").click()
                assert not branch.get_by_role("dialog", name="讲解面板").count()
                assert branch.get_by_label("发给论文教练的消息", exact=True).evaluate("e => e === document.activeElement")
                # Side quest: the reader closes it in their own words; the quest log files it under its chapter.
                quest = branch.get_by_role("group", name="支线任务").first
                quest.get_by_role("button", name="我弄懂了").click()
                quest.get_by_label("用一句话写下你弄懂了什么（可以不写）").fill("观测次数不同，比较就不公平；先把预算对齐再看差距。")
                quest.get_by_role("button", name="记下，支线完成").click()
                branch.get_by_text("支线完成：已弄懂").first.wait_for()
                quest.scroll_into_view_if_needed()
                branch.wait_for_timeout(300)
                branch.screenshot(animations="disabled", path=str(output / "side-quest-done.png"))
                branch.get_by_role("button", name="任务日志").first.click()
                log = branch.get_by_role("dialog", name="任务日志")
                log.get_by_text("我的收获：观测次数不同").wait_for()
                branch.wait_for_timeout(300)
                branch.screenshot(animations="disabled", path=str(output / "quest-log.png"))
                branch.keyboard.press("Escape")
                assert not log.count()
                branch.close()
                # Narrow viewport checks are not a claim about iPad/Pencil hardware.
                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(200)
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                page.screenshot(animations="disabled", path=str(output / "reading-narrow.png"))
                # Empty-library API fixture; the application rendering is unchanged.
                welcome = browser.new_page(viewport={"width": 1440, "height": 1000})
                welcome.route("**/api/state", lambda route: route.fulfill(json={"papers": [], "sync": {}, "conflicts": []}))
                welcome.goto(f"http://127.0.0.1:{port}/#" + urlencode({"token": token}))
                welcome.locator("#welcome-title").wait_for()
                welcome.screenshot(animations="disabled", path=str(output / "welcome.png"))
                welcome.get_by_role("button", name="导入论文", exact=True).click()
                welcome.get_by_role("dialog", name="打开一篇论文", exact=True).wait_for()
                welcome.screenshot(animations="disabled", path=str(output / "import.png"))
                for _ in range(15):
                    welcome.keyboard.press("Tab")
                    assert welcome.get_by_role("dialog").evaluate("d => d.contains(document.activeElement)")
                welcome.keyboard.press("Escape")
                assert welcome.get_by_role("button", name="导入论文", exact=True).evaluate("e => e === document.activeElement")
                # Reduced motion removes both entry motion and legacy hover transitions.
                welcome.emulate_media(reduced_motion="reduce")
                welcome.get_by_role("button", name="导入论文", exact=True).click()
                assert welcome.get_by_role("dialog").evaluate("e => getComputedStyle(e).animationName") == "none"
                assert welcome.get_by_role("button", name="关闭导入").evaluate("e => getComputedStyle(e).transitionDuration") == "0s"
                welcome.keyboard.press("Escape")
                welcome.set_viewport_size({"width": 390, "height": 844})
                assert welcome.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")
                welcome.screenshot(animations="disabled", path=str(output / "welcome-narrow.png"))
                # Touch users must be able to exit immersion directly, without a keyboard.
                touch = browser.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
                tablet = touch.new_page()
                tablet.on("pageerror", lambda error: errors.append(str(error)))
                tablet.goto(f"http://127.0.0.1:{port}/#" + urlencode({"token": token, "paper": paper["id"]}))
                tablet.get_by_label("进入沉浸模式", exact=True).tap()
                exit_button = tablet.get_by_label("退出沉浸模式", exact=True)
                assert exit_button.is_visible()
                box = exit_button.bounding_box()
                assert box and box["width"] >= 44 and box["height"] >= 44
                assert not tablet.get_by_label("更多阅读工具", exact=True).is_visible()
                exit_button.tap()
                assert tablet.get_by_label("进入沉浸模式", exact=True).is_visible()
                touch.close()
                from check_pdf_controls import check_pdf_controls
                controls = check_pdf_controls(browser, store, paper, port, token, output)
                mainline_scene(browser, store, coach, paper, conversation, port, token, output, errors)
                browser.close()
                if errors:
                    raise RuntimeError("Browser errors: " + "; ".join(errors))
                print(json.dumps({**controls, "browser_errors": errors, "viewport": [1440, 1000],
                                  "narrow_viewport": [390, 844], "dialog_focus": "passed",
                                  "reduced_motion": "passed", "touch_immersion_exit": "passed",
                                  "keyboard_divider": "passed", "source": "synthetic", "dialogue": "scripted, not live AI"}, ensure_ascii=False))
        finally:
            server.should_exit = True
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError("The showcase server did not stop cleanly.")


FIGURE = """---
title: 预算相同后，差距还剩多少
subtitle: 预设图解示例 · 非实时模型回复
---
先说结论：两组都观测 20 次，预算相同；差距只剩 2 个单位，而且没有误差范围。

## 第 2 页的三组数字
| 策略 | 观测次数 | 效用 | 能比吗 |
|---|---|---|---|
| 固定时钟 | 20 | 61 | ok |
| 事件触发 | 20 | 63 | ok |
| 信息上限 | 20 | 66 | warn 只是参照 |
"""


def demo_frame(page, caption):
    """One frame of the README demo: the real page plus a caption drawn by the browser."""
    page.evaluate("""text => {
        let tag = document.getElementById('demo-caption');
        if (!tag) {
            tag = document.createElement('div');
            tag.id = 'demo-caption';
            tag.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:9999;padding:10px 20px;' +
                'border-radius:999px;background:#203229e6;color:#fbfbf7;font:600 20px/1.3 system-ui,sans-serif;box-shadow:0 6px 24px #0004;pointer-events:none';
            document.body.append(tag);
        }
        tag.textContent = text;
    }""", caption)
    shot = page.screenshot(animations="disabled")
    page.evaluate("document.getElementById('demo-caption')?.remove()")
    return shot


def save_demo(frames, path, width=960):
    """An animated WebP small enough for a README (each frame held long enough to read)."""
    import io

    from PIL import Image

    images = []
    for data in frames:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        images.append(image.resize((width, round(image.height * width / image.width)), Image.LANCZOS))
    images[0].save(path, save_all=True, append_images=images[1:], duration=[2600, 2800, 2800, 2400], loop=0, quality=72, method=6)


def mainline_scene(browser, store, coach, paper, conversation, port, token, output, errors):
    """The mainline as a task: the PDF turns to a marked sentence and a small figure sits in the reply."""
    from paper_research_coach import reading
    from paper_research_coach.models import now

    session = store.list("session", paper["id"])[0]
    with store.connect() as db:
        session = reading.begin(store, store.get("paper", paper["id"]), session, db)
    takeaways = [("orient", "我要判断：提升来自观测时机，还是只来自更多观测。"),
                 ("insight", "贡献句：在相同预算下，事件触发改变的是何时观测。"),
                 ("model", "输入是估计的决策损失，输出是何时观测。"),
                 ("method", "损失变大时才观测，把预算花在会改变决策的时刻。")]
    done = [{"step": k, "evidence": "预设示例", "page_index": 0, "finished_at": now(), "takeaway": t} for k, t in takeaways]
    # Start on page 1, so the coach visibly takes the reader to page 2.
    cursor = {**session["cursor"], "page_index": 0, "page_label": "1"} if session.get("cursor") else None
    store.put("session", {**session, "cursor": cursor, "reading_flow": {**session["reading_flow"], "completed": done}, "stage": "evidence",
                          "pending_question": "两组预算相同后，你预测效用差距还会在吗？",
                          "choices": ["几乎消失", "仍然明显", "说不准，要看误差"]}, session["revision"])
    figure = coach.save_explainer(paper["id"], conversation, FIGURE, message_id="showcase-main", origin="mainline")
    focus, _ = coach.focus_action(paper["id"], 1, ["Both policies receive 20 observations per episode."], "预算是否相同")
    focus["id"] = "focus:showcase-main"
    coach.save_message({"id": "showcase-main", "conversation_id": conversation, "role": "assistant", "status": "completed",
                        "intent": "follow", "step": "evidence", "created_at": now(), "actions": [focus, coach.explainer_action(figure)],
                        "task": {"question": "两组预算相同后，你预测效用差距还会在吗？", "choices": ["几乎消失", "仍然明显", "说不准，要看误差"]},
                        "content": "**预设带读示例 · 非实时模型回复**\n\n现在看证据。① 说两组都观测 20 次，预算是对齐的。\n\n先别看结果：**预算相同后，你预测差距还会在吗？**"})
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.add_init_script("localStorage.setItem('prc-pane-ratio', '0.58')")  # a wider conversation for the picture
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(f"http://127.0.0.1:{port}/#" + urlencode({"token": token, "paper": paper["id"]}))
    quest = page.locator(".quest-card").first
    quest.wait_for()
    page.get_by_role("figure", name="图解：预算相同后，差距还剩多少").wait_for()
    assert quest.get_by_role("button", name="几乎消失").is_visible()
    page.locator(".pdf-page[data-page-index='0'] canvas").wait_for()
    page.wait_for_timeout(500)
    frames = [demo_frame(page, "预设演示 · 主线任务卡：看哪里、做什么、怎样算完成")]
    quest.get_by_title("在 PDF 里看这一句").first.click()
    mark = page.locator(".coach-mark").first
    mark.wait_for()
    page.wait_for_timeout(700)
    # The mark sits on the words it names (the server's PDF coordinates meet pdf.js's layout).
    words = page.locator(".textLayer span").filter(has_text="Both policies receive 20 observations per episode.").first.bounding_box()
    box = mark.bounding_box()
    assert abs(box["x"] - words["x"]) < 4 and abs(box["y"] + box["height"] - words["y"] - words["height"]) < 5, (box, words)
    assert page.get_by_label("阅读页码", exact=True).input_value() == "2"
    page.screenshot(animations="disabled", path=str(output / "mainline.png"))
    page.emulate_media(color_scheme="dark")
    page.wait_for_timeout(300)
    page.screenshot(animations="disabled", path=str(output / "mainline-dark.png"))
    page.emulate_media(color_scheme="light")
    page.wait_for_timeout(300)
    frames.append(demo_frame(page, "PDF 翻到第 2 页，要看的句子标上 ①"))
    page.get_by_role("figure").get_by_role("button", name="展开全部").click()
    page.locator(".xp-inline table").scroll_into_view_if_needed()
    page.wait_for_timeout(300)
    frames.append(demo_frame(page, "回复里嵌着一张小图；预测题可以一键作答"))
    page.get_by_role("button", name="回到第 1 页").click()
    page.wait_for_timeout(700)
    frames.append(demo_frame(page, "一键回到你原来读的地方"))
    save_demo(frames, output / "demo.webp")
    # Scrolling moves the page number; the "back" chip returns to where the reader was.
    page.locator(".pdf-scroll").evaluate("e => e.scrollTo(0, e.scrollHeight)")
    page.wait_for_function("() => document.querySelector('[aria-label=\"阅读页码\"]').value === '3'")
    # The quest log and the journey tree: chapters, my takeaways, side quests.
    page.get_by_role("button", name="任务日志").first.click()
    log = page.get_by_role("dialog", name="任务日志")
    log.get_by_text("收获：贡献句").wait_for()
    page.wait_for_timeout(300)
    page.screenshot(animations="disabled", path=str(output / "quest-log-main.png"))
    log.get_by_role("button", name="复盘树").click()
    tree = page.get_by_role("dialog", name="复盘树")
    tree.get_by_text("我要判断：提升来自观测时机").wait_for()
    page.wait_for_timeout(400)
    page.screenshot(animations="disabled", path=str(output / "journey.png"))
    page.emulate_media(color_scheme="dark")
    page.wait_for_timeout(300)
    page.screenshot(animations="disabled", path=str(output / "journey-dark.png"))
    page.emulate_media(color_scheme="light")
    tree.get_by_role("button", name="关闭复盘树").click()
    page.close()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, default=Path("docs/images"))
    cli.add_argument("--chromium", default=os.environ.get("CHROMIUM_PATH"))
    args = cli.parse_args()
    capture(args.output, args.chromium)


if __name__ == "__main__":
    main()
