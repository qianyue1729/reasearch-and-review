# 顶会论文盲审自进化工坊 (`paper-review-evolve`)

> **源码与完整图文案例库**：[https://github.com/qianyue1729/reasearch-and-review](https://github.com/qianyue1729/reasearch-and-review)

将顶会学术论文（IEEE S&P / CCS / USENIX Security / NDSS / ICML / NeurIPS / ICLR / ACL / OSDI 等）从初稿打磨至 Oral 级定稿的**多轮独立盲审自进化方法论**固化为可复用的自动化闭环。

![五轮零上下文三视角 PC 盲审评分收敛与反臃肿核验轨迹](assets/showcase/showcase_review_convergence.png)

![ICML 2025 顶会论文插图端到端复刻总览对比](assets/showcase/showcase_icml25_figure_reproduction.png)

## 核心哲学：六大支柱

1. **零上下文独立盲审隔离（Zero-Context Blind Isolation）**
   - 严禁由刚写完正文的作者主会话自己给自己打分（避免证实偏差与分数虚高）。
   - 每一轮盲审必须派生全新的只读 `research` 子代理，仅投喂编译后的匿名产物（`main.pdf`、`main.tex`、实验结果 JSON 与审稿包），完全屏蔽历史对话、前序轮次得分与修改过程。
2. **三正交 PC 人设 + 近两年顶会真标杆锚定（Orthogonal Personas & Exemplar Grounding）**
   - 启动盲审前先检索目标顶会近两年的同方向标杆论文（Exemplars），提取其模型规模、实验矩阵、形式化定理深度与威胁模型标准。
   - 每轮并发启动 **3 位视角正交的 PC 审稿人**（如「理论/形式化证明审稿人」「系统架构与复现审计审稿人」「实验泛化与统计严谨度审稿人」），全方位暴露短板。
3. **重证据轻话术与「云端/Colab 优先」算力策略（Evidence Over Rhetoric & Cloud-First Compute）**
   - 将审稿意见严格拆解为三类：
     - **A 类（实证/规模短板）**：如模型太小（Toy Model）、缺少 OOD 基准、缺少真实系统端到端计时。必须**优先通过云端/Colab 算力（或已有真实实验日志）补齐现代旗舰级实验**，绝不阻塞或压垮本地机器，也绝不用辩解话术掩盖实证缺失。
     - **B 类（理论/数学严谨性短板）**：本地补齐完整二阶/信息论/密码学定理证明与界值核验。
     - **C 类（诚实边界说明）**：在 Discussion / Threat Model 中坦诚界定适用范围，杜绝夸大声明（Overclaiming）。
4. **单源真值与机检棘轮（Single-Source Truth & Audit Ratchet）**
   - 强制遵循 `真实实验 JSON -> 资产生成脚本 (make_assets.py) -> LaTeX 宏/表格 -> 编译并脱敏 (compile_and_scrub) -> 确定性机检 (review_cli.py audit)` 流水线。
   - 任何一轮盲审发出前，必须确保机检 **0 违例**（无孤立假数字、无 `\resizebox{\columnwidth}` 字号崩坏、无未定义引用、`Overfull \hbox <= 8.0pt`、PDF 元数据与时区完全擦除）。
5. **单调收敛判据（Monotonic Convergence Gate）**
   - 通过 `review_ledger.json` 记录每轮 3 位审稿人的评分、Major/Minor 数量与修复映射。
   - 仅当 **① 3 位审稿人全部给出正向录用评分（Accept 区间）、② 0 个阻断性 Major 缺陷、③ 连续两轮均分变化 `|Δ| < 0.3`** 时，判定盲审收敛。
6. **终轮反臃肿瘦身与视觉/Oral 闭环（Final De-Bloating & Oral Package）**
   - 破除多轮补丁造成的「防御性堆砌（Defensive Bloat）」：
     - **摘要瘦身**：严格控制在 **150–220 词**，用连贯学术叙事替代罗列式参数报菜名。
     - **表格旗舰优先**：所有多模型/多配置表格以 **目标核心对象（Target Model）为第一列，并按最大旗舰规模（如 70B → 4B）降序排列**，杜绝小辅助模型喧宾夺主。
     - **配图与 Oral 交付**：联动 `paper-figure-studio` 检查首屏 Teaser 图与方法架构图（`.pptx` + `.pdf` 双交付），并支持一键导出 300 DPI 高清图表与中文 Oral 演讲指南 Markdown。

## 内置工具 (`review_cli.py`)

- `init`：初始化 `<project>/.scratch/paper-review-evolve/review_ledger.json` 与顶会配置。
- `prompts`：生成第 `k` 轮的 3 份零上下文正交 PC 盲审 Prompt。
- `audit`：执行正文/PDF/日志确定性机检（摘要词数、页数红线、`Overfull \hbox`、残留旧标签、PDF 匿名元数据擦除）。
- `record`：录入第 `k` 轮三位审稿人打分与缺陷统计，自动计算是否达到收敛判据并更新 `REVIEW_REPORT.md`。
- `debloat-check`：执行定稿前的反臃肿可读性检查（摘要词数、表格首列与行序检查、配图清单与 Oral 文档完备度）。
