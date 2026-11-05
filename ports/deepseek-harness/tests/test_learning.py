import asyncio
import json
import re
from pathlib import Path

import httpx

from paper_research_coach.server import create_app
from paper_research_coach.store import Store
from paper_research_coach.workspaces import read_json


class LearningText:
    """Explicit test author; production uses Harness's signed-in account."""
    calls = []
    fail_text = ""
    no_methods = False

    def __init__(self, *args):
        pass

    async def close(self):
        pass

    async def text(self, prompt, schema=None, **kwargs):
        title = (schema or {}).get("title")
        self.calls.append((title, prompt))
        if title == "Lesson":
            text = re.search(r"<source_data>\n([\s\S]*?)\n</source_data>", prompt)[1]
            if self.fail_text and self.fail_text in text:
                raise ValueError("Synthetic account interruption")
            quote = text.strip()[:120]
            if "REFERENCES_ONLY" in text:
                return json.dumps({"role": "references", "title": "引用列表", "core": "这里只列出引用。", "quote": quote, "takeaways": [], "concepts": [], "glossary": [], "methods": [], "questions": [], "disposition_reason": "合成引用列表，不伪造正文。"})
            value = {"role": "content", "title": "比较条件与证据", "core": "比较需要匹配预算，并保留不确定性。", "quote": quote,
                "takeaways": ["核对比较条件。", "证据不足时保留判断。"],
                "concepts": [{"name": "预算匹配", "explanation": "用相同预算进行比较。", "when": "解释比较结果时", "quote": quote}],
                "glossary": [{"term": "预算匹配", "definition": "保持比较双方预算一致。", "context": "本段讨论公平比较。", "quote": quote, "full_name": "", "meaning": ""}],
                "methods": [] if self.no_methods else [{"name": "预算匹配比较", "kind": "framework", "summary": "先匹配预算，再判断证据。", "problem": "比较条件不同", "when": "比较策略时", "rationale": "避免将预算优势误认作策略优势。",
                    "prerequisites": ["知道比较双方预算。"], "limitations": ["原文没有给出成功保证。"], "steps": [{"action": "核对双方预算相同。", "input": "两个策略及预算", "output": "预算匹配的比较", "check": "确认观测次数相同。"}],
                    "success_checks": ["比较条件清楚。"], "tags": ["预算", "比较"], "quote": quote}],
                "questions": [{"question": "比较前应该先核对什么？", "options": ["双方预算是否相同", "先假定某策略成功"], "correct": 0, "explanation": "原文要求匹配比较条件。", "quote": quote, "ability": "解释"}], "disposition_reason": ""}
            return json.dumps(value, ensure_ascii=False)
        if title == "Synthesis":
            nodes = json.loads(prompt.split("节点：\n", 1)[1])
            edges = [{"from_id": nodes[0]["id"], "to_id": nodes[1]["id"], "type": "supports", "explanation": "概念有助于理解此方法，属于学习组织推断。"}] if len(nodes) > 1 else []
            return json.dumps({"thesis": "匹配比较条件，再检查证据和不确定性。", "relationships": edges}, ensure_ascii=False)
        if title == "Answer":
            block_id = re.search(r"SOURCE ([^\s]+) \|", prompt)[1]
            body = prompt.split("SOURCE ", 1)[1].split("\n", 1)[1].split("\n\nSOURCE ", 1)[0]
            return json.dumps({"answer": "需要核对预算，并保留不确定性。", "coverage": "covered", "citations": [{"block_id": block_id, "quote": body.strip()[:80]}], "added_explanation": ""}, ensure_ascii=False)
        return "综合各分段的条件与不确定性。"


async def add_text(learning, kb_id, filename, text):
    async def chunks():
        yield text.encode("utf-8")
    return await learning.upload(kb_id, filename, chunks())


async def finish(workspace, job):
    await workspace.jobs.tasks[job["id"]]
    record = workspace.store.get("job", job["id"])
    assert record["state"] == "completed", record
    return record


