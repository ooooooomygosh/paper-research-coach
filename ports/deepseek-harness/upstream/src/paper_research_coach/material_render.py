"""Dedicated process for the vendored renderer and canonical method validators."""
from pathlib import Path
import json
import sys

from .workspaces import INTEGRATIONS, read_json, write_json


def main():
    build = Path(sys.argv[1]).resolve()
    kb = build / "knowledge.learnkb"
    sys.path.insert(0, str(INTEGRATIONS / "learn-from-materials/scripts"))
    from prc_render_page import render
    from methods import validate_library, validate_binding, patterns
    from methodology import validate as validate_methodology, markdown as methodology_markdown
    page = read_json(build / "page.json")
    library = validate_library(read_json(kb / "methods.json"), kb)
    validate_binding(page)
    structure = validate_methodology(read_json(kb / "methodology.json"), page, kb)
    render(page, build / "page.html", build / "page.md")
    (kb / "patterns.md").write_text(patterns(library), encoding="utf-8")
    (kb / "methodology.md").write_text(methodology_markdown(structure, source_labels=page.get("sourceLabels")), encoding="utf-8")
    (build / "methods.json").write_text(json.dumps(library, ensure_ascii=False, indent=2), encoding="utf-8")
    write_json(build / "methodology.json", structure)
    with (build / "page.md").open("a", encoding="utf-8") as stream:
        stream.write("\n\n" + patterns(library) + "\n\n" + methodology_markdown(structure, source_labels=page.get("sourceLabels")))
    write_json(build / "integration-report.json", {"brand": "Paper Research Coach", "renderer": "learn-from-materials 1.1.0 / PRC adaptation", "page_contract": "passed", "method_sources": "matched",
        "methodology_sources": "matched", "semantic_review": "not-independent", "visual_review": "not-run", "note": "PRC integration output; not an upstream finalize audit certificate."})
    print("Learning page and canonical method sources validated and rendered.")


if __name__ == "__main__":
    main()
