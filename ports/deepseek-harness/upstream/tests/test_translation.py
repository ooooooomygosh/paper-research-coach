import asyncio
import copy
import json

import pytest
from fastapi.testclient import TestClient

from paper_research_coach.server import create_app
from paper_research_coach.store import Conflict
from paper_research_coach.translation import (
    SelectionRequest,
    Translation,
    TranslationRequest,
    matching_translation,
    sentences,
    transform_rect,
    validate_links,
)


def mapping():
    return {
        "segments": [
            {
                "id": "0:a",
                "translated": True,
                "source": {
                    "page_index": 0,
                    "text": "First result. Second result.",
                    "rects": [[60, 600, 260, 650]],
                },
                "target": {
                    "page_index": 0,
                    "text": "第一个结果。第一个结论。第二个结果。",
                    "rects": [[60, 600, 260, 650]],
                },
                "links": [
                    {"source_ids": [0], "target_ids": [0, 1]},
                    {"source_ids": [1], "target_ids": [2]},
                ],
            }
        ],
        "dual_transforms": [
            {"original": [1, 0, 0, 1, 0, 0], "translated": [1, 0, 0, 1, 600, 0]}
        ],
    }


def selection(anchor, quote="First result.", view="original", rects=None):
    return SelectionRequest(
        anchor={**anchor, "quote": quote, "rects": rects or [[60, 610, 150, 625]]},
        view=view,
    )


def test_saved_alignment_split_merge_and_paragraph_fallback(anchor):
    data = mapping()
    result = matching_translation(data, selection(anchor))
    assert (
        result["text"] == "第一个结果。第一个结论。" and result["level"] == "sentence"
    )
    assert result["source_anchor"]["quote"] == "First result."
    result = matching_translation(
        data, selection(anchor, "第一个结论。", "dual", [[660, 610, 750, 625]])
    )
    assert result["source_anchor"]["quote"] == "First result."
    assert max(r[2] for r in result["source_anchor"]["rects"]) < 600
    data["segments"][0]["links"] = []
    assert matching_translation(data, selection(anchor))["level"] == "paragraph"


def test_repeated_sentences_require_location_not_text_only(anchor):
    data = mapping()
    other = copy.deepcopy(data["segments"][0])
    other["id"] = "0:b"
    other["source"]["rects"] = [[60, 400, 260, 450]]
    other["target"]["text"] = "另一个段落。"
    other["links"] = []
    data["segments"].append(other)
    assert matching_translation(data, selection(anchor))["segment_id"] == "0:a"
    req = selection(anchor)
    req.anchor.rects = []
    assert matching_translation(data, req)["status"] == "unavailable"
    req.anchor.page_index = 1
    assert matching_translation(data, req)["status"] == "unavailable"


def test_rotated_cropped_affine_positions_and_singular_rejection():
    rect = [30, 80, 120, 140]
    matrix = [0, 1, -1, 0, 700, -25]
    assert transform_rect(transform_rect(rect, matrix), matrix, True) == pytest.approx(
        rect
    )
    with pytest.raises(ValueError):
        transform_rect(rect, [0, 0, 0, 0, 0, 0], True)


def test_alignment_rejects_incomplete_duplicate_and_uncertain_links():
    source = sentences("Result 0.5 is unchanged. Two tests agree.")
    target = sentences("结果0.5不变。两次试验一致。")
    assert len(source) == len(target) == 2
    valid = {
        "links": [{"source_ids": [0, 1], "target_ids": [0, 1], "uncertain": False}]
    }
    assert validate_links(valid, source, target)
    for invalid in [
        {"links": []},
        {"links": [{"source_ids": [0], "target_ids": [0], "uncertain": False}]},
        {
            "links": [
                {"source_ids": [0, 0, 1], "target_ids": [0, 1], "uncertain": False}
            ]
        },
        {"links": [{"source_ids": [0, 1], "target_ids": [0, 1], "uncertain": True}]},
    ]:
        assert validate_links(invalid, source, target) == []


def test_jobs_are_idempotent_configuration_is_frozen_and_queued_stop_is_durable(
    store, paper, monkeypatch
):
    async def run():
        trans = Translation(store)
        monkeypatch.setattr(trans, "interpreter", lambda: "optional-python")

        async def hold(job):
            await asyncio.Event().wait()

        monkeypatch.setattr(trans, "run", hold)
        request = TranslationRequest(
            operation_id="once", source_version=paper["source_version"]
        )
        job = await trans.create(paper["id"], request)
        trans.settings(
            {
                "model": "another-model",
                "effort": "high",
                "lang_in": "en",
                "lang_out": "zh-CN",
            }
        )
        assert (await trans.create(paper["id"], request))["id"] == job["id"]
        assert trans.job(job["id"])["model"] == "gpt-6-luna"
        with pytest.raises(Conflict):
            await trans.create(
                paper["id"], request.model_copy(update={"operation_id": "other"})
            )
        assert (await trans.stop(job["id"]))["state"] == "cancelled"
        resumed = await trans.retry(job["id"])
        assert resumed["model"] == "gpt-6-luna"
        await trans.close()
        restored = Translation(store)
        assert restored.job(job["id"])["state"] == "queued"
        await restored.close()

    asyncio.run(run())


