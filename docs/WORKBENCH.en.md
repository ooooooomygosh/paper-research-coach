# Workbench guide

[Home](../README.en.md) · [Quick start](QUICKSTART.md) · [中文](WORKBENCH.md)

This guide describes the current source. Installed behavior depends on the downloaded version. Historical host and Zotero verification is recorded in [Testing](TESTING.md), not newly certified by this polish pass. Everything below is optional after basic installation.

## Reading and continuity

Use `prc open` to start or reuse the loopback service and authenticate the browser. Each new browser needs its own launch authentication. Never share the token-bearing launch URL. macOS users can also use the repository’s `scripts/open-workbench.command` after installation.

The library starts collapsed. Wide layouts give the source most of the space, with a draggable split; narrow layouts stack the panes. PDF position, zoom and scroll state are scoped to the paper and version. Page-number edits commit on Enter or blur; Escape cancels the draft. Immersive mode uses Cmd / Ctrl + Shift + Enter. Escape dismisses the topmost surface before leaving the reading mode.

Each paper has one durable local conversation and native Codex thread, reused across refresh, service restart and model changes. Earlier conversations remain read-only history under the coach tools. `prc open --paper PAPER_ID` and `prc coach send --file message.txt --wait` resume the same binding; the compatibility `--new` flag does not create another thread. Uncertain creation is reconciled before retrying.

Automatic initialization is capped at 3000 characters, and ordinary per-turn position guidance at 300 characters; mainline turns also carry a short, code-generated method card for the current step. Exact learner messages, explicitly attached selections and images are kept separately. Whole pages, all notes and duplicate histories are not automatically resent every turn; source tools retrieve what is needed.

### Mainline and detours

- **Where you are**: the mainline card at the top of the coach panel is always visible — an eight-segment track, “step n/8 · name”, and the step’s goal or current question.
- **Advance**: its button reads **开始跟读** (start), then **继续主线** (continue), or **回答并继续主线** (answer and continue) while you have typed something. With a pending question, typing an answer and pressing Enter also counts as answering.
- **Detour**: select text or a region in the PDF and choose **讨论这处**, or just ask. A detour never advances or resets the mainline; press **继续主线** to return.
- **Intent and help mode** sit above the message box and apply to this turn only.
- **Getting the most out of it**: answer each step in a sentence before reading the feedback; state the contribution and your own next step in your words; park unfamiliar terms that do not block the current judgment. See [The reading method](METHOD.en.md).

Use secondary tools for the full route with evidence receipts, model connection, notes and evidence. Direct questions and explicit explanations do not require a complete reading route or translated PDF. Eight dimensions represent coverage, not measured mastery. Note consent and local performance-recording consent remain separate; AI explanations and Continue clicks do not demonstrate independent understanding.

## PDF zoom and annotations (rc7+)

Pinch on a trackpad or touchscreen to zoom around the gesture position (25%–400%). Ordinary scrolling stays native. A frosted toolbar provides zoom, fit width, previous/next page and direct page entry, region selection and download; it becomes horizontal below the page on narrow screens.

Select text or a region, then keep the mark or write a note. Chinese and bilingual annotations persist on their exact PDF layout across reloads. They are scoped to the translation job and file hash, so regenerated layouts cannot silently reuse old coordinates. Existing notes remain available.

The toolbar downloads the current PDF with native highlights, rectangles and note contents embedded in a separate copy. Original files are preserved. Source-aligned passages can still be discussed as original evidence; unmapped translated selections can be saved as notes.

## Optional bilingual translation

Choose the translation model and reasoning effort independently of the coach, using the existing Codex login. The configured default is GPT-6-Luna / low; use the actual available-model list. Each task snapshots its model and languages.

Default concurrency is two papers and four model requests globally, adjustable to 1–4 papers and 1–8 requests. Browser sessions share one backend queue. Batch selection supports bibliographic search and reuses existing current-version tasks or translations. Closing the browser does not stop the queue; the computer and service must remain running.

Mono and bilingual PDFs are readable as soon as generated, before sentence alignment finishes. Paragraph mappings can serve selection help during alignment; reliable sentence mappings refine it later. Discussing translated material attaches the original source anchor. **Original selections can be discussed before any translation exists.**

