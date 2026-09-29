import pytest
from reportlab.pdfgen import canvas
from paper_research_coach.store import Store


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "source.pdf"
    c = canvas.Canvas(str(path), pagesize=(600, 800))
    c.drawString(60, 720, "Synthetic research paper. This is not a published result.")
    c.drawString(
        60, 680, "Budget-matched evidence distinguishes competing explanations."
    )
    c.showPage()
    c.drawString(60, 720, "Repeated quote. Repeated quote.")
    c.showPage()
    c.save()
    return path


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "data")


@pytest.fixture
def paper(store, pdf):
    return store.add_paper("Synthetic paper", str(pdf), goal="Check the mechanism")


@pytest.fixture
def anchor(paper):
    return {
        "paper_id": paper["id"],
        "source_version": paper["source_version"],
        "page_index": 0,
        "page_label": "1",
        "quote": "Budget-matched evidence",
        "rects": [[60, 675, 230, 695]],
        "status": "verified",
    }