def test_extraction_keeps_every_material_and_real_source_positions(tmp_path):
    async def run():
        app = create_app(Store(tmp_path), "secret")
        ws = app.state.workspace
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1", headers={"authorization": "Bearer secret"}) as client:
            response = await client.post("/api/workspace/kbs", json={"title": "合成资料学习库", "depth": "systematic"})
            assert response.status_code == 200, response.text
            kb = response.json()
            for name, text in [("evidence.md", "# Evidence\nA comparison must use the same budget. Record uncertainty before making a claim.\n"),
                               ("方法.txt", "第一节\n先明确问题，再检查证据。证据不足时保留不确定性，不得直接推广结论。\n")]:
                result = await client.post(f"/api/workspace/kbs/{kb['id']}/materials", params={"filename": name}, content=text.encode())
                assert result.status_code == 200, result.text
            root = ws.store.directory("kb", kb["id"])
            output = root / "extraction-check"
            output.mkdir()
            result = await ws.learning.extract(kb["id"], output)
            assert len(result["metadata"]["sources"]) == 2
            assert {Path(block["source_file"]).name for block in result["blocks"]} == {"evidence.md", "方法.txt"}
            full_text = (output / "knowledge.learnkb/full_text.txt").read_text(encoding="utf-8")
            for block in result["blocks"]:
                assert block["text"] == full_text[block["start_char"]:block["end_char"]]
            assert read_json(output / "knowledge.learnkb/source_manifest.json")["total_sources"] == 2
            assert (output / "knowledge.learnkb/material-security-report.json").is_file()
            assert result["source_revision"] == 2
            assert await ws.learning.extract(kb["id"], output) == result
            assert not ws.store.get("kb", kb["id"])["published"]
        await ws.close()
    asyncio.run(run())


def test_extraction_does_not_silently_ignore_unsupported_materials(tmp_path):
    async def run():
        app = create_app(Store(tmp_path), "secret")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1", headers={"authorization": "Bearer secret"}) as client:
            kb = (await client.post("/api/workspace/kbs", json={"title": "Input validation"})).json()
            bad = await client.post(f"/api/workspace/kbs/{kb['id']}/materials", params={"filename": "do-not-run.exe"}, content=b"fixture")
            assert bad.status_code == 400
            assert (await client.get("/api/workspace/kbs/" + kb["id"])).json()["materials"] == []
            assert (await client.post(f"/api/workspace/kbs/{kb['id']}/build", json={})).status_code == 400
        await app.state.workspace.close()
    asyncio.run(run())


def test_grounded_learning_build_renders_real_six_module_page_and_learning_loop(tmp_path):
    async def run():
        LearningText.calls = []
        app = create_app(Store(tmp_path), "secret", workspace_text_factory=LearningText)
        ws = app.state.workspace
        kb = ws.learning.create({"title": "来源可追溯的合成学习", "depth": "systematic"})
        await add_text(ws.learning, kb["id"], "study.md", "# Fair comparison\nCompare policies using the same number of observations. Report uncertainty. Stop when evidence is insufficient.\n")
        await add_text(ws.learning, kb["id"], "references.txt", "REFERENCES_ONLY\nSynthetic reference A; synthetic reference B.\n")
        await finish(ws, ws.learning.build(kb["id"], {}))
        detail = ws.learning.detail(kb["id"])
        assert detail["published"]["total_blocks"] == detail["published"]["processed_blocks"] == 2
        assert len(detail["page"]["contentUnits"]) == 1
        assert len(detail["coverage"]["dispositions"]) == 2
        assert detail["page"]["methodLibrary"]["status"] == "extracted"
        assert detail["page"]["relationships"][0]["evidence"] == "inference"
        _, directory, _ = ws.learning.publication(kb["id"])
        html = (directory / "page.html").read_text(encoding="utf-8")
        assert 'id="frameworks"' in html and 'id="glossary"' in html and 'id="notes"' in html
        assert (directory / "knowledge.learnkb/patterns.md").is_file()
        assert (directory / "knowledge.zip").is_file()
        methods = ws.learning.methods("预算")
        assert methods and methods[0]["card"]["evidence"] == "material"
        unit = detail["page"]["contentUnits"][0]
        ws.learning.progress(kb["id"], {"unit_id": unit["id"], "completed": True, "note": "我的理解：先核对比较条件。"})
        question = detail["questions"][0]
        bad = ws.learning.attempt(kb["id"], {"question_id": question["id"], "answer": 1})
        assert not bad["correct"] and bad["reference_answer"] == 0
        await finish(ws, ws.learning.ask(kb["id"], {"question": "为什么要匹配预算？", "unit_id": unit["id"]}))
        updated = ws.learning.detail(kb["id"])
        assert updated["progress"][updated["published"]["version"] + ":" + unit["id"]]["completed"]
        assert updated["chat"][-1]["citations"]
        citation = updated["chat"][-1]["citations"][0]
        assert citation["quote"] in ws.learning.source(kb["id"], citation["block_id"])["text"]
        assert updated["chat"][-1]["version"] == updated["published"]["version"]
        await finish(ws, ws.learning.ask(kb["id"], {"question": "请接着解释上一点。", "unit_id": unit["id"]}))
        assert "此前本版本的学习对话" in LearningText.calls[-1][1]
        assert "为什么要匹配预算？" in LearningText.calls[-1][1]
        await ws.close()
    asyncio.run(run())


