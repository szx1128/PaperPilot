# 📄 PaperPilot — 从论文发现到知识沉淀的科研阅读助手

> 面向科研人员的论文阅读助手，覆盖从发现、筛选、理解、提问到笔记沉淀的完整流程。

PaperPilot 是一个面向科研论文阅读流程的可运行原型系统。系统通过在线 Demo 展示论文发现、阅读意图排序、PDF 阅读、摘要问答、趋势分析、关系图谱、文献综述、Reviewer 分析和阅读意图建模等核心能力。

## Online Demo

本项目支持通过 Streamlit Community Cloud 在线部署。

在线访问地址：

> 部署完成后填写：`https://your-app-url.streamlit.app`

如果当前没有配置 LLM API Key，系统会以基础模式运行，论文搜索、排序和基础展示功能仍可使用，摘要问答、Reviewer 分析和科研洞察等功能需要配置 API Key 后启用。

## 📌 项目简介

PaperPilot 是一个面向科研工作者的学术论文阅读助手。它不只是简单的 PDF 总结工具，而是围绕真实科研阅读流程设计的一站式工具，帮助解决科研人员日常面临的五个核心问题：

1. ❓ 不知道某个研究方向最近有哪些新论文
2. ❓ 找到大量论文后，难以判断哪些最值得优先阅读
3. ❓ 阅读论文时，难以快速理解研究问题、方法、贡献和局限
4. ❓ 想围绕论文细节提问，但需要反复翻找原文
5. ❓ 读完论文后，阅读笔记和知识沉淀效率低

## 🚧 当前版本

**v1.6.6（在线部署与可运行 Demo 补丁）**

已完成：
- [x] 论文发现（arXiv 搜索，15s 超时，示例兜底）
- [x] 论文排序（前沿追踪 / 领域了解 / 深入了解三种阅读模式）
- [x] **领域了解模式**：面向刚进入某一方向的用户，优先推荐综述、路线图、benchmark、dataset、代表性方法和权威元信息信号较强的论文，帮助建立领域知识框架
- [x] **深入了解模式**：面向科研精读场景，先检查论文与查询方向的相关性，再筛选方法完整、实验充分、具有可复现线索和权威发表信号的重点阅读候选论文
- [x] **深入了解相关性门控**：修复 benchmark / evaluation / ablation 等质量信号压过查询相关性的问题，避免无关论文仅凭质量关键词排到前列
- [x] 结构化总结（LLM + Fallback，PDF 增强）
- [x] PDF 上传与文本解析（pypdf）
- [x] 论文问答（LLM + 关键词 Fallback，引用片段，问答历史）
- [x] 阅读笔记生成（含问答历史 + 追踪摘要）
- [x] **关注领域追踪**（关注领域管理、一键刷新、新论文识别、状态标记）
- [x] **Reviewer 视角分析**（LLM + Fallback，优点/不足/创新性/方法/实验/风险/审稿倾向）
- [x] **创新点分析**（LLM + Fallback，核心创新/贡献/新颖性/方法差异/潜在影响）
- [x] **研究趋势分析**（关键词分布、时间分布、分类分布、热点/新兴/高分主题、代表论文、趋势总结）
- [x] **论文关系图谱**（基于相似度/分类/作者/引用字段的关系网络、Graphviz 图、主题簇、中心论文）
- [x] **在线部署适配**（Streamlit Community Cloud 配置、runtime.txt、部署文档、Secrets 说明、无 API Key 基础模式）

### Version 1.6.6：在线部署与可运行 Demo 补丁

本版本聚焦在线部署与可运行 Demo，不新增论文分析算法。项目已补齐 Streamlit Community Cloud 部署所需配置，包括 `runtime.txt`、`.streamlit/config.toml`、`.env.example`、`docs/deployment.md` 和 Docker 兜底运行说明。

部署时推荐将真实 API Key 放在 Streamlit Cloud Secrets 中，而不是提交 `.env`。未配置 API Key 时，系统仍会以基础模式运行，论文搜索、排序、PDF 基础阅读和本地启发式分析流程不会因缺少 LLM Key 直接崩溃。

### Version 1.6.5：深入了解模式相关性门控补丁

本版本修复“深入了解模式”中质量信号可能压过查询相关性的问题。深入了解排序现在采用“先相关、再深入”：搜索召回阶段会根据用户原始 query 及少量主题扩展词过滤低相关论文；排序阶段会先计算方法完整性、实验充分性、venue、可复现等质量信号，再用 query relevance gate 限制这些信号的影响。

例如用户搜索 `4dvar` 时，系统会将 `4D-Var`、`four-dimensional variational`、`variational data assimilation`、`data assimilation` 视为主题相关表达，但不会把 `benchmark`、`evaluation`、`ablation` 等扩展搜索质量词当作相关性核心。无明确主题命中的论文不会因为有 benchmark、ablation 或 venue 信号而排到深入了解结果前列。

