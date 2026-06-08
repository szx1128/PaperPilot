# PaperPilot 演示脚本

> 版本：v1.6.6 | 最后更新：2026-06-08

本文档描述 PaperPilot 当前版本（v1.6.6）的完整演示流程。

---

## 演示准备

1. 安装依赖：`pip install -r requirements.txt`
2. 配置环境变量（可选）：`cp .env.example .env` 并填入 LLM API Key
3. 准备一篇 arXiv 论文的 PDF 文件（可选，用于 PDF 增强演示）
4. 启动：`cd paperpilot && streamlit run app.py`
5. 打开浏览器访问 `http://localhost:8501`

---

## 场景：在线 Demo 部署说明（v1.6.6 新增）

1. 说明项目入口是 `streamlit run app.py`，因此适合部署到 Streamlit Community Cloud。
2. 展示仓库中的部署文件：`requirements.txt`、`runtime.txt`、`.streamlit/config.toml`、`.env.example`、`docs/deployment.md`。
3. 强调 `.env` 和 `.streamlit/secrets.toml` 不会提交到仓库，真实 API Key 应通过 Streamlit Cloud Secrets 配置。
4. 说明没有 API Key 时系统不会崩溃，会进入基础模式：搜索、排序、PDF 解析和规则分析仍可演示，LLM 摘要、问答、Reviewer 等能力会降级或提示配置。
5. 如果尚未获得公开链接，明确说明：当前已完成部署适配，下一步需要人工推送 GitHub 并在 Streamlit Community Cloud 选择 `app.py` 部署。

答辩话术：

> 本轮我做的是可运行 Demo 的部署适配，而不是继续堆功能。PaperPilot 保持 Streamlit 单入口，考核方可以本地用 `streamlit run app.py` 运行，也可以把仓库部署到 Streamlit Community Cloud。API Key 不写入代码和仓库，而是本地 `.env` 或云端 Secrets 管理；没有 Key 时系统会进入基础模式，保证 Demo 不会因为密钥缺失直接崩溃。

---

## 场景 A：论文搜索与阅读（完整流程）

1. 在「📖 论文阅读」Tab 中，输入关键词搜索（例如：`large language model reasoning`）
2. 如果 arXiv 不可用，点击「使用内置示例论文继续演示」
3. 排序：选择 Top K，点击「对搜索结果排序」，查看六维评分和推荐理由
4. 总结：选择一篇论文，点击「生成结构化总结」，查看 7 字段中文总结
5. PDF：上传对应论文的 PDF，点击「解析 PDF」，查看页数和文本预览
6. 返回步骤 3 重新生成总结，观察「✅ 已结合 PDF 文本」提示
7. QA：进入步骤 5，输入问题（例如：「这篇论文的主要创新点是什么？」），查看回答和引用片段
8. 笔记：进入步骤 6，生成 Markdown 笔记，预览并下载

> 📸 截图：`screenshots/01_reading_workflow.png`

---

## 场景：领域了解模式演示（v1.6.3 新增）

1. 输入一个研究方向，例如 `large language model reasoning`。
2. 在阅读模式中选择“领域了解模式”。
3. 说明该模式不是为了找最新论文，而是为了建立领域知识框架。
4. 点击搜索，系统会自动扩展 survey、review、benchmark、taxonomy、evaluation 等查询。
5. 点击排序，展示领域了解分。
6. 重点讲解排序维度：
   - 综述/路线价值；
   - 经典/代表性信号；
   - 权威元信息信号；
   - 问题定义清晰度；
   - 方法覆盖度；
   - Benchmark/Dataset 价值；
   - 新鲜度只占很低权重。
7. 展示一篇推荐论文，并说明为什么它适合作为领域入口。
8. 强调：该模式中的经典性和权威性是基于当前元信息的启发式判断，仍需人工结合引用、venue 和领域背景确认。

答辩话术：

> 我最开始的系统更偏前沿追踪，因为 arXiv 搜索天然偏最新论文。但后来我意识到，科研阅读存在不同阶段。刚进入一个领域时，用户并不一定需要最新论文，而是需要知道这个领域研究什么、经典工作有哪些、主流方法路线是什么、常用 benchmark 是什么。因此我新增了领域了解模式，把排序目标从“找最新论文”调整为“建立领域知识框架”。

