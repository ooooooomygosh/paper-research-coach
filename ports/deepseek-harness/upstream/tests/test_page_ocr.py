from pathlib import Path
import pytest
from paper_research_coach import page_ocr
from paper_research_coach.store import Conflict, digest


def test_cached_ocr_binds_recognition_to_file_version(pdf, tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(page_ocr, "_engine", lambda: "Apple Vision")
    def recognize(path, index, engine, lang):
        calls.append(index)
        return "OCR text"
    monkeypatch.setattr(page_ocr, "_recognize", recognize)
    version = digest(pdf)
    cache = tmp_path / "ocr-cache"
    assert not page_ocr.recognize_page(pdf, 0, version, cache)["cached"]
    assert page_ocr.recognize_page(pdf, 0, version, cache)["cached"]
    assert not page_ocr.recognize_page(pdf, 1, version, cache)["cached"]
    assert calls == [0, 1]
    pdf.write_bytes(b"replaced")
    with pytest.raises(Conflict):
        page_ocr.recognize_page(pdf, 0, version, cache)