该补丁仍然只基于标题、摘要和 arXiv 元信息做启发式排序，不接入外部数据库，不做真实 citation、venue ranking 或论文质量判断。

### Version 1.6.4：深入了解模式与权威发表信号补丁

本版本在已有阅读意图排序基础上新增“深入了解模式”。该模式面向已经具备一定领域基础、希望筛选值得精读论文的用户，综合考虑论文相关性、方法完整性、实验充分性、baseline 与 ablation 信号、可复现信号、局限讨论以及权威会议/期刊发表信息，帮助用户选择适合精读、复现、比较和批判分析的候选论文。

需要注意的是，权威发表信息只是加分项，不是一票否决项。对于尚未正式发表但质量信号较强的 arXiv 论文，系统仍会将其作为候选论文展示，并提示用户进一步人工确认。

PaperPilot 将论文阅读建模为不同阅读意图：

1. 领域了解模式：帮助用户快速建立领域认知；
2. 深入了解模式：帮助用户筛选值得精读、复现和批判分析的代表性论文；
3. 前沿追踪模式：帮助用户关注最新论文和新兴趋势。

| 阅读模式 | 适用阶段 | 排序重点 |
|----------|----------|----------|
| 前沿追踪模式 | 已了解方向，希望看最近进展 | 主题相关性、贡献价值、方法/证据信号、适度新鲜度 |
| 领域了解模式 | 刚进入方向，希望建立知识框架 | survey、review、taxonomy、benchmark、dataset、代表性方法、权威元信息信号 |
| 深入了解模式 | 已确定方向，希望精读/复现/对比 | 先约束查询相关性，再看方法完整性、实验充分性、baseline/ablation、可复现性、局限讨论、权威发表信号 |

> 注意：深入了解模式只基于标题、摘要和 arXiv 元信息进行轻量启发式判断，不接入 citation count、h-index、真实 venue ranking 或外部学术数据库，不等同于真实论文质量或真实学术影响力评价。

### Version 1.6.3：领域了解模式与阅读意图建模补丁

本版本新增“领域了解模式”，用于帮助用户刚进入一个研究方向时建立领域知识框架。与偏向最新论文的前沿追踪不同，领域了解模式会优先关注 survey、review、overview、taxonomy、benchmark、dataset、代表性方法论文，以及带有权威发表元信息信号的论文。

该模式的核心思想是：论文价值不是绝对固定的，而是取决于用户当前的科研阅读目标。对于领域入门用户，系统更关注“这个领域研究什么、有哪些经典/代表性工作、大家通常怎么做、如何评价方法”，而不是单纯追求最新论文。

> 注意：当前经典性和权威性判断仅为基于 arXiv 元信息、标题和摘要的启发式信号，不等同于真实引用量或真实学术影响力评价。

### v1.5.0 新增功能

- [x] **论文关系图谱 Tab**：基于标题、摘要、关键词、分类、作者和引用字段构建论文关系网络
- [x] **Graphviz 图展示**：可视化论文间关系，支持降级显示 DOT 源码
- [x] **主题簇聚类**：DFS 连通分量识别论文主题簇
- [x] **中心论文识别**：加权度计算，识别关系网络中的中心论文
- [x] **边类型**：内容相似度边、共享分类边、共享作者边、引用字段边
- [x] **状态隔离**：关系图谱只写 paper_graph_result / paper_graph_source / paper_graph_paper_ids

### v1.3.1 修复说明

- [x] 修复趋势分析 Tab 重复展示块（category_distribution、representative_papers、warnings）
- [x] 删除不存在的 UI 字段展示（emerging_keywords、topic_buckets、interpretation）
- [x] 当前搜索/排序结果同时兼容 ranked_papers 和未排序的 papers/search_results
- [x] 修复 recent_months 参数实际运用于 emerging_topics 算法
- [x] 文档与实际返回结构一致

### v1.3.0 新增功能

- [x] **研究趋势分析 Tab**：关键词统计、时间分布、分类分布、热点/新兴/高分主题、代表论文、趋势总结
- [x] **多数据来源**：当前搜索/排序结果、关注追踪历史、合并分析
- [x] **状态隔离**：趋势分析只读已有数据，不修改任何其他 session_state

### v1.2.3 修复说明

本次为稳定性补丁，不新增功能：

- 修复 Reviewer Tab 生成分析时覆盖 `current_paper`/`current_paper_id`
- 修复 Reviewer 当前上传 PDF 的 manual_pdf 绑定问题
- 修复 summary selectbox 切换论文后 `selected_paper` 不同步
- 修复 Markdown 笔记生成可能混用旧 `selected_paper` 的问题
- 修复 QA fallback 返回结构缺少 `evidence_chunks`
- 修复只传 chunks 不传 paper_text 时 fallback 误判"未上传 PDF"
- 复查 QA summary 按 paper_id 过滤

## 📋 功能规划

