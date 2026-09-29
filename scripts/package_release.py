"""Build a wheel with prebuilt UI plus a portable skill ZIP. No private state is included."""

import shutil, subprocess, sys, zipfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
subprocess.run(
    [sys.executable, str(root / "scripts/validate_skill.py")], check=True, cwd=root
)
subprocess.run(["npm", "ci", "--prefix", "frontend"], check=True, cwd=root)
subprocess.run(["npm", "--prefix", "frontend", "run", "build"], check=True, cwd=root)
licenses = root / "src/paper_research_coach/licenses"
licenses.mkdir(exist_ok=True)
for package in ["pdfjs-dist", "react", "react-dom", "scheduler", "lucide-react"]:
    folder = root / "frontend/node_modules" / package
    source = next(
        (
            p
            for p in [folder / "LICENSE", folder / "LICENSE.txt", folder / "LICENSE.md"]
            if p.is_file()
        ),
        None,
    )
    if not source:
        raise RuntimeError("Missing third-party license: " + package)
    shutil.copyfile(source, licenses / (package + ".txt"))
(licenses / "NOTICE.txt").write_text(
    "Paper Research Coach bundles PDF.js (Mozilla and contributors, Apache-2.0), React and scheduler (Meta and contributors, MIT), and Lucide (ISC). Their licenses remain applicable to those components. Project MIT licensing does not relicense them.\n"
)
subprocess.run([sys.executable, "-m", "build", "--wheel"], check=True, cwd=root)
out = root / "dist"
out.mkdir(exist_ok=True)
version = "2.0.0rc1"
with zipfile.ZipFile(
    out / f"paper-research-coach-skill-{version}.zip", "w", zipfile.ZIP_DEFLATED
) as archive:
    for path in (root / "skills/paper-research-coach").rglob("*"):
        if path.is_file():
            archive.write(path, path.relative_to(root / "skills"))
    archive.write(root / "LICENSE", "paper-research-coach/LICENSE")
print(
    "Release artifacts:",
    *[p.name for p in out.iterdir() if p.suffix in (".zip", ".whl")],
)
