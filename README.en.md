# Paper Research Coach

### Read beyond the summary. Make the judgment your own.

A local workspace that keeps **the paper, one concrete question, and your thinking** together. Also available as a portable reading-coach Skill. Built for researchers who want to understand, check, and transfer a paper’s ideas—not collect another AI summary.

[中文](README.md) · [Quick start](docs/QUICKSTART.md) · [Workbench guide](docs/WORKBENCH.en.md) · [Contributing](CONTRIBUTING.md)

[![Verification](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml/badge.svg)](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-526653.svg)](LICENSE)

![Actual workbench: source on the left and a source-grounded discussion on the right. Synthetic paper and scripted dialogue.](docs/images/reading.webp)

*Actual built UI; the paper, values and dialogue are explicitly illustrative, not live-model output or evidence of learning benefit. [Reproduce the showcase and full-size screenshots](docs/SHOWCASE.md).*

> **Preview software, not a proven learning intervention.** These features, including `prc-demo`, require `2.0.0rc6` or newer. Choose that version in Releases; if its packages are not available yet, follow the source quickstart.

## What reading looks like

Keep the source visible. Start with a figure, equation, unfamiliar sentence, or a claim you disagree with. Ask for a hint or a direct explanation; the reading route is not a mandatory lesson sequence.

| Your question | The coach’s job |
|---|---|
| What did the authors actually notice? | Separate the distinctive observation from background and the proposed method. |
| Does this result support the claim? | Inspect the evidence, matched budgets, alternative explanations and limits. |
| Is my difficulty language or the concept? | Separate translation, prerequisite knowledge and the paper’s argument; preserve qualifiers. |
| Where did my thought come from? | Keep your words apart from AI commentary, with a return path to the source. |
| What changes in my research next? | Record a provisional judgment, unresolved question or smallest useful test—not a compulsory summary. |

> **Reader:** Could this gain just come from taking more measurements?  
> **Coach:** First check whether Figure 1 matches the two measurement budgets. Would that explanation still hold? A direct explanation is fine too.

*This is an illustrative exchange, not a live-model result. Solving a local question or deciding not to pursue a paper is also a valid outcome.*

## Choose your starting point

### Reading guidance only: install the Skill

Download `paper-research-coach-skill-*.zip` from [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases). Extract the complete folder into your host’s skill directory:

| Host | User-level directory |
|---|---|
| Codex | `~/.agents/skills/paper-research-coach/` |
| Claude Code | `~/.claude/skills/paper-research-coach/` |
| Pi | `~/.pi/agent/skills/paper-research-coach/` |

Attach a paper and ask: **“Use paper-research-coach to guide my reading. Start with the authors’ key observation.”** Keep `references` and `assets`, not just `SKILL.md`. This mode uses your host’s existing model setup; it does not require this project’s Python, Node.js or Zotero installation. Format compatibility is not a claim that every host and model has been tested.

### Source and conversation together: install the workbench

Requires **Python 3.10+**. Download the `.whl` from [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases), then run in the download directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
# Replace the filename with the wheel you actually downloaded.
python -m pip install "./paper_research_coach-<version>-py3-none-any.whl"
prc open
```

The wheel already includes the interface. **Node.js is only needed for source development.** See [Quick start](docs/QUICKSTART.md) for Windows, source installation and troubleshooting. The workbench’s AI conversation currently uses a locally authenticated Codex CLI; the Skill’s multi-host support does not mean the workbench has all those backends.

Then: **import one PDF → select one passage → ask your current question.** Zotero and whole-paper translation are optional, not prerequisites.

The new preview includes a disposable example:

```bash
prc-demo
```

It opens an original three-page synthetic paper in a separate temporary library on port `8766`. It does not read your personal papers, call a model automatically, or grant recording/sync consent. `Ctrl+C` stops the service and removes the example records. Export outside that temporary folder before stopping to keep anything. This command is not in rc5.

## Quiet by default

The library is collapsed while reading. Keep the PDF and one persistent conversation side by side; use fit-width, position recovery, adjustable panes and immersive reading. Notes, sync and model configuration stay in secondary tools. Existing conversations, drafts and evidence anchors remain intact.

Zotero, a OneDrive / Obsidian directory, bilingual translation, review and exports are optional extensions: [Workbench guide](docs/WORKBENCH.en.md).

## Privacy and limits

Papers and reading records are stored locally, and the service binds to loopback. **Local storage does not mean offline AI.** Using the coach or translation sends relevant content to the configured model provider. Zotero writes require authorization. Never share the private launch link, which carries an access credential. See [Data and access boundaries](docs/SECURITY.md).

There is no human learning-effect claim, no full Safari / iPad / Pencil certification, no real-time cross-device collaboration, and no guarantee of OCR for scanned PDFs. Zotero currently uses the first PDF attachment of an item: check the version before annotating. See [Testing](docs/TESTING.md) and [Review](docs/FINAL-REVIEW.md).

## Contribute

Start with [CONTRIBUTING.md](CONTRIBUTING.md). Describe the reading task that was interrupted—not just the control you would like to add. Use synthetic reproduction material; do not submit private PDFs, databases, credentials or conversations.

Original code and documentation: [MIT](LICENSE). [Reading-method sources](docs/SOURCES.md) and [translation-component licensing](docs/THIRD_PARTY_TRANSLATION.md) retain their respective boundaries.
