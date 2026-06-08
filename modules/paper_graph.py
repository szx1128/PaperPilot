"""
PaperPilot 论文关系图谱模块。

基于论文元信息（标题、摘要、关键词、分类、作者、引用字段）构建论文关系网络，
包括内容相似度边、共享分类边、共享作者边、引用字段边。
支持连通分量聚类、中心论文计算和 Graphviz DOT 图生成。

纯 Python 标准库实现。不依赖外部 API，不引用重型 ML/NLP 库。

依赖：
- Python 标准库（re, collections, datetime）
- modules/paper_identity.py（get_paper_id）
"""

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from modules.paper_identity import get_paper_id

# ═══════════════════════════════════════════════════════════
# 停用词 & 技术短语
# ═══════════════════════════════════════════════════════════

STOP_WORDS = {
    "the", "a", "an", "and", "or", "of", "in", "on", "for", "to", "with",
    "by", "from", "using", "based", "paper", "method", "model", "approach",
    "results", "task", "study", "show", "propose", "proposes", "proposed",
    "this", "that", "these", "those", "it", "its", "they", "them", "their",
    "we", "our", "us", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "can",
    "could", "may", "might", "shall", "should", "not", "no", "but", "if",
    "as", "at", "so", "such", "also", "only", "new", "one", "two", "all",
    "each", "every", "other", "some", "more", "most", "very", "well",
    "just", "now", "how", "which", "what", "when", "where", "who", "while",
    "over", "out", "up", "into", "about", "through", "during", "before",
    "after", "above", "below", "between", "under", "both", "few", "much",
    "many", "first", "novel", "better", "improved", "different", "various",
    "use", "used", "uses", "demonstrate", "demonstrates", "shown",
    "present", "presents", "presented", "explore", "explores", "explored",
    "introduce", "introduces", "introduced", "yet", "still", "however",
    "recent", "current", "existing", "previous", "prior", "state", "art",
    "large", "small", "high", "low", "many", "way", "ways", "need",
    "important", "key", "challenge", "challenges", "problem", "problems",
    "issue", "issues", "application", "applications", "system", "systems",
    "framework", "frameworks", "work", "works", "field", "domain",
    "performance", "effective", "effectiveness", "efficient", "efficiency",
}

TECH_PHRASES = [
    "large language model", "large language models",
    "retrieval augmented generation", "retrieval augmented",
    "augmented generation",
    "diffusion model", "diffusion models",
    "graph neural network", "graph neural networks",
    "reinforcement learning",
    "multimodal learning", "multimodal",
    "instruction tuning",
    "chain of thought",
    "question answering",
    "information retrieval",
    "scientific discovery",
    "long context",
    "retrieval method", "retrieval methods",
    "language model", "language models",
    "neural network", "neural networks",
    "transformer model", "transformer models",
    "knowledge graph", "knowledge graphs",
    "text generation", "code generation",
    "image generation", "video generation",
    "representation learning",
    "self supervised", "self supervised learning",
    "few shot", "zero shot",
    "prompt engineering",
    "fine tuning", "fine tuned",
    "transfer learning",
    "attention mechanism",
    "encoder decoder",
    "natural language processing",
    "computer vision",
    "speech recognition",
    "machine translation",
    "sentiment analysis",
    "named entity recognition",
    "text summarization",
    "reading comprehension",
    "semantic search",
    "dense retrieval",
    "sparse retrieval",
    "contrastive learning",
    "generative adversarial",
    "variational autoencoder",
    "bayesian inference",
    "causal inference",
    "federated learning",
    "edge computing",
    "explainable ai", "explainable artificial intelligence",
    "responsible ai",
    "algorithmic fairness",
    "distribution shift",
    "out of distribution",
    "domain adaptation",
    "domain generalization",
    "data augmentation",
    "knowledge distillation",
    "model compression",
    "quantization",
    "low rank adaptation", "lora",
    "mixture of experts",
    "retrieval augmented",
    "tool augmented",
    "human feedback",
    "constitutional ai",
    "safety alignment",
    "jailbreak",
    "red teaming",
    "machine unlearning",
    "continual learning",
]


# ═══════════════════════════════════════════════════════════
# 1. 论文收集 & 归一化
# ═══════════════════════════════════════════════════════════

