"""
PaperPilot 文献综述生成模块。

从论文列表中生成结构化中文文献综述，包括主题分组、方法对比、代表性论文、
研究空白和未来方向。支持规则版（默认）和可选 LLM 增强。

不依赖外部 API，不读取 PDF 全文，不引入重型依赖。
"""

import re
from collections import Counter
from datetime import datetime

# ── 方法关键词 ────────────────────────────────────────────

METHOD_FAMILIES = {
    "Retrieval Augmented Generation": {
        "keywords": ["retrieval", "rag", "retrieve", "retriever", "augmented generation", "dense retrieval"],
        "strengths": "适合需要外部知识或长文档检索的任务。",
        "limitations": "效果依赖检索质量和上下文整合能力。",
    },
    "Large Language Models / Transformers": {
        "keywords": ["language model", "llm", "transformer", "gpt", "pretrain", "fine-tune", "instruction tuning"],
        "strengths": "通用性强大，适合多类 NLP 任务。",
        "limitations": "计算成本高，幻觉和事实性仍需关注。",
    },
    "Multimodal Learning": {
        "keywords": ["multimodal", "vision-language", "image-text", "audio", "video", "cross-modal"],
        "strengths": "能够融合多模态信息进行联合推理。",
        "limitations": "多模态对齐和跨模态泛化仍是挑战。",
    },
    "Graph Neural Networks": {
        "keywords": ["graph neural", "gnn", "graph network", "node", "edge", "message passing", "graph convolution"],
        "strengths": "适合关系型数据和结构化推理。",
        "limitations": "大规模图训练成本高，泛化到新图结构有限。",
    },
    "Diffusion / Generative Models": {
        "keywords": ["diffusion", "generative model", "ddpm", "score-based", "denoising"],
        "strengths": "高质量生成，适合图像、分子、文本生成。",
        "limitations": "推理速度慢，采样步骤多。",
    },
    "Reinforcement Learning": {
        "keywords": ["reinforcement learning", "rl", "policy", "reward", "rlhf", "ppo", "dpo"],
        "strengths": "适合序列决策和偏好对齐。",
        "limitations": "样本效率低，奖励设计困难。",
    },
    "Evaluation / Benchmark": {
        "keywords": ["evaluation", "benchmark", "metric", "dataset", "leaderboard", "assessment"],
        "strengths": "为领域提供标准评测基线。",
        "limitations": "评测覆盖面和偏差可能影响可靠性。",
    },
    "Agent / Tool Use": {
        "keywords": ["agent", "tool", "planning", "action", "environment", "api call", "function call"],
        "strengths": "适合需要自主决策和环境交互的任务。",
        "limitations": "复杂环境下的可靠性和安全性仍需验证。",
    },
}

TECH_PHRASES = [
    "large language model", "retrieval augmented generation", "question answering",
    "information retrieval", "multimodal learning", "graph neural network",
    "diffusion model", "reinforcement learning", "instruction tuning",
    "chain of thought", "long context", "scientific discovery", "reasoning",
    "evaluation", "alignment", "agent", "tool use", "code generation",
    "knowledge graph", "text generation", "summarization",
]


# ── 公共函数 ──────────────────────────────────────────────

