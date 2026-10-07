# Changelog

## Unreleased

- Explain the reading method: `docs/METHOD.md` (and English) sets out why each practice is there — the passive → active → critical → creative ladder, a non-linear reading order, the seven principles with the researchers' advice, scientific-method and learning-science work behind them, Hua Gang's ten questions mapped onto the eight steps, what it helps with and what it does not promise. Both READMEs gain a short “why read this way” section.
- Coach with the method, not only cite it: new `references/questions.md` (reading order, Kajiya's five introduction questions, critical and creative questions, the ten-question template, getting unstuck), loaded by the Skill and available to the workbench coach; selection, coaching, notebook and review references gain venue priority, parking non-blocking terms, abstract self-translation, the “never reread” note standard and half-page reviews. Four new eval scenarios cover them.
- Sources: record the two Zhihu articles (Wang Shuyi; Shum and Hua) as read in full and add the learning-science and scientific-method literature with DOIs.
- Render PDFs in browsers without the very newest JavaScript APIs: pdf.js 6's modern build calls `Map#getOrInsertComputed` and `Math.sumPrecise`, so every page failed on e.g. Chromium 141. Use the polyfilled legacy build and log swallowed render errors.
- Add a dark theme that follows the system. Roughly 230 near-duplicate colours became ~20 semantic tokens; light mode is visually unchanged and the PDF page is gently dimmed at night.
- Conversation: Enter sends and Shift+Enter breaks a line (IME confirmation never sends); the composer grows with the draft; the quoted passage stays visible under the learner's question; replies no longer repeat its location; finished turns are no longer stamped “已保存”; `**加粗：**正文` renders in Chinese replies (remark-cjk-friendly).
- An unavailable coach now says so (未连接 / 需要登录) with a reconnect action, instead of “连接中” forever; reading, marks and notes stay usable.
- Annotations: a kept highlight is shown as “原文标记”, not “我的原话”, is no longer counted or sent to the coach as a pending learner thought, and “写下想法” starts a thought at the same place.
- Install the Skill as a Claude Code plugin (`/plugin marketplace add ooooooomygosh/paper-research-coach`) or with `npx skills add`; name common Chinese requests in the Skill description; check that all release versions agree.
- Redesign the README in both languages with a light/dark hero screenshot, comparison table, feature grid, three install paths and an FAQ.
- `npm audit fix` for a new high-severity `source-map-js` advisory that failed the CI audit step; collapse duplicated portal/inline coach JSX.

## 2.0.0rc9

- Move original, Chinese and bilingual PDF view switching into the floating toolbar, with unavailable translations disabled until ready.

## 2.0.0rc8

- Consolidate page navigation, zoom, fit, region selection and annotated downloads in the floating PDF toolbar; remove duplicate controls from the header and reading drawer.
- Keep direct page entry in the toolbar, with a compact wrapped layout on narrow screens.

## 2.0.0rc7 — PDF gestures and translated annotations

- Add focal-point-preserving trackpad/touch pinch zoom and a compact frosted toolbar for zoom, fit, page navigation, region selection and annotated PDF download. Gestures preview the existing canvas and rasterize once on release.
- Persist translated selections separately from original-source evidence, scoped to the translation job, layout and PDF content hash. Restore highlights and rectangles in their matching Chinese/bilingual PDF after reload; reject changed files and unrelated layouts.
- Add explicit mark/note actions for text and regions, preserve preceding drafts when starting a note on a new selection, and export native highlight/rectangle annotations in the selected PDF.
- Extend browser checks with actual touch input, trackpad zoom/focal position, cross-view annotation persistence and annotated downloads; preserve legacy request fingerprints.

## 2.0.0rc6 — reading polish

- Refine paper surfaces, toolbar grouping, split-handle visibility, focus/hover feedback and restrained dialog/drawer motion; honor reduced motion and keep a direct touch immersion exit.
- Repair synthetic PDF text extraction with indirect stream objects and allow PDF embedded fonts in CSP. Browser checks now exercise actual passage selection, motion preferences and touch exit.
- Add a disposable `prc-demo` entrypoint with a synthetic, searchable three-page paper and isolated temporary storage; no automatic model request or authorization.
- Commit page-number edits on Enter/blur, cancel with Escape, and keep the persisted cursor separate from typing.
- Use native modal dialogs with explicit keyboard wrapping for import, metadata and reading-task edits; preserve file/title/goal after failed import and support single-PDF drag/drop.
- Search across bibliographic fields; expose a useful empty state; discuss selected original text without whole-paper translation.
- Refine local-question and non-native-language coaching without forcing a route or conflating translation with evidence.
- Reorganize bilingual repository entrypoints, quickstart, detailed guides, review boundaries and contribution/report templates. Add offline documentation checks and a separate synthetic browser/showcase workflow.

### Earlier unreleased work included in this version

- Add searchable batch background translation and bilingual library badges; share a persistent queue across browser sessions and automatically resume pending work after service restart.
- Run multiple paper workers and multiplex independent Codex translation/alignment requests with configurable global limits (default two papers / four requests). Make finished PDFs readable before alignment completes and reuse saved PDFs on resume.
- Automatic Zotero and literature-folder checks default to every 10 minutes, with a manual refresh in the reading tools drawer. Index each sync poll's paper list once and limit the translation layout worker's CPU threads.
- Bind each paper to one durable workbench conversation and native Codex thread; resume across restarts/model changes and reconcile unknown creation without duplicating threads. Keep previous chats as read-only history.
- Bound initialization and per-turn automatic context, preserving exact user messages while retrieving pages, notes and methods on demand.
- Add optional BabelDOC 0.6.4 whole-paper translation through separate Codex login connections, independent model settings, resumable cached tasks, mono/dual PDFs and saved sentence/paragraph source mappings.
- Default to a quiet, resizable PDF/chat reading surface, secondary tools drawer and immersive mode with persistent drafts, selections and viewport position.

## 2.0.0rc5 (release candidate)

- Ground legacy durable text sends in their selected PDF page while preserving retry fingerprints; keep cross-page images rejected.
- Bound per-paper model context and migration history with explicit excerpt metadata and scoped, paginated original-note/dialogue retrieval; keep database records intact.
- Add opt-in evidence-backed local learning feedback, linked to exact learner answers and pages actually read. Keep this separate from note consent and mastery certification.
- Add PDF outline navigation, cancellable text search, and source-scoped reading history. Preserve new selections and drafts across asynchronous actions.
- Include per-turn intent and help controls, safer note-source rebinding, persistent page annotations, fit-width reading and Chinese IME handling from the reviewed PR.
- Strengthen contribution, mechanism, competing-explanation and fair-budget checks in the Skill, and retain stopping decisions for irrelevant papers.
- Build a source distribution alongside the wheel and portable Skill. Derive release tags and package versions from built artifacts.
- Report the installed runtime version consistently and keep local access tokens out of service startup output.

## 2.0.0rc4 (release candidate)

- Add prompt-free, per-paper guided reading with eight persisted steps. Questions and annotations preserve the mainline return point; completion requires a real recall answer from the current round.
- Use only paper-research-coach, with natural writing guidance inside the Skill. Add a complete reading-route reference and adapt CLI continuation to the same flow.
- Scope conversation selection and creation to the current paper; remove global CLI history import and reject cross-paper access.
- Add `prc open` and a double-click launcher to reuse or start the local service and authenticate external browsers. Accept a complete launch link on the connection page.
- Render actual PDF pages for the coach through a bounded visual tool, and provide clickable source locations. Preserve original PDF bytes.
- Fix PDF.js 6 region navigation and keep the note editor open while choosing a position. Correct the discussed-state reset caused by equivalent coordinate representations.
- Connect Codex CLI, streaming replies, interruption, refresh recovery, shared CLI/web conversations, note comments, research ideas and review actions.
- Simplify the reading surface with a persistent sidebar toggle, compact coaching controls, and secondary menus for exports, metadata and connection settings. Restore note revisions after AI comments and retain answered review records for coaching feedback.
- Use translucent exported PDF highlights so linked comments at the same location keep the text and figures readable.

## 2.0.0rc3 (release candidate)

- Show a waiting-for-input message when a PDF location is selected without note text.
- Complete an interrupted note transaction even when its editor has since been cleared, while preserving the saved original. Added two regression checks; 17 frontend checks pass.

## 2.0.0rc2 (release candidate)

- Resolve arXiv metadata from the exact PDF version, with structured authors and verified arXiv DOI, when registry lookup is incomplete.
- Preserve earlier-version titles instead of silently substituting metadata from a newer PDF. Added a regression test; 57 backend and 15 frontend checks.

## 2.0.0rc1 (release candidate)

- Rebuilt the incomplete single-file prototype into a complete portable Agent Skill.
- Added a local PDF reading workbench with exact-word notes, anchors, revision history, sessions, evidence-backed relationships, comparison records, ideas, and adjustable retrieval practice.
- Added one transactional service used by CLI and HTTP, with operation IDs, optimistic concurrency and source-version checks.
- Added Zotero 10 native local API synchronization, explicit authorization, instance separation and conflict/deletion resolution.
- Added OneDrive/Obsidian folder discovery, content-based Zotero binding, append-only Markdown revisions, explicit file conflicts, and a macOS login service.
- Fixed audit reproductions for autosave races, PDF replacement, rich notes, instance isolation and interrupted imports/exports; added 56 backend and 15 frontend regression tests.
- Verified core Zotero 10.0.4 round trips and adapted native creation/annotation queries.
- Added Markdown/CSV/annotated-PDF exports, bundled frontend distribution, synthetic fixtures, behavioral scenarios and a human study protocol.

Verification scope is recorded in docs/TESTING.md. This release does not claim measured educational effectiveness.
