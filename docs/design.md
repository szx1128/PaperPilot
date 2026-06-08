# PaperPilot 系统设计文档

> 版本：v1.6.6 | 最后更新：2026-06-08

---

## 一、项目定位

### 为什么不是简单的 PDF 总结工具

简单的 PDF 总结工具仅做一件事：输入 PDF → 输出摘要。PaperPilot 的不同在于：

1. **流程完整性**：覆盖从论文发现 → 筛选 → 理解 → 追问 → 沉淀的完整闭环，而非只做"总结"这一个动作；
2. **可解释排序**：不是黑箱推荐，而是基于多维度打分并给出中文推荐理由；
3. **Fallback 健壮性**：所有依赖 LLM 的模块均具备降级方案，无 API Key 也能正常运行；
4. **学术场景适配**：arXiv API 集成、结构化总结模板、引用片段问答、Markdown 笔记生成，均围绕真实科研流程设计。

---

## 二、五个核心模块

| 模块 | 职责 | 输入 | 输出 |
|------|------|------|------|
| Paper Discovery | 论文发现 | 研究方向关键词 | 论文元信息列表 |
| Paper Ranking | 论文排序（前沿追踪 / 领域了解 / 深入了解） | 论文列表 + 用户关键词 + 阅读模式 | 排序列表 + 多维分数 + 推荐理由 + 推荐等级 |
| Paper Reading | 结构化总结 | 论文信息 + 可选 PDF 全文 | 7 字段中文总结 |
| PDF Parser | PDF 解析 | 用户上传的 PDF 文件 | 全文文本 + 页码标记 |
| Paper QA | 论文问答（LLM + 关键词 Fallback） | 论文内容 + 用户问题 | 回答 + 引用片段 + 页码 |
| Paper Note | 笔记生成 | 论文信息 + 总结 + QA + 追踪摘要 | Markdown 笔记文件 |
| Paper Tracker | 追踪管理 | 关注领域 + arXiv API | 论文历史 + 新论文 + 状态 |

### 在线 Demo 部署设计（v1.6.6）

PaperPilot 保持 Streamlit 单入口：`streamlit run app.py`。在线部署优先支持 Streamlit Community Cloud，通过 `requirements.txt` 声明依赖、`runtime.txt` 指定 Python 3.11、`.streamlit/config.toml` 提供基础运行配置。真实 API Key 不进入代码和仓库，本地通过 `.env` 配置，云端通过 Streamlit Secrets 配置。缺少 API Key 时，LLM 相关模块自动进入 Fallback 或基础模式，保证 Demo 首页、搜索、排序和非 LLM 分析流程仍可运行。

### 追踪模块设计

**模块文件：**
- `modules/tracker_store.py` — 本地 JSON 读写（watchlist.json、paper_history.json、tracker_state.json）
- `modules/paper_tracker.py` — 追踪业务逻辑（CRUD、刷新、去重、状态、筛选排序）

**数据流：**
1. 用户创建 watch item → 保存到 `data/watchlist.json`
2. 用户点击刷新 → `paper_tracker.refresh_watch_item()` → 调用 `arxiv_client.search_papers()` → 调用 `ranker.rank_papers()` → 去重合并到 `paper_history.json`
3. 论文状态变更 → 更新 `paper_history.json`
4. 笔记生成时 → `build_tracker_summary()` → 写入 Markdown

**为什么用 JSON：**
- 零运维依赖，不需要数据库安装
- 单机个人工具定位，无多机同步需求
- 结构简单，可以直接用文本编辑器查看/调试

### 模块依赖关系

```
arxiv_client (无依赖)
    ↓
ranker (依赖 arxiv_client 的输出)
    ↓
summarizer (依赖 arxiv_client 的输出 + 可选 pdf_parser 输出)
    ↓
qa_engine (依赖 summarizer 输出 + pdf_parser 输出)
    ↓
note_generator (依赖以上所有模块的输出)
```

**QA 架构说明：** QA 模块采用"关键词检索 + LLM/Fallback 回答"模式，不是复杂 RAG。流程：用户提问 → 从 PDF 文本中按关键词检索 Top 4 片段 → LLM 模式调用 API 综合片段生成回答 / Fallback 模式直接展示检索到的片段。不引入向量数据库、LangChain 或 LlamaIndex。

### Ranking Design（v2.2 阅读意图驱动排序）