def generate_literature_review(
    papers: list[dict],
    source_name: str = "当前论文集合",
    review_topic: str | None = None,
    max_papers: int = 20,
    use_llm: bool = False,
    trend_result: dict | None = None,
    graph_result: dict | None = None,
) -> dict:
    """主入口。生成结构化文献综述。"""
    # 该综述基于当前论文集合生成，不联网补全领域文献，因此输出会保守标注样本局限。
    if not papers:
        return _empty_result(source_name, review_topic, "暂无可生成文献综述的论文，请先搜索论文或刷新关注领域。")

    # 去重 + 规范化，把搜索结果/追踪结果统一成综述需要的轻量字段。
    normalized = _normalize_papers(papers, max_papers)
    if not normalized:
        return _empty_result(source_name, review_topic, "规范化后无有效论文数据。")

    topic = review_topic or source_name
    warnings = []
    if len(normalized) < 3:
        warnings.append("当前样本较少（< 3 篇），综述仅反映有限论文集合，不适合作为完整领域综述。")

    # 主题分组：用技术短语把论文分到粗粒度研究主题，帮助用户建立领域框架。
    theme_groups = _build_theme_groups(normalized)

    # 方法对比：用预定义方法家族总结常见路线，不做自动学科分类模型。
    method_comparison = _build_method_comparison(normalized)

    # 代表性论文：每个主题优先选当前样本内高分论文，避免单一主题垄断。
    representative_papers = _select_representative_papers(normalized, theme_groups, limit=8)

    # 研究空白：从当前样本缺失的关键词线索中生成候选问题，仍需人工确认。
    research_gaps = _build_research_gaps(normalized, warnings)

    # 未来方向
    future_directions = _build_future_directions(normalized, theme_groups, trend_result, graph_result, warnings)

    # Markdown 是最终交付形态，方便复制到报告或答辩材料。
    review_md = _build_markdown(
        topic, source_name, normalized, theme_groups, method_comparison,
        representative_papers, research_gaps, future_directions, warnings,
        trend_result, graph_result,
    )

    return {
        "success": True,
        "source_name": source_name,
        "paper_count": len(papers),
        "used_paper_count": len(normalized),
        "paper_ids": [p["paper_id"] for p in normalized],
        "review_topic": topic,
        "review_markdown": review_md,
        "outline": _build_outline(topic),
        "theme_groups": theme_groups,
        "method_comparison": method_comparison,
        "representative_papers": representative_papers,
        "research_gaps": research_gaps,
        "future_directions": future_directions,
        "warnings": warnings,
    }


# ── 论文规范化 ────────────────────────────────────────────

def _normalize_papers(papers: list[dict], max_papers: int) -> list[dict]:
    """去重 + 规范化 + 排序截断。"""
    # 综述只使用前 max_papers 篇，避免样本过大导致规则综述冗长不可读。
    seen = set()
    normalized = []
    for paper in papers:
        pid = _safe_paper_id(paper)
        if not pid or pid in seen:
            continue
        seen.add(pid)

        title = paper.get("title") or "Untitled Paper"
        abstract = paper.get("abstract") or paper.get("summary") or ""
        authors = _safe_authors(paper)
        categories = _safe_categories(paper)
        published = paper.get("published") or ""
        score = (
            paper.get("final_score")
            or paper.get("score_total")
            or paper.get("total_score")
            or paper.get("score")
            or paper.get("rank_score")
            or 0
        )
        url = paper.get("url") or paper.get("arxiv_url") or paper.get("pdf_url") or paper.get("entry_id") or ""
        keywords = _extract_keywords(title + " " + abstract)

        normalized.append({
            "paper_id": pid,
            "title": title,
            "abstract": abstract,
            "summary": abstract,
            "authors": authors,
            "categories": categories,
            "published": published,
            "score": score if score else None,
            "url": url,
            "keywords": keywords,
        })

    # 按分数降序，无分数按日期，保证综述优先覆盖当前排序认为更重要的论文。
    normalized.sort(key=lambda p: (p["score"] or 0, p.get("published") or ""), reverse=True)
    return normalized[:max_papers]


def _safe_paper_id(paper: dict) -> str:
    try:
        from modules.paper_identity import get_paper_id
        return get_paper_id(paper)
    except ImportError:
        return paper.get("paper_id") or paper.get("arxiv_id") or paper.get("id") or ""


def _safe_authors(paper: dict) -> list[str]:
    authors = paper.get("authors") or []
    if isinstance(authors, str):
        return [a.strip() for a in authors.split(",") if a.strip()]
    return authors if isinstance(authors, list) else []


def _safe_categories(paper: dict) -> list[str]:
    cats = paper.get("categories") or []
    if isinstance(cats, str):
        return [c.strip() for c in cats.split(",") if c.strip()]
    return cats if isinstance(cats, list) else []


