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
            ("user", "【预设读者问题】这个提升，会不会只是因为测量次数更多？", anchor),
            ("assistant", "**预设带读示例 · 非实时模型回复**\n\n先看第 2 页：两组都是 **20 次观测**。这排除了“只是测量更多”这个解释，但还不能证明时机选择稳定有效。\n\n原文同时写着：*No error bars, repeated runs or trajectory details are reported.*\n\n我们现在只核对一个问题：**还缺什么证据，才能相信这 2 个单位的差距？**", anchor),
        ]
        for index, (role, content, source) in enumerate(messages):
            coach.save_message({"id": f"showcase-{index}", "conversation_id": conversation,
                                "role": role, "content": content, "status": "completed",
                                "anchor": source, "intent": "detour"})
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
                assert page.locator(".textLayer").text_content().strip()
                from PIL import Image
                with Image.open(output / "reading.png") as shot:
                    assert min(shot.convert("RGB").getpixel((30, 90))) > 230, "PDF paper is not visible"
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
                cursor.fill("3")
                assert page.locator(".pdf-page").get_attribute("data-page-index") == str(int(before) - 1)
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


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, default=Path("docs/images"))
    cli.add_argument("--chromium", default=os.environ.get("CHROMIUM_PATH"))
    args = cli.parse_args()
    capture(args.output, args.chromium)


if __name__ == "__main__":
    main()
