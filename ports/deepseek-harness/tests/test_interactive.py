import json
import re

import pytest
from pydantic import ValidationError

from paper_research_coach.interactive_page import InteractivePage, grounded_page, markdown, render_page


def fixture(kind="steps"):
    value = {"kind": kind, "title": "合成教学示例", "summary": "先检查条件，再判断证据。"}
    if kind in ("concepts", "steps"):
        value["items"] = [{"title": "比较条件", "detail": "比较必须使用相同的预算。"}, {"title": "证据边界", "detail": "保留尚未排除的解释。"}]
    if kind == "comparison":
        value.update(columns=["方法 A", "方法 B"], rows=[{"label": "预算", "values": ["相同", "未提供"], "explanation": "缺少预算时不能判断比较是否公平。"}])
    if kind == "evidence":
        value.update(question="应该先检查什么？", options=["预算是否匹配", "先假定普适有效"], answer=0, explanation="先检查比较条件。")
    if kind == "parameters":
        value.update(family="linear", parameters=[{"name": name, "label": name, "unit": "无量纲", "minimum": -1, "maximum": 2, "value": 1} for name in ["a", "b"]], assumptions="这是教学示意，不是论文实验数据。")
    return value


@pytest.mark.parametrize("kind", ["concepts", "steps", "comparison", "parameters", "evidence"])
def test_real_component_artifact_renders_without_a_model_or_external_resources(kind):
    page = grounded_page(json.dumps(fixture(kind)), [])
    html = render_page(page, "page-test")
    assert page["title"] in markdown(page)
    assert 'id="module"' in html and 'id="page-data"' in html
    assert "'sha256-" in html and "connect-src 'none'" in html
    assert not re.search(r"<(script|link)[^>]+(?:src|href)=", html)
    assert "模型解释 · 未绑定原文" in html


def test_quote_is_matched_only_to_the_selected_source_and_keeps_literal_original():
    value = fixture()
    value.update(source_id="b1", source_quote="预算必须相同")
    sources = [{"id": "b1", "label": "合成资料，第 4 页", "text": "比较时，预算\n必须相同。", "anchor": {"paper_id": "p", "source_version": "v1", "page_index": 3}}]
    page = grounded_page(json.dumps(value), sources)
    assert page["source_quote"] == "预算\n必须相同"
    assert page["source_anchor"]["source_version"] == "v1"
    value["source_quote"] = "模型虚构的收益"
    with pytest.raises(ValueError, match="引用不在"):
        grounded_page(json.dumps(value), sources)
    with pytest.raises(ValueError, match="独立问题"):
        grounded_page(json.dumps(value), [])


def test_model_text_cannot_escape_the_json_payload_or_become_an_executable_script():
    value = fixture()
    value["summary"] = '</script><script>window.stolen=true</script>'
    html = render_page(grounded_page(json.dumps(value), []), "page-test")
    assert '<script>window.stolen=true</script>' not in html
    assert '\\u003c/script' in html


@pytest.mark.parametrize("mutation", [
    lambda v: v["parameters"].append(v["parameters"][0]),
    lambda v: v["parameters"][0].update(value=10),
    lambda v: v.update(assumptions=""),
    lambda v: v.update(x_max=float("inf")),
])
def test_invalid_parameter_ranges_are_rejected_before_publication(mutation):
    value = fixture("parameters")
    mutation(value)
    with pytest.raises((ValueError, ValidationError)):
        InteractivePage.model_validate(value)


def test_formula_families_reject_an_unbounded_slider_combination():
    value = fixture("parameters")
    value["family"] = "exponential"
    value["parameters"].append({"name": "k", "label": "增长系数", "unit": "无量纲", "minimum": 0, "maximum": 1000, "value": 1})
    with pytest.raises(ValueError, match="指数范围"):
        InteractivePage.model_validate(value)


def test_account_component_generation_history_failure_and_exports(tmp_path):
    import asyncio
    import httpx
    from paper_research_coach.server import create_app
    from paper_research_coach.store import Store

    class Text:
        invalid = False
        closed = 0
        calls = []

        def __init__(self, *args):
            pass

        async def text(self, prompt, **kwargs):
            self.calls.append((prompt, kwargs))
            return '{"bad": true}' if self.invalid else json.dumps(fixture("parameters"))

        async def close(self):
            Text.closed += 1

    async def run():
        app = create_app(Store(tmp_path), "secret", workspace_text_factory=Text)
        ws = app.state.workspace
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1", headers={"authorization": "Bearer secret"}) as client:
            row = (await client.post('/api/workspace/studios', json={"question": "Explain a parameter", "presentation": "components"})).json()
            url = '/api/workspace/studios/' + row["id"]
            assert not Text.calls
            async def generate():
                job = (await client.post(url + '/generate', json={})).json()
                task = ws.jobs.tasks.get(job["id"])
                if task:
                    await task
                return ws.store.get("job", job["id"])
            assert (await generate())["state"] == "completed"
            current = (await client.get(url)).json()
            first = current["published"]["version"]
            assert current["published"]["format"] == "components"
            assert Text.calls[0][1]["schema"]["title"] == "InteractivePage"
            html = await client.get('/api/workspace/view/studio/' + row["id"])
            assert html.status_code == 200 and 'prc-question' in html.text and 'allow-same-origin' not in html.headers['content-security-policy']
            assert (await client.get('/api/workspace/export/studio/' + row["id"] + '/page.json')).json()["kind"] == "parameters"
            await client.put('/api/workspace/storage/studio/' + row["id"], json={"key": "prc-interactive:" + first, "value": '{"params":{"a":1.7}}'})
            assert (await generate())["state"] == "completed"
            second = (await client.get(url)).json()
            assert second["history"][0]["version"] == first
            assert second["storage"]["prc-interactive:" + first]
            assert (await client.get('/api/workspace/view/studio/' + row["id"], params={"version": first})).status_code == 200
            Text.invalid = True
            assert (await generate())["state"] == "failed"
            assert (await client.get(url)).json()["published"]["version"] == second["published"]["version"]
            assert Text.closed == 4  # two successful calls plus one bounded repair
        await ws.close()
    asyncio.run(run())


