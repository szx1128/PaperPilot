# PaperPilot 迭代开发日志

> 记录每个开发阶段的完成内容、遇到的问题、解决方案和验收结果。

---

## Version 1.6.8：在线 API 输入与会话级配置补丁（2026-06-08）

- [x] 在侧边栏新增“LLM API 设置”区域，支持 DeepSeek / OpenAI / 自定义 OpenAI-Compatible；
- [x] API Key 输入框使用 password 类型；
- [x] 支持用户输入 Base URL 和模型名称；
- [x] 点击“保存本次会话 API 配置”后，仅写入 `st.session_state`，不写入 `.env`、data 或 secrets 文件；
- [x] 点击“清除本次会话 API 配置”后，恢复部署 Secrets / 环境变量 / 基础模式；
- [x] `llm_client` 新增统一动态配置解析，优先级为：会话输入 > Streamlit Secrets > 本地 `.env` / 环境变量 > 基础模式；
- [x] LLM 状态显示配置来源、模型名称和脱敏 Key，不展示完整 API Key；
- [x] 摘要、QA、Reviewer 和创新点分析在无 API Key 时显示侧边栏配置提示；
- [x] 更新 README、deployment、limitations 和 demo_script 文档。

---

## Version 1.6.6：在线部署与可运行 Demo 补丁（2026-06-08）

- [x] 保持 Streamlit 主入口为 `streamlit run app.py`，不引入额外后端服务；
- [x] 补齐 Streamlit Community Cloud 部署文件：`runtime.txt`、`.streamlit/config.toml`；
- [x] 清理 `requirements.txt`，仅保留当前代码实际需要的轻量依赖；
- [x] 更新 `.env.example`，说明本地 `.env` 与云端 Secrets 的配置方式；
- [x] 新增 `docs/deployment.md`，包含本地运行、在线部署、Secrets、无 API Key 模式和常见问题；
- [x] 新增 Dockerfile 作为本地/考核环境兜底运行方案；
- [x] 更新 README 的 Online Demo、Quick Start 和 Deployment 说明；
- [x] 增强 LLM 配置读取，支持环境变量、`.env`、Streamlit Secrets，并识别占位符为未配置；
- [x] 未配置 API Key 时页面显示基础模式提示，不影响搜索、排序和非 LLM 功能启动。

---

## Version 0.1 — 项目骨架（2026-06-06）

### 阶段目标

建立 PaperPilot 项目的基础工程结构，创建完整的目录树、Streamlit 页面骨架、依赖声明和环境配置模板。本阶段不实现任何业务逻辑。

### 已完成内容

- [x] 创建完整项目目录结构（`paperpilot/` 根目录 + 4 个子目录）
- [x] 创建 `app.py` Streamlit 主页面骨架（标题、说明、6 步占位）
- [x] 创建 `requirements.txt`（streamlit, arxiv, pypdf, python-dotenv, requests）
- [x] 创建 `.env.example`（LLM_API_KEY, LLM_BASE_URL, LLM_MODEL）
- [x] 创建 `.gitignore`（.env, __pycache__, data/uploads/, .DS_Store 等）
- [x] 创建 `modules/__init__.py`（包初始化 + 模块说明）
- [x] 创建 `modules/utils.py`（文本清洗、分数归一化、时间衰减、关键词匹配、JSON 缓存）
- [x] 创建 README.md 初稿（项目简介、安装方式、运行方式、项目结构）
- [x] 创建 design.md 初稿（设计思想、模块说明、数据流、Fallback 设计）
- [x] 创建 iteration_log.md 初稿（本文件）
- [x] 创建 limitations.md 初稿（当前限制说明）
- [x] 创建 prompts.md 占位
- [x] 创建 demo_script.md 占位

### 当前未实现内容

以下模块仅存在于目录结构中，尚未实现：

- [ ] `modules/arxiv_client.py` — 论文发现
- [ ] `modules/ranker.py` — 论文排序
- [ ] `modules/summarizer.py` — 结构化总结
- [ ] `modules/pdf_parser.py` — PDF 解析
- [ ] `modules/qa_engine.py` — 论文问答
- [ ] `modules/note_generator.py` — 笔记生成
- [ ] `modules/llm_client.py` — LLM 统一调用
- [ ] `app.py` 中的业务逻辑集成

### 验收结果

| 验收项 | 状态 |
|--------|------|
| 进入 paperpilot/ 目录 | ✅ |
| `streamlit run app.py` 可运行 | ✅ |
| 页面正常打开 | ✅ |
| 显示项目标题和阶段占位 | ✅ |
| 目录结构完整 | ✅ |
| 文档初稿存在 | ✅ |
| 无报错 | ✅ |
| 未实现业务逻辑 | ✅ |

### 已知问题

无。

### 下一阶段计划

**阶段 1：论文发现闭环**

- 实现 `modules/arxiv_client.py`
- 在 `app.py` 中集成搜索 UI 和结果展示
- 用户输入关键词 → 调用 arXiv API → 返回论文列表

---

## Version 0.2 — 论文发现闭环（2026-06-06）

### 阶段目标

实现用户输入研究方向关键词后，系统调用 arXiv API 搜索论文，并在 Streamlit 页面中展示论文基本信息。不做排序。