排序目标：帮助用户从搜索结果中选择在当前阅读目标下更值得优先阅读的论文，而非评价论文真实学术质量。论文的阅读价值不是绝对固定的：前沿追踪关注最近进展，领域了解关注能帮助用户建立知识框架的论文，深入了解关注哪些论文更适合作为精读、复现、方法对比或后续研究切入候选。

#### 阅读意图驱动排序

PaperPilot 将论文排序从单一综合评分扩展为阅读意图驱动排序。不同阅读阶段对应不同排序目标：

- 领域了解模式：偏向 survey、overview、benchmark 和路线梳理论文；
- 深入了解模式：偏向方法完整、实验充分、可复现、可批判分析且具有发表可信度的论文；
- 前沿追踪模式：偏向近期论文和新兴方向。

其中，深入了解模式强调科研精读所需的判断维度，包括问题定义、方法结构、实验设计、baseline / ablation、局限讨论、可复现线索和 venue authority。v1.6.5 进一步加入 query relevance gate，用来约束这些质量信号只能在论文与用户查询方向相关时充分发挥作用。

#### 阅读意图层

| 模式 | 用户阶段 | 核心问题 |
|------|----------|----------|
| 前沿追踪模式 | 已了解方向，希望快速跟踪新进展 | 最近有哪些相关论文值得看？ |
| 领域了解模式 | 刚进入方向，希望建立知识框架 | 这个领域研究什么、有哪些路线和评价方式？ |
| 深入了解模式 | 已确定方向，希望深入比较和推进 | 哪些论文值得精读、复现、对比或用于发现研究空间？ |

#### 前沿追踪模式

综合分 = 0.35 × 主题相关性 + 0.20 × 贡献价值 + 0.15 × 方法清晰度 + 0.15 × 证据支撑 + 0.10 × 新鲜度 + 0.05 × 可读性

| 维度 | 权重 | 设计理由 |
|------|------|---------|
| 主题相关性 | 35% | 最重要的筛选指标，判断论文是否与研究方向相关 |
| 贡献价值 | 20% | 判断摘要中是否清楚表达了贡献信号（新方法/新结论） |
| 方法清晰度 | 15% | 判断摘要结构是否清晰（问题-方法-结果三段式） |
| 证据支撑 | 15% | 判断是否有实验或理论支撑（兼顾实验/理论论文） |
| 新鲜度 | 10% | 新论文有适度加分，但不过度 |
| 可读性 | 5% | 辅助维度，摘要长度和句子结构是否适合快速阅读 |

设计决策：
- 所有分数使用固定规则，不依赖 Min-Max 归一化（保证跨搜索结果稳定）
- 不引入 citation count / venue / 作者 h-index（arXiv 不提供这些信息）
- 不依赖 LLM（本地计算，无 API Key 也能运行）
- 推荐理由为可解释中文文本，包含推荐等级（强烈推荐/推荐优先阅读/可作为候选/低优先级/暂不推荐）

#### 领域了解模式（v1.6.3）

领域了解模式面向刚进入某一方向的用户，目标不是找最新论文，而是帮助回答：这个领域研究什么、有哪些综述/路线、大家通常怎么做、如何评价方法、哪些论文适合作为重点阅读候选。

领域了解分 = 0.18 × 主题相关性 + 0.18 × 综述/路线价值 + 0.14 × 经典/代表性信号 + 0.12 × 权威元信息信号 + 0.14 × 问题定义清晰度 + 0.12 × 方法覆盖度 + 0.07 × Benchmark/Dataset 价值 + 0.03 × 可读性 + 0.02 × 新鲜度

| 维度 | 权重 | 设计理由 |
|------|------|---------|
| 主题相关性 | 18% | 仍需确认论文与用户输入方向相关 |
| 综述/路线价值 | 18% | survey、review、overview、taxonomy、roadmap 更适合作为领域入口 |
| 经典/代表性信号 | 14% | 基于发布时间、贡献信号和基础方法/数据集/benchmark 信号做轻量估计 |
| 权威元信息信号 | 12% | 仅基于 arXiv journal_ref/comment 中的 venue 关键词，缺失时给中性分 |
| 问题定义清晰度 | 14% | 入门阶段需要先理解该领域解决什么问题 |
| 方法覆盖度 | 12% | 能比较、分类、总结方法路线的论文更适合建立知识框架 |
| Benchmark/Dataset 价值 | 7% | benchmark、dataset、evaluation 论文有助于理解领域如何评价方法 |
| 可读性 | 3% | 信息组织清晰仍有帮助，但不是核心排序目标 |
| 新鲜度 | 2% | 了解领域时不能让最新论文天然占优 |

