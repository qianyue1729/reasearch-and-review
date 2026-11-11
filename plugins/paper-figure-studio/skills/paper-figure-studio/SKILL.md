---
name: paper-figure-studio
description: >-
  Generates ICML/NeurIPS/ICLR/ACL Oral-grade academic paper figures end-to-end inside any paper project
  using the verified Editable PPTX + Localized AI Micro-Asset + Render-Inspect-Fix closed-loop pipeline.
  Produces both a 100% mouse-editable PowerPoint file (.pptx with native OOXML math subscripts/superscripts)
  and a tight-cropped publication vector PDF (.pdf ready for \includegraphics). Use whenever the user asks
  to draw, design, upgrade, or export an Intro figure, Teaser, Method Overview, system architecture diagram,
  or conceptual mechanism figure for a research paper.
---

# 顶会论文视图直出工坊 (`paper-figure-studio`)

在任意学术论文项目下直出达到 **ICML / NeurIPS / ICLR Oral** 水准的配图，同时交付：
1. **100% 原生可编辑 `.pptx`**（PowerPoint / WPS 打开即可鼠标拖拽每个框、箭头、局部图标并双击修改 OOXML 上下标公式）；
2. **紧致裁切真矢量 `.pdf`**（零多余白边，直接 `\includegraphics[width=\textwidth]{...}` 嵌入 LaTeX，放大 800% 锐利无损）。

---

## 核心组件路径

设 `<SCRIPTS>` 为 `C:/Users/wxy12/.gemini/config/plugins/paper-figure-studio/skills/paper-figure-studio/scripts`：
- **论文真值与版心扫描器**：[paper_context.py](./scripts/paper_context.py)
- **AI 局部小素材抠图精修器**：[ai_asset_prep.py](./scripts/ai_asset_prep.py)
- **原生 PPTX + OOXML 公式绘图 SDK**：[pptx_fig_kit.py](./scripts/pptx_fig_kit.py)（API 速查见 [pptx-kit-api.md](./references/pptx-kit-api.md)）
- **矢量导出 + 六项机检 + 三图回看闭环引擎**：[export_inspect.py](./scripts/export_inspect.py)
- **顶会构图范式与 LaTeX 版位规范**：[icml-neurips-paradigms.md](./references/icml-neurips-paradigms.md)

---

## 标准五步执行工作流（不可跳步）

### Step 1：扫描论文项目真值与版心（杜绝野生符号与错误宽高比）

在目标论文目录运行：
```powershell
python "C:/Users/wxy12/.gemini/config/plugins/paper-figure-studio/skills/paper-figure-studio/scripts/paper_context.py" `
  --project-dir "<论文项目路径>"
```
核对三项真值：
1. **目标版心与 `2.0x` 画布缩比法则**：
   - 跨双栏 `figure*`（如 ICML `6.75in` / `article` `6.5in` / NeurIPS `5.5in`）→ PPT 画布宽度取 **`2 × textwidth`**（如 `13.5in` 或 `13.0in`，高 `4.4–5.4in`），正文字号用 **`13.5–17pt`**（缩印 50% 后恰为黄金 `6.8–8.5pt`），线条宽度 **`>= 1.3pt`**（缩印后 `>= 0.65pt`）。
   - 单栏 `figure`（如 ICML `3.25in`）→ PPT 画布宽取 **`6.5in`**，同样严格保持 `0.5x` 缩印比例。
2. **逐字符对齐正文公式与 `\newcommand` 宏**：图上出现的张量角标、阈值参数、核心指标百分比必须 100% 取自 `main.tex` / `macros.tex`，严禁编造野生符号。
3. **选择高命中构图范式**（详见 [icml-neurips-paradigms.md](./references/icml-neurips-paradigms.md)）：拒绝画成空洞的“组织架构连线框”——必须画出**具体数据/矩阵形态**、**基线退后 vs 本文高亮**，或带 **`1→2→3→4` 序号锚点**的故事板分区 `(a)` / `(b)`。

---

### Step 2：调用 `image-generator` 生成局部纯视觉小素材 + 自动抠除白底

> **严禁让 AI 位图模型直接画整张架构图、数学公式或连接箭头！** 只用 `image-generator` 子代理生成 1–3 个局部纯视觉小插画（如多智能体几何徽章、输入图像 Patch、沙盒盾牌图标、代码审查放大镜）。

1. 向 `image-generator` 下发提示词时强制附加约束：
   `pure solid #FFFFFF white background, flat minimal academic vector style, generous margin, NO text, NO letters, NO numbers, NO arrows, NO drop shadows`