### 已完成内容

- [x] 创建 `modules/arxiv_client.py`：封装 arXiv API 搜索
  - `search_papers(query, max_results=20)` 返回标准化论文列表
  - `fetch_paper_by_id(paper_id)` 按 ID 获取单篇论文
  - 内部辅助函数 `_parse_result()` 和 `_format_date()`
  - 完善的异常处理：网络错误、API 错误均返回空列表，不崩溃
- [x] 修改 `app.py` 步骤 1：实现真实搜索功能
  - 关键词输入框（默认示例：large language model reasoning）
  - 搜索数量选择器（5/10/20/30，默认 20）
  - 搜索按钮 + spinner 加载状态
  - 搜索结果保存到 `st.session_state.papers`
  - 每篇论文用 expander 展示：标题、作者、日期、摘要、arXiv 链接、PDF 链接
  - 友好提示：空输入、空结果、API 错误分别处理
- [x] 搜索结果自动缓存到 `data/papers.json`（调用 `save_papers_cache`）
- [x] 侧边栏功能状态：论文发现标记为 ✅，其余标记为 ⬜
- [x] 修正阶段 0 遗留问题：README.md 措辞、iteration_log.md 链接、screenshots/.gitkeep

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/arxiv_client.py` | 新建 |
| `app.py` | 重写（集成搜索功能） |
| `README.md` | 修改（修正措辞） |
| `docs/iteration_log.md` | 修改（修正链接 + 新增 v0.2） |
| `screenshots/.gitkeep` | 新建 |

### 验收结果

| 验收项 | 状态 |
|--------|------|
| `streamlit run app.py` 可运行 | ✅ |
| 页面中可以输入关键词 | ✅ |
| 点击搜索后返回 arXiv 论文 | ✅ |
| 每篇展示标题、作者、日期、摘要、arXiv 链接、PDF 链接 | ✅ |
| 搜索结果保存到 `data/papers.json` | ✅ |
| 无 API Key 时也能正常运行 | ✅ |
| 未实现排序、总结、PDF、QA、笔记 | ✅ |

### 已知问题

无。

### 下一阶段计划

**阶段 2：论文排序闭环**

- 实现 `modules/ranker.py`：四维度打分（关键词相关性、发布时间新鲜度、标题匹配程度、摘要信息量）
- 在 `app.py` 步骤 2 中集成排序展示
- 展示综合分、各项分数和中文推荐理由
- 默认展示 Top 10，可调整

---

## Version 0.3 — 论文排序闭环（2026-06-06）

### 阶段目标

基于阶段 1 的搜索结果，实现四维度可解释排序。用户搜索论文后，系统对结果打分排序，展示综合分、各维度分数和中文推荐理由。排序逻辑纯本地计算，不依赖任何外部服务。

### 已完成内容

- [x] 创建 `modules/ranker.py`：实现四维度排序引擎
  - `rank_papers(papers, query, top_k)` 核心排序函数
  - 四个维度独立评分函数：`_calc_keyword_score`、`_calc_freshness_score`、`_calc_title_score`、`_calc_abstract_info_score`
  - Min-Max 归一化 `_normalize_dimension`
  - 中文推荐理由生成 `_generate_reason`（根据分数分布自动生成差异化推荐语）
  - 固定权重：关键词 0.4 + 新鲜度 0.3 + 标题 0.2 + 摘要信息量 0.1
- [x] 修改 `app.py` 步骤 2：集成排序功能
  - Top K 选择器（5/10/15/20，默认 10）
  - 排序按钮 + spinner 加载状态
  - 排序结果保存到 `st.session_state.ranked_papers`
  - 每篇展示：排名、综合分、四项分数（metric 卡片）、推荐理由、摘要、链接
  - 重新搜索自动清空旧排序结果
- [x] 侧边栏状态更新：论文发现 ✅，论文排序 ✅
- [x] 清理 `__pycache__` 目录

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/ranker.py` | 新建 |
| `app.py` | 重写（集成排序功能） |
| `docs/iteration_log.md` | 修改（新增 v0.3） |

### 验收结果

| 验收项 | 状态 |
|--------|------|
| `streamlit run app.py` 可运行 | ✅ |
| 先搜索论文，再点击排序 | ✅ |
| 页面展示 Top K 排序结果 | ✅ |
| 每篇论文有综合分 | ✅ |
| 每篇论文有四个维度分数 | ✅ |
| 每篇论文有中文推荐理由 | ✅ |
| 排序逻辑不依赖 LLM，不需要 API Key | ✅ |
| 重新搜索后旧排序结果会清空 | ✅ |
| 不实现总结、PDF、QA、笔记 | ✅ |
| 更新了 iteration_log.md | ✅ |

### 已知问题

无。

### 下一阶段计划

**阶段 3：结构化总结**

- 实现 `modules/llm_client.py`（LLM 统一调用 + fallback 判断）
- 实现 `modules/summarizer.py`（LLM 模式 + 模板 fallback 模式）
- 在 `app.py` 步骤 3 中集成总结功能
- 用户选择一篇论文 → 生成中文结构化总结

---