设计边界：
- 不接入 citation count，因此不能真实判断经典论文；
- 不接入完整 venue 数据库，因此不能真实判断权威性；
- 权威信号只来自 arXiv 元信息中的关键词；
- 推荐理由使用“可能”“候选”“启发式信号”“建议人工确认”等保守措辞；
- 领域了解模式不是顶会顶刊精准识别系统。

#### 深入了解模式（v1.6.4）

深入了解模式面向已经确定研究方向的用户。它不再只是问“这篇论文是否新”，也不只是问“是否适合入门”，而是问：这篇论文是否适合作为精读、复现、方法对比或后续研究问题分析的候选。

#### 深入了解相关性门控（v1.6.5）

v1.6.5 将深入了解模式调整为“先相关、再深入”的两阶段排序：

1. **查询相关性判断**：基于用户原始 query 和少量主题扩展词判断论文是否属于目标方向。例如 `4dvar` 会扩展到 `4D-Var`、`four-dimensional variational`、`variational data assimilation`、`data assimilation`。
2. **质量信号评分**：在相关性成立的前提下，再综合方法完整性、实验充分性、baseline / ablation、可复现性、局限讨论和权威发表信号。

深入了解质量分 = 0.11 × 贡献价值 + 0.09 × 问题定义清晰度 + 0.16 × 方法完整性 + 0.16 × 实验/证据充分性 + 0.12 × 权威发表信号 + 0.10 × 可复现性信号 + 0.05 × 方法路线代表性 + 0.03 × 局限与讨论信号 + 0.03 × 新鲜度；最终分再经过 query relevance gate。

设计要点：
- query relevance 只看用户原始 query 和主题扩展词，不把 benchmark、evaluation、ablation、code、venue 等质量词当作相关性核心；
- `score == 0` 的论文会被强压到低分，不会因为质量信号排到前列；
- `0 < score < 0.15` 的论文只作为弱相关候选，质量信号会被强降权；
- `score >= 0.35` 后，方法、实验、venue、可复现等质量信号才充分参与排序。

| 维度 | 权重 | 设计理由 |
|------|------|---------|
| 查询相关性门控 | 门控项 | 先判断论文是否命中用户原始 query 或主题扩展词，避免质量信号压过主题相关性 |
| 贡献价值 | 11% | 关注论文是否有明确方法、系统、数据集或理论贡献 |
| 问题定义清晰度 | 9% | 精读前需要确认问题定义是否清楚 |
| 方法完整性 | 16% | 识别框架、架构、算法、训练/推理流程、形式化或实现细节等信号 |
| 实验/证据充分性 | 16% | 关注实验、benchmark、baseline、ablation、分析、数值结果或理论证明 |
| 权威发表信号 | 12% | 基于 arXiv journal_ref/comment/venue/doi 等元信息启发式识别正式会议、期刊、proceedings 或 DOI |
| 可复现性信号 | 10% | 识别 code、GitHub、release、implementation details、hyperparameters 等线索 |
| 方法路线代表性 | 5% | 基于本次搜索结果共同术语估计论文是否贴近当前结果集合的常见路线 |
| 局限与讨论信号 | 3% | limitation、discussion、future work、open problem 等信号有助于后续选题 |
| 新鲜度 | 3% | 新论文有很低权重，不让 freshness 主导深入了解排序 |

设计边界：
- 不接入 Semantic Scholar、OpenAlex、DBLP 或 Google Scholar；
- 不做真实 citation count、h-index 或 venue ranking；
- 当前主流路线信号只表示“在本次搜索结果中常见”，不代表真实学术领域主流；
- 可复现性只基于标题、摘要和 arXiv 元信息关键词，不读取 PDF 全文或验证代码仓库；
- 权威发表信号是加分项，不是一票否决项；arXiv-only 论文仍可作为候选；
- under review / submitted / preprint 不会被当作 accepted 或正式发表处理；
- 推荐理由使用“候选”“可能”“启发式信号”“建议人工确认”等保守措辞。

### Reviewer 视角分析模块设计

**模块文件：** `modules/reviewer.py`

**输入来源（优先级从高到低）：**
1. PDF 解析文本 — 最丰富的论文内容
2. 论文结构化总结 — 已生成的 7 字段总结
3. QA 历史 — 用户与论文的深入对话
4. 排序评分 — 六维度评分客观指标
5. 论文元数据 — 标题、摘要、作者、分类

