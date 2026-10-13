<div align="center">

<img src="docs/images/logo.svg" width="88" height="88" alt="Paper Research Coach">

# Paper Research Coach

**Read beyond the summary. Make the judgment your own.**

A local workspace that keeps **the paper, your question and your thinking** together, and a portable reading-coach Skill for Claude Code, Codex and Pi.<br>
It does not write you another summary. It checks the evidence with you, one passage at a time, and leaves the judgment in your hands.

[![Verification](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml/badge.svg)](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml)
[![Release](https://img.shields.io/github/v/release/ooooooomygosh/paper-research-coach?include_prereleases&label=release&color=365c47)](https://github.com/ooooooomygosh/paper-research-coach/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-526653)](docs/QUICKSTART.md)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-Claude%20Code%20%C2%B7%20Codex%20%C2%B7%20Pi-7f9871)](#quick-start)
[![License: MIT](https://img.shields.io/badge/license-MIT-526653)](LICENSE)

[简体中文](README.md) · **English** · [Quick start](docs/QUICKSTART.md) · [Reading method](docs/METHOD.en.md) · [Workbench guide](docs/WORKBENCH.en.md) · [Design](docs/DESIGN.md) · [Contributing](CONTRIBUTING.md)

</div>

<br>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/reading-dark.webp">
  <img src="docs/images/reading.webp" alt="Actual workbench: the PDF on the left and a discussion about the same passage on the right; the quoted source travels with the reader's question.">
</picture>

<p align="center"><sub>Actual UI, following your light / dark theme · synthetic paper and a labelled scripted dialogue, not live-model output; no model was connected · <a href="docs/SHOWCASE.md">Reproduce</a></sub></p>

> [!NOTE]
> **Preview software, not a proven learning intervention.** The newest packages are the **top** entry on [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases) (pre-releases, so GitHub’s “Latest” badge does not point to them). The Skill installed through the Claude Code plugin or `npx skills add` comes straight from the main branch and is always current.

## How it differs from “summarise this paper”

|  | Typical AI paper assistant | Paper Research Coach |
|---|---|---|
| **Each turn gives you** | A page-long summary | One passage, one question, at most one thinking task |
| **Who judges** | The AI states a conclusion | A provisional judgment, checked against the source; ask for a hint, a direct explanation, or a challenge |
| **Your thoughts** | Lost in the chat | Saved verbatim, apart from AI comments, with a page anchor |
| **Evidence** | Hard to trace back | Every message and note returns to its place in the PDF; anchors from an older PDF version are flagged |
| **What remains** | Another summary | A provisional judgment, open questions and the smallest useful test |
| **Your data** | Uploaded | PDFs and notes stay local; only the turns you send reach the configured model |

## Why read this way

The habits students use most — rereading, highlighting, summarising — are among the least effective; familiarity with material in front of you easily passes for understanding, and a fluent AI summary makes the illusion stronger. This method spends its effort on getting **you** to predict, check, explain and recall, drawing on three kinds of sources:

| Source | Representatives | Practices it brings |
|---|---|---|
| Researchers’ experience | Harry Shum & Gang Hua’s “three levels, four stages, ten questions”, Shuyi Wang (relaying Peter Carr), Keshav, Mu Li, Nielsen, Hamming | Don’t read linearly: abstract → conclusion → figures → introduction → discussion, methods last, stop any time; skim / careful / study; ten questions as a coverage check; end with a next research step |
| Scientific method | Platt’s *Strong Inference*, Chamberlin’s multiple hypotheses, Popper, Toulmin | For a key claim, list alternatives and seek discriminating evidence and strong simple baselines |
| Learning science | Cognitive apprenticeship, scaffolding, cognitive load, retrieval practice, the generation effect, self-explanation | One move per turn; predict before looking; fade help by ability; keep your own words; recall with the paper closed |

Each paper should push you up one level: from **passive** reading (what it says) to **active** (what it is for), **critical** (does it hold up) and **creative** (what can I do with it). The pocket version: after each paper, be able to say **what judgment it changes, why you believe it, and how it changes your next step**.

👉 The seven principles, where the eight-step route comes from, the theory behind each practice and a reading list are in **[The reading method](docs/METHOD.en.md)**. These sources motivate the design; they do not show that this tool improves learning.

## Highlights

<table>
<tr>
<td width="33%" valign="top">

**🎯 Shows you the source**<br>
Wherever the coach is, the PDF turns to that page and numbers the sentences to read ①②③. Each sentence must be on that page word for word, so it cannot be made up; one click takes you back.

</td>
<td width="33%" valign="top">

**✅ One small task at a time**<br>
A task card above the message box says where to look, what to do and what counts as done. Predictions are one tap; when a step is done the next task appears at once, so you keep reading.

</td>
<td width="33%" valign="top">

**🧭 Explainer panel, one click back to the mainline**<br>
Ask a concrete question and a panel opens beside the paper: figures, tables and short sentences, with follow-ups. Mainline replies can carry a small figure too. Press “回到主线” and the mainline is where it was.

</td>
</tr>
<tr>
<td valign="top">

**📜 A smooth PDF**<br>
Scroll through all pages; pinch or Ctrl+scroll to zoom; click [12] or Figure 3 in the paper to jump there. Immersive mode, dark theme and position recovery.

</td>
<td valign="top">

**🖍️ Marks are not opinions**<br>
A highlight is the paper's words, a note is yours. Each finished step keeps one takeaway in your words; together they are your review.

</td>
<td valign="top">

**🌐 Non-native friendly**<br>
Separates language barriers from conceptual gaps; no whole-paper translation required. In optional bilingual PDFs, marks are kept per rendition.

</td>
</tr>
<tr>
<td valign="top">

**💬 Talk about the source**<br>
Select a sentence and choose “discuss”; the quote travels with your question. Enter sends; Enter in an empty box continues the mainline.

</td>
<td valign="top">

**🔄 Stays current by itself**<br>
New versions are verified and installed in the background; the switch happens when nobody is reading, or with one “reload” click. Skill copies follow.

</td>
<td valign="top">

**🔌 Two ways, one method**<br>
Install the Skill for coaching in your agent, or run the local workbench to read and discuss side by side. Zotero, translation and exports are optional.

</td>
</tr>
</table>

<table>
<tr>
<td width="50%"><img src="docs/images/welcome.webp" alt="Welcome screen: start with one paper worth reading"></td>
<td width="50%"><img src="docs/images/annotations.webp" alt="Highlights and region marks kept separately in a side-by-side PDF view"></td>
</tr>
<tr>
<td align="center"><sub>First run: import one PDF and start</sub></td>
<td align="center"><sub>Marks kept per rendition in the side-by-side view (both columns are synthetic English, a layout test)</sub></td>
</tr>
</table>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/mainline-dark.webp">
  <img src="docs/images/mainline.webp" alt="A mainline task: on the left the PDF has turned to the evidence page with sentence 1 marked; on the right the reply carries a small comparison table and the task card above the message box shows where to look, the task, what counts as done and one-tap answers.">
</picture>

<p align="center"><sub>The mainline task card: synthetic paper and a labelled scripted reply, not live model output · the PDF has turned to the page and numbered the sentence</sub></p>

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/branch-dark.webp">
  <img src="docs/images/branch.webp" alt="Explainer panel: the PDF on the left, and on the right a panel answering a concrete question with a flow chart, a table and a callout; a “back to the mainline” button sits at the top right.">
</picture>

<p align="center"><sub>The explainer panel: synthetic paper and a labelled scripted explanation, not live model output · press “回到主线” and the mainline stays where it was</sub></p>

## Quick start

| You want | Use |
|---|---|
| **Read the paper and discuss it side by side** (recommended) | [Option 1: the workbench](#option-1-the-workbench-one-line-install-three-steps) |
| AI-guided reading inside Claude Code or Codex only | [Option 2: the Skill only](#option-2-the-skill-only) |

### Option 1: the workbench, one-line install, three steps

**1. Install.** Paste one line in a terminal.

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/ooooooomygosh/paper-research-coach/main/scripts/install.sh | sh
```

```powershell
# Windows PowerShell (not yet run on real Windows; if it fails, use the manual steps in the quick start)
irm https://raw.githubusercontent.com/ooooooomygosh/paper-research-coach/main/scripts/install.ps1 | iex
```

The script finds the newest release, **verifies its SHA-256**, and installs it into its own environment: with [uv](https://docs.astral.sh/uv/) if you have it (uv can fetch Python too), else pipx, else `python -m venv`. No admin rights, no change to your library or shell configuration. Read it first if you like: [install.sh](scripts/install.sh).

**2. Open.** Type `prc`. The browser opens the workbench; with no papers yet you see the welcome page. For a double-click launcher later, run `prc shortcut` and an icon appears on your Desktop.

**3. Read.** Import a PDF → press “开始跟读” (start reading) or select a passage and press “讨论这处” (discuss this). The AI coach uses your local Codex CLI, signed in once; without it, reading, marking and notes still work. To try first: `prc-demo` (a three-page synthetic paper that does not touch your library).

### Staying current

| What you use | How it updates |
|---|---|
| **The workbench** | **Nothing to do.** While it runs, it checks at most once a day, verifies a new version and installs it in the background. It switches over when nobody is reading; if a page is open, the library and “⋯” say the new version is ready and **重新载入** (reload) takes about 5 seconds and keeps your place. The next `prc` also switches to it. By hand: `prc update`. |
| **The Skill inside the workbench** | It ships in the same package, so it updates with the workbench. |
| **A Skill installed separately** | Copied by `prc install-skill`: the workbench brings it to its own version each time it starts (by hand: `prc install-skill --sync`). Claude Code plugin: turn on auto-update for the marketplace, or run `/plugin marketplace update paper-research-coach` (menu names depend on your Claude Code version). Installed with `npx skills add`: run the same command again. |

At most once a day the workbench makes **one anonymous request** to GitHub's releases API. It sends no papers, notes or identity. An update installs only a package published by this project, and only after it matches the `SHA256SUMS` published in the same release. To stop automatic installs, switch it off in Settings → 版本与更新 or set `PRC_NO_AUTO_UPDATE=1`; to stop checking too, `PRC_NO_UPDATE_CHECK=1`.

### Option 2: the Skill only

**Claude Code (recommended)**

```text
/plugin marketplace add ooooooomygosh/paper-research-coach
/plugin install paper-research-coach@paper-research-coach
```

Attach a paper and ask: **“Guide my reading of this paper. Start with the authors' key observation.”** It uses your host's existing model; no Python, Node.js, Zotero or separate API key from this project is needed.

**Codex, Pi and other hosts**

```bash
npx skills add ooooooomygosh/paper-research-coach
```

<details>
<summary>Without npx: install the Skill by hand</summary>

Download `paper-research-coach-skill-*.zip` from the top entry on [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases) and extract the **complete folder** into your host's skill directory:

| Host | User-level directory |
|---|---|
| Codex | `~/.agents/skills/paper-research-coach/` |
| Claude Code | `~/.claude/skills/paper-research-coach/` |
| Pi | `~/.pi/agent/skills/paper-research-coach/` |

Keep `references` and `assets`, not just `SKILL.md`. Format compatibility is not a claim that every host and model has been tested.

</details>

With the workbench installed, the Skill in Claude Code can attach to the same paper's reading progress through `prc` and open the explainer panel in the workbench.

<details>
<summary>Uninstall, manual install, troubleshooting</summary>

- **Uninstall**: `uv tool uninstall paper-research-coach` (pipx: `pipx uninstall paper-research-coach`; venv: delete `~/.paper-research-coach` and `~/.local/bin/prc`). Your library is not deleted; `prc doctor` shows where it is.
- **Manual install, source installs, Windows details**: see the [Quick start](docs/QUICKSTART.md).
- **`prc` not found**: open a new terminal; if that fails, run the full path printed at the end of the install script.
- **Browser did not open**: `prc` prints the address; or run `prc` again.
- **AI not connected**: sign in to your local Codex CLI, then press “重新连接” (reconnect) in the conversation.

</details>

## What a turn looks like

> **Reader:** Could this gain just come from taking more measurements?
>
> **Coach:** (the PDF has turned to page 2 and marked ①) Look at ①: both groups observe 20 times, so the budgets match. Do you predict the gap survives? (one tap: almost gone / still clear / can't tell) A direct explanation is fine too.

<sub>An illustrative exchange, not a live-model result. Solving one local question or deciding not to pursue a paper are valid outcomes too.</sub>

| Your question | The coach's job |
|---|---|
| What did the authors actually notice? | Separate the distinctive observation from background and the proposed method. |
| Does this result support the claim? | Inspect the evidence, matched budgets, alternative explanations and limits. |
| Is my difficulty language or the concept? | Separate translation, prerequisite knowledge and the paper's argument; preserve qualifiers. |
| Where did my thought come from? | Keep your words apart from AI commentary, with a return path to the source. |
| What changes in my research next? | Record a provisional judgment, an open question or the smallest useful test. |

## Privacy and limits

- Papers and reading records are stored locally and the service binds to loopback. **Local storage does not mean offline AI**: using the coach or translation sends relevant content to the configured model provider.
- The update check makes at most one anonymous request a day to GitHub's releases API, carrying no papers, notes or identity. By default a verified package from this project is installed in the background; switch that off in Settings, with `PRC_NO_AUTO_UPDATE=1`, or stop checking with `PRC_NO_UPDATE_CHECK=1`.
- Zotero writes require your authorization. Never share the launch link, which carries an access credential. See [Data and access boundaries](docs/SECURITY.md).
- There is no human learning-effect claim, no full Safari / iPad / Pencil certification and no guaranteed OCR for scanned PDFs. Zotero items with several attachments currently use the first PDF. See [Testing](docs/TESTING.md) and [Review](docs/FINAL-REVIEW.md).

## FAQ

<details>
<summary><b>Do I need a separate paid API key?</b></summary>

The Skill uses the model your host (Claude Code, Codex, Pi) is already configured with. The workbench's coach currently runs through a locally signed-in Codex CLI; reading, marking, notes and exports need no model at all.

</details>

<details>
<summary><b>Does it grade me or decide that I have “mastered” something?</b></summary>

No. Only if you enable recording of answers and feedback does it store one observation per ability, quoting your own words and the criterion used. Clicks, reading an AI explanation or completed steps are never treated as evidence of mastery.

</details>

<details>
<summary><b>Does it work with Zotero or Obsidian?</b></summary>

Yes, optionally. Zotero sync needs Zotero 10+ with the local API enabled and your authorization. OneDrive / Obsidian folders, bilingual translation, review and talk exports are covered in the [Workbench guide](docs/WORKBENCH.en.md).

</details>

<details>
<summary><b>What about scanned PDFs?</b></summary>

Automatic OCR is not guaranteed. You can mark a region and discuss its image with the coach; an empty text layer is not an empty page.

</details>

## Contribute

Start with [CONTRIBUTING.md](CONTRIBUTING.md). Describe the reading task that was interrupted, not just the control you would like to add. Use synthetic reproduction material; do not submit private PDFs, databases, credentials or conversations.

If this project helps you read, a star ⭐ helps other careful readers find it.

<a href="https://star-history.com/#ooooooomygosh/paper-research-coach&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=ooooooomygosh/paper-research-coach&type=Date&theme=dark">
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=ooooooomygosh/paper-research-coach&type=Date" width="600">
  </picture>
</a>

## License and credits

Original code and documentation: [MIT](LICENSE). [Reading-method sources](docs/SOURCES.md) and [translation-component licensing](docs/THIRD_PARTY_TRANSLATION.md) retain their respective boundaries.
