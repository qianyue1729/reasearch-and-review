# `pptx_fig_kit.py` 快速 API 与原生公式速查

## 1. 最小完整骨架

```python
import sys
from pathlib import Path

KIT_DIR = r"C:\Users\wxy12\.gemini\config\plugins\paper-figure-studio\skills\paper-figure-studio\scripts"
sys.path.insert(0, KIT_DIR)

from pptx_fig_kit import FigureCanvas, PALETTE, PP_ALIGN, set_math_runs, parse_math_expr

# 13.5 x 4.8 in -> 缩印至 ICML 6.75in 双栏恰为 0.5x（14pt -> 7pt，16pt -> 8pt）
cv = FigureCanvas(width_in=13.5, height_in=4.8)

# 1) 分区底板（底部自动放 (a) / (b) 子图注，绝不在画布顶部放总标题）
cv.add_zone(
    0.20, 0.16, 6.35, 4.12,
    fill_rgb=PALETTE["zone_blue"], line_rgb=PALETTE["border_blue"],
    subcaption="(a) Directional Consensus Diagnosis",
)

# 2) 单框混排粗体标题 + 普通说明 + 原生 OOXML 上下标公式（拖拽框体时文字整体跟随！）
cv.add_rich_box(
    0.42, 1.20, 3.20, 0.92,
    fill_rgb=PALETTE["white"], line_rgb=PALETTE["teal"], line_pt=1.6,
    lines=[
        [
            {"text": "Saturated Cohort  ", "size": 14, "bold": True, "color": PALETTE["teal"]},
            {"math": r"(p_i \ge 1 - \varepsilon)", "size": 13.5, "color": PALETTE["ink"]},
        ],
        [
            {"text": "Information decays ", "size": 12.5, "color": PALETTE["ink_soft"]},
            {"math": r"(\partial I_i / \partial \delta < 0)", "size": 12.5, "color": PALETTE["teal"]},
            {"text": " → Retire", "size": 12.5, "bold": True, "color": PALETTE["teal"]},
        ],
    ],
)

# 3) 独立原生数学公式胶囊框
cv.add_math_box(
    0.42, 3.52, 5.90, 0.54,
    expr=r"R_i = a_i \cdot (\mathbb{1}[p_i \ge \tfrac{1}{2}] + \mathbb{1}[p_i < \tfrac{1}{2}]\,d_i)",
    size=14.5, fill_rgb=PALETTE["white"], line_rgb=PALETTE["border_blue"],
)

# 4) 嵌入经 ai_asset_prep.py 去白底的局部 AI 图标（自动等比居中）
cv.add_picture_fit("assets/icon_clean.png", x=0.45, y=0.32, box_w=0.68, box_h=0.68)

# 5) 闭环阅读动线序号徽章 + 直线/正交折线箭头
cv.add_step_badge(cx=0.42, cy=0.34, num=1, fill_rgb=PALETTE["navy"])
cv.add_arrow(3.62, 1.66, 4.15, 1.66, color=PALETTE["teal"], pt=2.0)
cv.add_ortho_arrow(
    [(12.80, 3.85), (12.80, 4.20), (1.10, 4.20), (1.10, 3.92)],
    color=PALETTE["navy"], pt=1.8, dashed=True,
)

cv.save("fig_overview.pptx")
```

## 2. 支持的 LaTeX-lite 原生数学语法（`parse_math_expr`）

- **上下标**：`x_i`、`z_{<i}^t`、`p_{\mathrm{fut}}`、`\alpha_i^3`（自动转为 `Cambria Math` + OOXML `baseline="-25000"` / `"32000"` 原生可编辑文本段）。
- **希腊字母与花体**：`\alpha \beta \gamma \delta \varepsilon \theta \lambda \mu \pi \rho \sigma \tau \Delta \Sigma \Omega`、`\mathbb{1}`、`\mathcal{P} \mathcal{R} \mathcal{C} \mathcal{D} \mathcal{F}`。
- **重音修饰**：`\tilde{z}`（`z̃`）、`\hat{y}`（`ŷ`）、`\bar{p}`（`p̄`）。
- **关系与算子**：`\le \ge \ne \approx \equiv \sim \cdot \odot \oplus \times \pm \to \mapsto \Rightarrow \cap \cup \emptyset \in \notin \subseteq \partial \sum \checkmark \timesmark`。
- **正体函数与短词**：`\mathrm{CoRe}`、`\text{audit}`，以及 `exp, log, max, min, iff` 自动正体，单字母变量自动斜体。