def collect_graph_papers(
    ranked_papers: list[dict] | None = None,
    papers: list[dict] | None = None,
    tracked_papers: list[dict] | None = None,
    tracking_history: dict | None = None,
) -> list[dict]:
    """多来源收集论文，按 get_paper_id 去重。"""
    # 图谱输入可能来自搜索、排序、追踪历史，先合并去重再建图，避免同一论文出现多个节点。
    seen: set[str] = set()
    merged: list[dict] = []

    def _add(paper: dict):
        if not isinstance(paper, dict):
            return
        pid = get_paper_id(paper)
        if not pid or pid == "manual_pdf" or pid == "unknown":
            return
        if pid in seen:
            return
        seen.add(pid)
        merged.append(paper)

    for source in [ranked_papers, papers, tracked_papers]:
        if source:
            for p in source:
                _add(p)

    if tracking_history and isinstance(tracking_history, dict):
        hp = tracking_history.get("papers", {})
        if isinstance(hp, dict):
            for p in hp.values():
                _add(p)
        elif isinstance(hp, list):
            for p in hp:
                _add(p)

    return merged


# ═══════════════════════════════════════════════════════════
# 2. 关键词提取
# ═══════════════════════════════════════════════════════════

def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    return str(val).strip()


def _extract_keywords(text: str) -> list[str]:
    """从文本中提取关键词（含技术短语识别）。"""
    if not text:
        return []
    text_lower = text.lower()

    keywords: list[str] = []

    # 技术短语优先，避免 RAG、LLM 等多词概念被拆成无意义的单词。
    for phrase in TECH_PHRASES:
        if phrase in text_lower:
            keywords.append(phrase)

    # 单词切分作为补充，用停用词过滤泛词，降低噪声边。
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]*[a-zA-Z0-9]|[a-zA-Z]", text_lower)
    for w in words:
        w = w.strip("-")
        if len(w) < 3 or w.isdigit() or w in STOP_WORDS:
            continue
        keywords.append(w)

    # 去重保持顺序
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        if kw not in seen:
            seen.add(kw)
            result.append(kw)
    return result


def _keyword_set(paper: dict) -> set[str]:
    """论文的关键词集合。"""
    title = _safe_str(paper.get("title", ""))
    abstract = _safe_str(paper.get("abstract") or paper.get("summary", ""))
    combined = f"{title} {abstract}"[:5000]
    return set(_extract_keywords(combined))


# ═══════════════════════════════════════════════════════════
# 3. Jaccard 相似度
# ═══════════════════════════════════════════════════════════

