# Paper Research Coach

A portable Agent Skill and local reading workbench for graduate researchers. Move from choosing a paper to explaining its contribution, testing its evidence, preserving your own thoughts, developing falsifiable questions, and preparing recall or presentations.

**2.0.0rc5 is a release candidate.** Core note/annotation round trips were verified against Zotero 10.0.4. Host coverage and remaining special-case checks are documented in TESTING.md.

[中文](README.md) · [Design rationale](docs/DESIGN.md) · [Sources](docs/SOURCES.md) · [Verification scope](docs/TESTING.md)

## What it does

The coach advances one concrete reading move at a time, with a real source location and at most one thinking task. It gives direct explanations when requested, accepts detours and pauses, and tracks assistance by ability rather than page count. Theory, empirical, measurement, dataset and survey papers use different checks.

Your words and AI comments remain separate, with anchors and revision history. The workbench connects PDFs, evidence-backed relationships, comparison records, ideas, adjustable retrieval practice and exports. The UI defaults to Chinese; the skill follows your language.

## Quiet reading, durable coaching and optional translation

Each paper has one canonical workbench conversation and one persisted native Codex thread. Refresh, reopening, restarting the service and changing the coach model resume that same thread. Earlier conversations remain read-only history. `--new` now reconnects idempotently. Initial instructions are bounded to 3000 characters; normal turns add at most 300 automatic characters, then preserve exact user words and explicit selections/images. Full pages, note collections and copied history are retrieved only on demand.

The library starts collapsed. The compact toolbar opens a secondary drawer for translation, coach/model/history, notes and other tools. Wide screens use a resizable 70/30 PDF/chat split, small screens stack independently scrolling panes, and immersive mode retains only PDF, conversation and composer. Escape closes the topmost overlay before leaving immersive mode. Drafts and rendering state remain mounted; paper/version-scoped page, scroll and zoom are persisted.

Translation uses a separate, tool-free Codex connection with existing login, defaulting to GPT-6-Luna with low reasoning. BabelDOC 0.6.4 generates Chinese and side-by-side bilingual PDFs and saved paragraph/glyph mappings; sentence alignment supports split/merged sentences, with paragraph fallback when uncertain. Selecting text queries saved translations; discussing it attaches the original source anchor. Jobs freeze their settings, run one at a time, and preserve cached work across cancellation and restart. Changed source versions leave previous translations archived.

Install the optional worker with Python 3.12 in `<data_dir>/babeldoc-env` (BabelDOC supports Python 3.10–3.13):

```bash
uv venv --python 3.12 "/path/to/prc-data/babeldoc-env"
uv pip install --python "/path/to/prc-data/babeldoc-env/bin/python" "BabelDOC==0.6.4"
```

