# 顶会论文视图工坊 (`paper-figure-studio`)

面向 **ICML / NeurIPS / ICLR / CVPR / ACL** 等顶尖学术会议论文项目的端到端配图插件。无需安装任何额外三方服务，基于本机 `python-pptx` + `LibreOffice` + `PyMuPDF (fitz)` + `image-generator` 子代理，在任意论文项目下一键直出 **100% 原生可编辑 PowerPoint 源文件（`.pptx`）** 与 **零白边真矢量论文配图（`.pdf`）**。

## 核心管线

1. **论文真值上下文提取（`paper_context.py`）**：自动扫描论文目录内的 `main.tex`、`sections/*.tex` 与 `macros.tex`，识别会议宏包版心宽度（`icml` / `neurips` / `iclr` / `acl` / `article`）、提取 `\newcommand` 定量宏与正文核心公式，杜绝符号漂移。
2. **AI 局部小素材抠图精修（`ai_asset_prep.py`）**：将 `image-generator` 生成的纯白底局部插画/图标自动洪泛抠除白底转为 RGBA 透明通道、紧致裁切并按圆角或高清尺寸归一化，绝不让位图模型触碰数学公式和箭头连接。
3. **OOXML 原生数学与高审美矢量绘图库（`pptx_fig_kit.py`）**：清除 Office 默认阴影，遵循 `2.0x` 印刷缩比法则，内置 LaTeX-lite 数学解析器（自动转换为 `Cambria Math` + OOXML `baseline` 原生上下标，PowerPoint/WPS 双击可改字）、色盲友好学术调色板、序号锚点 `①②③④`、正交折线跳连与矩阵热力格。
4. **渲染回看与六项排版机检闭环（`export_inspect.py`）**：使用独立临时 Profile 调用 `soffice --headless` 转矢量 PDF（不受桌面已打开窗口干扰），矢量级紧致裁切白边，自动检测文字折行、重叠、缩印字号 `<6pt`、灰底黑字与图内冗余标题，并同步输出英寸坐标尺诊断图与双栏论文原大模拟图供视觉复核。
