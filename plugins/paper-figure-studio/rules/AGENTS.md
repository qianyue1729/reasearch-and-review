# 顶会论文配图生成守则 (`paper-figure-studio`)

当用户在学术论文项目（含 `.tex` / `paper/`）中要求绘制或精修 Intro 动机图、Method Overview 方法架构图或机制分镜图时，遵守以下四条铁律：

1. **双交付物 PPT 优先路线（可编辑 `.pptx` + 真矢量 `.pdf`）**：
   - 除基于真实实验 CSV/JSONL 绘制的定量曲线/柱状图继续使用 `Matplotlib`（`pdf.fonttype = 42`）外，架构总览图、痛点对比图与机制分镜图默认走 `paper-figure-studio` 技能的 **`python-pptx`（OOXML 原生公式）→ `LibreOffice` 静默导出紧致裁切矢量 `.pdf` → `PyMuPDF` 渲染回看自检** 管线，同时向论文目录交付 100% 鼠标可拖拽改字的 `.pptx` 与可直接 `\includegraphics` 的真矢量 `.pdf`。

2. **AI 生图严格限缩于「局部纯视觉小素材」**：
   - 严禁调用 `image-generator` 直接生成整张方法架构图、带角标数学公式或因果连接箭头（位图模型易吞掉关键角标如 $<i$ 且不可编辑）。
   - 仅允许用 `image-generator` 生成无文字、纯白底局部插画/图标/样本 Patch，经 `ai_asset_prep.py` 自动去白底裁切后再嵌入 `.pptx` 矢量骨架。

3. **论文真值符号与 `2.0x` 缩印字号对齐**：
   - 动笔前先用 `paper_context.py` 读取目标论文的宏包版心宽度（如 ICML 双栏 `6.75in` / 单栏 `3.25in`）与 `\newcommand` 真值宏、核心公式符号，确保图内张量角标与正文 100% 逐字符一致，严禁臆造野生符号或假实验数字。
   - 采用 `2.0x` 画布缩比法则（跨双栏画布宽 `13.5in`、单栏画布宽 `6.5in`，PPT 正文字号 `14–18pt`，缩印至论文后等效 `7–9pt`），严禁灰底黑字、严禁在图内顶部重复写大标题（标题归 LaTeX `\caption`）。

4. **强制执行「渲染回看自检闭环（Render-Inspect-Fix）」**：
   - 严禁只跑完生成脚本就直接向用户交图！每次生成或修改 `.pptx` 后必须运行 `export_inspect.py`，并用 `read_file` 亲眼核验生成的 `<stem>_preview.png`、带英寸坐标尺的 `<stem>_ruler_grid.png` 与双栏原大模拟页 `<stem>_icml_mockup.png`；若机检报告 `audit_report.json` 存在文字意外折行、重叠、越界或缩印字号过小，必须修正重跑直至零硬伤通过。
