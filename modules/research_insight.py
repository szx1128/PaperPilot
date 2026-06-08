"""
PaperPilot 科研洞察与后续选题建议模块。

基于当前论文集合、趋势分析、关系图谱和文献综述结果，
生成启发式科研洞察，帮助梳理研究问题、方法路线、代表论文、
研究空白与后续阅读方向。

仅做轻量规则化分析，不引入大型依赖。
所有输出保守表达，不代表完整领域结论。
"""

from collections import Counter


def generate_research_insight(
    papers,
    trend_result=None,
    graph_result=None,
    literature_review_result=None,
    max_papers=12,
):
    """主入口。生成科研洞察与后续选题建议。"""
    # 洞察模块整合趋势、图谱、综述结果，但仍然是启发式建议，不替代专家选题判断。
    if not papers:
        return {
            "field_problem": "",
            "main_method_routes": [],
            "representative_papers": [],
            "research_gaps": ["请先搜索论文或刷新关注领域后再生成科研洞察。"],
            "potential_questions": [],
            "next_reading_plan": [],
            "confidence_notes": ["当前无可用的论文数据。"],
            "used_paper_count": 0,
            "paper_count": 0,
            "markdown": "",
            "mode": "heuristic",
        }

    # 先把论文集合压缩到高分候选，避免低质量或弱相关样本主导后续建议。
    normalized = _normalize_for_insight(papers, max_papers)
    used = len(normalized)

    hot_topics = _extract_hot_topics(trend_result)
    keywords = _extract_keywords(normalized, top_k=8)
    field_problem = _build_field_problem(normalized, trend_result, hot_topics, keywords)
    method_routes = _build_method_routes(normalized, hot_topics, keywords)
    rep_papers = _select_rep_papers(normalized, graph_result, hot_topics)
    gaps = _build_gaps(normalized, literature_review_result)
    questions = _build_questions(normalized, gaps, keywords)
    reading_plan = _build_reading_plan(rep_papers, gaps)
    confidence = _build_confidence_notes()
    md = _build_markdown(field_problem, method_routes, rep_papers, gaps, questions, reading_plan, confidence, used, len(papers))

    return {
        "field_problem": field_problem,
        "main_method_routes": method_routes,
        "representative_papers": rep_papers,
        "research_gaps": gaps,
        "potential_questions": questions,
        "next_reading_plan": reading_plan,
        "confidence_notes": confidence,
        "used_paper_count": used,
        "paper_count": len(papers),
        "markdown": md,
        "mode": "heuristic",
    }


# ── 内部工具 ──────────────────────────────────────────────

def _safe_text(val):
    return str(val) if val else ""


def _get_title(paper):
    return paper.get("title") or "Untitled"


def _get_abstract(paper):
    return paper.get("abstract") or paper.get("summary") or ""


def _get_paper_id_safe(paper):
    try:
        from modules.paper_identity import get_paper_id
        return get_paper_id(paper)
    except ImportError:
        return paper.get("paper_id") or paper.get("arxiv_id") or paper.get("id") or ""


def _get_score(paper):
    return paper.get("rank_score") or paper.get("total_score") or paper.get("score") or paper.get("final_score") or 0


# ── 论文规范化 ────────────────────────────────────────────

def _normalize_for_insight(papers, max_papers):
    # 多来源论文统一字段并去重；洞察只关心标题、摘要、分数和稳定 paper_id。
    seen = set()
    result = []
    for p in papers:
        pid = _get_paper_id_safe(p)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        result.append({
            "title": _get_title(p),
            "abstract": _get_abstract(p),
            "paper_id": pid,
            "score": _get_score(p),
            "authors": p.get("authors") or [],
            "published": p.get("published") or "",
        })
    result.sort(key=lambda x: x["score"] or 0, reverse=True)
    return result[:max_papers]


# ── 关键词提取 ────────────────────────────────────────────

TECH_TERMS = [
    "retrieval", "reasoning", "benchmark", "evaluation", "alignment",
    "agent", "multimodal", "graph", "efficient", "robust",
    "generalization", "safety", "interpretable", "scalable",
    "fine-tuning", "instruction", "chain-of-thought", "planning",
    "knowledge", "question answering", "summarization",
]

