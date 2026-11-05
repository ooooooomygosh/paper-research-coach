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