---

## 场景：深入了解模式演示（v1.6.4 新增）

1. 搜索一个研究方向，例如 `retrieval augmented generation` 或 `large language model reasoning`。
2. 在阅读模式中选择“深入了解模式”。
3. 观察排序结果不再只按最新论文靠前，而是优先推荐方法完整、实验充分、适合精读的论文。
4. 点击搜索，系统会自动扩展 method framework、benchmark evaluation、ablation comparison、code implementation 等查询。
5. 点击排序，展示深入了解分。
6. 重点讲解排序维度：
   - 主题相关性；
   - 贡献价值；
   - 问题定义清晰度；
   - 方法完整性；
   - 证据充分性；
   - 权威发表信号；
   - 可复现性信号；
   - 方法路线代表性；
   - 局限与讨论信号；
   - 新鲜度只占很低权重。
7. 展示某篇论文的深入阅读推荐理由，例如：
   - 是否有权威发表信息；
   - 是否有 framework / architecture 等方法信号；
   - 是否有 evaluation / benchmark / baseline 等实验信号；
   - 是否有 ablation / analysis 等深入分析信号；
   - 是否有 code / dataset 等可复现信号。
8. 说明该模式适合用户已经了解领域后，进一步选择精读论文、复现对象和相关工作分析对象。
9. 强调：该模式中的权威发表、可复现性和路线代表性判断都只是基于标题、摘要和 arXiv 元信息的启发式信号，不代表真实 citation、真实 venue 等级或真实论文质量。

答辩话术：

> 这个模式体现的是科研阅读中的“精读筛选”环节。系统不是简单推荐最新论文，而是结合方法完整性、实验充分性、可复现信号和发表可信度，帮助用户判断哪些论文更值得深入阅读。权威发表信息只是加分项，不是一票否决项；没有 venue 信息的 arXiv 论文仍然可以作为候选。

---

## 场景：深入了解模式相关性门控演示（v1.6.5 新增）

1. 搜索一个窄方向，例如 `4dvar`。
2. 在阅读模式中选择“深入了解模式”。
3. 说明该模式现在采用“先相关、再深入”：先判断论文是否命中 `4D-Var`、`four-dimensional variational`、`variational data assimilation`、`data assimilation` 等主题表达，再看方法、实验、venue 和可复现信号。
4. 点击搜索，观察原始搜索结果中显示“查询相关性门控”和命中主题词。
5. 点击排序，确认 4D-Var / variational data assimilation 相关论文排在前面。
6. 说明 benchmark / evaluation / ablation 是质量信号，不会单独作为 `4dvar` 相关性证据。
7. 展示弱相关或低相关论文的推荐理由，强调系统会提示“相关性弱，已被降权”，而不是把它描述成高度适合深入阅读。

答辩话术：

> v1.6.5 修复的是深入了解模式中的一个排序偏差：以前质量信号只要很强，比如 benchmark、ablation、venue，就可能压过用户真正输入的研究方向。现在系统先做 query relevance gate，让论文先和 `4dvar` 这种具体方向建立主题匹配，再让实验充分性、方法完整性和发表信号参与排序。这仍然是启发式过滤，不代表系统能替代人工判断论文质量。

---

## 场景 B：关注领域追踪（v0.9 新增）

1. 切换到「📡 关注追踪」Tab
2. 新增关注领域：
   - 名称：`Large Language Model Agents`
   - 关键词：`"large language model" AND agent`
   - 分类（可选）：`cs.CL, cs.AI`
   - 数量：10
   - 点击「✅ 新增关注领域」
3. 新增第二个领域：取消勾选「启用」可创建暂停状态
4. 在关注领域列表中：
   - 点击「🔄 刷新所有启用领域」，观察 Spinner 和刷新结果统计
   - 点击单个领域的刷新按钮，观察单领域刷新
   - 点击「⏸️ 停用」切换启用状态
   - 点击「✏️ 编辑」修改领域参数
   - 点击「🗑️ 删除」，确认二次确认流程
5. 查看新发现论文：
   - 刷新后观察「新发现 N 篇」
   - 再次刷新同一领域，验证新发现数为 0（不重复显示旧论文）
