"""Create a new reviewed manifest/archive bound to the exact delivered HTML.

Original delivery remains untouched. Geometry success is not visual or semantic
proof. Run only after a permitted browser verification produced a layout report.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path
import zipfile

SCHEMA = 'learn-from-materials/layout-review-v1'
THEMES = {'warm-paper', 'minimal', 'dark'}
WIDTHS = {390, 819, 820, 821, 980, 981, 1024, 1039, 1040, 1041, 1440, 2105}
TABS = {'frameworks', 'content', 'glossary', 'rules', 'practice', 'notes'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def measured_layout(s, width):
    """Reject contradictory pass flags; mirror the browser geometry contract."""
    def number(v):
        return type(v) in (int, float) and math.isfinite(v)
    def rect(v):
        return isinstance(v, dict) and all(number(v.get(k)) for k in ('x', 'y', 'width', 'height')) and v['width'] > 0 and v['height'] > 0
    if not isinstance(s, dict) or not all(number(s.get(k)) for k in ('viewportWidth', 'viewportHeight', 'scrollWidth')):
        raise ValueError('Missing geometry measurements')
    p, panel, nav = (s.get(k) for k in ('page', 'panel', 'nav'))
    if not all(rect(v) for v in (p, panel, nav)):
        raise ValueError('Missing geometry rectangles')
    if (s['viewportWidth'] != width or s['viewportHeight'] <= 0 or
        s['scrollWidth'] > width + 2 or p['width'] < min(1200, width - 60) or
        panel['width'] < .88 * p['width'] or panel['x'] < p['x'] - 2 or
        panel['x'] + panel['width'] > p['x'] + p['width'] + 2 or
        abs(p['x'] + p['width'] / 2 - width / 2) > 24 or
        s.get('navDirection') != 'row' or nav['height'] > 100 or
        panel['y'] - nav['y'] - nav['height'] > 80 or s.get('gridColumns') != 1):
        raise ValueError('Geometry contradicts passed status')


def validate_report(report, html):
    if not isinstance(report, dict) or report.get('schemaVersion') != SCHEMA:
        raise ValueError('Unsupported layout review schema')
    if report.get('htmlSha256') != sha(Path(html).read_bytes()):
        raise ValueError('Layout report is stale or belongs to another HTML')
    if report.get('status') != 'passed' or report.get('errors') != []:
        raise ValueError('Browser layout check did not pass')
    rows = report.get('checks')
    if not isinstance(rows, list) or any(not isinstance(r, dict) or r.get('errors') != [] for r in rows):
        raise ValueError('Invalid layout measurements')
    actual = {(r.get('theme'), r.get('width'), r.get('tab')) for r in rows}
    required = {(t, w, tab) for t in THEMES for w in WIDTHS for tab in TABS}
    if not required <= actual:
        raise ValueError('Incomplete viewport/theme/module matrix')
    for row in rows:
        measured_layout(row.get('measurements'), row['width'])
    # Widths revisited after expansion test resize recovery, not just isolated sizes.
    for theme in THEMES:
        for tab in TABS:
            visited = [r.get('width') for r in rows if r.get('theme') == theme and r.get('tab') == tab]
            if visited[-2:] != [820, 1440]:
                raise ValueError('Missing resize-return checks')
    full = report.get('fullscreen')
    if not isinstance(full, list) or any(not isinstance(r, dict) or r.get('errors') != [] for r in full):
        raise ValueError('Invalid fullscreen checks')
    if not {(t, w, m) for t in THEMES for w in (390, 1440, 2105) for m in ('frameworks', 'rules')} <= {
            (r.get('theme'), r.get('width'), r.get('module')) for r in full}:
        raise ValueError('Incomplete fullscreen checks')
    match = re.search(r'<script\s+id="pageData"[^>]*>(.*?)</script>', Path(html).read_text(encoding='utf-8'), re.S)
    if not match:
        raise ValueError('HTML has no pageData')
    data = json.loads(match.group(1))
    available = {'frameworks':bool(data.get('frameworks')), 'rules':data.get('methodology', {}).get('status') == 'ready'}
    for row in full:
        if row.get('status') == 'not-applicable' and available.get(row.get('module'), True):
            raise ValueError('Cannot skip an available fullscreen graph')
        if row.get('status') != 'not-applicable':
            s = row.get('measurements', {})
            rect = s.get('rect', {})
            values = [rect.get(k) for k in ('x', 'y', 'width', 'height')] + [s.get('viewportWidth'), s.get('viewportHeight')]
            if not all(type(v) in (int, float) and math.isfinite(v) for v in values):
                raise ValueError('Missing fullscreen measurements')
            x, y, w, h, vw, vh = values
            if vw != row['width'] or vh <= 0 or max(abs(x), abs(y), abs(w - vw), abs(h - vh)) > 3:
                raise ValueError('Fullscreen geometry contradicts passed status')
            measured_layout(row.get('restored'), row['width'])
    if not isinstance(report.get('screenshots'), list) or not report['screenshots']:
        raise ValueError('Screenshot evidence is required')


def within(root, relative):
    if not isinstance(relative, str) or Path(relative).is_absolute():
        raise ValueError('Evidence path must be relative')
    p = (root / relative).resolve()
    if not p.is_relative_to(root) or not p.is_file():
        raise ValueError('Missing or unsafe evidence path: ' + relative)
    return p


def record(manifest_path, report_path):
    manifest_path, report_path = Path(manifest_path).resolve(), Path(report_path).resolve()
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    report = json.loads(report_path.read_text(encoding='utf-8'))
    files = manifest.get('files', [])
    payload = {}
    for entry in files:
        p = within(root, entry['path'])
        data = p.read_bytes()
        if sha(data) != entry.get('sha256'):
            raise ValueError('Delivery file changed: ' + entry['path'])
        payload[entry['path']] = data
    htmls = [root / name for name in payload if Path(name).suffix == '.html' and len(Path(name).parts) == 1]
    if len(htmls) != 1:
        raise ValueError('Expected one root HTML in delivery')
    validate_report(report, htmls[0])
    stem = manifest_path.name.removesuffix('.delivery.json') + '.layout-reviewed'
    new_manifest, archive = root / (stem + '.delivery.json'), root / (stem + '.zip')
    if new_manifest.exists() or archive.exists():
        raise ValueError('Reviewed delivery already exists; preserve prior files')
    for i, entry in enumerate(report['screenshots']):
        p = within(report_path.parent, entry.get('path'))
        data = p.read_bytes()
        if sha(data) != entry.get('sha256'):
            raise ValueError('Screenshot changed')
        key = stem + '.evidence/' + str(i + 1) + p.suffix
        payload[key] = data
        entry['path'] = key
    report_name = stem + '.layout-review.json'
    payload[report_name] = (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    manifest.update(status='layout-checked', layoutCheck='passed', visualReview='not-run', layoutReport=report_name)
    manifest['warnings'] = [w for w in manifest.get('warnings', []) if w != '视觉检查未运行；此交付仅完成静态校验']
    manifest['warnings'].append('自动几何检查通过；截图的可读性与视觉效果仍需人工查看，语义判断仍是复核者记录。')
    manifest['checks'] = list(dict.fromkeys(manifest.get('checks', []) + ['responsive-layout']))
    manifest['files'] = [{'path':n, 'bytes':len(d), 'sha256':sha(d)} for n, d in payload.items()]
    data = (json.dumps(manifest, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    # Screenshot evidence stays in this new ZIP; no modification of the original package.
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, body in payload.items():
            z.writestr(name, body)
        z.writestr(new_manifest.name, data)
    with new_manifest.open('xb') as f:
        f.write(data)
    return {'manifest':str(new_manifest), 'archive':str(archive)}


if __name__ == '__main__':
    from cli_output import configure_output
    configure_output()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path)
    p.add_argument('report', type=Path)
    a = p.parse_args()
    try:
        print(json.dumps(record(a.manifest, a.report), ensure_ascii=False, indent=2))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        p.exit(2, str(exc) + '\n')
