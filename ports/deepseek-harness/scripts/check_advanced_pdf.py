"""Check advanced PDF tools against an isolated, running DSH plugin.

Requires Playwright, Chromium, ReportLab and pypdf. The smoke adds one synthetic
form to the target test library and reads back its browser download.
"""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from pypdf import PdfReader, PdfWriter
from pypdf.actions import JavaScript
from reportlab.pdfgen import canvas

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("url", help="DSH plugin URL, including its /paper-research-coach/ prefix")
parser.add_argument("--chromium", help="Chromium executable (optional with Playwright Chromium)")
args = parser.parse_args()
url = args.url.rstrip("/") + "/"
with TemporaryDirectory(prefix="prc-advanced-smoke-") as work, sync_playwright() as playwright:
    raw_form = Path(work) / "raw-form.pdf"
    form = Path(work) / "form.pdf"
    c = canvas.Canvas(str(raw_form))
    c.drawString(50, 745, "Participant:")
    c.acroForm.textfield(name="participant", x=125, y=730, width=220, height=28)
    c.showPage()
    c.save()
    writer = PdfWriter(clone_from=raw_form)
    writer.add_open_action(JavaScript('this.getField("participant").value = "PDF SCRIPT RAN"; this.print();'))
    writer.write(form)
    browser = playwright.chromium.launch(
        executable_path=args.chromium,
        headless=True, args=["--disable-gpu"],
    )
    page = browser.new_page(viewport={"width": 1440, "height": 1000}, accept_downloads=True)
    page.add_init_script("globalThis.prcPrints = 0; window.print = () => { globalThis.prcPrints++; };")
    errors = []
    requests = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda req: requests.append(req.url))
    result = page.request.post(url + "api/upload?title=Advanced%20PDF%20form%20smoke",
                               headers={"Content-Type": "application/pdf"}, data=form.read_bytes())
    assert result.ok, result.text()
    paper = result.json()["id"]
    page.goto(url + "#paper=" + paper)
    page.locator(".pdf-page canvas").first.wait_for()
    assert not any("/pdf-viewer/" in request for request in requests), requests
    original_requests = len([r for r in requests if "/api/pdf/" + paper in r])
    page.get_by_role("button", name="高级 PDF 工具").click()
    frame_loc = page.frame_locator('iframe[title="PDF.js 高级工具"]')
    field = frame_loc.locator('.annotationLayer input[name="participant"]')
    field.wait_for(timeout=12000)
    assert field.input_value() == ""
    assert field.evaluate("() => !PDFViewerApplication.pdfViewer.enableScripting")
    assert field.evaluate("() => globalThis.prcPrints") == 0
    field.fill("Ada Workbench")
    field.press("Tab")
    page.get_by_role("button", name="返回阅读").click()
    page.get_by_role("button", name="继续编辑").click()
    frame_loc.locator("#printButton").click()
    frame_loc.locator("body").evaluate("() => new Promise((resolve, reject) => { let t = setInterval(() => { if (prcPrints === 1) { clearInterval(t); resolve(); } }, 30); setTimeout(() => { clearInterval(t); reject(new Error('print timed out')); }, 6000); })")
    with page.expect_download() as download:
        frame_loc.locator("#downloadButton").click()
    copy = Path(work) / "form-copy.pdf"
    download.value.save_as(copy)
    assert PdfReader(copy).get_fields()["participant"]["/V"] == "Ada Workbench"
    assert PdfReader(form).get_fields()["participant"]["/V"] == ""
    page.get_by_role("button", name="返回阅读").click()
    page.locator("dialog.advanced-pdf-dialog").wait_for(state="detached")
    assert len([r for r in requests if "/api/pdf/" + paper in r]) == original_requests, requests
    assert not any(urlsplit(r).netloc and urlsplit(r).netloc != urlsplit(url).netloc for r in requests), requests
    assert not errors, errors
    print("DSH Chromium advanced viewer: lazy load, no duplicate PDF request, document JS suppressed, field edit, discard prompt, print dispatch, edited download and no external request passed.")
