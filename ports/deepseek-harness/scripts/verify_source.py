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


# upstream/tests/test_install_script.py runs scripts/install.sh, a POSIX installer, and expects a venv laid
# out as bin/python. Windows lays it out as Scripts/python.exe, and a GitHub Windows runner has sh and curl
# (Git for Windows), so the test's own skip condition does not apply and it cannot pass there. The main
# workflow runs that test on Linux, so the Windows run leaves it out. This uses --ignore with a real path:
# a --deselect string would be compared with test ids that use backslashes on Windows and match nothing.
posix_only = ['--ignore', ROOT / 'upstream/tests/test_install_script.py'] if os.name == 'nt' else []
run([sys.executable, '-X', 'utf8', '-m', 'pytest', 'upstream/tests',
     'tests/test_studio.py', 'tests/test_learning.py', 'tests/test_distribution.py', 'tests/test_interactive.py', '-q', '--tb=short', *posix_only])
run([node, '--test', 'tests/host.test.mjs', 'tests/studio.test.mjs', 'tests/interactive-runtime.test.mjs'])
frontend = ROOT / 'upstream/frontend'
run([node, 'node_modules/typescript/bin/tsc', '--noEmit'], frontend)
run([node, 'node_modules/vitest/vitest.mjs', 'run', '--maxWorkers=4'], frontend)
run([node, 'node_modules/vite/bin/vite.js', 'build'], frontend)
print('Source checks passed. No live-account or desktop acceptance is inferred.')