## Version 0.4 — 结构化总结（2026-06-06）

### 阶段目标

实现基于论文标题和摘要的中文结构化总结。支持 LLM 模式和 Fallback 模板模式，LLM 不可用时自动降级，系统不崩溃。首次引入 LLM 调用能力。

### 已完成内容

- [x] 创建 `modules/llm_client.py`：LLM 统一调用模块
  - `is_llm_available()` 判断 LLM 是否可用
  - `call_llm(system_prompt, user_prompt, temperature)` 调用 OpenAI 兼容 API
  - `get_llm_info()` 返回配置信息（供 UI 显示）
  - 网络超时 30s + 最多 2 次重试，4xx 错误不重试
  - 支持环境变量配置：LLM_API_KEY、LLM_BASE_URL、LLM_MODEL
- [x] 创建 `modules/summarizer.py`：结构化总结引擎
  - `generate_summary(paper, full_text)` 核心函数
  - LLM 模式：调用 LLM + JSON 解析（3 种解析策略）
  - Fallback 模式：关键词匹配 + 固定模板填充
  - 7 个字段：one_sentence、background、core_problem、method、contributions、limitations、reading_suggestion
  - LLM 响应解析失败自动退回 Fallback
- [x] 修改 `app.py` 步骤 3：集成总结功能
  - 论文选择器（从排序结果中选择）
  - "生成结构化总结"按钮 + spinner
  - 总结结果存储到 `st.session_state.summary`
  - LLM 模式显示 "🤖 LLM 生成"，Fallback 显示 "📋 模板生成"
  - 新搜索/重排序清空旧总结
- [x] 侧边栏新增 LLM 状态指示（已就绪 / 未配置）
- [x] 更新 README.md 版本状态

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/llm_client.py` | 新建 |
| `modules/summarizer.py` | 新建 |
| `app.py` | 重写（集成总结功能） |
| `README.md` | 修改（更新版本状态） |
| `docs/iteration_log.md` | 修改（新增 v0.4） |

### 验收结果

| 验收项 | 状态 |
|--------|------|
| `streamlit run app.py` 可运行 | ✅ |
| 用户可以先搜索论文 | ✅ |
| 用户可以对论文排序 | ✅ |
| 用户可以从排序结果中选择一篇论文 | ✅ |
| 点击按钮后可以生成中文结构化总结 | ✅ |
| 没有 LLM API Key 时 fallback 模式正常运行 | ✅ |
| fallback 模式明确标注"模板生成" | ✅ |
| 总结包含 7 个字段 | ✅ |
| LLM 调用失败时不会崩溃 | ✅ |
| 不实现 PDF、QA、笔记生成 | ✅ |
| 更新了 iteration_log.md | ✅ |

### 已知问题

无。

### 下一阶段计划

**阶段 3.5：简易 Markdown 阅读笔记生成**

- 实现 `modules/note_generator.py`
- 基于论文信息 + 总结生成 Markdown 笔记
- 支持页面预览和下载
- 不引入复杂功能，保持简单

---

### 阶段 3 二次修正（2026-06-07）

修正 v0.4 中 LLM 总结模块的以下问题：

- [x] **LLM 字段校验**：新增 `_validate_summary_fields()`，检查 LLM 返回是否包含全部 7 个必要字段，缺失时自动退回 fallback
- [x] **LLM 字段类型归一化**：新增 `_normalize_summary_fields()`，将 list 类型字段（如 contributions）转换为 Markdown bullet 格式，避免 st.markdown 显示异常
- [x] **清理缓存**：删除 `__pycache__/`

---

## Version 0.5 — 简易 Markdown 阅读笔记生成（2026-06-07）

### 阶段目标

在用户完成搜索 → 排序 → 选择 → 总结后，基于选中论文和总结生成 Markdown 阅读笔记，支持页面预览和文件下载。

### 已完成内容

- [x] 创建 `modules/note_generator.py`：笔记生成模块
  - `generate_note(paper, summary)` 生成 Markdown 笔记（基本信息 + 7 个总结字段 + 阅读建议）
  - `make_note_filename(paper)` 生成安全文件名（格式：`{Author}_{Year}_{title}.md`）
  - `save_note_to_file(note_md, paper)` 保存到 `data/notes/`，失败不抛异常
  - 辅助函数 `_format_authors()`、`_slugify()`
- [x] 修改 `app.py` 步骤 6：集成笔记生成
  - "生成 Markdown 阅读笔记"按钮
  - 笔记预览（st.markdown 渲染）
  - 下载按钮（st.download_button）
  - 本地保存状态提示（成功路径 / 失败提示）
- [x] 状态管理：搜索/重排序/重总结时清空 `note_md`
- [x] 更新侧边栏和版本号

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/note_generator.py` | 新建 |
| `modules/summarizer.py` | 修改（字段校验 + 类型归一化） |
| `app.py` | 重写（集成笔记生成） |
| `README.md` | 修改（更新版本状态） |
| `docs/iteration_log.md` | 修改（新增 v0.5 + 二次修正） |

### 验收结果