def test_source_without_a_method_is_not_forced_into_fake_action_rules(tmp_path):
    async def run():
        LearningText.no_methods = True
        try:
            app = create_app(Store(tmp_path), "secret", workspace_text_factory=LearningText)
            ws = app.state.workspace
            kb = ws.learning.create({"title": "概念型资料", "depth": "systematic"})
            await add_text(ws.learning, kb["id"], "concept.txt", "A fair comparison has a shared budget. This is a concept, not an executable procedure.\n")
            await finish(ws, ws.learning.build(kb["id"], {}))
            detail = ws.learning.detail(kb["id"])
            assert detail["page"]["decisionRules"] == []
            assert detail["page"]["methodLibrary"]["status"] == "none"
            assert detail["page"]["methodology"]["status"] == "not-applicable"
            await ws.close()
        finally:
            LearningText.no_methods = False
    asyncio.run(run())


def test_rebuild_failure_preserves_published_work_and_resume_uses_unit_checkpoints(tmp_path):
    async def run():
        LearningText.calls = []
        app = create_app(Store(tmp_path), "secret", workspace_text_factory=LearningText)
        ws = app.state.workspace
        kb = ws.learning.create({"title": "可恢复学习"})
        await add_text(ws.learning, kb["id"], "first.txt", "Compare policies using the same budget. Report uncertainty.\n")
        await finish(ws, ws.learning.build(kb["id"], {}))
        first = ws.store.get("kb", kb["id"])["published"]["version"]
        first_unit = ws.learning.detail(kb["id"])["page"]["contentUnits"][0]["id"]
        ws.learning.progress(kb["id"], {"unit_id": first_unit, "version": first, "completed": True, "note": "第一版笔记"})
        await add_text(ws.learning, kb["id"], "second.txt", "Synthetic interruption target. A comparison requires a shared budget.\n")
        LearningText.fail_text = "Synthetic interruption target"
        try:
            failing = ws.learning.build(kb["id"], {})
            await ws.jobs.tasks[failing["id"]]
            assert ws.store.get("job", failing["id"])["state"] == "failed"
            assert ws.store.get("kb", kb["id"])["published"]["version"] == first
            assert ws.store.get("kb", kb["id"])["needs_rebuild"]
            completed_first = sum(title == "Lesson" and "Compare policies using the same budget" in prompt for title, prompt in LearningText.calls)
        finally:
            LearningText.fail_text = ""
        await finish(ws, ws.learning.build(kb["id"], {"resume": True}))
        assert sum(title == "Lesson" and "Compare policies using the same budget" in prompt for title, prompt in LearningText.calls) == completed_first
        assert ws.store.get("kb", kb["id"])["published"]["version"] != first
        assert ws.store.get("kb", kb["id"])["history"][0]["version"] == first
        latest = ws.learning.detail(kb["id"])["published"]["version"]
        ws.learning.progress(kb["id"], {"unit_id": first_unit, "version": latest, "completed": False, "note": "第二版笔记"})
        saved = ws.learning.detail(kb["id"], first)["progress"]
        assert saved[first + ":" + first_unit]["note"] == "第一版笔记"
        assert saved[first + ":" + first_unit]["completed"]
        assert saved[latest + ":" + first_unit]["note"] == "第二版笔记"
        await ws.close()
    asyncio.run(run())


def test_quote_check_rejects_invented_evidence():
    from paper_research_coach.learning_content import exact_quote
    import pytest
    assert exact_quote("same budget", "same\nbudget") == "same\nbudget"
    with pytest.raises(ValueError, match="引用不在"):
        exact_quote("This result is proven", "This result is uncertain")


