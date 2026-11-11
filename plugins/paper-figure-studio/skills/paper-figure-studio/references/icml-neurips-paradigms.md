# ICML / NeurIPS / ICLR 顶会配图构图范式与硬性规范

## 一、官方排版机检硬红线（以 `papercheck.icml.cc` 最严标准为基线）

1. **Caption 位置铁律**：`Figure` 的 `\caption` **必须在图片正下方**（`Table` 的 `\caption` 必须在表格正上方），图片与图注间距约 `0.1in`。
2. **严禁图内重复大标题**：画布顶部不要再写一行居中大号标题（如 *"Framework of XXX"*）；子分区可在底部写 `(a) ...`、`(b) ...`，总标题职责归属 `\caption{\textbf{Overview of ...}}`。
3. **严禁灰底黑字与极细线**：官方 Author Instructions 明确禁止中性灰底叠黑字（缩印与色弱阅读易糊）；底板须采用高明度低饱和语义浅色（明度 $\ge 92\%$），印刷态线条粗细 $\ge 0.5\text{pt}$（`2.0x` PPT 画布中设 `>= 1.2pt`）。
4. **色盲安全双编码**：正负/优劣对比优先使用 **蓝青（Teal `#158072` / Blue `#2563B2`）vs 珊瑚橙红（Coral `#C6423A` / Amber `#C27016`）**，并同时用符号（`✓` vs `✗`、实线 vs 虚线）双重区分，绝不仅靠纯红绿区分。
5. **标准版心尺寸速查**：
   - **ICML (`icml2025` / `icml2026`)**：双栏总宽 `\textwidth = 6.75in`，单栏宽 `\columnwidth = 3.25in`，栏距 `0.25in` → PPT 画布取 `13.5in`（跨双栏）或 `6.5in`（单栏）。
   - **NeurIPS / ICLR**：单栏宽 `\textwidth = 5.5in` → PPT 画布取 `11.0in`。
   - **CVPR / ICCV**：双栏总宽 `6.875in`，单栏宽 `3.25in` → PPT 画布取 `13.75in` 或 `6.5in`。
   - **ACL / EMNLP**：双栏总宽 `6.3in`，单栏宽 `3.03in` → PPT 画布取 `12.6in` 或 `6.1in`。
   - **ArXiv Preprint (`article`, `margin=1in`)**：正文宽 `6.5in` → PPT 画布取 `13.0in`（兼容后续一键切换 ICML `6.75in` 无需重排）。

---

## 二、四大 Oral 高命中 Method Overview 构图范式

| 论文形态 | 推荐构图范式 | 视觉核心设计点 |
|---|---|---|
| **多阶段机制 + 闭环系统**（如基准演化、RL/Agent 自博弈、MCTS） | **左机制矩阵 `(a)` + 右闭环漏斗 `(b)` + 序号锚点 `①②③④`** | 左侧画出真实输入输出矩阵与分流判据公式；右侧按 `①→②→③→④` 标清闭环演化与门控过滤，底部/顶部一条正交折线回流闭环 |
| **神经网络/生成流内部算子创新**（如 TarFlow、注意力核改造） | **宏观流水线 + 折线放大镜对齐核心公式** | 左 45% 画端到端数据块流转（`×T`），右 55% 放大单个 Block 内部张量路径，把正文核心公式原样标在汇合节点旁 |
| **在既有基座上做轻量插件/引导改造**（如 ConceptAttention） | **基线低饱和退后 + 新增通路高饱和高亮** | 原有模型主干采用浅蓝灰细线退后，仅将本文新增支路/损失项用鲜明青绿或琥珀色加粗高亮，一眼分清哪里是本文贡献 |
| **消除系统性短视/退化的新范式**（如 CollabLLM、离散扩散） | **Before vs. After 镜像对照栅格** | 左右或上下严格对齐同一组微缩玩具输入（如 3–5 个任务格或一轮真实交互），直观对比旧规则误删/崩溃 vs 新规则精准命中 |

---

## 三、标准 LaTeX 嵌入模板

```latex
\begin{figure*}[t]
  \centering
  \includegraphics[width=\textwidth]{fig_overview.pdf}
  \caption{\textbf{Overview of \textsc{MethodName}.}
  \textbf{(a)} Summarize the core mechanism and exact decision equation.
  \textbf{(b)} Trace steps \textcircled{1}--\textcircled{4} of the closed-loop pipeline, matching every symbol in \S3--\S4.}
  \label{fig:overview}
\end{figure*}
```