| 验收项 | 状态 |
|--------|------|
| `streamlit run app.py` 可运行 | ✅ |
| 用户可以搜索论文 | ✅ |
| 用户可以排序论文 | ✅ |
| 用户可以选择论文并生成总结 | ✅ |
| 用户可以生成 Markdown 阅读笔记 | ✅ |
| 页面可以预览笔记 | ✅ |
| 可以下载 .md 文件 | ✅ |
| 笔记包含基本信息和 7 个总结字段 | ✅ |
| 无 LLM API Key 时完整流程仍可运行 | ✅ |
| 不实现 PDF、QA、引用片段、问答历史 | ✅ |
| 更新了 iteration_log.md 和 README.md | ✅ |

### 已知问题

无。

### 下一阶段计划

**阶段 4：PDF 上传与解析**

- 实现 `modules/pdf_parser.py`
- 支持 PDF 上传、文本提取、段落分段
- 加密/扫描版 PDF 友好提示

---

## Version 0.5.1 — 稳定性与安全修复（2026-06-07）

### 阶段目标

修复 v0.5 中的安全风险和稳定性问题：确保 .env 不被提交、清理缓存文件、增加 arXiv 请求超时控制、提供网络失败时的示例数据降级方案。

### 已完成内容

- [x] **安全修复**
  - 确认 `.gitignore` 覆盖 `.env`、`__pycache__/`、`*.pyc`、`.DS_Store`
  - 清理 `data/notes/` 中的测试笔记，仅保留 `.gitkeep`
  - 在 `docs/limitations.md` 中新增"安全注意事项"章节（API Key 保护 + 打包前清理清单）
- [x] **arXiv 稳定性修复**
  - 重写 `modules/arxiv_client.py`：使用 `requests` 直接调用 arXiv API，设置 15s 超时
  - 返回格式改为结构化 dict：`{"papers": [...], "error": None|str}`
  - 新增 `get_sample_papers()`：内置 5 篇经典 LLM 论文作为兜底
  - 网络超时/连接错误/HTTP 错误均有明确中文错误提示
- [x] **app.py 适配**
  - 搜索失败时不覆盖已有结果
  - 三种状态区分：成功有结果/成功无结果/失败
  - 搜索失败时展示"使用内置示例论文继续演示"按钮
  - 示例论文结构完全兼容排序、总结、笔记流程

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/arxiv_client.py` | 重写（requests + 超时 + 结构化返回 + 示例数据） |
| `app.py` | 修改（适配新返回格式 + 示例降级按钮） |
| `docs/iteration_log.md` | 修改（新增 v0.5.1） |
| `docs/limitations.md` | 修改（新增安全注意事项） |
| `data/notes/` | 清理（仅保留 .gitkeep） |

### 验收结果

| 验收项 | 状态 |
|--------|------|
| 项目目录无 `__pycache__` | ✅ |
| 项目目录无 `__MACOSX` | ✅ |
| `.env` 已在 `.gitignore` | ✅ |
| `data/notes/` 仅保留 `.gitkeep` | ✅ |
| arXiv 搜索有 15s timeout | ✅ |
| 超时/失败不卡 spinner | ✅ |
| 示例论文 5 篇均为真实论文，HTTP 200 | ✅ |
| 完整流程（示例→排序→总结→笔记）可运行 | ✅ |
| 文档已更新（README/design/limitations/demo_script） | ✅ |

### 已知问题

空关键词搜索 bug（已在本轮后续修复中解决）。

### v0.5.1 二次修复（2026-06-07）

- [x] **修复示例兜底按钮不生效**：改用 `st.session_state.show_sample_fallback` 状态驱动，按钮移到 `if search_btn:` 外部
- [x] **修复空关键词搜索 bug**：空关键词只显示 warning，不访问未定义的 `result`
- [x] **优化 arXiv 超时提示**：提示文字说明国际链路不稳定，引导使用示例数据
- [x] **核对示例论文**：5 篇均为真实论文，arXiv ID/URL 对应，HTTP 200 验证通过
- [x] **文档统一更新**：README、design.md、limitations.md、demo_script.md 版本同步为 v0.5.1

### 下一阶段计划

**阶段 4：PDF 上传与解析**

---

## Version 0.6.0 — PDF 上传与解析（2026-06-07）

### 阶段目标

实现 PDF 上传与文本解析功能，将提取的 PDF 文本接入结构化总结模块，支持基于全文的增强总结。

### 已完成内容

- [x] 创建 `modules/pdf_parser.py`
  - `extract_text_from_pdf(uploaded_file)` 使用 pypdf.PdfReader 逐页提取
  - 页码标记、文本清洗（去 `\x00`、合并空行）
  - 错误降级：加密 PDF、扫描版（字符数 < 50）、损坏 PDF
  - `get_text_preview(text, max_chars)` 预览截断
- [x] 修改 `app.py` 步骤 4
  - `st.file_uploader` 上传组件 + "解析 PDF" 按钮
  - 解析结果展示：文件名、页数、字符数、文本预览（前 1500 字）
  - 解析失败不崩溃，显示错误提示
- [x] 总结模块接入 PDF 文本
  - `generate_summary(paper, full_text=pdf_text)` 传入全文
  - 页面提示：✅ 已结合 PDF / ℹ️ 未上传 PDF
- [x] 优化 `modules/summarizer.py`
  - full_text 截取上限从 3000 → 6000 字符
  - LLM prompt 明确指示优先使用全文、不编造

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/pdf_parser.py` | 新建 |
| `app.py` | 修改（PDF 上传 UI + 总结联动） |
| `modules/summarizer.py` | 修改（full_text 增强） |
| `README.md` | 修改（v0.6.0） |
| `docs/iteration_log.md` | 修改（新增 v0.6.0） |
| `docs/design.md` | 修改（新增 pdf_parser 说明） |
| `docs/demo_script.md` | 修改（新增 PDF 场景） |
| `docs/limitations.md` | 修改（新增 PDF 限制） |

