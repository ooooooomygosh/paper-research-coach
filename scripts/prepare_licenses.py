import shutil
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / "src/paper_research_coach/licenses"
folder.mkdir(exist_ok=True)
(folder / "NOTICE.txt").write_text(
    "Paper Research Coach bundles PDF.js (Apache-2.0), React and scheduler (MIT), "
    "Lucide (ISC), and Markdown/math rendering components including react-markdown, "
    "remark, rehype and KaTeX (MIT). Component and dependency license files are "
    "included here. Python dependencies pypdfium2/PDFium and Pillow are installed "
    "from their distributions, which include their own license notices. "
    "The optional BabelDOC 0.6.4 translation component is AGPL-3.0, installed "
    "separately, and retains its upstream license; see BabelDOC-0.6.4.txt. "
    "Project MIT licensing does not relicense those components.\n"
)
lock = json.loads((root / "frontend/package-lock.json").read_text())
for package_path, metadata in lock["packages"].items():
    if not package_path or metadata.get("dev"):
        continue
    source = root / "frontend" / package_path
    package = package_path.removeprefix("node_modules/").replace("/", "__")
    license = next((
        p
        for p in (source / "LICENSE", source / "LICENSE.txt", source / "LICENSE.md")
        if p.is_file()
    ), None)
    if license:
        shutil.copyfile(license, folder / (package + ".txt"))

shutil.copyfile(root / "docs/BabelDOC-0.6.4-LICENSE.txt", folder / "BabelDOC-0.6.4.txt")