def _extract_keywords(text: str) -> list[str]:
    """提取技术关键词。"""
    text_lower = text.lower()
    found = []
    for phrase in TECH_PHRASES:
        if phrase in text_lower:
            found.append(phrase)
            if len(found) >= 8:
                break
    # 如果技术短语不够，补充高频词，避免冷门主题完全没有关键词。
    if len(found) < 4:
        words = re.findall(r"[a-z]{4,}", text_lower)
        stop_words = {"this", "that", "with", "from", "have", "been", "were", "their", "which", "about", "paper", "propose", "method", "model", "using", "based", "approach", "result", "study", "research", "show", "demonstrate", "include"}
        word_counts = Counter(w for w in words if w not in stop_words)
        extras = [w for w, _ in word_counts.most_common(10) if w not in found]
        found.extend(extras[:6 - len(found)])
    return found


# ── 主题分组 ──────────────────────────────────────────────

def _build_theme_groups(papers: list[dict]) -> list[dict]:
    # 主题分组用短语命中，不声称是完整的 topic modeling。
    theme_map = {}
    for paper in papers:
        assigned = set()
        keywords = paper.get("keywords", [])
        title_abs = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()

        for phrase in TECH_PHRASES:
            if phrase in title_abs and phrase not in assigned:
                theme_name = phrase.title()
                if theme_name not in theme_map:
                    theme_map[theme_name] = {"papers": [], "paper_ids": [], "keywords": []}
                if paper["paper_id"] not in theme_map[theme_name]["paper_ids"]:
                    theme_map[theme_name]["papers"].append(paper)
                    theme_map[theme_name]["paper_ids"].append(paper["paper_id"])
                    theme_map[theme_name]["keywords"].extend(keywords)
                    assigned.add(phrase)

    # 合并过小主题到“综合研究”，避免每篇论文都形成孤立主题。
    merged = []
    other_papers = []
    for theme, data in theme_map.items():
        if len(data["papers"]) >= 2:
            merged.append({
                "theme": theme,
                "paper_count": len(data["papers"]),
                "paper_ids": data["paper_ids"],
                "keywords": list(set(data["keywords"]))[:5],
                "summary": _theme_summary(theme, len(data["papers"])),
            })
        else:
            other_papers.extend(data["papers"])

    # 综合研究主题
    if other_papers:
        other_ids = list(set(p["paper_id"] for p in other_papers))
        merged.append({
            "theme": "综合研究",
            "paper_count": len(other_ids),
            "paper_ids": other_ids,
            "keywords": [],
            "summary": "该主题涵盖当前论文集合中不属于主要主题的其他研究。",
        })

    # 确保至少有一个主题
    if not merged:
        merged.append({
            "theme": "综合研究",
            "paper_count": len(papers),
            "paper_ids": [p["paper_id"] for p in papers],
            "keywords": [],
            "summary": "当前论文集合未形成明显主题分组，统一归为综合研究。",
        })

    return merged


def _theme_summary(theme: str, count: int) -> str:
    summaries = {
        "Retrieval Augmented Generation": f"该主题包含 {count} 篇论文，主要关注检索增强生成在问答和长上下文任务中的应用。",
        "Large Language Model": f"该主题包含 {count} 篇论文，主要关注大语言模型的训练、微调和推理能力。",
        "Multimodal Learning": f"该主题包含 {count} 篇论文，主要关注多模态信息的融合与联合学习。",
        "Graph Neural Network": f"该主题包含 {count} 篇论文，主要关注图神经网络在分子、关系等结构化数据上的应用。",
        "Reinforcement Learning": f"该主题包含 {count} 篇论文，主要关注强化学习在序列决策和对齐中的应用。",
    }
    return summaries.get(theme, f"该主题包含 {count} 篇相关论文。")


# ── 方法对比 ──────────────────────────────────────────────

