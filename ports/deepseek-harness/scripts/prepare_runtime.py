"""Turn the prepared Windows venv into a self-contained Python directory."""
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "runtime" / "python"
source = Path(sys.base_prefix)
for pattern in ("python*.exe", "python*.dll", "vcruntime*.dll", "LICENSE.txt"):
    for file in source.glob(pattern):
        shutil.copy2(file, target / file.name)
shutil.copytree(source / "DLLs", target / "DLLs", dirs_exist_ok=True)
shutil.copytree(source / "Lib", target / "Lib", dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("site-packages", "__pycache__", "test", "idlelib", "ensurepip"))
(target / "pyvenv.cfg").unlink(missing_ok=True)
print("Self-contained Python:", target / "python.exe")
