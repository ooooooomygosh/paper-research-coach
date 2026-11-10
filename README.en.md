<div align="center">
<img src="docs/images/logo.svg" width="80" alt="Paper Research Coach">

# Paper Research Coach

### Read in your chosen language. Keep the evidence and your own judgment together.

A PDF reader with selection questions, shared annotations, expandable explanations and offline bilingual study pages.

[简体中文](README.md) · **English** · [Download DSH 1.3.1](https://github.com/ooooooomygosh/paper-research-coach/releases/tag/dsh-v1.3.1) · [DSH guide](docs/DEEPSEEK_HARNESS.md#english) · [Reading method](docs/METHOD.en.md)

[![Verification](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml/badge.svg)](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/verify.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-526653)](LICENSE)
</div>

![An explanation expanded into the in-app reading area, with follow-up, PDF comparison and fullscreen controls](docs/images/explanation-large.png)

*Actual interface with synthetic material and preset replies, not live-model output. Explanations can leave the sidebar and use the reading workspace.*

## What changes in this release

Ask about a selection in a Chinese or bilingual PDF without losing the language or reading position. Click an evidence reference to navigate. Expand a detailed explanation, compare it beside the paper, enter fullscreen or explicitly open a separate window. Changing the display does not regenerate the answer.

- **Connected evidence and annotations:** page markers open the note text. Translated locations distinguish exact, paragraph-level and unresolved matches. Export creates an annotated PDF copy.
- **Smaller reading moves:** choose skim, understand or reconstruct. A flexible four-stage route covers relevance, mechanism, evidence and boundaries, then your own judgment and recall. Skip, pause or request a small prerequisite explanation where needed.
- **Bilingual study pages:** index a selection, chapter or full paper; generate source text, Chinese translation and analysis with stop/resume and revision support. Reuse existing user notes and export one offline HTML file.
- **Traceable diagrams:** concept, method and argument nodes return to the source. Collapse branches or hide nodes for recall. Model analysis stays distinct from the learner's words.

![A study page with source text and Chinese translation on the left, paragraph analysis and notes on the right](docs/images/study-reading.png)

*Synthetic material with preset analysis, not live-model output. Images, fonts, diagrams and note snapshots are embedded; offline viewing makes no external requests.*

<details>
<summary>See the adjustable PDF and explanation comparison</summary>

![The paper and explanation beside one another](docs/images/explanation-compare.png)

Synthetic material and preset replies. Narrow windows switch between full-width paper and explanation views.
</details>

## DeepSeek Harness plugin

**DSH 1.3.1 · workbench core 2.0.0rc15.** Uses the signed-in Harness account, with no extra API key or Codex CLI. Existing knowledge-base learning, Zotero/folder sync, ideas, review and export remain available.