def test_translation_cache_separates_versions_model_languages_and_engine(store, paper):
    class Engine:
        def __init__(self):
            self.calls = 0

        async def text(self, prompt, **kwargs):
            self.calls += 1
            return f"译文{self.calls}"

    async def run():
        trans = Translation(store)
        engine = Engine()
        job = {
            "paper_id": paper["id"],
            "source_version": paper["source_version"],
            "engine_version": "0.6.4",
            "model": "gpt-6-luna",
            "effort": "low",
            "lang_in": "en",
            "lang_out": "zh-CN",
        }
        assert await trans.cached_text(
            engine, job, "Source"
        ) == await trans.cached_text(engine, job, "Source")
        assert engine.calls == 1
        for key, value in [
            ("model", "different"),
            ("source_version", "new"),
            ("engine_version", "next"),
            ("lang_out", "ja"),
        ]:
            await trans.cached_text(engine, {**job, key: value}, "Source")
        assert engine.calls == 5
        await trans.close()

    asyncio.run(run())


def test_missing_component_and_version_change_preserve_existing_records(
    store, paper, monkeypatch
):
    async def run():
        trans = Translation(store)

        def missing():
            raise ValueError("翻译组件未安装")

        monkeypatch.setattr(trans, "interpreter", missing)
        with pytest.raises(ValueError, match="组件"):
            await trans.create(
                paper["id"],
                TranslationRequest(
                    operation_id="missing", source_version=paper["source_version"]
                ),
            )
        assert not trans.jobs(paper["id"])
        with pytest.raises(Conflict):
            await trans.create(
                paper["id"],
                TranslationRequest(operation_id="wrong-version", source_version="old"),
            )
        assert (
            store.get("paper", paper["id"])["source_version"] == paper["source_version"]
        )
        await trans.close()

    asyncio.run(run())


def test_translation_endpoints_authenticate_and_check_anchor_version(
    store, paper, anchor
):
    app = create_app(store, token="private")
    directory = store.root / "translations" / "finished"
    directory.mkdir(parents=True)
    (directory / "mapping.json").write_text(json.dumps(mapping(), ensure_ascii=False))
    for kind in ("mono", "dual"):
        (directory / f"{kind}.pdf").write_bytes(b"%PDF-1.4\n")
    job = {
        "id": "finished",
        "paper_id": paper["id"],
        "operation_id": "finished",
        "source_version": paper["source_version"],
        "state": "completed",
        "artifacts": {
            "mapping": str(directory / "mapping.json"),
            "mono": str(directory / "mono.pdf"),
            "dual": str(directory / "dual.pdf"),
        },
    }
    with store.connect() as db:
        db.execute(
            "INSERT INTO translation_jobs VALUES (?,?,?,?)",
            (job["id"], paper["id"], job["operation_id"], json.dumps(job)),
        )
    with TestClient(app, base_url="http://127.0.0.1") as client:
        assert client.get("/api/translation/settings").status_code == 401
        auth = {"Authorization": "Bearer private"}
        settings = client.get("/api/translation/settings", headers=auth).json()
        assert settings["model"] == "gpt-6-luna" and settings["effort"] == "low"
        response = client.post(
            "/api/translation/jobs/finished/selection",
            json=selection(anchor).model_dump(),
            headers=auth,
        )
        assert (
            response.status_code == 200
            and response.json()["text"] == "第一个结果。第一个结论。"
        )
        wrong = selection(anchor)
        wrong.anchor.source_version = "old"
        assert (
            client.post(
                "/api/translation/jobs/finished/selection",
                json=wrong.model_dump(),
                headers=auth,
            ).status_code
            == 409
        )
        other = store.add_paper("Other")
        wrong = selection(anchor)
        wrong.anchor.paper_id = other["id"]
        assert (
            client.post(
                "/api/translation/jobs/finished/selection",
                json=wrong.model_dump(),
                headers=auth,
            ).status_code
            == 409
        )


def test_selection_crossing_paragraphs_falls_back_to_saved_paragraphs(anchor):
    data = mapping()
    other = copy.deepcopy(data["segments"][0])
    other.update(id="0:next", links=[])
    other["source"].update(
        text="Another paragraph starts here.", rects=[[60, 500, 260, 550]]
    )
    other["target"]["text"] = "下一段从这里开始。"
    data["segments"].append(other)
    req = selection(
        anchor,
        "Second result. Another paragraph starts here.",
        rects=[[60, 610, 150, 625], [60, 510, 150, 525]],
    )
    result = matching_translation(data, req)
    assert result["status"] == "ready" and result["level"] == "paragraph"
    assert "第二个结果" in result["text"] and "下一段" in result["text"]
    assert result["source_anchor"]["quote"] == req.anchor.quote
    req.anchor.rects = [[60, 100, 150, 125]]
    assert matching_translation(data, req)["status"] == "unavailable"
