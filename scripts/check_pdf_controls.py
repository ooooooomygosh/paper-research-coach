"""Real-browser gestures and persisted annotations using synthetic layout fixtures."""
import json
from urllib.parse import urlencode

from pypdf import PdfReader, PdfWriter, Transformation


def check_pdf_controls(browser, store, paper, port, token, output):
    url = f"http://127.0.0.1:{port}/#" + urlencode({'token': token, 'paper': paper['id']})
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(url)

    def ready(view=None):
        page.wait_for_function("""view => {
            const e = document.querySelector('.pdf-page');
            return e && Number(e.dataset.pageIndex) >= 0 && (!view || (view === 'original' ? !e.dataset.derived : e.dataset.derived?.includes(':' + view + ':')));
        }""", arg=view)

    ready()
    percent = lambda: int(page.get_by_label('PDF 缩放比例', exact=True).inner_text().rstrip('%'))
    initial = percent()
    old = page.locator('.pdf-page').bounding_box()
    center = {'x': old['x'] + 300, 'y': old['y'] + 240}
    page.mouse.move(center['x'], center['y'])
    page.keyboard.down('Control')
    page.mouse.wheel(0, -45)
    page.keyboard.up('Control')
    page.wait_for_function("() => !document.querySelector('.pdf-gesturing')")
    ready()
    assert percent() > initial, 'Trackpad pinch must zoom the PDF'
    current = page.locator('.pdf-page').bounding_box()
    assert abs((current['x'] + 300 * current['width'] / old['width']) - center['x']) < 3
    assert abs((current['y'] + 240 * current['height'] / old['height']) - center['y']) < 3
    assert page.evaluate('visualViewport.scale') == 1, 'The application itself must not zoom'
    page.get_by_label('PDF 适应宽度', exact=True).click()
    ready()
    page.get_by_label('PDF 下一页', exact=True).click()
    ready()
    page.get_by_label('PDF 上一页', exact=True).click()
    ready()

    # These are layout fixtures, not a generated translation or model-quality claim.
    directory = store.root / 'translations' / 'browser-layout'
    directory.mkdir(parents=True)
    source = PdfReader(paper['source_path'])
    (directory / 'mono.pdf').write_bytes(open(paper['source_path'], 'rb').read())
    writer = PdfWriter()
    for source_page in source.pages:
        width, height = float(source_page.mediabox.width), float(source_page.mediabox.height)
        target = writer.add_blank_page(width=width * 2, height=height)
        target.merge_page(source_page)
        target.merge_transformed_page(source_page, Transformation().translate(tx=width))
    with (directory / 'dual.pdf').open('wb') as stream:
        writer.write(stream)
    (directory / 'mapping.json').write_text('{"segments": []}')
    job = dict(id='browser-layout', paper_id=paper['id'], source_version=paper['source_version'], operation_id='browser-layout', state='completed', progress=100,
               artifacts={kind: str(directory / (kind + ('.json' if kind == 'mapping' else '.pdf'))) for kind in ('mono', 'dual', 'mapping')})
    with store.connect() as db:
        db.execute('INSERT INTO translation_jobs VALUES (?,?,?,?)', (job['id'], paper['id'], job['operation_id'], json.dumps(job)))
    page.reload()
    ready()

    def change_view(view):
        page.get_by_label('更多阅读工具', exact=True).click()
        page.get_by_role('button', name='翻译', exact=True).click()
        page.get_by_label('PDF 阅读视图', exact=True).select_option(view)
        page.get_by_label('关闭阅读工具', exact=True).click()
        ready(view)

    def region():
        page.get_by_label('PDF 框选区域', exact=True).click()
        frame = page.locator('.pdf-page').bounding_box()
        x, y = frame['x'] + frame['width'] * .58, frame['y'] + 140
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x + 100, y + 70, steps=5)
        page.mouse.up()
        page.get_by_role('dialog', name='区域批注').wait_for()

    change_view('mono')
    region()
    page.get_by_role('button', name='记笔记', exact=True).click()
    page.get_by_label('记录想法', exact=True).fill('中文视图的区域笔记：保持这处证据。')
    page.get_by_text('已保存 · 等待讨论', exact=True).wait_for()
    mono_note = next(n for n in store.list('note', paper['id']) if n['content'].startswith('中文视图的区域笔记'))
    assert mono_note['anchor']['page_index'] is None
    assert mono_note['anchor']['rendition']['view'] == 'mono'
    page.get_by_label('关闭阅读工具', exact=True).click()
    assert page.locator(f'[data-note-id="{mono_note["id"]}"]').count() == 1
    page.reload()
    ready()
    change_view('mono')
    assert page.locator(f'[data-note-id="{mono_note["id"]}"]').count() == 1
    change_view('dual')
    assert page.locator(f'[data-note-id="{mono_note["id"]}"]').count() == 0
    region()
    page.get_by_role('button', name='记笔记', exact=True).click()
    page.get_by_label('记录想法', exact=True).fill('双语视图的区域笔记：右栏不要错位。')
    page.get_by_text('已保存 · 等待讨论', exact=True).wait_for()
    dual_note = next(n for n in store.list('note', paper['id']) if n['content'].startswith('双语视图的区域笔记'))
    assert dual_note['id'] != mono_note['id'], 'A new selection must not overwrite the preceding note'
    assert dual_note['anchor']['rendition']['rects'][0][0] > 612
    page.get_by_label('关闭阅读工具', exact=True).click()
    assert page.locator(f'[data-note-id="{dual_note["id"]}"]').count() == 1

    # Text selection also persists even when sentence alignment is unavailable.
    passage = page.locator('.textLayer span').filter(has_text='Both policies receive 20 observations per episode.').last
    passage.evaluate("""e => {
        const range = document.createRange(); range.selectNodeContents(e);
        const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
        e.dispatchEvent(new MouseEvent('mouseup', {bubbles: true}));
    }""")
    page.get_by_role('button', name='保留标记', exact=True).click()
    page.get_by_role('button', name='已保留在 PDF', exact=True).wait_for()
    page.get_by_label('关闭译文', exact=True).click()
    page.evaluate('window.getSelection().removeAllRanges()')
    page.screenshot(animations='disabled', path=str(output / 'pdf-annotations-dual.png'))
    with page.expect_download() as download:
        page.get_by_label('下载当前 PDF（含批注）', exact=True).click()
    saved = output / 'annotated-dual.pdf'
    download.value.save_as(saved)
    annotations = [a.get_object() for p in PdfReader(saved).pages for a in p.get('/Annots', [])]
    assert any(a['/Subtype'] == '/Square' and '双语视图' in a['/Contents'] for a in annotations)
    assert any(a['/Subtype'] == '/Highlight' for a in annotations)
    assert not any('中文视图' in a['/Contents'] for a in annotations)
    change_view('original')
    assert page.locator(f'[data-note-id="{dual_note["id"]}"]').count() == 0
    page.close()

    # Actual Chromium touch input, not a synthetic DOM TouchEvent.
    context = browser.new_context(viewport={'width': 820, 'height': 1000}, has_touch=True, is_mobile=True)
    touch = context.new_page()
    touch.on('pageerror', lambda error: errors.append(str(error)))
    touch.goto(url)
    touch.wait_for_function("() => Number(document.querySelector('.pdf-page')?.dataset.pageIndex) >= 0")
    before = int(touch.get_by_label('PDF 缩放比例').inner_text().rstrip('%'))
    session = context.new_cdp_session(touch)
    def points(gap):
        return [{'x': 350 - gap, 'y': 260, 'id': 1}, {'x': 350 + gap, 'y': 260, 'id': 2}]
    session.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': points(40)})
    for gap in (50, 60, 70, 80):
        session.send('Input.dispatchTouchEvent', {'type': 'touchMove', 'touchPoints': points(gap)})
    session.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
    touch.wait_for_function("() => !document.querySelector('.pdf-gesturing') && Number(document.querySelector('.pdf-page')?.dataset.pageIndex) >= 0")
    assert int(touch.get_by_label('PDF 缩放比例').inner_text().rstrip('%')) > before
    assert touch.evaluate('visualViewport.scale') == 1
    assert not touch.get_by_role('dialog').count(), 'Pinching must not create a selection'
    touch.screenshot(animations='disabled', path=str(output / 'pdf-touch-zoom.png'))
    context.close()
    assert not errors, errors
    return {'trackpad_zoom': 'passed', 'touch_pinch': 'passed', 'translated_annotations': 'passed', 'annotated_download': 'passed'}