| Platform | Current installation |
|---|---|
| **macOS Apple silicon** | [Download PRC-DSH-1.3.1-mac.zip](https://github.com/ooooooomygosh/paper-research-coach/releases/download/dsh-v1.3.1/PRC-DSH-1.3.1-mac.zip), fully quit Harness, extract and open `安装.command`, then restart and choose “论文研读”. Native-host checks use Harness **0.2.2-rc.1** |
| Windows | `PRC-DSH-1.2.0-win-x64.zip` is a historical distribution. This release does not provide a 1.3.1 Windows installer or claim native Windows installation validation. A macOS ZIP or standalone wheel is not a Windows plugin |

The macOS plugin checks **DSH-specific releases**, verifies host compatibility and SHA-256, and stages a package for the next full Harness restart. It does not replace a running reading process. Settings show the actual plugin version, staged status and manual check. Older installations first upgrade with this package. The standalone wheel updater stays disabled inside DSH.

Papers, translations, notes and conversations remain in `~/.dsh/paper-research-coach` or the configured `DSH_HOME`. Legacy eight-step records and original answers are retained; continuing resumes the saved question and position before using the four-stage route. Installation and updates retain backups and a previous build. [Installation and recovery](docs/DEEPSEEK_HARNESS.md#english) · [Source build](ports/deepseek-harness/README.md)

## Other entry points

| Entry | Usage |
|---|---|
| **Standalone workbench** | Local PDF reading and Codex CLI coaching; its wheel releases and update flow remain separate |
| **Skill only** | Coaching through the model configured in Claude Code, Codex or Pi; graphical workbench and DSH packages are separate |

## Workbench

```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/ooooooomygosh/paper-research-coach/main/scripts/install.sh | sh
```

```powershell
# Windows PowerShell (not yet run on real Windows; if it fails, use the manual steps in the quick start)
irm https://raw.githubusercontent.com/ooooooomygosh/paper-research-coach/main/scripts/install.ps1 | iex
```

The script finds the newest release, verifies its SHA-256, and installs into its own environment: [uv](https://docs.astral.sh/uv/) if present, else pipx, else `python -m venv`. No admin rights, no change to your library or shell configuration.

Then run `prc`, import a PDF, and press “开始跟读” (start reading). The AI conversation goes through your local Codex CLI, signed in once; without it, reading, marking, notes and export still work. To try first: `prc-demo` (a three-page synthetic paper that never touches your library).

While it runs, the workbench checks for updates at most once a day, verifies and installs in the background, and switches when nobody is reading; `prc update` does it by hand. Uninstalling leaves the library alone; `prc doctor` prints where it lives. Manual install, source runs and Windows details are in the [quick start](docs/QUICKSTART.md).

## Skill only

Claude Code:

```text
/plugin marketplace add ooooooomygosh/paper-research-coach
/plugin install paper-research-coach@paper-research-coach
```

Codex, Pi and other hosts:

```bash
npx skills add ooooooomygosh/paper-research-coach
```

Then attach a paper and say: "Walk me through this paper, starting with the finding the authors care about most." No Python, Node.js, Zotero or separate model key from this project.

Without npx: download `paper-research-coach-skill-*.zip` from [Releases](https://github.com/ooooooomygosh/paper-research-coach/releases) and unzip the **whole folder** into the host's skill directory (Codex `~/.agents/skills/`, Claude Code `~/.claude/skills/`, Pi `~/.pi/agent/skills/`). `SKILL.md` alone is not enough; it needs the `references` and `assets` beside it.

## Data and validation boundaries

- Original PDFs remain read-only. Source evidence, model analysis and user annotations remain distinct. Model features send the relevant material to the configured service; local records do not make inference offline.
- Section detection is heuristic. Scanned pages can be discussed as images; formulas and figures retain original-page verification images. Quote matching checks provenance, not semantic correctness.
- Checks include automated regressions, synthetic Chrome scenarios, a legacy-data upgrade copy and real-account synthetic PDF questions/source navigation on macOS Harness 0.2.2-rc.1. [Detailed scope](ports/deepseek-harness/docs/BILINGUAL-READING.md)
- This run does not establish learning benefits or validate real Zotero writes. Saving notes and recording learning performance remain separate permissions.

## Documentation and credits

[Quick start](docs/QUICKSTART.md) · [Method and sources](docs/METHOD.en.md) · [Workbench guide](docs/WORKBENCH.en.md) · [DSH guide](docs/DEEPSEEK_HARNESS.md#english) · [Contributing](CONTRIBUTING.md) · [Security](SECURITY.md)

Original code and documents are [MIT](LICENSE); citation metadata is in [CITATION.cff](CITATION.cff). Explanations reuse [Answer me with HTML](https://github.com/QingYunA/answer-me-with-html); knowledge-base learning reuses [Learn from Materials](https://github.com/dmoshehun-prog/learn-from-materials). [Third-party notices](ports/deepseek-harness/THIRD_PARTY.md) and font OFL licenses are retained.

[Performance and reading continuity](docs/PERFORMANCE-AND-RESUME.md)