2. 收到原始位图后，运行 `ai_asset_prep.py` 洪泛剥离白底转为 RGBA 透明背景并紧致裁切（避免贴入浅色底板时露出难看的白方块）：
```powershell
python "C:/Users/wxy12/.gemini/config/plugins/paper-figure-studio/skills/paper-figure-studio/scripts/ai_asset_prep.py" `
  --input "<raw_icon.jpg>" `
  --output "<scratch_dir>/assets/icon_clean.png" `
  --tol 30 --pad 8 --max-px 480
```
（若素材本身是矩形照片或噪声 Patch，加 `--keep-bg --rounded 20` 保留画面并切圆角。）

---

### Step 3：基于 `pptx_fig_kit.py` 编写可复跑绘图脚本产出 `.pptx`

在当前会话 `scratch/`（或论文项目的 `scripts/`）下编写构建脚本，引入 `pptx_fig_kit`（详细方法签名见 [pptx-kit-api.md](./references/pptx-kit-api.md)）：
```python
import sys
sys.path.insert(0, r"C:\Users\wxy12\.gemini\config\plugins\paper-figure-studio\skills\paper-figure-studio\scripts")
from pptx_fig_kit import FigureCanvas, PALETTE, PP_ALIGN
```
编写要点：
- **单对象富文本优先**：尽量用 `canvas.add_rich_box(...)` 在同一个圆角框的 `text_frame` 内混排粗体小标题、说明短句与 `{"math": r"p_i \ge 1 - \varepsilon"}` 原生公式，使人类后续在 PowerPoint 里拖动框体时文字整体跟随。
- **短标签禁自动折行**：圆形节点、胶囊徽章、箭头旁短注一律保持 `wrap=False`，防止 `0.8` 或 `98.8%` 被挤成两行。
- **遵循顶会红线**：**不在画布顶部写全图大标题**（留给 LaTeX `\caption`）；**不用中性灰底配黑字**（统一用 `PALETTE["zone_blue" | "zone_mint" | "zone_amber" | "zone_coral" | "zone_lavender"]` 高明度浅色底板）。

---

### Step 4：强制执行「渲染回看自检闭环（Render-Inspect-Fix）」

运行一键导出与机检命令：
```powershell
python "C:/Users/wxy12/.gemini/config/plugins/paper-figure-studio/skills/paper-figure-studio/scripts/export_inspect.py" `
  --pptx "<论文目录>/fig_overview.pptx" `
  --out-pdf "<论文目录>/fig_overview.pdf" `
  --inspect-dir "<scratch_dir>/inspect_r1" `
  --target-width-in 6.75
```
随后**必须执行两层检验**：
1. **第一层（确定性机检 JSON）**：核查终端输出的 `overall` 与 `C1`–`C6` 六项检查（矢量路径完整性、缩印字号 `>=6pt`、零意外折行、零文本框重叠、零灰底黑字、无冗余顶标题）。任何 `FAIL` 必须立即修脚本重跑。
2. **第二层（Agent 视觉真机回看）**：用 `read_file` 同时打开：
   - `<stem>_preview.png`（300 DPI 高清成图，检查箭头指向、视觉重心、图标融合度、上下标基线）；
   - `<stem>_ruler_grid.png`（带 `0.5"` 英寸坐标尺与红框告警，直接读尺微调 `(x, y, w, h)` 坐标，无需盲猜）；
   - `<stem>_icml_mockup.png`（100% 印刷比例双栏论文模拟页，确认缩印到真实页面宽度后字号依然清晰利落）。

**至少完成 1 次回看微调（若首轮有瑕疵则修至全绿 `PASS` 且视觉无可挑剔）后，才允许进入 Step 5 交付！**

---

### Step 5：落盘论文项目并交付 LaTeX 挂载片段

1. 将最终版 `<fig_name>.pptx` 与 `<fig_name>.pdf` 保存到目标论文项目的 `paper/`（或 `paper/figures/`）目录下。
2. 若用户要求直接接入正文，同步更新对应 `.tex` 中的 `\includegraphics` 并编译验证零报错；若用户仅要求直出配图，给出可直接粘贴的 `figure*` / `figure` LaTeX 代码块（Caption 在图下方，粗体首句点明核心机制结论）。