6. 筛选：
   - 按领域筛选
   - 按状态筛选
   - 勾选「仅新发现」
   - 在关键词搜索框中输入作者名或来源领域名称
7. 状态管理：
   - 将多篇论文分别标记为 `starred`、`reading`、`read`
   - 刷新后验证状态不丢失
8. 笔记集成：
   - 切换到「📖 论文阅读」Tab
   - 搜索、排序、选择论文、生成总结
   - 生成 Markdown 笔记
   - 查看笔记中的「关注追踪摘要」章节（含统计概览和新发现论文）

> 📸 截图：`screenshots/02_tracker_workflow.png`

---

## 场景 C：纯 Fallback 降级演示

1. 删除 `.env` 文件（模拟无 LLM API Key）
2. 断开网络（模拟 arXiv 不可用）
3. 使用内置示例论文完成搜索 → 排序 → 总结（模板模式） → 笔记
4. 验证系统在任何配置下均不崩溃

> 📸 截图：`screenshots/03_fallback_demo.png`

---

## 场景 D：Reviewer 视角分析（v1.0 新增）

1. 切换到「🔍 Reviewer 分析」Tab
2. 选择分析来源：「当前搜索结果」（需先在论文阅读中搜索并排序）
3. 从下拉框中选择一篇论文
4. 点击「生成 Reviewer 分析」
5. 查看结构化分析：总体评价、优点、不足、创新性、方法、实验、风险
6. 查看审稿人可能追问的问题列表
7. 查看模拟接收倾向（decision + score）
8. 展开依据片段
9. 切换到「关注追踪」Tab，刷新论文
10. 回到 Reviewer Tab，选择「关注追踪历史」来源，选择追踪论文进行分析
11. 回到「论文阅读」Tab，生成 Markdown 笔记
12. 查看笔记中「Reviewer 视角分析」章节

> 📸 截图：`screenshots/04_reviewer_workflow.png`

---


## 场景 E：状态隔离稳定性演示（v1.2.3 新增）

1. 搜索论文 A，在论文阅读 Tab 选择论文 A
2. 切到 Reviewer Tab，选择论文 B
3. 生成 Reviewer 分析
4. 返回论文阅读 Tab，确认当前论文仍是 A（current_paper_id 没变）
5. 只上传 PDF，不选择 arXiv 论文
6. 确认 current_paper_id 和 pdf_bound_paper_id 都是 manual_pdf
7. 进入 Reviewer Tab，选择"当前上传 PDF"
8. 生成 Reviewer，确认 reviewer_paper_id 是 manual_pdf，current_paper_id 没变
9. 切换 summary selectbox 到论文 B
10. 生成 Markdown 笔记，确认不会混入论文 A 的 summary、QA、Reviewer
11. 调用 QA，确认 evidence_chunks 存在且不误报"未上传 PDF"

> 📸 截图：`screenshots/05_stability_demo.png`

---


## 场景 F：研究趋势分析演示（v1.6.2 新增）

1. 搜索一个研究方向，例如 `retrieval augmented generation` 或 `large language model agent`
2. 查看排序结果
3. 进入「📈 趋势分析」Tab
4. 选择"当前搜索/排序结果"
5. 生成趋势分析
6. 展示热门关键词
7. 展示时间分布
8. 展示分类分布
9. 10. 展示趋势解读
11. 切换到"关注追踪历史"或"合并分析"
12. 说明趋势分析不会改变当前阅读论文、PDF 绑定、summary、QA、Reviewer

> 📸 截图：`screenshots/06_trend_analysis.png`

---


## 场景 G：论文关系图谱演示（v1.6.2 新增）

1. 搜索 large language model
2. 获取或排序论文（至少 5 篇）
3. 进入「🕸️ 关系图谱」Tab
4. 选择"当前搜索/排序结果"
5. 设置最大节点数 20
6. 生成图谱
7. 展示 Graphviz 关系图
8. 展示中心论文列表
9. 展示主题簇
10. 展示边表（关系类型 + 原因）
11. 展示节点表
12. 切回论文阅读 Tab，确认 current_paper_id 没有被图谱改变

---

## 预期演示时长

约 40-45 分钟（含领域了解模式、深入了解模式和 7 种原有场景切换）