### 验收结果

### 已知问题

无。

### 下一阶段计划

**阶段 5：论文问答**

---

## Version 0.7.0 — 论文问答（2026-06-07）

### 阶段目标

实现基于 PDF 文本的论文问答模块，支持 LLM 和关键词 Fallback 双模式，展示引用片段，记录问答历史，并将问答历史集成到 Markdown 笔记中。

### 已完成内容

- [x] 创建 `modules/qa_engine.py`：问答引擎
  - `answer_question(question, paper, summary, pdf_text)` 核心函数
  - PDF 文本分段：按 `===== Page N =====` 分割 + 段落切分
  - 关键词检索：`retrieve_relevant_chunks()` 命中分数排序 + Top K 兜底
  - LLM 模式：调用 LLM API，综合片段生成回答
  - Fallback 模式：直接展示检索到的片段 + 保守回答
  - 无 PDF 时基于摘要/总结给出保守回答
- [x] 修改 `app.py` 步骤 5：集成问答 UI
  - `qa_history` session_state 管理
  - 问题输入 + 提交按钮 + 清空历史按钮
  - LLM/Fallback 模式标签展示
  - 引用片段展示（page + snippet）
  - 新搜索/重排序/重总结清空旧问答
- [x] 修改 `modules/note_generator.py`
  - `generate_note(paper, summary, qa_history)` 支持问答历史参数
  - 笔记中新增"论文问答记录"板块，逐条展示问题和引用
- [x] 文档更新：README、design、limitations、demo_script、prompts、iteration_log

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/qa_engine.py` | 新建 |
| `app.py` | 修改（QA UI + 状态管理） |
| `modules/note_generator.py` | 修改（qa_history 参数） |
| `README.md` | 修改（v0.7.0） |
| `docs/design.md` | 修改（新增 QA 架构说明） |
| `docs/limitations.md` | 修改（新增 QA 限制） |
| `docs/demo_script.md` | 修改（新增 QA 场景） |
| `docs/prompts.md` | 修改（写入实际 prompt） |
| `docs/iteration_log.md` | 修改（新增 v0.7.0） |

### 验收结果

### 已知问题

无。

### 下一阶段计划

项目核心功能已全部实现。后续可考虑：文档打磨、性能优化，或根据需求增加高级功能。

---

## Version 0.8.0 — 排序重构：六维阅读优先级评分（2026-06-07）

### 阶段目标

重构评分机制，从四维简单关键词排序升级为六维可解释阅读优先级评分。删除 Min-Max 归一化，改用固定规则保证跨搜索结果分数稳定。

### 已完成内容

- [x] 重写 `modules/ranker.py`（v2.0）
  - 新增六个评分维度：主题相关性（35%）、贡献价值（20%）、方法清晰度（15%）、证据支撑（15%）、新鲜度（10%）、可读性（5%）
  - 全部使用固定规则 + 关键词命中，不依赖 Min-Max 归一化
  - 贡献价值：检测 contribution/novelty/artifact/result 四类术语
  - 方法清晰度：检测 problem-method-result 三段式摘要素结构
  - 证据支撑：同时支持实验论文（benchmark/dataset/baseline/ablation）和理论论文（theorem/proof/bound）
  - 新鲜度：固定区间（30天→100, 90天→90, ... 3年+→35），旧论文不归零
  - 可读性：摘要长度 + 句子数量综合评价
  - 推荐等级：强烈推荐/推荐优先阅读/可作为候选/低优先级/暂不推荐
  - 推荐理由：综合多个维度生成科研阅读建议
- [x] 更新 `app.py` 排序 UI
  - 两行 4+4 布局展示 6 个维度 + 推荐等级
  - 排序模块顶部展示评分公式和免责说明
- [x] 更新所有文档至 v0.8.0

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/ranker.py` | 重写（v2.0，~330 行） |
| `app.py` | 修改（维度展示 + 公式说明） |
| `README.md` | 修改（v0.8.0，六维评分） |
| `docs/design.md` | 修改（新增 Ranking Design 章节） |
| `docs/limitations.md` | 修改（新增排序限制 + 修正问答行） |
| `docs/iteration_log.md` | 修改（新增 v0.8.0） |

### 验收结果

### 已知问题

无。

---

## Version 0.9.0 — 关注领域追踪与最新论文发现（2026-06-07）

