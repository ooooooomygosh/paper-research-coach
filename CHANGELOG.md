# Changelog

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
