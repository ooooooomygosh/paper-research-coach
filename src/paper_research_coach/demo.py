"""Disposable, synthetic reading material. No model call or personal-library access."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlencode

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from .store import Store


def _write_pdf(path: Path) -> None:
    """Generate an original, searchable fixture with existing runtime dependencies."""
    writer = PdfWriter()
    pages = [
        (
            "When should a sensor observe?",
            "A budget-matched thought experiment",
            [
                "1. The question",
                "Fresh observations can improve a decision, but cost time and energy.",
                "Does event-triggered sensing win because of better timing,",
                "or simply because it purchases more information?",
                "",
                "2. A provisional mechanism",
                "The policy observes when estimated decision loss grows.",
                "The claim is to spend a fixed budget at action-changing moments.",
                "Better timing and a larger budget are different explanations.",
                "",
                "3. A discriminating test",
                "Compare policies at the SAME number of observations.",
                "Measure downstream decision utility and observation cost together.",
                "Before looking at the next page, predict what would change.",
            ],
        ),
        (
            "Does the evidence separate the explanations?",
            "Figure 1 / invented values, NOT an experiment",
            [
                "Both policies receive 20 observations per episode.",
                "If more observations explained all the gain, what would remain?",
                "",
                "Fixed schedule:       61 utility units",
                "Event-triggered:      63 utility units",
                "Information oracle:   66 utility units",
                "",
                "These numbers are invented for reading practice.",
                "No error bars, repeated runs or trajectory details are reported.",
                "A small difference is not evidence of a reliable advantage.",
                "",
                "What uncertainty or alternative explanation would you test next?",
            ],
        ),
        (
            "From a judgment to a small test",
            "One falsifiable question; one stopping condition",
            [
                "Observation: the budget-matched difference is small.",
                "Hypothesis: timing matters near action-changing events.",
                "Alternative: favorable trajectories explain the average gain.",
                "Simple baseline: a threshold rule with the same sensing budget.",
                "Smallest test: compare slow changes and abrupt changes separately.",
                "Falsification: no consistent advantage in either condition.",
                "Stopping condition: even the oracle has little useful headroom.",
                "",
                "Your judgment may be: this is not worth making more complex.",
                "That is a valid reading outcome, not an unfinished summary.",
            ],
        ),
    ]
    for number, (title, subtitle, body) in enumerate(pages, 1):
        page = writer.add_blank_page(width=612, height=792)
        font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                 NameObject("/Subtype"): NameObject("/Type1"),
                                 NameObject("/BaseFont"): NameObject("/Helvetica")})
        page[NameObject("/Resources")] = DictionaryObject({
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
        commands = []

        def text(x, y, size, value):
            escaped = value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"BT /F1 {size} Tf {x} {y} Td ({escaped}) Tj ET")

        commands.append("0.20 0.34 0.26 rg")
        text(48, 747, 9, "PAPER RESEARCH COACH / SYNTHETIC TEACHING MATERIAL")
        text(48, 696, 19, title)
        text(48, 670, 11, subtitle)
        commands.append("0.84 0.88 0.83 RG 48 650 m 564 650 l S")
        commands.append("0.16 0.20 0.17 rg")
        for line, value in enumerate(body):
            text(48, 615 - line * 25, 11, value)
        text(48, 34, 9, "Fictional study for reading practice. No empirical claim.")
        text(550, 34, 9, str(number))
        stream = DecodedStreamObject()
        stream.set_data("\n".join(commands).encode("ascii"))
        page[NameObject("/Contents")] = stream
    writer.add_metadata({"/Title": "Synthetic reading practice", "/Author": "Paper Research Coach"})
    with path.open("wb") as output:
        writer.write(output)


def prepare_demo(root: Path) -> tuple[Store, dict]:
    """Only populate a fresh directory; never reuse or modify an existing library."""
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    if any(root.iterdir()):
        raise ValueError("示例需要空目录，不会覆盖已有文件或书库。")
    pdf = root / "synthetic-reading.pdf"
    _write_pdf(pdf)
    store = Store(root)
    paper = store.add_paper(
        "示例 · 何时值得获取一次新观测？（合成材料）", str(pdf),
        authors="Paper Research Coach · 非真实研究", year="2026", status="reading",
        goal="区分机制收益与额外信息的收益",
    )
    session = store.list("session", paper["id"])[0]
    anchor = {"paper_id": paper["id"], "source_version": paper["source_version"],
              "page_index": 1, "page_label": "2", "status": "verified"}
    store.put("session", {**session, "stage": "evidence", "cursor": anchor,
                          "next_action": "比较第 2 页相同预算下的结果，检查是否足以支持结论。",
                          "pending_question": "还需要什么证据，才能排除另一种解释？"}, session["revision"])
    store.put("note", {"paper_id": paper["id"],
                       "content": "【示例原话】预算相同后仍有一点差距，但没有误差范围，我还不能相信这个优势。",
                       "anchor": {**anchor, "quote": "No error bars, repeated runs or trajectory details are reported."}})
    store.set_setting("active-paper", paper["id"])
    return store, paper


def serve_demo(port: int = 8766, no_open: bool = False) -> None:
    """Run in the foreground; Ctrl+C removes demo files, not the user's library."""
    import threading
    import webbrowser
    import uvicorn
    from .server import create_app, session_token

    if not 1024 <= port <= 65535:
        raise ValueError("请选择 1024–65535 之间的端口。")
    with TemporaryDirectory(prefix="prc-demo-") as directory:
        store, paper = prepare_demo(Path(directory))
        token = session_token(store)
        fragment = urlencode({"token": token, "paper": paper["id"]})
        url = f"http://127.0.0.1:{port}/#{fragment}"
        print("合成阅读示例 · 独立临时书库 · 未连接 Zotero · 未发起模型请求", flush=True)
        print("Ctrl+C 退出并清理示例记录；需要保留的笔记请先导出。", flush=True)
        print(f'另一个终端可运行：prc --data-dir "{directory}" open --port {port}', flush=True)
        timer = None
        if not no_open:
            timer = threading.Timer(1.5, lambda: webbrowser.open(url))
            timer.start()
        try:
            uvicorn.run(create_app(store, token), host="127.0.0.1", port=port,
                        access_log=False, timeout_graceful_shutdown=3)
        finally:
            if timer:
                timer.cancel()


def parser():
    import argparse
    cli = argparse.ArgumentParser(description="Open a disposable, synthetic reading library.")
    cli.add_argument("--port", type=int, default=8766)
    cli.add_argument("--no-open", action="store_true", help="Do not open the browser automatically")
    return cli


def main():
    args = parser().parse_args()
    serve_demo(port=args.port, no_open=args.no_open)


if __name__ == "__main__":
    main()
