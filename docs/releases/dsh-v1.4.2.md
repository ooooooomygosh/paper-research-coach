# DSH 1.4.2 · 修复裁剪文字导致的译本叠字

- 翻译前检查被矩形裁剪隐藏的文字。确认文字完全位于裁剪区域外、且页面渲染一致后，从临时输入中移除相应文字，保留原 PDF 和图表。
- PDF 排版会合并同一行里被拆开的邮箱，避免作者简介首行重叠。
- 生成译本后，核对页数并检测大面积文字重叠。已有译本在后台检查。受影响的任务会显示「重建译本」，可以生成独立的新版本。
- 1.4.1 的 Zotero 主题筛选可在论文栏与批量翻译中切换。「讲解当前页」与选中文字后的讲解入口支持返回源 PDF。

macOS Apple silicon 可通过「Zotero 与设置 → 版本与更新」暂存新版，然后完全退出并重开 Harness。也可下载并解压 `PRC-DSH-1.4.2-mac.zip` 后运行 `安装.command`。 [安装与恢复](../DEEPSEEK_HARNESS.md)

## English

- Translation prepares a temporary PDF after verifying that fully clipped text does not contribute to the rendered page.
- Email addresses split across blocks on the same line are joined before typesetting.
- Before a translation is available, DSH checks page counts and looks for sustained text overlap. A saved translation flagged by the background check can be rebuilt as a separate rendition.
- Topic filters and interactive explanation entry points from 1.4.1 are included.

This release provides a macOS Apple silicon package and an update through Harness Settings. [Installation and recovery](../DEEPSEEK_HARNESS.md#english)