def _build_method_comparison(papers: list[dict]) -> list[dict]:
    # 方法路线来自 METHOD_FAMILIES 映射，便于后续按项目需求增删。
    method_map = {}
    for paper in papers:
        title_abs = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()
        matched = None
        for family, info in METHOD_FAMILIES.items():
            if any(kw in title_abs for kw in info["keywords"]):
                matched = family
                break
        if not matched:
            matched = "Other / 综合方法"

        if matched not in method_map:
            method_map[matched] = {"papers": [], "paper_ids": []}
        if paper["paper_id"] not in method_map[matched]["paper_ids"]:
            method_map[matched]["papers"].append(paper)
            method_map[matched]["paper_ids"].append(paper["paper_id"])

    result = []
    for family, info in METHOD_FAMILIES.items():
        if family in method_map:
            data = method_map[family]
            result.append({
                "method_family": family,
                "paper_count": len(data["papers"]),
                "representative_papers": data["paper_ids"][:3],
                "strengths": info["strengths"],
                "limitations": info["limitations"],
            })

    # Other
    if "Other / 综合方法" in method_map:
        result.append({
            "method_family": "Other / 综合方法",
            "paper_count": len(method_map["Other / 综合方法"]["papers"]),
            "representative_papers": method_map["Other / 综合方法"]["paper_ids"][:3],
            "strengths": "涵盖多种方法路线。",
            "limitations": "方法差异较大，难以直接比较。",
        })

    return result


# ── 代表性论文 ────────────────────────────────────────────

def _select_representative_papers(papers: list[dict], theme_groups: list[dict], limit: int = 8) -> list[dict]:
    selected = []
    seen_ids = set()

    # 每个主题至少选一篇最高分，体现“覆盖不同路线”而不是只追综合分。
    for tg in theme_groups:
        best = None
        for pid in tg.get("paper_ids", []):
            if pid in seen_ids:
                continue
            paper = next((p for p in papers if p["paper_id"] == pid), None)
            if paper and (best is None or (paper.get("score") or 0) > (best.get("score") or 0)):
                best = paper
        if best:
            selected.append(best)
            seen_ids.add(best["paper_id"])

    # 补足到 limit
    for paper in papers:
        if len(selected) >= limit:
            break
        if paper["paper_id"] not in seen_ids:
            selected.append(paper)
            seen_ids.add(paper["paper_id"])

    result = []
    for paper in selected[:limit]:
        result.append({
            "paper_id": paper["paper_id"],
            "title": paper.get("title", ""),
            "published": paper.get("published", ""),
            "score": paper.get("score"),
            "categories": paper.get("categories", []),
            "url": paper.get("url", ""),
            "reason": _rep_reason(paper, theme_groups),
        })
    return result


def _rep_reason(paper: dict, theme_groups: list[dict]) -> str:
    score = paper.get("score")
    pid = paper["paper_id"]
    themes = [tg["theme"] for tg in theme_groups if pid in tg.get("paper_ids", [])]
    parts = []
    if themes:
        parts.append(f"代表{themes[0]}方向")
    if score:
        parts.append(f"评分 {score:.0f}")
    if not parts:
        parts.append("在当前样本中具有代表性")
    return "，".join(parts) + "。"


# ── 研究空白 ──────────────────────────────────────────────

def _build_research_gaps(papers: list[dict], warnings: list[str]) -> list[str]:
    # 研究空白来自样本内关键词缺失和比例判断，是启发式提示，不是领域定论。
    all_text = " ".join(p.get("abstract", "") + p.get("title", "") for p in papers).lower()
    gaps = []

    eval_kws = ["evaluation", "benchmark", "metric", "dataset", "leaderboard"]
    eval_count = sum(1 for kw in eval_kws if kw in all_text)
    if eval_count < 3:
        gaps.append("当前论文集合中系统性评测和跨数据集泛化分析相对不足。")

    robust_kws = ["robustness", "generalization", "safety", "adversarial", "out-of-distribution"]
    if not any(kw in all_text for kw in robust_kws):
        gaps.append("泛化性、鲁棒性与安全性讨论在现有样本中较少出现，后续可加强验证。")

    real_kws = ["real-world", "deployment", "production", "application", "clinical"]
    if not any(kw in all_text for kw in real_kws):
        gaps.append("真实应用场景和部署成本相关讨论较少，落地验证仍需加强。")

    method_kws = ["propose", "proposed", "introduce", "novel", "new method"]
    if sum(1 for kw in method_kws if kw in all_text) > len(papers) * 0.6:
        gaps.append("多数论文关注方法设计，跨领域交叉与整合研究仍有空间。")

    if len(papers) < 5:
        gaps.append("当前样本量较少，不能充分判断该领域的研究空白与挑战。")

    if not gaps:
        gaps.append("基于当前论文集合，研究空白尚不明显，可能需要扩大文献覆盖范围。")
    return gaps[:6]