Use `Scripts/python.exe` on Windows, or set `PRC_BABELDOC_PYTHON` before starting the service for a different environment. The base reader works without the component. First use downloads upstream layout/font/tokenizer assets. No extra API key is used. See [licensing and compatibility](docs/THIRD_PARTY_TRANSLATION.md) and [validation scope](docs/TESTING.md).

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
python -m pip install /path/to/paper_research_coach-2.0.0rc5-py3-none-any.whl
prc install-skill --host codex
prc serve
```

Use `--host claude` or `--host pi` for another host. On Windows activate the virtual environment through `Scripts/Activate.ps1`. The wheel bundles the React/PDF.js frontend; Node.js is not needed at runtime. See TESTING.md for operating-system coverage.

On macOS, after installation you can also double-click `scripts/open-workbench.command` in the repository.

Import a PDF and use the Coach conversation beside it. The workbench drives your local Codex CLI with its existing provider, model and login configuration. Initialization provides concise coaching rules; turns append a short natural page hint and exact user text, with explicit selections and images. Pages, notes and detailed methods are retrieved on demand. Responses stream, can be interrupted, and survive refreshes and service restarts. Attach the current page image when discussing figures.

Use `prc open --paper PAPER_ID` to open the browser with local authentication and the selected paper conversation. It reuses the running service or starts one when needed; `--new` reconnects to the same canonical conversation for that paper. The conversation picker shows only the selected paper's saved conversations and never enumerates global CLI history. `prc coach send --file message.txt --wait` continues that same workbench conversation from the CLI. Live workbench conversations currently use Codex; the portable skill still supports Codex, Claude Code and Pi.

Conversation history is stored locally. Note consent controls additional verbatim learner notes; AI comments remain separate. Next actions, research ideas and recall questions can be saved directly through workbench tools. Selected source material goes to the model service configured in the CLI. Inference starts when the user sends a message. Saved and discussed remain distinct states.

## Guided reading without a custom prompt

Click **Start reading** for a paper. Every paper follows the same eight-step route: reading goal, distinctive contribution, problem setup, mechanism, evidence, scope and judgment, research transfer, and recall. The coach adapts the evidence to the paper type. **Continue the route** resumes the current step; answering its question uses the answer-and-continue action. Ordinary questions, notes and selection discussions are detours that preserve the return point. A round ends only after all eight steps and a real recall answer from this round.

Conversations are scoped to one paper. Creating or switching chats preserves that paper’s notes and reading progress. The workbench does not enumerate global CLI history. Use `prc open` to open an authenticated browser session, and `prc coach send --follow --wait` to continue without entering a prompt.

Import a downloaded PDF in the workbench, or save it to the selected Zotero collection for indexing. Notes and annotations sync to the linked Zotero item when authorized; connected folder exports go to `06_PRC阅读记录`. Conversations, progress and review attempts are stored locally. GitHub contains the software and Skill, not the personal library.

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

Node.js 24.15+ is needed for source builds. `examples/create_demo.py` creates original synthetic teaching material. After verification, the first successful main-branch build creates the initial preview release with the wheel and skill ZIP. Later main builds preserve that release; new version tags publish separate previews.

Software tests do not establish learning gains. A [human trial protocol](docs/HUMAN-TRIAL.md) separately evaluates accuracy, independent explanation, transfer and amount of assistance. No learner-outcome study has been completed.

Original code and documentation: [MIT](LICENSE). Third-party reading sources are credited and paraphrased, not redistributed or relicensed. Bundled libraries retain their own licenses. [Data and security boundaries](docs/SECURITY.md).

## OneDrive and local literature folders

Choose and authorize a Zotero collection, then connect a literature folder in Settings or run `prc vault configure --path /path/to/literature` and `prc vault scan`. PDFs are matched by content; existing Zotero attachments and original files remain intact. New papers receive linked attachments. Existing Obsidian paper cards remain read-only external sources, including their AI attribution.

New and imported editable notes are exported under `06_PRC阅读记录/<paper-id>/` as append-only Markdown revisions. Editing an exported revision imports that edit; concurrent edits become explicit conflicts. New Markdown files initially have unconfirmed external authorship. Source PDFs and original cards are never overwritten, and missing cloud files never cause cascading deletion.

`prc service install` enables a macOS login service. It scans the folder every 10 minutes and synchronizes with running Zotero every 10 minutes; sleep/logout pauses work. Use `prc service status` or `prc service stop`. Other platforms can keep `prc serve` running. SQLite and credentials stay outside OneDrive.

New Zotero parents require bibliographic identity verified against the PDF's first page. Crossref and arXiv provide structured metadata; OpenAlex is optional (`prc metadata openalex-key` stores your key in the OS keyring). Only identifiers and titles leave the computer. Unresolved papers remain locally readable and do not block other imports. `prc metadata resolve --paper <id> --refresh` retries a lookup; `prc metadata status` shows source records.

The reader includes PDF outlines, cancellable local text search and back/forward reading locations. Optional learning feedback links exact learner answers to checked source pages, actual assistance and explicit criteria; it records a local performance, not mastery.
