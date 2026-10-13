"""Rewrite tests/fixtures/explainers/*.doc.json from the .md drafts.

The browser tests render these parsed documents, so Python (the only parser) and the
renderer are checked against the same drafts. A pytest check fails when they are stale.
"""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "src"))
from paper_research_coach.explainer import parse_draft  # noqa: E402

folder = root / "tests/fixtures/explainers"
for draft in sorted(folder.glob("*.md")):
    doc = parse_draft(draft.read_text(encoding="utf-8")).doc
    draft.with_suffix(".doc.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", draft.with_suffix(".doc.json").relative_to(root))