# ── 未来方向 ──────────────────────────────────────────────

def _build_future_directions(
    papers: list[dict],
    theme_groups: list[dict],
    trend_result: dict | None,
    graph_result: dict | None,
    warnings: list[str],
) -> list[str]:
    directions = []

    # 基于主题组生成
    if theme_groups:
        top_theme = theme_groups[0]["theme"]
        directions.append(f"围绕{top_theme}方向，进一步深入研究仍可能是重点。")

    # 基于方法对比
    method_counts = Counter(p.get("method_family", "") for p in papers)
    if len(method_counts) >= 3:
        directions.append("不同方法路线的比较和融合值得进一步关注。")

    if trend_result and trend_result.get("hot_topics"):
        hot = trend_result.get("hot_topics", [])[:2]
        hot_names = []
        for h in hot:
            if isinstance(h, dict):
                name = h.get("topic") or h.get("keyword") or ""
                if name:
                    hot_names.append(str(name))
            elif isinstance(h, str):
                hot_names.append(h)
        if hot_names:
            directions.append(f"近期热点如{', '.join(hot_names)}等方向可能值得持续关注。")

    if graph_result and graph_result.get("central_papers"):
        directions.append("关系图谱中的中心论文可能代表该领域的关键连接点，建议关注相关方向。")

    directions.append("多模态、工具调用和领域知识结合的交叉方向可能带来新的突破。")

    if len(papers) < 5:
        directions.append("建议扩大文献检索范围，以获更全面的领域认知。")

    directions.append("建议关注相关方法的落地验证和真实场景评估。")

    return directions[:6]


# ── Markdown 生成 ─────────────────────────────────────────