**工作流程：**
1. `build_review_context()` 从各来源提取上下文
2. LLM 可用 → `_try_llm_review()` 调用 LLM 生成结构化审稿分析
3. LLM 不可用 → `analyze_as_reviewer_fallback()` 使用规则模板生成分析
4. `normalize_review_result()` 补全缺失字段
5. `extract_evidence_for_review()` 从文本中提取依据片段
6. `format_review_markdown()` 转换为 Markdown 供笔记使用

**输出字段：**
overall_assessment、strengths、weaknesses、novelty_analysis、methodology_analysis、experiment_analysis、clarity_analysis、potential_questions、risk_flags、improvement_suggestions、recommendation（decision + score）、confidence、evidence、mode

**为什么不在本轮做更多扩展：**
- 趋势分析需要跨时间维度的数据聚合
- 关系图谱需要引用网络解析
- 文献综述需要多论文摘要和关联分析
- 这些功能适合在后续版本独立实现

**PDF 文本流转说明：** 用户在步骤 4 上传 PDF → `pdf_parser` 提取文本并存入 `session_state.pdf_text` → 步骤 3 生成总结时，`app.py` 将 `pdf_text` 作为 `full_text` 参数传入 `generate_summary()` → `summarizer` 截取前 6000 字符加入 LLM prompt，生成基于全文的增强总结。用户不上传 PDF 时，总结仅基于标题和摘要，流程不受影响。

---


### 状态隔离设计（v1.2.3）

**关键状态变量说明：**
- `current_paper` / `current_paper_id`：只表示当前阅读论文（仅由论文阅读 Tab 主流程修改）
- `reviewer_paper_id`：Reviewer 分析归属论文（Reviewer Tab 使用，不修改 current_paper）
- `summary_paper_id`：summary 归属论文
- `pdf_bound_paper_id`：当前上传 PDF 绑定论文
- `selected_rev` / `selected_rev_id`：Reviewer Tab 局部变量

**设计原则：**
- Reviewer Tab 使用 `selected_rev`/`reviewer_paper_id`，不应修改 `current_paper`
- `manual_pdf` 是合法特殊 paper_id，不允许被 rewrite 为 hash_xxx
- PDF context 必须按 paper_id 判断是否可用（`_get_pdf_context_for_paper_id()`）
- 笔记生成必须使用 `current_paper`/`current_paper_id`，并按 `paper_id` 过滤 summary、QA、Reviewer
- 所有 Tab 的论文数据过滤必须基于 `paper_id`，不允许用标题字符串判断



### 研究趋势分析模块设计（v1.6.2）

**模块文件：** `modules/trend_analyzer.py`

**职责：** 纯数据分析，不依赖 Streamlit UI。输入论文列表，输出结构化趋势分析。

**数据来源：**
1. 当前搜索/排序结果（`ranked_papers`）
2. 关注追踪历史（`tracker_history`）
3. 合并分析（上述两者合并去重）

**核心函数：**
- `normalize_paper_for_trend()` — 统一不同来源 paper 字段
- `collect_trend_papers()` — 多来源收集 + paper_id 去重
- `extract_keywords()` — unigram/bigram 关键词统计（不引入外部 NLP）
- `analyze_time_distribution()` — 按月/年统计论文分布
- `analyze_category_distribution()` — arXiv 分类分布
- `analyze_emerging_topics()` — 启发式新兴关键词识别（older vs recent）
- `select_representative_papers()` — 按 score 选取代表论文
- `analyze_research_trends()` — 总入口

**状态隔离原则：**
- `trend_analysis_result` 独立存储，不影响其他 session_state
- 趋势分析 Tab 不调用 `_set_current_paper`，不修改任何现有状态
- 趋势分析只读取数据，不写入 PDF/summary/QA/Reviewer/innovation 状态

**关键词统计方法：** 使用 Python 标准库 `re` + `collections.Counter`，过滤停用词和泛化词，支持 unigram 和 bigram。

**时间分布方法：** 解析多种日期格式，统计按月/年分布。

**分类分布方法：** 处理 categories 为 list 或 string 的兼容情况。

**新兴关键词判断方法：** 按时间中位切分 older/recent，分别统计关键词，取 recent 明显增多的词。

**主题桶规则：** 10 个预定义主题桶（LLM、RAG、Multimodal、Agents、Evaluation、Efficient、Safety、Scientific AI、Graph、CV），基于关键词匹配。
### 论文关系图谱模块设计（v1.6.2）