| 模块 | 功能 | 状态 |
|------|------|------|
| Paper Discovery | arXiv 搜索、超时保护、示例兜底 | ✅ 已完成 |
| Paper Ranking | 前沿追踪 / 领域了解 / 深入了解三种阅读模式评分（固定规则） | ✅ 已完成 |
| Paper Reading | 结构化总结（LLM + Fallback + PDF 增强） | ✅ 已完成 |
| PDF Parser | PDF 上传、文本提取、预览 | ✅ 已完成 |
| Paper QA | 论文问答 + 引用片段 + 问答历史 | ✅ 已完成 |
| Paper Tracker | 关注领域管理、论文追踪、去重、状态 | ✅ 已完成 |
| Reviewer | 审稿视角分析（LLM + Fallback，证据，推荐） | ✅ 已完成 |
| Paper Note | Markdown 笔记生成（QA + 追踪 + Reviewer） | ✅ 已完成 |
| Trend Analysis | 研究趋势分析（关键词、时间、分类、热点/新兴/高分主题） | ✅ 已完成 |
| Paper Graph | 论文关系图谱（相似度/分类/作者边、Graphviz、主题簇） | ✅ 已完成 |

### 核心设计原则

- 🔄 **Fallback 优先**：所有依赖 LLM 的模块均有无 API 降级方案，系统不会因缺少 API Key 而崩溃
- 📊 **可解释性**：排序给出多维分数和中文推荐理由，不是黑箱推荐
- 🧱 **模块化**：每个模块独立封装，可单独升级而不影响整体
- 🌐 **中文友好**：面向中文科研用户，总结和交互以中文为主

## 📦 安装方式

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

```bash
# 1. 克隆项目
git clone <repo-url>
cd paperpilot

# 2. 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量（可选，不配置则使用 Fallback 模式）
cp .env.example .env
# 编辑 .env 填入 LLM API Key
```

## ▶️ 运行方式

```bash
cd paperpilot
streamlit run app.py
```

启动后在浏览器中访问 `http://localhost:8501`。

> 💡 即使不配置 `.env` 文件，系统也能正常运行（使用模板和关键词匹配作为 Fallback）。

## Deployment

推荐使用 Streamlit Community Cloud 部署：

1. 上传代码到 GitHub；
2. 在 Streamlit Community Cloud 中选择该仓库；
3. Main file path 填写 `app.py`；
4. 在 Secrets 中配置 API Key；
5. 点击 Deploy；
6. 获取在线访问链接。

详细步骤见 `docs/deployment.md`。

Docker 兜底运行方式：

```bash
docker build -t paperpilot .
docker run -p 8501:8501 --env-file .env paperpilot
```

## 📁 项目结构

```
paperpilot/
├── app.py                    # Streamlit 主入口
├── requirements.txt          # Python 依赖
├── runtime.txt               # Streamlit Cloud Python 版本
├── Dockerfile                # Docker 兜底运行配置
├── README.md                 # 项目说明
├── .env.example              # 环境变量模板
├── .gitignore
├── .streamlit/
│   └── config.toml           # Streamlit Cloud 基础配置（不含 secrets）
├── modules/                  # 核心业务模块
│   ├── __init__.py
│   ├── arxiv_client.py       # arXiv API 封装
│   ├── ranker.py             # 论文排序（前沿追踪 / 领域了解 / 深入了解模式）
│   ├── summarizer.py         # 结构化总结（LLM + 模板 Fallback）
│   ├── llm_client.py         # LLM 统一调用
│   ├── pdf_parser.py         # PDF 解析
│   ├── qa_engine.py          # 论文问答
│   ├── note_generator.py     # 笔记生成
│   ├── paper_tracker.py      # 追踪业务逻辑
│   ├── tracker_store.py      # 追踪数据持久化
│   ├── reviewer.py           # Reviewer 视角分析
│   └── utils.py              # 公共工具
├── data/                     # 数据存储
│   ├── papers.json           # 搜索论文缓存
│   ├── watchlist.json        # 关注领域列表
│   ├── paper_history.json    # 追踪论文历史
│   ├── tracker_state.json    # 最近刷新状态
│   ├── notes/                # 生成的笔记
│   └── uploads/              # 上传的 PDF
├── docs/                     # 项目文档
│   ├── design.md             # 设计文档
│   ├── project_thinking.md   # 项目思考与科研工作流说明
│   ├── iteration_log.md      # 迭代日志
│   ├── limitations.md        # 局限性分析
│   ├── prompts.md            # LLM Prompt 模板
│   ├── deployment.md         # 在线部署说明
│   └── demo_script.md        # 演示脚本
└── screenshots/              # 截图目录
```

## 🛠 技术栈

- **语言**：Python 3.11（Streamlit Cloud 使用 `runtime.txt` 指定）
- **界面**：Streamlit
- **论文来源**：arXiv API
- **PDF 解析**：pypdf
- **LLM 调用**：OpenAI 兼容 API（可选）
- **存储**：本地 JSON + Markdown 文件

## 📄 License

MIT