def test_native_sources_do_not_treat_a_user_selection_as_pdf_evidence(tmp_path):
    import asyncio
    from reportlab.pdfgen import canvas
    from paper_research_coach.server import create_app
    from paper_research_coach.store import Store
    path = tmp_path / 'synthetic.pdf'
    pdf = canvas.Canvas(str(path)); pdf.drawString(40, 700, 'Real PDF evidence must be checked.'); pdf.save()
    async def run():
        app = create_app(Store(tmp_path / 'data'), 'secret'); ws = app.state.workspace
        paper = ws.papers.add_paper('Synthetic metadata', str(path))
        source = {"paper_id": paper["id"], "page_index": 0, "quote": "This is not in the PDF."}
        sources = await ws.interactive_sources(source)
        assert 'Real PDF evidence' in sources[0]["text"]
        assert source["quote"] not in sources[0]["text"]
        assert 'Synthetic metadata' not in sources[0]["text"]
        assert sources[0]["anchor"]["source_version"] == paper["source_version"]
        with pytest.raises(ValueError, match="换版"):
            await ws.interactive_sources({**source, "source_version": "old-version"})
        await ws.close()
    asyncio.run(run())


def test_sources_are_rechecked_before_async_publication(tmp_path):
    import asyncio
    from paper_research_coach.server import create_app
    from paper_research_coach.store import Store
    calls = []

    class Text:
        def __init__(self, *args):
            pass
        async def text(self, prompt, **kwargs):
            value = fixture()
            value.update(source_id="pdf-page", source_quote="预算必须相同")
            return json.dumps(value)
        async def close(self):
            pass

    async def run():
        app = create_app(Store(tmp_path), "secret", workspace_text_factory=Text)
        ws = app.state.workspace
        async def sources(context, question):
            calls.append(context)
            if len(calls) > 1:
                raise ValueError("source changed during generation")
            return [{"id": "pdf-page", "label": "Synthetic PDF, page 1", "text": "预算必须相同", "context": {"paper_id": "p", "source_version": "v1"}}]
        ws.studio.sources = sources
        row = ws.studio.create({"question": "Explain", "presentation": "components", "context": {"paper_id": "p"}})
        job = ws.studio.generate(row["id"], {})
        await ws.jobs.tasks[job["id"]]
        assert ws.store.get("job", job["id"])["state"] == "failed"
        assert ws.store.get("studio", row["id"])["published"] is None
        assert calls[-1]["source_version"] == "v1"
        await ws.close()
    asyncio.run(run())


@pytest.mark.parametrize("kind, expected", [
    ("comparison", ["缺少预算时不能判断比较是否公平。", "解释"]),
    ("evidence", ["模型参考选项：1. 预算是否匹配", "先检查比较条件。"]),
    ("parameters", ["y = a·x + b", "输入定义域：[0, 4]", "输入（无量纲）", "输出（无量纲）", "最小值", "初始值"]),
])
def test_markdown_keeps_the_component_explanations_and_parameter_contract(kind, expected):
    exported = markdown(grounded_page(json.dumps(fixture(kind)), []))
    for text in expected:
        assert text in exported


def test_standalone_exports_keep_known_pdf_and_knowledge_base_versions():
    value = fixture()
    value.update(source_id="block", source_quote="预算必须相同")
    for binding in [
        {"paper_id": "p", "source_version": "pdf-v2", "page_index": 3},
        {"kb_id": "kb", "version": "kb-build-v3", "unit_id": "unit-1"},
    ]:
        version = binding.get("version") or binding["source_version"]
        source = {"id": "block", "label": "合成原文，第 4 页", "text": "预算必须相同", "context": {**binding, "quote": "not evidence"}}
        page = grounded_page(json.dumps(value), [source])
        assert page["source_context"] == binding
        assert version in page["source_label"]
        assert version in markdown(page)
        assert version in render_page(page, "export-test")
        assert "not evidence" not in json.dumps(page)


def test_switching_to_components_uses_the_current_edited_document(tmp_path):
    import asyncio
    from paper_research_coach.server import create_app
    from paper_research_coach.store import Store
    prompts = []

    class Text:
        def __init__(self, *args):
            pass
        async def text(self, prompt, **kwargs):
            prompts.append(prompt)
            return json.dumps(fixture())
        async def close(self):
            pass

    async def run():
        app = create_app(Store(tmp_path), "secret", workspace_text_factory=Text)
        ws = app.state.workspace
        row = ws.studio.create({"question": "Revise", "source": "CURRENT_EDITED_DRAFT_MARKER"})
        ws.store.patch("studio", row["id"], {"component_spec": grounded_page(json.dumps(fixture("steps")), [])})
        ws.studio.update(row["id"], {"presentation": "components"})
        job = ws.studio.generate(row["id"], {})
        await ws.jobs.tasks[job["id"]]
        assert ws.store.get("job", job["id"])["state"] == "completed"
        assert "CURRENT_EDITED_DRAFT_MARKER" in prompts[0]
        assert "不是核验来源" in prompts[0]
        assert "source_context" not in prompts[0]  # derived metadata is not model schema
        await ws.close()
    asyncio.run(run())