**模块文件：** `modules/paper_graph.py`

**职责：** 基于论文元信息（标题、摘要、分类、作者、引用字段）构建论文关系网络。纯 Python 标准库实现。

**核心函数：**
- `build_paper_graph()` — 总入口
- `collect_graph_papers()` — 多来源收集 + get_paper_id 去重
- `_build_nodes()` — 节点构建（按 score/date 选 max_nodes 篇）
- `_build_edges()` — 四种边类型构建
- `_find_clusters()` — DFS 连通分量聚类
- `_find_central_papers()` — 加权度中心论文
- `_generate_dot()` — Graphviz DOT 字符串

**节点结构：** id / title / short_title / authors / categories / published / score / keywords / url

**边类型：**
- content_similarity：Jaccard 关键词相似度（权重 0.55）
- shared_category：共享 arXiv 分类（权重 0.20）
- shared_author：共享作者（权重 0.15）
- reference_relation：引用/关联字段匹配（权重 0.35）

**边权重规则：** weight = content_sim×0.55 + min(cat_overlap/3,1)×0.20 + min(author_overlap/2,1)×0.15 + (ref_match ? 0.35 : 0)，上限 1.0

**聚类方式：** 保留边为无向边，DFS 找连通分量。

**状态隔离：** 关系图谱只写 paper_graph_result / paper_graph_source / paper_graph_paper_ids。不修改 current_paper、selected_paper、pdf_bound_paper_id 等核心状态。


## 三、预期数据流

```
用户输入方向关键词
    → arXiv API 搜索
    → 返回论文列表（标题、作者、日期、摘要、链接）
    → 多维打分排序
    → 展示排序结果 + 推荐理由
    → 用户选择论文
    → 获取全文（可选上传 PDF）
    → 生成结构化总结（LLM 或模板 Fallback）
    → 用户提问
    → 生成回答 + 引用片段（LLM 或关键词匹配 Fallback）
    → 汇总所有信息
    → 生成 Markdown 笔记
    → 保存到本地 / 下载
```

数据在 Streamlit `session_state` 中流转，跨步骤共享。同时将论文元信息缓存到 `data/papers.json`。

---

## 四、Fallback 设计思想

### 核心原则

> 任何依赖外部服务的模块，都必须有降级策略。系统在任何配置下都应能正常运行。

### 降级层级

```
Level 1: LLM API 可用 → 最佳体验（智能总结、智能问答）
    ↓ 不可用时自动降级
Level 2: 无 LLM API → 模板 + 关键词匹配（可运行、可完成流程）
    ↓ 即使 PDF 也无法解析
Level 3: 仅 arXiv 搜索 + 排序 + 模板总结 + 基本笔记（最简可用状态）
```

### 各模块 Fallback 策略

| 模块 | 正常模式 | Fallback 模式 |
|------|---------|--------------|
| arxiv_client | arXiv API（15s 超时） | arXiv 超时/失败时使用内置真实示例论文兜底 |
| ranker | 规则打分 | 无需 Fallback（纯本地计算） |
| summarizer | LLM 生成 | 模板：关键词提取 + 固定模板填充 |
| qa_engine | LLM + 引用 | 关键词匹配：分词 → 匹配段落 → 返回匹配段落 |
| note_generator | 组装 Markdown | 无需 Fallback（纯本地拼接） |
| pdf_parser | pypdf/PyMuPDF | 返回错误提示，不阻塞后续流程 |

### Fallback 显示约定

所有 Fallback 输出均需明确标注，如：
> ⚠️ 当前为模板生成模式（未配置 LLM API Key）。部分分析可能不够深入。

---

## 五、技术选型理由

| 技术 | 理由 |
|------|------|
| Python | 生态丰富，arXiv/pypdf/Streamlit 均有成熟库 |
| Streamlit | 纯 Python 即可构建 Web UI，无需前端开发 |
| arXiv API | 免费、无需认证、覆盖 CS/物理/数学等学科 |
| pypdf | 轻量纯 Python PDF 解析，零依赖 |
| JSON 存储 | 无需数据库安装维护，适合单机工具 |
| OpenAI 兼容 API | 通用接口，支持多种 LLM 提供商 |

---

## 六、设计约束

- 不使用数据库（保持零运维依赖）
- 不做复杂前端（Streamlit 单页应用）
- 不做用户系统（个人工具定位）
- 不做向量检索（保持简单，留给后续迭代）
- 不做多 Agent 协作（单 Agent 足够覆盖场景）
