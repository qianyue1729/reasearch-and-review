# 顶会审稿规范与三正交 PC 人设参考 (`venue_profiles.md`)

本参考手册定义了主流计算机顶会的版面红线、评分制式、**三正交 PC 审稿人视角（3 Orthogonal Personas）**以及高频一票否决雷区，供 `review_cli.py` 与盲审子代理调用。

---

## 1. 安全四大顶会 (`sp` / `ccs` / `usenix` / `ndss`)

### 1.1 版面与格式红线
- **IEEE S&P (`sp`)**：正文上限 **13 页**（不含 Ethics Considerations、References 与 Appendices），总页数上限 **18 页**（或按当年 CFP 规定）；双栏 `IEEEtran` (`\documentclass[conference,compsoc]{IEEEtran}`)。
- **ACM CCS (`ccs`)**：正文上限 **12 页**（不含伦理声明、参考文献与附录），双栏 `acmart` (`\documentclass[sigconf,anonymous,review]{acmart}`)。
- **USENIX Security (`usenix`)**：正文上限 **13 页**（不含伦理声明、开放科学声明、参考文献与附录），双栏 `usenix`。
- **摘要词数红线**：**150–220 词**（超过 250 词判定为冗余臃肿，必须精简）。

### 1.2 评分体系（1–5 分制或 1–10 分制，默认 5 分制）
- `5.0`: Strong Accept (Top 1–3%, Oral / Distinguished Paper 水准)
- `4.0`: Accept (明显高于录用线，3 位审稿人收敛目标 `>= 4.0`)
- `3.0`: Weak Accept / Borderline (存在未解疑虑或实证缺口)
- `2.0`: Weak Reject (存在明显实验或假设硬伤)
- `1.0`: Reject / Strong Reject (威胁模型不成立或实证严重不足)

### 1.3 三正交 PC 审稿人视角
1. **Persona A — 密码学/形式化安全与协议审稿人 (`Crypto & Formal Security PC`)**
   - **关注焦点**：威胁模型（半诚实 vs. 恶意对手）是否自洽、密码学原语（FHE/MPC/ZK/TEE）的参数与电路深度是否真实、数学定理/界值是否严密、是否存在协议层信息泄露或与标准安全定义的冲突。
   - **典型刁难**：「你的防御是否破坏了原有的密码学安全可组合性？」「参数 $N, \Delta, L$ 下真实的乘法深度与 Bootstrap 开销是多少，还是仅仅用明文模拟替代了密文执行？」
2. **Persona B — 侧信道/隐私量化与统计严谨度审稿人 (`Side-Channel, Privacy & Statistical Rigor PC`)**
   - **关注焦点**：攻击/防御在信息论或差分隐私（DP / Rényi DP / MI）下的严格界、非渐近有限样本置信区间、多次独立随机种子方差、自适应攻击者（Adaptive Adversary）对防御的反制。
   - **典型刁难**：「如果攻击者知道你的防御参数并重新训练自适应分类器，防御还会生效吗？」「信息泄露上限是渐近近似还是有限样本精确界？」
3. **Persona C — 大模型系统/真实基准与复现审计审稿人 (`LLM Systems & Artifact Audit PC`)**
   - **关注焦点**：目标模型规模是否达到当代顶会工业级水准（如 `7B–70B`，拒绝只跑 `0.5B–1.5B` 玩具模型）、跨架构/跨词表与分布外（OOD）泛化表现、图表与正文及代码 JSON 真值是否 100% 吻合、表格排版与首列逻辑是否清晰。
   - **典型刁难**：「为什么表格里全是 1.5B 的小模型？在 32B/70B 生产级大模型上结论还成立吗？」「我核对了你的脚本和正文宏，某处数字是否有硬编码不一致？」

---

## 2. 机器学习三大会 (`icml` / `neurips` / `iclr`)

### 2.1 版面与格式红线
- **ICML (`icml`)**：正文 **8 页**（或按当年 CFP 9 页），参考文献与附录不限页数；必须包含 `Impact Statement`。
- **NeurIPS (`neurips`)**：正文 **9 页**，参考文献、附录与 `NeurIPS Paper Checklist` 不计入正文页数。
- **ICLR (`iclr`)**：正文建议 **9–10 页**（硬上限按当年要求）。
- **摘要词数红线**：**150–220 词**。

