"""Required canonical artifacts and deterministic readable exports."""
import hashlib
import json
from pathlib import Path


def check_canonical(page, kb, include_units=True):
    """Read-only preflight. Missing synthesis is never silently fabricated."""
    from methods import validate_library, validate_binding, patterns
    from methodology import validate, markdown
    kb = Path(kb)
    if page['meta']['mode'] != 'overview':
        return {}
    for name, field in [('methods.json', 'methodLibrary'), ('methodology.json', 'methodology')]:
        p = kb / name
        if not p.is_file():
            raise ValueError(f'Missing required deliverable: {p}. Create and verify its source-grounded content before rendering.')
        canonical = json.loads(p.read_text(encoding='utf-8'))
        if field not in page or page[field] != canonical:
            raise ValueError(f'Missing or stale {field} snapshot. Bind {name} before rendering, or use finalize.py for automatic binding.')
    validate_library(page['methodLibrary'], kb)
    validate_binding(page)
    validate(page['methodology'], page, kb)
    exports = {'patterns.md': patterns(page['methodLibrary']), 'methodology.md': markdown(page['methodology'])}
    if include_units:
        from unit_records import checked_unit_exports
        exports.update(checked_unit_exports(page, kb))
    return exports


def export_readable(kb, exports):
    """Derived files may be refreshed; preserve any prior differing prose."""
    kb = Path(kb)
    for name, content in exports.items():
        p = kb / name
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists() and p.read_text(encoding='utf-8') != content:
            old = p.read_bytes()
            archive = kb / 'history'
            archive.mkdir(exist_ok=True)
            backup = archive / (p.stem + '-' + hashlib.sha256(old).hexdigest()[:12] + p.suffix)
            if not backup.exists():
                backup.write_bytes(old)
        p.write_text(content, encoding='utf-8')


def verify_readable(kb, exports):
    for name, expected in exports.items():
        p = Path(kb) / name
        if not p.is_file() or p.read_text(encoding='utf-8') != expected:
            raise ValueError(f'Missing or stale readable deliverable: {p}')