def test_same_named_concepts_and_terms_keep_each_sources_distinct_meaning():
    from paper_research_coach.learning_content import assemble_page
    blocks, lessons = [], []
    for number, definition in enumerate(["机器学习中的预测模型", "实物的缩小比例模型"], 1):
        block = {"id": f"b{number}", "source_id": f"s{number}", "source": f"材料{number}", "source_file": f"material{number}.txt"}
        blocks.append(block)
        lessons.append({"id": f"u{number}", "block_id": block["id"], "role": "content", "source": block["source"], "title": "模型", "core": definition,
            "takeaways": [definition], "concepts": [{"name": "Model", "explanation": definition, "when": f"材料{number}的语境"}], "methods": [], "questions": [],
            "glossary": [{"term": "Model", "definition": definition, "context": f"材料{number}的语境", "full_name": "Model", "meaning": definition}]})
    page, _, _, _ = assemble_page({"id": "kb-meanings", "title": "不同语境", "language": "zh", "depth": "systematic"}, lessons, blocks)
    assert len(page["frameworks"]) == len(page["glossary"]) == 2
    assert page["frameworks"][0]["oneLine"] != page["frameworks"][1]["oneLine"]
    assert page["glossary"][0]["definition"] != page["glossary"][1]["definition"]
    assert page["glossary"][1]["units"] == ["u2"] and page["glossary"][1]["source"] == "材料2"
    assert page["contentUnits"][0]["frameworks"] != page["contentUnits"][1]["frameworks"]


def test_real_extraction_supports_bundled_pdf_and_office_epub_without_external_tools(tmp_path):
    from io import BytesIO
    from zipfile import ZipFile
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    def zipped(parts):
        output = BytesIO()
        with ZipFile(output, "w") as archive:
            for name, value in parts.items(): archive.writestr(name, value)
        return output.getvalue()
    pdf = BytesIO(); drawing = canvas.Canvas(pdf)
    drawing.drawString(50, 740, "Synthetic source evidence with explicit conditions."); drawing.showPage()
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light")); drawing.setFont("STSong-Light", 12)
    drawing.drawString(50, 740, "中文证据必须保留适用条件。"); drawing.showPage(); drawing.save()
    docx = zipped({"word/document.xml": '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Word 来源保留原始观点。</w:t></w:r></w:p></w:body></w:document>'})
    pptx = zipped({"ppt/slides/slide1.xml": '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>幻灯片核对材料边界。</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>'})
    epub = zipped({"META-INF/container.xml": '<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>',
        "OEBPS/content.opf": '<package xmlns="http://www.idpf.org/2007/opf" version="3.0"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>合成书</dc:title></metadata><manifest><item id="one" href="one.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="one"/></spine></package>',
        "OEBPS/one.xhtml": '<html xmlns="http://www.w3.org/1999/xhtml"><head><title>材料</title></head><body><h1>学习依据</h1><p>电子书来源必须可追溯。</p></body></html>'})
    async def run():
        app = create_app(Store(tmp_path / "data"), "secret"); ws = app.state.workspace
        kb = ws.learning.create({"title": "真实格式提取"})
        for name, content in [("source.pdf", pdf.getvalue()), ("source.docx", docx), ("source.pptx", pptx), ("source.epub", epub)]:
            async def chunks(): yield content
            await ws.learning.upload(kb["id"], name, chunks())
        output = ws.store.directory("kb", kb["id"]) / "format-check"; output.mkdir()
        result = await ws.learning.extract(kb["id"], output)
        assert len(result["metadata"]["sources"]) == 4
        text = (output / "knowledge.learnkb/full_text.txt").read_text(encoding="utf-8")
        for excerpt in ["Synthetic source evidence", "中文证据必须保留适用条件", "Word 来源保留原始观点", "幻灯片核对材料边界", "电子书来源必须可追溯"]:
            assert excerpt in text
        assert {block["locator"].get("pdf_page") for block in result["blocks"] if block["source_file"].endswith(".pdf")} == {1, 2}
        assert result["metadata"]["sources"][0]["extraction_method"] == "pypdfium2"
        pdf_path = ws.store.directory("kb", kb["id"]) / ws.store.get("kb", kb["id"])["materials"][0]["file"]
        paper = ws.papers.add_paper("合成中文 PDF", str(pdf_path))
        assert "中文证据必须保留适用条件" in await ws.context({"paper_id": paper["id"], "page_index": 1})
        await ws.close()
    asyncio.run(run())