METHOD_KEYWORDS = {
    "检索增强": ["retrieval", "rag", "retrieve", "retriever"],
    "推理增强": ["reasoning", "chain-of-thought", "cot", "planning"],
    "评测基准": ["benchmark", "evaluation", "eval", "dataset"],
    "智能体方法": ["agent", "tool use", "planning"],
    "多模态方法": ["multimodal", "vision-language", "image", "video"],
    "图方法": ["graph", "knowledge graph", "gnn"],
    "高效训练": ["efficient", "fine-tuning", "lora", "distillation"],
    "对齐与安全": ["alignment", "safety", "preference", "rlhf"],
}


def _extract_keywords(papers, top_k=10):
    # 只统计少量技术词，目的是给洞察生成“方向线索”，不是完整关键词抽取。
    counter = Counter()
    for p in papers:
        text = (p["title"] + " " + p["abstract"]).lower()
        for term in TECH_TERMS:
            if term in text:
                counter[term] += 1
    return [w for w, _ in counter.most_common(top_k)]


def _extract_hot_topics(trend_result):
    if not trend_result:
        return []
    hot = trend_result.get("hot_topics") or []
    result = []
    for h in hot:
        if isinstance(h, dict):
            name = h.get("topic") or h.get("keyword") or ""
            if name:
                result.append(str(name))
        elif isinstance(h, str):
            result.append(h)
    return result


# ── 内容生成 ──────────────────────────────────────────────

def _build_field_problem(papers, trend_result, hot_topics, keywords):
    # 如果趋势模块已有摘要，优先复用，保证不同模块输出口径一致。
    if trend_result and trend_result.get("trend_summary"):
        return trend_result.get("trend_summary")[:300]

    kw_str = "、".join(keywords[:4]) if keywords else "多个技术方向"
    count = len(papers)
    return f"从当前 {count} 篇论文样本看，该方向主要围绕 {kw_str} 等主题展开，核心问题涉及模型可靠性、可解释性和泛化能力的提升。"


def _build_method_routes(papers, hot_topics, keywords):
    # 方法路线根据关键词家族匹配，输出时附带相关论文作为证据。
    routes = []
    combined_text = " ".join(p["title"] + " " + p["abstract"] for p in papers).lower()
    for route_name, route_kws in METHOD_KEYWORDS.items():
        if any(kw in combined_text for kw in route_kws):
            evidence_papers = []
            for p in papers:
                pt = (p["title"] + " " + p["abstract"]).lower()
                if any(kw in pt for kw in route_kws):
                    evidence_papers.append(p["title"][:80])
                    if len(evidence_papers) >= 2:
                        break
            routes.append({
                "route": route_name,
                "evidence": f"当前样本中检测到 {route_name} 相关关键词和论文。",
                "related_papers": evidence_papers,
            })
    return routes


def _select_rep_papers(papers, graph_result, hot_topics, limit=5):
    # 优先关系图谱中心论文
    central_ids = set()
    if graph_result:
        for cp in (graph_result.get("central_papers") or []):
            cid = cp.get("paper_id") or cp.get("id") or ""
            if cid:
                central_ids.add(cid)

    result = []
    # 中心论文优先：图谱中心代表“当前样本中连接较多”，不是引用量最高。
    for p in papers:
        if p["paper_id"] in central_ids and len(result) < limit:
            result.append({
                "title": p["title"],
                "paper_id": p["paper_id"],
                "reason": "该论文在关系图谱中处于中心位置，可能是当前样本中的关键连接点。",
            })
    # 高分论文补足，保证没有图谱中心时仍能给出可精读候选。
    for p in papers:
        if p["paper_id"] not in {r["paper_id"] for r in result} and len(result) < limit:
            score = p.get("score") or 0
            if score > 0:
                result.append({
                    "title": p["title"],
                    "paper_id": p["paper_id"],
                    "reason": f"在当前样本中评分较高，适合作为精读对象。",
                })
    # 再补足
    for p in papers:
        if p["paper_id"] not in {r["paper_id"] for r in result} and len(result) < min(limit, 3):
            result.append({
                "title": p["title"],
                "paper_id": p["paper_id"],
                "reason": "该论文标题和摘要与当前热点主题重合较多，适合作为后续精读对象。",
            })
    return result


