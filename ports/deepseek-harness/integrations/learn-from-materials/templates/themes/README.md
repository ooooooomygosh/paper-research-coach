# 主题作用域规范

`render_page.py` 固定内联本目录的三个兼容主题文件（列表见 `render_page.py::THEMES`），组件样式之后依次内联 `templates/visual-finish.css` 和 `templates/liquid-finish.css`。最后一层定义液态表面及主题专属变量；旧 ID 保持稳定以便已有页面数据和本地选择继续工作。每个主题变量都要以 `body[data-theme="主题名"]` 限定作用域。

| 主题名 | 中文名 | 文件 |
|---|---|---|
| `warm-paper` | 海盐云纱 | `warm-paper.css` → `visual-finish.css` → `liquid-finish.css` |
| `minimal` | 黑白水墨 | `minimal.css` → `visual-finish.css` → `liquid-finish.css` |
| `dark` | 竹月清 | `dark.css` → `visual-finish.css` → `liquid-finish.css` |

配色由主题作用域中的 `--liquid-*`、`--ink`、`--surface*`、`--hero-accent` 和 `--dg-*` 等变量共同负责；共享玻璃表面读取变量，不能用固定色覆盖全部主题。海盐保留蓝白与淡黄点缀；水墨以白纸、灰黑笔触、飞白和纸纹为主，只在局部使用深墨；竹月保留绿、暖白与茶金。调深主色时同时检查正文、连线、浮片和高光，避免颜色被透明白层冲淡，也避免把水墨整页涂黑。

更新主题时同时检查最终 CSS、`base.html` 菜单、英文界面词条、`render_page.py::THEMES`、`verify_static.py::THEMES` 和 `verify-page.js::knownThemes`。`dark` 现为历史存储 ID，竹月清整体采用明亮纸面；深色局部卡片仍需浅色文字。
运行 `verify_static.py`，确认每个主题作用域和菜单项都存在。

> **坑位**：`verify-page.js` 的 `knownThemes` 曾列出 6 个主题（`ink-wash` / `vintage-editorial` / `paper-ink` 并不存在），
> 导致它在 `selectOption` 上 30s 超时、报「测试异常」。静态校验（以 `THEMES` 为准）反而是对的。
> 任何新增/删减主题，都要以 `render_page.py::THEMES` 为基准同步所有消费方。
