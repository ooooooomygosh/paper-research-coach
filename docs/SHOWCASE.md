# Reproducible reading showcase

![Actual reading workbench with synthetic material and explicitly scripted dialogue](images/reading.webp)

The showcase is the actual built workbench, not a marketing mockup. The paper, values and notes are synthetic. Any conversation injected by the capture script is labelled **预设带读示例 · 非实时模型回复** in the UI. It is not evidence of model quality or learning benefit.

The committed WebPs are 1440-pixel-wide copies of the desktop captures: `reading.webp`, its dark-theme twin `reading-dark.webp` (the README picks one with `<picture>`), `welcome.webp` and `annotations.webp` from the PDF annotation check. Full-size desktop, welcome, import-dialog and narrow-viewport PNGs are available in the `reading-showcase` artifact of [Reading browser checks](https://github.com/ooooooomygosh/paper-research-coach/actions/workflows/showcase.yml), retained for 14 days. The script below recreates them after artifact expiry.

## First reading

![Welcome screen from the same built workbench](images/welcome.webp)

## Try the interface

After installing this version, run `prc-demo`. It creates an isolated temporary library and a searchable three-page teaching paper. No model call or Zotero connection is initiated automatically. Use a local question, inspect the equal-budget comparison, and return to the source from the sample note. This ordinary demo does not inject an AI answer.

## Reproduce screenshots and browser checks

Build and install the source as described in [Quick start](QUICKSTART.md), then:

```bash
python -m pip install 'playwright==1.58.0'
python -m playwright install chromium
python scripts/capture_showcase.py --output showcase
```

Headless capture uses software rendering to avoid black PDF screenshots on macOS GPUs.

The separate `Reading browser checks` workflow performs these checks on Ubuntu and uploads the PNGs as `reading-showcase`. The script starts its own loopback server and temporary store, blocks actual coach connection by returning an unavailable status, and seeds an explicitly scripted exchange. The empty-library screenshot uses an empty state API fixture; the UI rendering is unchanged. It does not use or upload a personal library.

Checks cover actual PDF text selection and its original-text popover, CSP violations, black PDF capture detection, keyboard split adjustment, reduced motion, direct touch immersion exit, page-number draft cancellation, native modal keyboard containment, Escape order and invoking-focus restoration, desktop layout and narrow-viewport horizontal overflow. Browser JavaScript errors cause failure. Viewport sizes are 1440 × 1000 and 390 × 844; a narrow Chromium viewport is not a tested iPad or Pencil device.

Use screenshots without browser chrome, URLs, launch tokens or private paths. Keep captions beside the images explaining synthetic source and scripted dialogue. Do not alter the UI to hide unavailable model connections or invent completed learning outcomes. The source fixture itself also labels invented values and missing experimental evidence.

## PDF interaction regression checks

The same browser workflow runs `check_pdf_controls.py`: trackpad pinch around a stable focal point, actual Chromium multi-touch input, independent notes in mono/dual layouts, refresh persistence, and native annotations in the downloaded PDF. Translation layout fixtures duplicate synthetic English content to test coordinate separation; they are not model-generated bilingual examples. Browser artifacts include the layout-test screenshots. Safari event handling is implemented; these checks do not certify physical Safari/iPad hardware.
