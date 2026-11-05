"""Prepare an ignored Windows bundle from an explicitly provided runtime."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', required=True, type=Path,
                        help='Existing portable runtime directory containing python/ and assets/.')
    args = parser.parse_args()
    source = args.runtime.resolve(strict=True)
    dest = ROOT / 'runtime'
    if sys.platform != 'win32':
        raise SystemExit('The installer bundle currently supports Windows x64 only.')
    required = ['python/python.exe', 'python/Lib/site-packages/PyPDF2/__init__.py',
                'python/Lib/site-packages/babeldoc/__init__.py',
                'python/msvcp140.dll', 'python/vcruntime140.dll', 'MSVC-NOTICE.txt']
    for name in required:
        if not (source / name).is_file():
            raise SystemExit(f'Missing runtime input: {name}')
    for name in ['python', 'assets']:
        if (dest / name).exists():
            raise SystemExit(f'Output already exists; use a fresh checkout: runtime/{name}')
    assets = json.loads((dest / 'ASSET-MANIFEST.json').read_text(encoding='utf-8'))['files']
    for name, expected in assets.items():
        file = source / 'assets' / name
        if not file.is_file() or file.is_symlink() or file.stat().st_size != expected['bytes'] or digest(file) != expected['sha256']:
            raise SystemExit(f'Asset absent or different from the tested package: {name}')
    for name in ['python', 'assets']:
        shutil.copytree(source / name, dest / name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc', 'direct_url.json', 'Scripts'))
    dlls = [file for file in (dest / 'python').glob('python*.dll')
            if re.fullmatch(r'python\d{2,3}\.dll', file.name)]
    if len(dlls) != 1:
        raise SystemExit('Expected one versioned Windows Python DLL.')
    (dlls[0].with_suffix('._pth')).write_text(
        'DLLs\nLib\n../../upstream/src\nLib/site-packages\nimport site\n', encoding='utf-8')
    python = dest / 'python/python.exe'
    probe = ('import importlib.metadata as m,platform,sys; '
             'assert platform.machine().upper() in ("AMD64","X86_64"); '
             'assert m.version("BabelDOC")=="0.6.4"; '
             'assert m.version("PyPDF2")=="3.0.1"; '
             'import paper_research_coach.embedded,pypdfium2,onnxruntime; '
             'print("Portable runtime imports verified")')
    subprocess.run([str(python), '-X', 'utf8', '-c', probe], cwd=ROOT, check=True)
    print('Bundle inputs prepared. Run source verification and build_release.py next.')


if __name__ == '__main__':
    main()
