# Reproducible reading showcase

The showcase is the actual built workbench, not a marketing mockup. The paper, values and notes are synthetic. Any conversation injected by the capture script is labelled **预设带读示例 · 非实时模型回复** in the UI. It is not evidence of model quality or learning benefit.

## Try the interface

After installing this version, run `prc-demo`. It creates an isolated temporary library and a searchable three-page teaching paper. No model call or Zotero connection is initiated automatically. Use a local question, inspect the equal-budget comparison, and return to the source from the sample note. This ordinary demo does not inject an AI answer.

## Reproduce screenshots and browser checks

Build and install the source as described in [Quick start](QUICKSTART.md), then:

```bash
python -m pip install 'playwright==1.58.0'
python -m playwright install chromium
python scripts/capture_showcase.py --output showcase
```

The separate `Reading browser checks` workflow performs these checks on Ubuntu and uploads the PNGs as `reading-showcase`. The script starts its own loopback server and temporary store, blocks actual coach connection by returning an unavailable status, and seeds an explicitly scripted exchange. The empty-library screenshot uses an empty state API fixture; the UI rendering is unchanged. It does not use or upload a personal library.

Checks cover page-number draft cancellation, native modal keyboard containment, Escape order and invoking-focus restoration, desktop layout and narrow-viewport horizontal overflow. Browser JavaScript errors cause failure. Viewport sizes are 1440 × 1000 and 390 × 844; a narrow Chromium viewport is not a tested iPad or Pencil device.

Use screenshots without browser chrome, URLs, launch tokens or private paths. Keep captions beside the images explaining synthetic source and scripted dialogue. Do not alter the UI to hide unavailable model connections or invent completed learning outcomes. The source fixture itself also labels invented values and missing experimental evidence.
