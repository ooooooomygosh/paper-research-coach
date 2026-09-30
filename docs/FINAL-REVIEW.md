# Reading experience and repository review

Scope: the source at `e3353af691bd866448663b489817d05ff7d8fb2b`, after the earlier active-reading PR. This review prioritizes a first useful reading moment and preserves the current persistent conversation, evidence model and authorization boundaries. It does not certify every integration or learning outcome.

## Findings and changes

| Finding | Reader impact | Change in this PR |
|---|---|---|
| Page input immediately writes the cursor on each keystroke | Typing page 12 can jump to page 1, lose focus or disturb reading position | A local draft commits on Enter/blur; Escape cancels and bounds are checked. |
| Import/metadata/task overlays are generic divs | Keyboard users can escape into background controls; focus is lost after closing | Native modal dialogs with accessible labels, background inertness, Escape priority and invoking-focus restoration. Busy import cannot be dismissed. |
| File-drop presentation did not supply complete drag/drop behavior | An apparently obvious action fails | Single-PDF drop, file-type feedback, deliberate title preservation, in-dialog error and retry without losing file/goal. |
| Search only considered the title | Readers cannot find remembered author/year/DOI combinations | Normalized, multi-field AND search with a clear empty state and reset. |
| Selected-text help implied whole-paper translation was needed first | An optional, expensive operation becomes an apparent prerequisite | Original passage remains discussable before any translation; distinguish translation, concepts and argument. |
| The landing page explained the system before the next action | Too much setup before reading one passage | Source-first copy, one primary import action, optional integrations and a disposable synthetic demo command. |
| README was an advanced operations manual with no simple front door | Visitors cannot tell which package to use or what AI backend is required | Short bilingual entrypoints; separate quickstart/workbench guides; explicit Skill vs workbench capability boundary. |
| main and release packages both said rc5 despite later source changes | Downloaded software does not match the described behavior | A new Python release version rc6; visible pre-merge caveat. Existing release artifacts remain immutable. |

The private npm workspace retains its existing internal version; the distributable Python wheel and CLI expose the release version. Dependency versions and the lockfile are unchanged in this polish pass. Playwright is a pinned developer-only dependency in the separate browser-check workflow.

## What we deliberately did not add

No new dashboard, onboarding wizard, mandatory lesson gate, full-paper translation gate, “mastery score”, cloud account, telemetry, remote font, automatic model request or synchronization grant. Plain-language help can end after the local question is answered. The Skill and compact runtime both preserve qualifiers and separate source-supported explanation from external background.

## Presentation references

Primary README references inspected for information architecture, not copied branding or screenshots:

- [Khoj](https://github.com/khoj-ai/khoj/blob/master/README.md): make the result and entry paths visible before the implementation inventory.
- [Logseq](https://github.com/logseq/logseq/blob/master/README.md): separate why/how-to-use from developer setup, and name limitations.
- [Stirling-PDF](https://github.com/Stirling-Tools/Stirling-PDF/blob/main/README.md): concise promise and quickstart, with advanced features behind documentation links.

Applied here: one reading promise, honest examples, two installation routes, optional capabilities, explicit privacy boundary, reproducible showcase and contribution instructions. No causal claim that a README creates stars.

## Remaining priorities

**P1 — actual reader trials.** Run the existing [human trial protocol](HUMAN-TRIAL.md): can readers reconstruct the key observation, mechanism and evidence without the explanation open? Measure interruptions and help needed, not message count. No learning benefit is established by this code review.

**P1 — exact Zotero attachment choice and per-note sync clarity.** Multiple PDF attachments still need a deliberate chooser before coordinate-bearing annotations are created; conflicting revisions must remain visible. This PR does not rewrite synchronization or claim universal Zotero compatibility.

**P1 — device validation.** Test Safari on macOS and a physical iPad with Pencil, text selection, split view, rotation and keyboard. Chromium viewport checks are not hardware certification. No cross-device live sync claim.

**P2 — progress semantics and recovery.** Eight dimensions can remain a coverage checklist, but must never gate a direct explanation or call partial reading failure. Continue testing behavior across model choices and long interrupted sessions; prompt wording alone is not a behavioral guarantee.

**P2 — maintainability.** Import/metadata dialogs and page navigation are now isolated. The main reading shell and coach module are still large; subsequent extraction should follow behavior boundaries with regression tests, not a wholesale UI rewrite.

## Verification boundary

See [Testing](TESTING.md) for historical integration runs. This review adds focused regression tests for page drafts, import retry, modal lifecycle, bibliographic search and a disposable demo. Actual PR CI and browser results are recorded with the PR; prior successful runs are not relabelled as this version’s evidence. No new live-model matrix or user study is implied.