Use the pinned BabelDOC 0.6.4 component in an independent Python 3.12 environment. Install [uv](https://docs.astral.sh/uv/) and substitute the data directory reported by `prc doctor`:

```bash
uv venv --python 3.12 "/path/to/prc-data/babeldoc-env"
uv pip install --python "/path/to/prc-data/babeldoc-env/bin/python" "BabelDOC==0.6.4"
```

On Windows the interpreter is `babeldoc-env/Scripts/python.exe`. An existing environment can be selected with `PRC_BABELDOC_PYTHON` before service startup. The base workbench still supports Python 3.10+; component limits and licenses are in [Third-party translation](THIRD_PARTY_TRANSLATION.md). A valid Codex login/model entitlement is required, but no separate model key is configured here.

The initial translation downloads upstream layout, font and tokenizer resources, then caches them. Jobs and cache entries distinguish source version, model, languages and component version. Restart resumes pending tasks; PDFs already generated are reused. Explicitly stopped jobs remain stopped. Replacement source versions archive old translations rather than presenting them as current. Automatic translation writeback to Zotero, cross-device job synchronization and a separate model API backend are not provided.

## Optional Zotero 10 connection

Enable local application communication in Zotero, choose a personal-library collection in the workbench and grant access in **Zotero’s own prompt**. Persistent synchronization needs persistent permission; one-time approval is not a permanent grant.

Bibliographic data and attachments come from Zotero. Notes, highlights and editable text annotations support round trips within the documented scope. The first PDF attachment is currently selected: verify the source when items have multiple attachments. This PR does not add an attachment chooser. Downloaded source PDFs remain read-only.

Concurrent changes preserve both versions and require resolution. Deletions require confirmation; papers and attachments are not automatically deleted. Source replacement marks old anchors for rechecking. Unlocated thoughts are linked notes; verified regions can become native annotations. Offline changes save locally before retrying synchronization.

The Zotero authorization key can access editable libraries; the application separately restricts operations to its selected collection. Keys are held in the OS credential store or process memory, not exports or source. See [Testing](TESTING.md) for actual integration coverage and remaining limitations.

## Optional OneDrive / Obsidian directory

First choose and authorize a Zotero collection. Configure the local literature directory in settings or run:

```bash
prc vault configure --path /path/to/literature
prc vault scan
prc vault status
prc service install
```

The macOS login service pauses during sleep or logout. Other platforms can run `prc serve`. Directory and Zotero polling default to ten minutes, with manual refresh in reading tools. `prc service status` inspects the service and `prc service stop` stops it.

PDF discovery deduplicates by bytes, reuses matching Zotero attachments and preserves their collections. New files are linked, not moved. Ambiguous duplicates require attention. Existing `01_论文卡片` metadata (`原文PDF路径` / `原文PDF`) is read as external source material without rewriting templates or Obsidian configuration; an AI-completed review is not learner mastery.

New notes and editable Zotero notes export into `06_PRC阅读记录/<paper-id>/` as append-only revision files. Edits can be read back and concurrent revisions remain conflicts. New Markdown initially has unconfirmed external authorship. A missing or deleted source does not delete workbench records. Annotation coordinates are only written to byte-identical PDFs.

SQLite, credentials and queues stay in the application data directory. Only exported notes go into the selected folder for OneDrive synchronization. Conversations and review responses are not claimed to be live cross-device state.

Before creating Zotero bibliographic items, the workbench checks the PDF title and queries Crossref, arXiv and optional OpenAlex, retaining author order. Unresolved metadata remains local and queued for review, rather than creating an empty-author item. Queries send the DOI/title, not the PDF. Use `prc metadata openalex-key`, `prc metadata resolve --paper PAPER_ID --refresh`, and `prc metadata status` for configuration and inspection.

## Notes, review and export

Thoughts, conversations, ideas, progress and original review answers save locally first. Synchronization requires the relevant connection and authorization. Answer retrieval-practice questions before requesting feedback; the default 1 / 3 / 7 / 14-day intervals are adjustable and do not send system notifications.

```bash
prc doctor
prc import /path/to/paper.pdf --title "Paper title" --goal "What must I judge?"
prc list
prc context PAPER_ID
prc resume PAPER_ID
prc text PAPER_ID 0
prc commit /path/to/transaction.json
prc history NOTE_ID
prc replace-source PAPER_ID /path/to/new-version.pdf
prc import-markdown PAPER_ID /path/to/notes.md
prc export paper --paper PAPER_ID
prc export ideas --paper PAPER_ID
prc export talk --paper PAPER_ID
prc export comparison
prc export pdf --paper PAPER_ID
```

`text` uses zero-based physical PDF page indices. Transactions use JSON files or stdin, operation IDs and revision checks; do not interpolate learner wording into shell commands. Exports include Markdown paper/idea cards, presentation outlines, comparison CSV and a separate annotated PDF. Unlocated or old-version notes remain in the cards without being painted onto an incorrect source.

## Development and boundaries

See [Quick start](QUICKSTART.md), [Contributing](../CONTRIBUTING.md) and [Showcase](SHOWCASE.md). `prc-demo` is temporary: export anything you need to keep before exiting. `python scripts/package_release.py` builds the Skill ZIP, wheel and source sdist in `dist/`. Successful main verification creates a prerelease for a new package version; existing artifacts are kept immutable.

SQLite is authoritative; Markdown/CSV are exports. Local storage does not mean offline AI. Consult [Security](SECURITY.md) for backups and access boundaries. Passing software tests is not a learning-effect result: see the [Human trial protocol](HUMAN-TRIAL.md) and [Review](FINAL-REVIEW.md). Original code and documentation use [MIT](../LICENSE); third-party resources retain their licenses and [attribution](SOURCES.md).

Switch between original, Chinese and bilingual PDFs directly in the frosted toolbar. Unavailable translations stay disabled; manage generation under More reading tools → Translation.
