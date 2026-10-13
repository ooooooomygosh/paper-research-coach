"""Draw the README's reading-loop diagrams and the repository's social preview.

    python scripts/readme_art.py                 # loop diagrams (SVG, zh/en, light/dark)
    python scripts/readme_art.py --social        # also docs/images/social-preview.png (needs Playwright + Chromium)

Everything is drawn from text here: no external fonts, scripts or images in the SVGs.
"""
from __future__ import annotations

import argparse
import base64
import os
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
IMAGES = ROOT / "docs" / "images"
FONT = "-apple-system, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans CJK SC', sans-serif"
THEMES = {
    "light": {"bg": "#fbfbf7", "card": "#ffffff", "line": "#d6e2cc", "ink": "#203229", "soft": "#5b6f63", "accent": "#365c47", "mark": "#4f8cc9", "chip": "#eef4ea"},
    "dark": {"bg": "#141a16", "card": "#1d2620", "line": "#34443a", "ink": "#e7efe8", "soft": "#a9bbad", "accent": "#9fcaa9", "mark": "#7fb2e5", "chip": "#24302a"},
}
STEPS = {
    "zh": [("看原文", "PDF 翻到那一页", "要看的句子标上 ①②③"),
           ("做一件事", "猜一猜，或答一句", "预测题一键作答"),
           ("对照证据", "教练核对你的话", "需要时给一张小图"),
           ("留下收获", "一句你自己的话", "八句连起来就是复盘")],
    "en": [("See the source", "the PDF turns to the page", "sentences numbered ①②③"),
           ("Do one thing", "predict or answer", "one-tap choices"),
           ("Check the evidence", "the coach checks your words", "a small figure if it helps"),
           ("Keep a takeaway", "one sentence, yours", "eight make your review")],
}
LOOP = {"zh": "下一件事马上出现 · 不用停下来想“接下来做什么”", "en": "the next task appears at once, so you keep reading"}