def _jaccard_similarity(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    if union == 0:
        return 0.0
    return intersection / union


# ═══════════════════════════════════════════════════════════
# 4. 节点构建
# ═══════════════════════════════════════════════════════════

def _build_nodes(papers: list[dict], max_nodes: int = 30) -> list[dict]:
    """构建节点列表。按 score 降序 / date 新优先选取。"""
    # 节点数量做上限控制，保证页面渲染和 Graphviz 生成在演示环境中足够稳定。
    valid = []
    for i, p in enumerate(papers):
        if not isinstance(p, dict):
            continue
        pid = get_paper_id(p)
        if not pid or pid == "manual_pdf":
            continue
        score = _extract_score(p)
        pub = _parse_date(p.get("published") or p.get("updated") or "")
        valid.append((p, pid, score, pub, i))

    # 排序：有 score > 无 score > date 新 > 原始顺序；图谱优先展示更值得读的候选。
    valid.sort(key=lambda x: (
        1 if x[2] is not None else 0,
        x[2] or 0,
        x[3] or datetime(2000, 1, 1, tzinfo=timezone.utc),
        -x[4],
    ), reverse=True)

    selected = valid[:max_nodes]
    nodes = []
    for paper, pid, score, pub, idx in selected:
        title = _safe_str(paper.get("title", "")) or "Untitled Paper"
        cats = _normalize_list(paper.get("categories", []))
        authors = _normalize_authors(paper.get("authors", []))
        kw = list(_keyword_set(paper))[:10]
        url = _safe_str(paper.get("url") or paper.get("arxiv_url") or paper.get("pdf_url") or "")
        pub_str = pub.strftime("%Y-%m-%d") if pub else ""

        nodes.append({
            "id": pid,
            "title": title,
            "short_title": title[:45] + ("..." if len(title) > 45 else ""),
            "authors": authors,
            "categories": cats,
            "published": pub_str,
            "score": score,
            "keywords": kw,
            "url": url,
            "source_index": idx,
        })
    return nodes


# ═══════════════════════════════════════════════════════════
# 5. 边构建
# ═══════════════════════════════════════════════════════════

def _build_edges(
    papers: list[dict],
    nodes: list[dict],
    min_similarity: float = 0.12,
    include_content: bool = True,
    include_category: bool = True,
    include_author: bool = True,
    include_reference: bool = True,
) -> list[dict]:
    """构建论文间关系边。"""
    # 这里的边是启发式关系边，不等同于真实引用关系；真实引用只在已有字段中出现时才使用。
    node_map = {n["id"]: n for n in nodes}
    paper_map = {}
    for p in papers:
        pid = get_paper_id(p)
        if pid and isinstance(p, dict):
            paper_map[pid] = p

    # 预计算关键词集合
    kw_sets: dict[str, set[str]] = {}
    for n in nodes:
        pid = n["id"]
        if pid in paper_map:
            kw_sets[pid] = _keyword_set(paper_map[pid])
        else:
            kw_sets[pid] = set()

    edges: list[dict] = []
    node_ids = [n["id"] for n in nodes]

    for i in range(len(node_ids)):
        for j in range(i + 1, len(node_ids)):
            id_a, id_b = node_ids[i], node_ids[j]
            n_a, n_b = nodes[i], nodes[j]
            content_sim = 0.0
            cat_overlap = 0
            author_overlap = 0
            ref_match = False
            relation_types: list[str] = []
            reasons: list[str] = []

            # 内容相似：基于关键词集合 Jaccard，相当于轻量主题重合度。
            if include_content and id_a in kw_sets and id_b in kw_sets:
                content_sim = round(_jaccard_similarity(kw_sets[id_a], kw_sets[id_b]), 3)
                if content_sim >= min_similarity:
                    relation_types.append("content_similarity")
                    reasons.append(f"关键词相似度 {content_sim:.2f}")

            # 共享分类：arXiv category 可以补充主题相似度，但权重低于内容相似。
            if include_category:
                cats_a = set(n_a.get("categories", []))
                cats_b = set(n_b.get("categories", []))
                cat_overlap = len(cats_a & cats_b)
                if cat_overlap > 0:
                    relation_types.append("shared_category")
                    reasons.append(f"共享分类 {', '.join(cats_a & cats_b)}")

            # 共享作者：同一作者/团队的论文可能方法路线相关，因此作为辅助边。
            if include_author:
                authors_a = set(n_a.get("authors", []))
                authors_b = set(n_b.get("authors", []))
                author_overlap = len(authors_a & authors_b)
                if author_overlap > 0:
                    relation_types.append("shared_author")
                    reasons.append(f"共同作者 {', '.join(authors_a & authors_b)}")

            # 引用/关联字段：只检查输入数据已有字段，不主动联网查引用。
            if include_reference:
                pa, pb = paper_map.get(id_a), paper_map.get(id_b)
                if pa and pb:
                    ref_match = _check_reference_match(pa, pb, id_b) or _check_reference_match(pb, pa, id_a)
                if ref_match:
                    relation_types.append("reference_relation")
                    reasons.append("引用或关联字段匹配")

            # 权重计算：多种关系信号相加，最后截断到 0-1，便于 UI 解释。
            weight = 0.0
            if include_content:
                weight += content_sim * 0.55
            if include_category:
                weight += min(cat_overlap / 3, 1.0) * 0.20
            if include_author:
                weight += min(author_overlap / 2, 1.0) * 0.15
            if include_reference and ref_match:
                weight += 0.35
            weight = min(weight, 1.0)

            # 保留条件：弱内容相似必须有分类/作者/引用等辅助信号，否则不连边。
            keep = (
                (content_sim >= min_similarity)
                or (cat_overlap > 0 and content_sim >= min_similarity * 0.5)
                or (author_overlap > 0)
                or ref_match
            )

            if keep and weight > 0:
                edges.append({
                    "source": id_a,
                    "target": id_b,
                    "weight": round(weight, 3),
                    "relation_types": relation_types,
                    "reason": "; ".join(reasons) if reasons else "弱关系",
                    "content_similarity": content_sim,
                    "category_overlap": cat_overlap,
                    "author_overlap": author_overlap,
                    "reference_match": ref_match,
                })

    # 按 weight 降序，限制最多 max_nodes * 3 条边
    edges.sort(key=lambda e: e["weight"], reverse=True)
    max_edges = len(nodes) * 3
    return edges[:max_edges]


def _check_reference_match(paper_a: dict, paper_b: dict, target_id: str) -> bool:
    """检查 paper_a 的引用/关联字段是否指向 paper_b 的 id。"""
    for field in ("references", "citations", "cited_by", "related_papers"):
        val = paper_a.get(field)
        if not val:
            continue
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    rid = item.get("paper_id") or item.get("id") or item.get("arxiv_id") or ""
                    if rid and (rid == target_id or rid in str(target_id)):
                        return True
                elif isinstance(item, str):
                    if target_id in item:
                        return True
        elif isinstance(val, str):
            if target_id in val:
                return True
    return False


# ═══════════════════════════════════════════════════════════
# 6. 聚类
# ═══════════════════════════════════════════════════════════

def _find_clusters(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """DFS 连通分量聚类。"""
    # 连通分量用于把相互关联的论文聚成主题簇，不做复杂社区发现。
    if not nodes:
        return []

    node_ids = {n["id"] for n in nodes}
    adjacency: dict[str, list[str]] = {nid: [] for nid in node_ids}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in adjacency and t in adjacency:
            adjacency[s].append(t)
            adjacency[t].append(s)

    visited: set[str] = set()
    clusters: list[dict] = []

    for nid in node_ids:
        if nid in visited:
            continue
        # BFS
        component: list[str] = []
        stack = [nid]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            component.append(cur)
            for nb in adjacency.get(cur, []):
                if nb not in visited:
                    stack.append(nb)

        # 提取 cluster 信息
        node_map = {n["id"]: n for n in nodes}
        comp_nodes = [node_map[c] for c in component if c in node_map]

        # top keywords
        all_kw: list[str] = []
        for cn in comp_nodes:
            all_kw.extend(cn.get("keywords", [])[:5])
        kw_counter = Counter(all_kw)
        top_keywords = [kw for kw, _ in kw_counter.most_common(5)]

        # 中心论文：加权度最高，表示在当前样本图中连接最多/最强。
        central_id = None
        central_title = ""
        max_deg = -1
        degrees: dict[str, float] = {}
        for e in edges:
            if e["source"] in component and e["target"] in component:
                degrees[e["source"]] = degrees.get(e["source"], 0) + e["weight"]
                degrees[e["target"]] = degrees.get(e["target"], 0) + e["weight"]
        for cid in component:
            deg = degrees.get(cid, 0)
            if deg > max_deg:
                max_deg = deg
                central_id = cid
                cn = node_map.get(cid)
                central_title = cn["title"] if cn else ""

        if not central_id and comp_nodes:
            central_id = comp_nodes[0]["id"]
            central_title = comp_nodes[0]["title"]

        clusters.append({
            "cluster_id": f"cluster_{len(clusters) + 1}",
            "size": len(component),
            "paper_ids": component,
            "top_keywords": top_keywords,
            "central_paper_id": central_id or "",
            "central_paper_title": central_title or "",
        })

    clusters.sort(key=lambda c: c["size"], reverse=True)
    return clusters


# ═══════════════════════════════════════════════════════════
# 7. 中心论文
# ═══════════════════════════════════════════════════════════

def _find_central_papers(nodes: list[dict], edges: list[dict]) -> list[dict]:
    """按加权度计算中心论文。"""
    node_map = {n["id"]: n for n in nodes}
    centrality: dict[str, float] = {}
    degree_count: dict[str, int] = {}

    for e in edges:
        s, t = e["source"], e["target"]
        w = e["weight"]
        centrality[s] = centrality.get(s, 0) + w
        centrality[t] = centrality.get(t, 0) + w
        degree_count[s] = degree_count.get(s, 0) + 1
        degree_count[t] = degree_count.get(t, 0) + 1

    # 没有边时，返回高分代表论文，避免 UI 空白，但明确中心性为 0。
    if not centrality:
        scored = sorted(nodes, key=lambda n: (n.get("score") or 0), reverse=True)
        return [{
            "paper_id": n["id"],
            "title": n["title"],
            "centrality_score": 0.0,
            "degree": 0,
            "score": n.get("score"),
            "categories": n.get("categories", []),
            "reason": "当前图谱无关系边，该论文为样本中评分最高的论文",
        } for n in scored[:5]]

    ranked = sorted(centrality.items(), key=lambda x: x[1], reverse=True)
    result = []
    for pid, cs in ranked[:5]:
        n = node_map.get(pid, {})
        # reason from connected keywords
        n_kw = set(n.get("keywords", [])[:5])
        all_kw: list[str] = []
        for e in edges:
            if e["source"] == pid or e["target"] == pid:
                other = e["target"] if e["source"] == pid else e["source"]
                on = node_map.get(other, {})
                all_kw.extend(on.get("keywords", [])[:3])
        kw_common = Counter(all_kw).most_common(3)
        kw_names = [k for k, _ in kw_common if k not in n_kw]
        reason = f"与多篇论文在{'、'.join(kw_names[:3])}主题上相似" if kw_names else "连接论文数量较多"

        result.append({
            "paper_id": pid,
            "title": n.get("title", ""),
            "centrality_score": round(cs, 2),
            "degree": degree_count.get(pid, 0),
            "score": n.get("score"),
            "categories": n.get("categories", []),
            "reason": reason,
        })
    return result


# ═══════════════════════════════════════════════════════════
# 8. DOT 图
# ═══════════════════════════════════════════════════════════

def _generate_dot(nodes: list[dict], edges: list[dict]) -> str:
    """生成 Graphviz DOT 字符串。"""
    # DOT 文本用于可视化预览和下载，保持简单无外部服务依赖。
    lines = ["graph PaperGraph {", '  rankdir=LR;', '  node [shape=box, style=rounded, fontsize=10];']

    node_map = {n["id"]: n for n in nodes}
    for n in nodes:
        label = _dot_escape(n.get("short_title", n.get("title", "?")))
        lines.append(f'  "{n["id"]}" [label="{label}"];')

    for e in edges:
        s, t = e["source"], e["target"]
        w = e["weight"]
        rt = "+".join(e.get("relation_types", [])[:2]) or "rel"
        label = f"{rt} ({w:.2f})"
        lines.append(f'  "{s}" -- "{t}" [label="{label}", fontsize=8];')

    lines.append("}")
    return "\n".join(lines)


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


# ═══════════════════════════════════════════════════════════
# 9. 图谱总结
# ═══════════════════════════════════════════════════════════

def _generate_graph_summary(result: dict) -> str:
    """中文图谱总结（规则型）。"""
    # 总结会主动说明“不是严格引用网络”，避免用户误解图谱含义。
    parts = []
    pc = result.get("paper_count", 0)
    nc = result.get("node_count", 0)
    ec = result.get("edge_count", 0)

    if nc == 0:
        return "暂无可构建图谱的论文。"

    parts.append(f"本次共分析 {pc} 篇论文，构建出 {nc} 个节点和 {ec} 条关系边。")

    # 引用字段
    has_ref = any(
        e.get("reference_match") for e in result.get("edges", [])
    )
    if not has_ref:
        parts.append("当前图谱主要基于标题、摘要、关键词、分类和作者信息推断论文关系，并未发现可用的真实引用字段，因此不能视为严格引用网络。")

    # 簇
    clusters = result.get("clusters", [])
    big_clusters = [c for c in clusters if c["size"] >= 2]
    if big_clusters:
        parts.append(f"从关系结构看，样本中形成了 {len(big_clusters)} 个较明显的主题簇，")
        top_clusters = big_clusters[:3]
        cluster_descs = []
        for c in top_clusters:
            kws = c.get("top_keywords", [])[:2]
            if kws:
                cluster_descs.append(f"集中在 {'、'.join(kws)}")
        parts.append("；".join(cluster_descs) + "。")
    else:
        parts.append("当前样本中未形成明显的主题簇，论文之间关系较为稀疏。")

    # 中心论文
    centrals = result.get("central_papers", [])
    if centrals and centrals[0].get("centrality_score", 0) > 0:
        top_c = centrals[0]
        parts.append(f"中心论文主要是「{top_c['title'][:40]}」，建议优先阅读中心论文，再沿相邻节点扩展阅读。")

    if nc < 5:
        parts.append("由于样本较少，图谱仅供参考。")
    elif ec < nc // 3:
        parts.append("图谱较为稀疏，可能是样本主题跨度大或摘要信息不足以判断相似性。")

    return "".join(parts)


# ═══════════════════════════════════════════════════════════
# 10. 总入口
# ═══════════════════════════════════════════════════════════

def build_paper_graph(
    papers: list[dict],
    source_name: str = "当前论文集合",
    max_nodes: int = 30,
    min_similarity: float = 0.12,
    include_content_edges: bool = True,
    include_category_edges: bool = True,
    include_author_edges: bool = True,
    include_reference_edges: bool = True,
) -> dict:
    """
    主入口。输入论文列表，输出论文关系图谱。

    参数:
        papers:                  论文列表
        source_name:             数据来源名称
        max_nodes:               最大节点数
        min_similarity:          最小内容相似度阈值
        include_content_edges:   包含内容相似边
        include_category_edges:  包含共享分类边
        include_author_edges:    包含共享作者边
        include_reference_edges: 包含引用字段边

    返回:
        dict with success / paper_count / node_count / edge_count / nodes / edges
        / clusters / central_papers / graph_summary / dot_graph / warnings
    """
    # 主入口只返回结构化数据，不直接画 UI，便于 Streamlit 页面和后续模块复用。
    warnings: list[str] = []

    if not papers:
        return {
            "success": False,
            "source_name": source_name,
            "paper_count": 0,
            "node_count": 0,
            "edge_count": 0,
            "nodes": [],
            "edges": [],
            "clusters": [],
            "central_papers": [],
            "graph_summary": "暂无可构建图谱的论文。",
            "dot_graph": "",
            "warnings": ["暂无论文数据，请先搜索论文或刷新关注追踪。"],
        }

    paper_count = len(papers)

    try:
        nodes = _build_nodes(papers, max_nodes=max_nodes)
    except Exception as e:
        warnings.append(f"节点构建异常: {e}")
        nodes = []

    if not nodes:
        return {
            "success": False,
            "source_name": source_name,
            "paper_count": paper_count,
            "node_count": 0,
            "edge_count": 0,
            "nodes": [],
            "edges": [],
            "clusters": [],
            "central_papers": [],
            "graph_summary": "无法构建有效节点，请检查论文数据。",
            "dot_graph": "",
            "warnings": warnings + ["无有效论文节点"],
        }

    try:
        edges = _build_edges(
            papers, nodes,
            min_similarity=min_similarity,
            include_content=include_content_edges,
            include_category=include_category_edges,
            include_author=include_author_edges,
            include_reference=include_reference_edges,
        )
    except Exception as e:
        warnings.append(f"边构建异常: {e}")
        edges = []

    try:
        clusters = _find_clusters(nodes, edges)
    except Exception as e:
        warnings.append(f"聚类分析异常: {e}")
        clusters = []

    try:
        central_papers = _find_central_papers(nodes, edges)
    except Exception as e:
        warnings.append(f"中心论文计算异常: {e}")
        central_papers = []

    dot_graph = ""
    try:
        dot_graph = _generate_dot(nodes, edges)
    except Exception as e:
        warnings.append(f"DOT 图生成异常: {e}")

    result = {
        "success": True,
        "source_name": source_name,
        "paper_count": paper_count,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "clusters": clusters,
        "central_papers": central_papers,
        "graph_summary": "",
        "dot_graph": dot_graph,
        "warnings": warnings,
    }

    try:
        result["graph_summary"] = _generate_graph_summary(result)
    except Exception as e:
        result["graph_summary"] = "图谱总结生成失败。"
        result["warnings"].append(f"总结生成异常: {e}")

    return result


# ═══════════════════════════════════════════════════════════
# 内部辅助函数
# ═══════════════════════════════════════════════════════════

def _extract_score(paper: dict, depth: int = 0) -> float | None:
    if depth > 2:
        return None
    for key in ("final_score", "total_score", "score", "rank_score", "score_total"):
        v = paper.get(key)
        if v is not None and isinstance(v, (int, float)):
            return float(v)
    raw = paper.get("raw")
    if isinstance(raw, dict) and raw is not paper:
        return _extract_score(raw, depth + 1)
    return None


def _parse_date(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = _safe_str(val)
    if not s:
        return None
    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", "%Y/%m/%d", "%Y-%m", "%Y"]:
        try:
            return datetime.strptime(s[:len(fmt)], fmt).replace(tzinfo=timezone.utc)
        except (ValueError, IndexError):
            continue
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        pass
    return None


def _normalize_list(val: Any) -> list[str]:
    if isinstance(val, list):
        return [_safe_str(v) for v in val if _safe_str(v)]
    if isinstance(val, str):
        parts = re.split(r"[,\s]+", val.strip())
        return [p.strip() for p in parts if p.strip()]
    return []


def _normalize_authors(val: Any) -> list[str]:
    if isinstance(val, list):
        return [_safe_str(v) for v in val if _safe_str(v)]
    if isinstance(val, str):
        parts = re.split(r"[,;、;；]+", val.strip())
        return [p.strip() for p in parts if p.strip()]
    return []