### 新增
- 关注领域管理（新增/编辑/删除/启用/停用）
- 一键刷新单个或所有启用领域的最新 arXiv 论文
- 论文去重（arXiv ID + title hash fallback）
- 新论文识别与标记
- 论文状态管理（unread/reading/read/starred/ignored）
- 本地 JSON 持久化（watchlist.json / paper_history.json / tracker_state.json）
- 追踪论文筛选与排序
- Markdown 笔记集成追踪摘要

### 修改文件
`modules/tracker_store.py`（新）、`modules/paper_tracker.py`（新）、`modules/arxiv_client.py`（categories）、`modules/note_generator.py`（tracker_summary）、`app.py`（追踪 Tab）、README/design/iteration demo_script/limitations 文档更新

### 限制
手动刷新、本地存储、不含 Reviewer/趋势/图谱/综述

---

## Version 1.0：Reviewer 视角分析（2026-06-07）

### 新增
- 支持基于搜索结果/追踪论文/上传 PDF 生成 Reviewer 分析
- 优点/不足/创新性/方法/实验/风险/审稿倾向分析
- 审稿人追问问题生成 + 接收风险标记
- LLM 模式和 Fallback 模式双支持
- 证据片段提取与展示
- Reviewer 分析写入 Markdown 笔记
- 新增「🔍 Reviewer 分析」Tab

### 修改文件
`modules/reviewer.py`（新）、`app.py`（Tab 3）、`modules/note_generator.py`（reviewer_result）、README/design/iteration/demo_script/limitations/prompts 文档更新

### 限制
- 分析仅为辅助参考，不代表正式审稿意见
- Fallback 模式较模板化
- PDF 文本不足时置信度降低
- 不包含趋势分析、关系图谱、文献综述

---


## Version 1.2.3 — Reviewer 状态隔离与笔记一致性补丁（2026-06-07）

### 阶段目标

修复 Reviewer Tab 覆盖 current_paper、manual_pdf 绑定、笔记生成一致性、QA fallback 返回结构等稳定性问题。本轮只修 bug，不做新功能。

### 已完成内容

- [x] **Reviewer Tab 状态隔离**
  - 删除 `_set_current_paper(selected_rev, source="reviewer")`，Reviewer Tab 不再修改 current_paper/current_paper_id
  - 新增 `_get_pdf_context_for_paper_id()` helper，Reviewer Tab 使用局部 selected_rev/selected_rev_id
  - Reviewer 分析使用 `reviewer_paper_id` 记录归属，不依赖 current_paper_id
- [x] **manual_pdf 稳定 ID**
  - `paper_identity.py` 中 `get_paper_id()` 新增 manual_pdf 特殊处理
  - Reviewer Tab "当前上传 PDF" 场景下正确保留 manual_pdf id
- [x] **summary selectbox 同步**
  - selectbox 切换论文后同步 `st.session_state.selected_paper`
- [x] **笔记生成一致性**
  - 以 `current_paper`/`current_paper_id` 为笔记主来源
  - 按 `note_paper_id` 严格过滤 summary/QA/Reviewer
  - manual_pdf 场景下构造展示用 paper dict
- [x] **QA fallback 返回结构补全**
  - fallback 返回中新增 `evidence_chunks` 字段
  - `_fallback_qa` 的 has_pdf 判断从 `pdf_text is not None` 改为 `bool(pdf_text) or bool(relevant)`
  - 只传 chunks 不传 paper_text 时不再误判"未上传 PDF"
- [x] **文档同步**：README、design、iteration、limitations、demo_script 更新至 v1.2.3

### 修改文件

| 文件 | 操作 |
|------|------|
| `app.py` | 修改（Reviewer Tab 状态隔离、summary selectbox 同步、笔记生成一致性、版本号） |
| `modules/paper_identity.py` | 修改（manual_pdf 特殊处理） |
| `modules/qa_engine.py` | 修改（evidence_chunks、has_pdf 检测） |
| `README.md` | 修改（v1.2.3） |
| `docs/design.md` | 修改（状态隔离设计章节） |
| `docs/iteration_log.md` | 修改（新增 v1.2.3） |
| `docs/limitations.md` | 修改（补充状态隔离说明） |
| `docs/demo_script.md` | 修改（新增稳定性演示场景） |

### 已知问题

无新增已知问题。


---




## Version 1.4.0 — 论文关系图谱（2026-06-07）

### 阶段目标

新增论文关系图谱功能，基于元信息和相似度构建论文间关系网络，支持 Graphviz 可视化。

### 已完成内容

- [x] 创建 `modules/paper_graph.py`：关系图谱模块
  - `build_paper_graph()` — 总入口
  - `collect_graph_papers()` — 多来源 + get_paper_id 去重
  - `_build_nodes()` — 节点选择（score/date 优先级）
  - `_build_edges()` — 四种边类型（content/category/author/reference）
  - `_find_clusters()` — DFS 连通分量
  - `_find_central_papers()` — 加权度中心性
  - `_generate_dot()` — Graphviz DOT 生成
  - `_generate_graph_summary()` — 中文图谱总结
- [x] `app.py` 新增「🕸️ 关系图谱」Tab
  - 三来源切换
  - 参数调节（max_nodes, min_similarity, 边类型开关）
  - Graphviz 图展示（失败降级 DOT 源码）
  - 中心论文 / 主题簇 / 边表 / 节点表
  - 状态隔离
