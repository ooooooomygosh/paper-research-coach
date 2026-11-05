# Current examples

- `overview-methods-content.json`: complete current English quick-overview data bound to `methods-demo.learnkb/`.
- `overview-current-zh.json`: complete current Chinese quick-overview data bound to `methods-demo-zh.learnkb/`.
- `overview-en-content.json`: pre-binding input retained for method-binding tests; use the bound current examples as the authoring reference.
- `methods-library-demo.html` / `features-en.html`: English current-design previews.
- `features-zh.html` / `learn-from-materials-demo.html`: Chinese current-design previews.
- `method-lab-synthetic.pdf`: original three-page English teaching material, distributed under MIT; not a real research paper.
- `overview-systematic-demo.json` / `systematic-demo.learnkb/`: historical Chinese systematic-study compatibility example with a source-heading index, coverage/summary records, a v2 action-rule ledger and a source-first content review.
- `systematic-demo.html` / `systematic-demo.md`: rendered systematic example from the same data and canonical method files.

The Method Lab examples and their knowledge bases are self-authored synthetic teaching material under MIT. No real paper full text or its derived knowledge base is bundled. Raw source quotes remain English in either locale. Current JSON examples include canonical methods and an explicitly labeled integrated structure. Additional compatibility data lives under `scripts/tests/fixtures/`; do not use it to author a new overview. HTML examples demonstrate code and interaction; browser visual acceptance is reported separately.

## Current sequential systematic example (1.1.0)

- `overview-sequential-systematic.json` / `sequential-systematic.learnkb/`: the current unit-record-v2, relation-ledger-v1 and content-review-v3 example. One executor performed separate source reread, correctness and omission/application passes on the three-page original material; see `review-notes.md` inside the knowledge base. This is a small synthetic example, not empirical performance evidence or a review generator.
- `sequential-authoring/project.json` and `units/`: editable canonical authoring inputs for `pipeline.py assemble`.
- `sequential-systematic-demo.html` / `.md`: the renderer preview of those same records. Full finalizer acceptance is recorded separately from browser/manual visual checks.
- `overview-systematic-demo.json` and `systematic-demo.learnkb/` remain unchanged historical fixtures for explicit compatibility tests; use the sequential example for new systematic authoring.

From the skill root, choose a work output outside the source knowledge base:

```text
python scripts/pipeline.py assemble examples/sequential-authoring/project.json --knowledge-base examples/sequential-systematic.learnkb --output-page WORK/sequential-page.json
python scripts/content_review.py examples/sequential-systematic.learnkb/content-review.json --page WORK/sequential-page.json --knowledge-base examples/sequential-systematic.learnkb
python scripts/finalize.py WORK/sequential-page.json --knowledge-base examples/sequential-systematic.learnkb --output-dir WORK/delivery --name method-lab
```