### 2.2 评分体系（1–10 分制）
- `8–10`: Strong Accept / Oral / Spotlight (`>= 7.5` 为强收敛目标)
- `6–7`: Weak Accept / Accept (`>= 6.5` 为基础录用收敛线)
- `5`: Borderline
- `1–4`: Reject

### 2.3 三正交 PC 审稿人视角
1. **Persona A — 理论分析与收敛性证明审稿人 (`Learning Theory & Optimization PC`)**
   - **关注焦点**：定理假设是否过强或脱离实际、收敛率/泛化界是否紧致、二阶泰勒展开或近似误差项是否有显式上界控制。
2. **Persona B — 大规模实证、消融实验与 SOTA 基线审稿人 (`Empirical Rigor & Baselines PC`)**
   - **关注焦点**：是否对比了近两年最新强基线、模型规模与数据集是否覆盖多领域 OOD、关键超参数消融是否完整、误差棒/多随机种子显著性是否报告。
3. **Persona C — 系统效率、可扩展性与清晰度审稿人 (`Scalability, Systems & Clarity PC`)**
   - **关注焦点**：算法真实墙钟时间（Wall-clock latency）与显存开销、图表与伪代码可读性、首屏 Figure 1 是否在 15 秒内讲清核心动机与贡献。

---

## 3. 自然语言处理顶会 (`acl` / `emnlp` / `naacl`)

### 3.1 版面与格式红线
- **Long Paper (`acl`)**：正文 **8 页**，`Limitations` 与 `Ethical Considerations` 必选（位于第 9 页、References 之前），附录不限。
- **摘要词数红线**：**130–200 词**。

### 3.2 三正交 PC 审稿人视角
1. **Persona A — 语言学机制与评测效度审稿人 (`Evaluation Validity & Analysis PC`)**
2. **Persona B — 多模型家族/多语言泛化与消融审稿人 (`Generalization & Scaling PC`)**
3. **Persona C — 复现性、人类/LLM-as-a-Judge 偏见审计审稿人 (`Reproducibility & Bias Audit PC`)**

---

## 4. 系统顶会 (`osdi` / `sosp` / `nsdi` / `eurosys`)

### 4.1 版面与格式红线
- **OSDI / SOSP (`osdi`)**：正文 **12 页**（不含 References），双栏。
- **摘要词数红线**：**150–220 词**。

### 4.2 三正交 PC 审稿人视角
1. **Persona A — 系统架构设计与不变量审稿人 (`Architecture & Correctness PC`)**
2. **Persona B — 端到端性能、尾延迟与硬件瓶颈审稿人 (`End-to-End Performance & Overhead PC`)**
3. **Persona C — 真实工作负载与开源制品审计审稿人 (`Real Workloads & Artifact Audit PC`)**

---

## 5. 顶会通用高频一票否决雷区（Desk-Reject & Major Revision Traps）

1. **匿名脱敏泄漏**：PDF Metadata 残留作者名、机器名、`PTEX.Fullbanner`、带个人时区偏移的 `CreationDate`/`ModDate`（如 `+08'00'`），或正文中出现自引暴露身份用语。
2. **玩具模型幻觉（Toy-Model Trap）**：声称解决大模型（LLM）问题，主表却被 `0.5B / 1.5B` 等小模型占满，缺乏 `32B / 70B` 级旗舰模型验证。
3. **主客颠倒的表格标号**：在主从协同（如草稿模型 $\mathcal{M}_q$ + 目标模型 $\mathcal{M}$）或迁移实验中，把辅助小模型放在表格最前面，导致审稿人扫视时误判实验规模低劣；**必须采用 `Target-First`（目标大模型居首，且按 70B → 4B 降序排列）**。
4. **多轮补丁导致的防御性臃肿（Defensive Bloat）**：摘要塞满 350+ 词的括号补丁和细碎编号，让审稿人第一眼窒息；**终轮必须执行反臃肿瘦身，恢复 150–220 词黄金叙事节奏**。
5. **图文脱离或字号失真**：滥用 `\resizebox{\columnwidth}{!}{...}` 导致不同表格字号忽大忽小甚至缩成蚂蚁字；缺少一目了然的 Figure 1 动机图。