- [x] 文档更新至 v1.5.0

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/paper_graph.py` | 新建（~540 行） |
| `app.py` | 修改（tab6、图谱 UI、版本号） |
| `README.md` | 修改（v1.5.0） |
| `docs/design.md` | 修改（新增关系图谱设计章节） |
| `docs/iteration_log.md` | 修改（新增 v1.5.0） |
| `docs/limitations.md` | 修改（补充图谱限制） |
| `docs/demo_script.md` | 修改（新增图谱演示） |


---

## Version 1.3.1 — 趋势分析 UI 与文档一致性补丁（2026-06-07）

### 阶段目标

修复 v1.3.0 中趋势分析 Tab 重复展示、UI 展示不存在字段、数据源不兼容搜索结果、recent_months 参数未生效的问题。

### 已完成内容

- [x] 删除趋势分析 Tab 重复展示块（分类分布、代表论文、warnings 不再重复）
- [x] 删除不存在的 UI 字段展示（emerging_keywords、topic_buckets、interpretation）
- [x] 当前搜索/排序结果同时兼容 ranked_papers、papers、search_results
- [x] 合并分析同时使用 ranked_papers + papers + search_results + tracking_history
- [x] `_analyze_emerging_topics` 按 recent_months 窗口切分（不足时回退前后半段）
- [x] 文档与实际返回结构一致：删除 analyze_topic_buckets / generate_trend_interpretation 描述

### 修改文件

| 文件 | 操作 |
|------|------|
| `app.py` | 修改（删除重复展示、数据源兼容、版本号 v1.3.1） |
| `modules/trend_analyzer.py` | 修改（_analyze_emerging_topics 使用 recent_months 窗口） |
| `README.md` | 修改（v1.3.1） |
| `docs/design.md` | 修改（删除 fake 函数描述） |
| `docs/iteration_log.md` | 修改（新增 v1.3.1） |


---

## Version 1.3.0 — 研究趋势分析（2026-06-07）

### 阶段目标

新增研究趋势分析功能，支持热门关键词、时间分布、分类分布、新兴关键词、主题桶和代表论文展示。

### 已完成内容

- [x] 创建 `modules/trend_analyzer.py`：纯数据分析模块
  - `normalize_paper_for_trend()` — 字段归一化
  - `collect_trend_papers()` — 多来源收集 + 去重
  - `extract_keywords()` — unigram/bigram 关键词统计
  - `analyze_time_distribution()` — 按月/年分布
  - `analyze_category_distribution()` — arXiv 分类分布
  - `analyze_emerging_keywords()` — 新兴关键词识别
  - `analyze_topic_buckets()` — 10 主题桶归类
  - `select_representative_papers()` — 代表论文
  - `generate_trend_interpretation()` — 中文趋势解读
  - `analyze_research_trends()` — 总入口
- [x] `app.py` 新增「📈 趋势分析」Tab
  - 三来源切换：搜索/排序结果、追踪历史、合并分析
  - 总览指标（论文数、时间跨度、分类数、热门/新兴关键词）
  - 时间分布柱状图
  - 热门关键词表格
  - 新兴关键词表格
  - 分类分布表格 + 柱状图
  - 主题桶 expander（含代表论文）
  - 代表论文表格
  - 趋势解读
  - 状态隔离：不修改 current_paper/pdf/summary/QA/Reviewer
- [x] 文档更新至 v1.3.0

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/trend_analyzer.py` | 新建（~820 行） |
| `app.py` | 修改（新增 tab5、趋势分析 UI、版本号） |
| `README.md` | 修改（v1.3.0） |
| `docs/design.md` | 修改（新增趋势分析设计章节） |
| `docs/iteration_log.md` | 修改（新增 v1.3.0） |
| `docs/limitations.md` | 修改（补充趋势分析限制） |
| `docs/demo_script.md` | 修改（新增趋势分析演示） |


---

## Version 1.6.4：深入了解模式与权威发表信号补丁（2026-06-08）

### 阶段目标

在不接外部数据库、不做真实引用/venue 分析、不重构主流程的前提下，新增“深入了解模式”。该模式用于帮助用户筛选适合作为精读、复现、方法对比或后续研究问题挖掘的候选论文。

### 已完成内容

- [x] `rank_papers()` 新增 `mode="deep"`，并兼容旧别名 `deep_research`，默认 `frontier` 调用保持兼容
- [x] 新增深入了解模式，用于筛选值得精读、复现和批判分析的候选论文
- [x] 在深入了解模式中加入权威发表信号，包括会议、期刊、proceedings、DOI 等启发式判断
- [x] 加强方法完整性、实验充分性、baseline、ablation、可复现和 limitation 信号
- [x] 增加深入阅读推荐理由，提升排序可解释性
- [x] 保留 arXiv-only 论文作为候选，不因缺少正式发表信息而直接排除
- [x] 新增 `deep_reading_role`：重点精读候选、复现候选、方法对比候选、研究空白候选、深入阅读候选
- [x] 新增保守推荐理由，明确所有判断均为标题、摘要和 arXiv 元信息启发式信号
- [x] 新增 `search_deep_research_papers()`，使用 method framework、benchmark evaluation、ablation comparison、code implementation 等 relevance 扩展搜索
- [x] `app.py` 阅读模式扩展为前沿追踪、领域了解、深入了解三种模式
- [x] 深入了解模式显示独立评分公式和结果指标
- [x] 更新 README、design、demo_script、limitations、project_thinking、iteration_log 文档

