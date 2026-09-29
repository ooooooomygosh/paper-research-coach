# Paper Research Coach

A portable Agent Skill and local reading workbench for graduate researchers. Move from choosing a paper to explaining its contribution, testing its evidence, preserving your own thoughts, developing falsifiable questions, and preparing recall or presentations.

**2.0.0rc1 is a release candidate.** Live Zotero 10 round-trip verification is still pending, so this is not labeled stable.

[中文](README.md) · [Design rationale](docs/DESIGN.md) · [Sources](docs/SOURCES.md) · [Verification scope](docs/TESTING.md)

## What it does

The coach advances one concrete reading move at a time, with a real source location and at most one thinking task. It gives direct explanations when requested, accepts detours and pauses, and tracks assistance by ability rather than page count. Theory, empirical, measurement, dataset and survey papers use different checks.

Your words and AI comments remain separate, with anchors and revision history. The workbench connects PDFs, evidence-backed relationships, comparison records, ideas, adjustable retrieval practice and exports. The UI defaults to Chinese; the skill follows your language.

## Skill only

Download the skill ZIP from [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases). Copy the entire `paper-research-coach` folder, including references and assets, into one of:

- Codex: `~/.agents/skills/paper-research-coach/`
- Claude Code: `~/.claude/skills/paper-research-coach/`
- Pi: `~/.pi/agent/skills/paper-research-coach/`

In a new chat: “Use paper-research-coach to read this paper with me. I need to decide whether its assumptions fit my research problem.”

No runtime or additional AI key is required. Plain Markdown notes work without the workbench. Format compatibility and live host verification are reported separately.

## Local workbench

Python 3.10+ is required. Download the wheel from Releases:

```bash
python3 -m venv ~/.venvs/paper-research-coach
source ~/.venvs/paper-research-coach/bin/activate
python -m pip install /path/to/paper_research_coach-2.0.0rc1-py3-none-any.whl
prc install-skill --host codex
prc serve
```

Use `--host claude` or `--host pi` for another host. On Windows activate the virtual environment through `Scripts/Activate.ps1`. The wheel bundles the React/PDF.js frontend; Node.js is not needed at runtime. See TESTING.md for operating-system coverage.

On macOS, after installation you can also double-click `scripts/open-workbench.command` in the repository.

Import a PDF, select text or a region, and write a thought. It saves locally. Return to your existing AI host and say “continue”; the skill reads the new notes and checkpoint. Saved and discussed are distinct states. The workbench does not call an AI service or reason in the background after your host session ends.

## Zotero

Zotero 10+ exposes a native local API. Enable local application communication in Advanced settings, select a personal-library collection in the workbench, and authorize writes in Zotero's own dialog. “Always Allow” enables persistent use; “Allow” permits a single write.

Bibliography and PDF attachment information flow from Zotero; notes and supported highlights/text annotations synchronize both ways. The first PDF attachment is the initial source; keep distinct PDF versions separate or explicitly manage the source. Simultaneous edits preserve both versions for resolution. Deletions require a decision and never cascade to source PDFs. Instance IDs isolate versions across libraries.

Keys remain in the OS credential store or memory. The app scopes synchronization to the chosen collection even though Zotero's native key itself is broader. Disconnection or denied authorization does not prevent local reading. Live-test limitations are explicitly listed in [TESTING.md](docs/TESTING.md).

## CLI and exports

`prc doctor`, `import`, `list`, `context`, `commit`, `resume`, `text`, `history`, `replace-source`, `import-markdown`, `serve`, `sync`, and `export` share the same data layer. Use JSON files or stdin for structured commits; operation IDs and expected revisions protect against duplicate retries and lost edits.

Exports: Markdown paper cards, research question cards, presentation outlines, comparison CSV and separate annotated PDFs. Only verified anchors for the current PDF version are exported as annotations. Original PDFs remain unchanged. Default review intervals of 1/3/7/14 days are editable product defaults, not established optimal schedules.

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
npm ci --prefix frontend
npm --prefix frontend run build
python scripts/prepare_licenses.py
python -m pip install -e '.[dev]'
pytest -q
python scripts/validate_skill.py
python scripts/package_release.py
```

Node.js 22.13+ is needed for source builds. `examples/create_demo.py` creates original synthetic teaching material. After verification, the first successful main-branch build creates the initial preview release with the wheel and skill ZIP. Later main builds preserve that release; new version tags publish separate previews.

Software tests do not establish learning gains. A [human trial protocol](docs/HUMAN-TRIAL.md) separately evaluates accuracy, independent explanation, transfer and amount of assistance. No learner-outcome study has been completed.

Original code and documentation: [MIT](LICENSE). Third-party reading sources are credited and paraphrased, not redistributed or relicensed. Bundled libraries retain their own licenses. [Data and security boundaries](docs/SECURITY.md).