def loop_svg(lang: str, theme: str) -> str:
    c = THEMES[theme]
    w, h, card_w, card_h, gap, top = 1000, 236, 222, 132, 26, 28
    title_size = 17 if lang == "zh" else 16
    left = (w - (4 * card_w + 3 * gap)) / 2
    parts = [
        (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" '
        f'aria-label="{escape(" → ".join(s[0] for s in STEPS[lang]))}">'),
        f'<rect width="{w}" height="{h}" rx="18" fill="{c["bg"]}"/>',
        (f'<defs><marker id="a" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        f'<path d="M0 0L10 5L0 10z" fill="{c["accent"]}"/></marker></defs>'),
    ]
    for i, (title, line1, line2) in enumerate(STEPS[lang]):
        x = left + i * (card_w + gap)
        parts += [
            f'<rect x="{x}" y="{top}" width="{card_w}" height="{card_h}" rx="14" fill="{c["card"]}" stroke="{c["line"]}" stroke-width="1.5"/>',
            f'<circle cx="{x + 30}" cy="{top + 32}" r="14" fill="{c["mark"] if i == 0 else c["accent"]}"/>',
            f'<text x="{x + 30}" y="{top + 37}" text-anchor="middle" font-family="{FONT}" font-size="14" font-weight="700" fill="{c["bg"]}">{i + 1}</text>',
            f'<text x="{x + 52}" y="{top + 38}" font-family="{FONT}" font-size="{title_size}" font-weight="700" fill="{c["ink"]}">{escape(title)}</text>',
            f'<text x="{x + 18}" y="{top + 78}" font-family="{FONT}" font-size="14" fill="{c["ink"]}">{escape(line1)}</text>',
            f'<text x="{x + 18}" y="{top + 104}" font-family="{FONT}" font-size="12.5" fill="{c["soft"]}">{escape(line2)}</text>',
        ]
        if i < 3:
            parts.append(f'<line x1="{x + card_w + 4}" y1="{top + card_h / 2}" x2="{x + card_w + gap - 6}" y2="{top + card_h / 2}" '
                         f'stroke="{c["accent"]}" stroke-width="2" marker-end="url(#a)"/>')
    # The loop back from the last card to the first.
    x_last = left + 3 * (card_w + gap) + card_w / 2
    x_first = left + card_w / 2
    y0, y1 = top + card_h + 4, top + card_h + 40
    parts += [
        (f'<path d="M{x_last} {y0} V{y1 - 10} Q{x_last} {y1} {x_last - 10} {y1} H{x_first + 10} Q{x_first} {y1} {x_first} {y1 - 10} V{y0 + 6}" '
        f'fill="none" stroke="{c["accent"]}" stroke-width="2" stroke-dasharray="5 5" marker-end="url(#a)"/>'),
        f'<rect x="{w / 2 - 230}" y="{y1 - 13}" width="460" height="26" rx="13" fill="{c["chip"]}"/>',
        f'<text x="{w / 2}" y="{y1 + 5}" text-anchor="middle" font-family="{FONT}" font-size="13.5" fill="{c["ink"]}">{escape(LOOP[lang])}</text>',
        "</svg>",
    ]
    return "\n".join(parts) + "\n"


def write_loops() -> list[Path]:
    written = []
    for lang in ("zh", "en"):
        for theme in ("light", "dark"):
            name = "loop" + ("" if lang == "zh" else "-en") + ("" if theme == "light" else "-dark") + ".svg"
            path = IMAGES / name
            path.write_text(loop_svg(lang, theme), encoding="utf-8")
            written.append(path)
    return written


def social_html() -> str:
    logo = (IMAGES / "logo.svg").read_text(encoding="utf-8")
    shot = base64.b64encode((IMAGES / "mainline.webp").read_bytes()).decode()
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
  html, body {{ margin: 0; width: 1280px; height: 640px; overflow: hidden; }}
  body {{ background: linear-gradient(135deg, #2d4d3b 0%, #365c47 55%, #4f7a5f 100%); font-family: {FONT}; color: #fbfbf7; }}
  .text {{ position: absolute; left: 72px; top: 92px; width: 520px; }}
  .logo svg {{ width: 96px; height: 96px; border-radius: 24px; box-shadow: 0 8px 28px #0003; }}
  h1 {{ margin: 28px 0 10px; font-size: 54px; letter-spacing: -.01em; line-height: 1.05; }}
  .zh {{ font-size: 30px; font-weight: 700; margin: 0 0 10px; color: #f3f7ef; }}
  .en {{ font-size: 21px; margin: 0 0 30px; color: #d6e2cc; }}
  .chips span {{ display: inline-block; margin: 0 8px 10px 0; padding: 7px 14px; border-radius: 999px; background: #ffffff1f; font-size: 17px; }}
  .shot {{ position: absolute; right: -40px; top: 70px; width: 700px; border-radius: 16px; box-shadow: 0 18px 50px #0006; transform: rotate(-2deg); }}
</style></head><body>
  <div class="text">
    <div class="logo">{logo}</div>
    <h1>Paper Research Coach</h1>
    <p class="zh">不止读懂论文，形成自己的研究判断</p>
    <p class="en">A source-grounded paper-reading coach: open the PDF, do one small task at a time, keep your own judgment.</p>
    <div class="chips"><span>翻到原文 · 标出句子</span><span>一次一个小任务</span><span>本地 PDF 工作台 + Skill</span></div>
  </div>
  <img class="shot" src="data:image/webp;base64,{shot}" alt="">
</body></html>"""


def write_social(chromium: str | None) -> Path:
    from playwright.sync_api import sync_playwright

    out = IMAGES / "social-preview.png"
    with sync_playwright() as p:
        options = {"args": ["--disable-gpu"]}
        if chromium:
            options["executable_path"] = chromium
        browser = p.chromium.launch(**options)
        page = browser.new_page(viewport={"width": 1280, "height": 640}, device_scale_factor=1)
        page.set_content(social_html(), wait_until="load")
        page.wait_for_timeout(300)
        page.screenshot(path=str(out))
        browser.close()
    return out


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--social", action="store_true")
    cli.add_argument("--chromium", default=os.environ.get("CHROMIUM_PATH"))
    args = cli.parse_args()
    for path in write_loops():
        print(path.relative_to(ROOT))
    if args.social:
        print(write_social(args.chromium).relative_to(ROOT))


if __name__ == "__main__":
    main()
