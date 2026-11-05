"""Run source checks without private receipts, host modification or model calls."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
node = shutil.which('node')
if not node:
    raise SystemExit('Node.js 24 is required.')
env = os.environ | {'PYTHONUTF8': '1', 'PYTHONPATH': str(ROOT / 'upstream/src')}


def run(args, cwd=ROOT):
    print('Checking:', ' '.join(map(str, args)), flush=True)
    subprocess.run(list(map(str, args)), cwd=cwd, env=env, check=True)


run([sys.executable, '-X', 'utf8', '-m', 'pytest', 'upstream/tests',
     'tests/test_studio.py', 'tests/test_learning.py', 'tests/test_distribution.py', '-q', '--tb=short'])
run([node, '--test', 'tests/host.test.mjs', 'tests/studio.test.mjs'])
frontend = ROOT / 'upstream/frontend'
run([node, 'node_modules/typescript/bin/tsc', '--noEmit'], frontend)
run([node, 'node_modules/vitest/vitest.mjs', 'run', '--maxWorkers=4'], frontend)
run([node, 'node_modules/vite/bin/vite.js', 'build'], frontend)
print('Source checks passed. No live-account or desktop acceptance is inferred.')