def _build_gaps(papers, lit_review):
    # 优先使用文献综述已有结果，减少模块之间对“研究空白”的重复判断。
    if lit_review and lit_review.get("research_gaps"):
        return lit_review["research_gaps"][:5]

    all_text = " ".join((p.get("abstract") or "") + (p.get("title") or "") for p in papers).lower()
    gaps = []
    if "evaluation" not in all_text and "benchmark" not in all_text:
        gaps.append("当前样本中系统性评测和标准基准相关讨论相对不足，建议结合评测维度进一步分析。")
    if "generalization" not in all_text and "robust" not in all_text:
        gaps.append("当前样本中泛化性与鲁棒性的验证线索较少，后续可关注跨数据集验证。")
    if "alignment" not in all_text and "safety" not in all_text:
        gaps.append("对齐与安全性讨论在现有样本中出现频率较低，值得作为后续关注方向。")
    gaps.append("不同方法路线之间的系统性对比和统一框架设计仍值得进一步探索。")
    if len(papers) < 5:
        gaps.append("当前样本量较小，研究空白的判断仅供参考，建议扩大文献检索范围。")
    return gaps[:5]


def _build_questions(papers, gaps, keywords):
    questions = []
    kw = keywords[:4] if keywords else ["retrieval", "reasoning"]
    questions.append(f"当前{kw[0]}方法的可靠性和效率是否可以在不同场景下保持一致？")
    if len(kw) > 1:
        questions.append(f"{kw[0]}与{kw[1]}的结合是否能产生更好的综合效果？")
    questions.append("从当前样本看，是否存在尚未被充分探索的交叉方向？")
    questions.append("当前主流方法在真实部署中的鲁棒性和可维护性如何？")
    if len(papers) < 5:
        questions.append("是否需要扩大文献覆盖范围以获得更全面的研究问题视角？")
    return questions[:5]


def _build_reading_plan(rep_papers, gaps):
    # 阅读计划只给轻量顺序建议，不生成复杂路径图。
    plan = []
    plan.append("先精读当前样本中的代表性论文，明确该方向的基本问题定义和研究框架。")
    plan.append("按方法路线分组阅读，了解不同技术路线的设计思路和关键贡献。")
    plan.append("对比代表性论文的实验设置和评价指标，关注跨论文的系统性对比。")
    if gaps and len(gaps) > 2:
        plan.append("结合识别到的研究空白，评估是否有值得进一步验证的方向。")
    plan.append("整理阅读笔记后，可以重新调用科研洞察功能获取更精确的后续选题线索。")
    return plan[:5]


def _build_confidence_notes():
    return [
        "本分析基于当前导入、搜索或追踪到的论文集合自动生成，不代表完整领域结论。",
        "论文关系图谱如被使用，仅作为启发式相似度参考，不等同于真实引用网络。",
        "研究空白和后续问题为辅助阅读和选题思考线索，仍需人工结合领域背景验证。",
        "建议结合人工精读和领域专家判断，不要仅依赖系统输出做出选题决策。",
    ]


# ── Markdown 生成 ─────────────────────────────────────────

def _build_markdown(field_problem, method_routes, rep_papers, gaps, questions, reading_plan, confidence, used, total):
    lines = [
        "# 科研洞察与后续选题建议",
        "",
        "> 本分析基于当前论文集合自动生成，仅作为科研阅读和选题思考的启发式参考，不代表完整领域结论。",
        "",
        f"**样本数量：** {used}/{total} 篇",
        "",
        "## 1. 核心研究问题",
        "",
        field_problem,
        "",
        "## 2. 主流方法路线",
        "",
    ]
    for mr in method_routes:
        lines.append(f"### {mr['route']}")
        lines.append(f"- 依据：{mr['evidence']}")
        papers_list = mr.get("related_papers", [])
        for rp in papers_list:
            lines.append(f"  - {rp}")
        lines.append("")

    lines.append("## 3. 代表性论文")
    lines.append("")
    for i, rp in enumerate(rep_papers, 1):
        lines.append(f"{i}. **{rp['title']}**")
        lines.append(f"   - 推荐理由：{rp['reason']}")
        lines.append("")

    lines.append("## 4. 潜在研究空白")
    lines.append("")
    for g in gaps:
        lines.append(f"- {g}")
    lines.append("")

    lines.append("## 5. 可探索的后续研究问题")
    lines.append("")
    for q in questions:
        lines.append(f"- {q}")
    lines.append("")

    lines.append("## 6. 后续阅读计划")
    lines.append("")
    for p in reading_plan:
        lines.append(f"- {p}")
    lines.append("")

    lines.append("## 7. 可信度与局限")
    lines.append("")
    for c in confidence:
        lines.append(f"- {c}")
    lines.append("")

    return "\n".join(lines)
