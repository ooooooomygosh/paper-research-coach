import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1]
folder = root / "src/paper_research_coach/licenses"
folder.mkdir(exist_ok=True)
for package in ["pdfjs-dist", "react", "react-dom", "scheduler", "lucide-react"]:
    source = root / "frontend/node_modules" / package
    license = next(
        p
        for p in (source / "LICENSE", source / "LICENSE.txt", source / "LICENSE.md")
        if p.is_file()
    )
    shutil.copyfile(license, folder / (package + ".txt"))