### 设计边界

- 不接 Semantic Scholar、OpenAlex、DBLP、Google Scholar
- 不做真实 citation count、h-index、venue ranking
- 不读取 PDF 全文做排序
- 不修改 PDF、QA、Reviewer、趋势、图谱、综述等下游状态逻辑

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/ranker.py` | 修改（新增 deep / 深入了解评分路径） |
| `modules/arxiv_client.py` | 修改（新增深入了解扩展搜索） |
| `app.py` | 修改（三模式选择、搜索、排序、展示） |
| `README.md` | 修改（v1.6.4 说明） |
| `docs/design.md` | 修改（三种阅读意图设计） |
| `docs/demo_script.md` | 修改（深入了解演示场景） |
| `docs/limitations.md` | 修改（深入了解限制） |
| `docs/project_thinking.md` | 修改（深入了解阶段说明） |
| `docs/iteration_log.md` | 修改（新增本节） |

---

## Version 1.6.5：深入了解模式相关性门控补丁（2026-06-08）

### 阶段目标

修复深入了解模式中质量信号可能压过查询相关性的问题，落实“先相关、再深入”的排序约束。该补丁不新增外部数据库、不做真实引用或 venue 验证，只调整搜索召回过滤、deep 排序门控和解释文案。

### 已完成内容

- [x] 新增 `expand_query_terms()` 和 `score_query_relevance()`，统一搜索召回与 deep 排序的查询相关性判断
- [x] 为 `4dvar` 增加 `4D-Var`、`four-dimensional variational`、`variational data assimilation`、`data assimilation` 等轻量主题扩展
- [x] `search_deep_research_papers()` 对扩展搜索结果先做 query relevance 过滤，零相关论文不进入结果，弱相关论文只作为尾部兜底
- [x] 深入了解排序拆分为 `deep_quality_score` 和 query relevance gate，避免 benchmark / evaluation / ablation / venue 等质量信号单独推高无关论文
- [x] `score_relevance` 在 deep 模式下改为 query relevance × 100，排序解释优先说明查询相关性
- [x] 共同术语/路线代表性只从 query-relevant 论文中抽取，并补充泛化停用词，减少 benchmark/evaluation 等词污染
- [x] `app.py` 原始搜索结果和 deep 排序结果展示查询相关性门控、命中主题词和弱相关提示
- [x] 更新 README、design、demo_script、limitations、iteration_log 文档

### 设计边界

- 不接 Semantic Scholar、OpenAlex、DBLP、Google Scholar
- 不做真实 citation count、h-index、venue ranking
- 不做语义检索或 RAG
- 不修改 PDF、QA、Reviewer、趋势、图谱、综述等下游状态逻辑
- 相关性门控是启发式信号，不代表系统能完整识别所有同义词或真实论文质量

### 修改文件

| 文件 | 操作 |
|------|------|
| `modules/ranker.py` | 修改（新增 query relevance、deep gate、弱相关解释） |
| `modules/arxiv_client.py` | 修改（深入了解搜索召回过滤） |
| `app.py` | 修改（v1.6.5 文案、query relevance 展示） |
| `README.md` | 修改（v1.6.5 说明） |
| `docs/design.md` | 修改（先相关、再深入两阶段设计） |
| `docs/demo_script.md` | 修改（4dvar 相关性门控演示） |
| `docs/limitations.md` | 修改（相关性门控限制） |
| `docs/iteration_log.md` | 修改（新增本节） |

---

## 版本历史

| 版本 | 日期 | 内容 |
|------|------|------|
| v1.6.5 | 2026-06-08 | 深入了解模式相关性门控补丁 |
| v1.6.4 | 2026-06-08 | 深入了解模式与权威发表信号补丁 |
| v1.5.0 | 2026-06-07 | 论文关系图谱 |
| v1.3.1 | 2026-06-07 | 趋势分析 UI 与文档一致性补丁 |
| v1.3.0 | 2026-06-07 | 研究趋势分析 |
| v1.2.3 | 2026-06-07 | Reviewer 状态隔离与笔记一致性补丁 |
| v0.9.0 | 2026-06-07 | 关注领域追踪与最新论文发现 |
| v0.8.0 | 2026-06-07 | 排序重构：六维阅读优先级评分 |
| v0.7.0 | 2026-06-07 | 论文问答 |
| v0.6.0 | 2026-06-07 | PDF 上传与解析 |
| v0.5.1 | 2026-06-07 | 稳定性与安全修复 |
| v0.5 | 2026-06-07 | 简易 Markdown 阅读笔记生成 |
| v0.4 | 2026-06-06 | 结构化总结 |
| v0.3 | 2026-06-06 | 论文排序闭环 |
| v0.2 | 2026-06-06 | 论文发现闭环 |
| v0.1 | 2026-06-06 | 项目骨架建立 |