def _build_markdown(
    topic, source_name, papers, theme_groups, method_comparison,
    representative_papers, research_gaps, future_directions, warnings,
    trend_result, graph_result,
) -> str:
    lines = []
    lines.append(f"# 文献综述：{topic}")
    lines.append("")

    # 1. 研究背景
    lines.append("## 1. 研究背景")
    lines.append("")
    lines.append(f"该文献综述基于{source_name}（{len(papers)} 篇论文）自动生成，旨在帮助研究者快速了解研究背景、主要主题、方法路线和代表工作。")
    lines.append("")

    # 2. 样本概况
    lines.append("## 2. 样本概况")
    lines.append("")
    lines.append(f"- 纳入论文：{len(papers)} 篇")
    lines.append(f"- 数据来源：{source_name}")

    # 时间范围
    dates = [p.get("published", "") for p in papers if p.get("published")]
    if dates:
        dates_sorted = sorted(dates)
        lines.append(f"- 时间范围：{dates_sorted[0] if dates_sorted else '未知'} 至 {dates_sorted[-1] if len(dates_sorted) > 1 else dates_sorted[0]}")

    # 分类
    all_cats = [c for p in papers for c in (p.get("categories") or [])]
    if all_cats:
        top_cats = Counter(all_cats).most_common(5)
        lines.append(f"- 主要 arXiv 分类：{', '.join(c[0] for c in top_cats)}")

    if warnings:
        lines.append(f"- ⚠️ {warnings[0]}")
    lines.append("")

    # 3. 主要研究主题
    lines.append("## 3. 主要研究主题")
    lines.append("")
    for tg in theme_groups:
        lines.append(f"### {tg['theme']}（{tg['paper_count']} 篇）")
        lines.append("")
        lines.append(tg["summary"])
        lines.append("")
    lines.append("")

    # 4. 方法路线对比
    lines.append("## 4. 方法路线对比")
    lines.append("")
    lines.append("| 方法路线 | 论文数 | 优势 | 局限 |")
    lines.append("|---------|-------|------|------|")
    for mc in method_comparison:
        lines.append(f"| {mc['method_family']} | {mc['paper_count']} | {mc['strengths']} | {mc['limitations']} |")
    lines.append("")

    # 5. 代表性论文
    lines.append("## 5. 代表性论文")
    lines.append("")
    for i, rp in enumerate(representative_papers, 1):
        title = rp.get("title", "")
        pub = rp.get("published", "")[:7] if rp.get("published") else ""
        cats = ", ".join(rp.get("categories", [])[:2])
        url = rp.get("url", "")
        reason = rp.get("reason", "")
        if url:
            lines.append(f"{i}. [{title}]({url})")
        else:
            lines.append(f"{i}. {title}")
        if pub or cats:
            lines.append(f"   - {pub}  {cats}")
        lines.append(f"   - {reason}")
        lines.append("")
    lines.append("")

    # 6. 共同发现与趋势
    lines.append("## 6. 共同发现与趋势")
    lines.append("")
    lines.append(f"基于{len(papers)} 篇论文的主题分组和方法对比，当前研究主要集中在{theme_groups[0]['theme'] if theme_groups else '多个方向'}。")
    if trend_result:
        trend_text = (
            trend_result.get("trend_summary")
            or trend_result.get("trend_interpretation")
        )
        if trend_text:
            lines.append("")
            lines.append(trend_text[:500])
    if graph_result and graph_result.get("central_papers"):
        lines.append("")
        lines.append("关系图谱显示部分论文在当前样本中关系较紧密，可作为进一步阅读的起点。")
    lines.append("")

    # 7. 局限与挑战
    lines.append("## 7. 局限与挑战")
    lines.append("")
    for gap in research_gaps:
        lines.append(f"- {gap}")
    lines.append("")

    # 8. 未来方向
    lines.append("## 8. 未来研究方向")
    lines.append("")
    for fd in future_directions:
        lines.append(f"- {fd}")
    lines.append("")

    # 9. 小结
    lines.append("## 9. 小结")
    lines.append("")
    lines.append(f"该文献综述基于{len(papers)} 篇论文自动生成。")
    if len(papers) >= 5:
        lines.append("当前样本覆盖了该方向的主要研究主题和方法路线。")
    else:
        lines.append("当前样本较少，综述结论仅供参考，建议扩大文献检索。")
    lines.append("研究者可结合代表性论文进一步深入阅读和对比。")
    lines.append("")

    # 参考论文
    lines.append("## 参考论文列表")
    lines.append("")
    for i, paper in enumerate(papers, 1):
        title = paper.get("title", "Untitled")
        authors = ", ".join(paper.get("authors", [])[:5])
        pub = paper.get("published", "")[:10]
        url = paper.get("url", "")
        if url:
            lines.append(f"{i}. [{title}]({url}). {authors}. {pub}")
        else:
            lines.append(f"{i}. {title}. {authors}. {pub}")
    lines.append("")

    return "\n".join(lines)


def _build_outline(topic: str) -> list[str]:
    return [
        f"文献综述：{topic}",
        "研究背景",
        "样本概况",
        "主要研究主题",
        "方法路线对比",
        "代表性论文",
        "共同发现与趋势",
        "局限与挑战",
        "未来研究方向",
        "小结",
        "参考论文列表",
    ]


def _empty_result(source_name: str, review_topic: str | None, message: str) -> dict:
    return {
        "success": False,
        "source_name": source_name,
        "paper_count": 0,
        "used_paper_count": 0,
        "paper_ids": [],
        "review_topic": review_topic or "",
        "review_markdown": "",
        "outline": [],
        "theme_groups": [],
        "method_comparison": [],
        "representative_papers": [],
        "research_gaps": [],
        "future_directions": [],
        "warnings": [message],
    }
