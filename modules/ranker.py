"""
PaperPilot 论文排序模块 — v2.2（三种阅读意图建模）。

基于固定规则打分，不依赖 Min-Max 归一化、LLM、或外部数据源。
目标：帮助用户在当前阅读目标下，从搜索结果中筛选更值得优先阅读的论文。

前沿追踪模式六个维度：
1. relevance_score       主题相关性（35%）
2. contribution_score    潜在贡献价值（20%）
3. method_clarity_score  方法清晰度（15%）
4. evidence_score        实验/理论支撑（15%）
5. freshness_score       发布时间新鲜度（10%）
6. readability_score     可读性与摘要完整度（5%）

领域了解模式关注 survey / review / taxonomy / benchmark / dataset / 方法覆盖
等入门价值信号，并保守使用 arXiv 元信息中的权威发表信号。

深入了解模式关注论文是否适合作为精读、复现、方法对比或后续研究问题
挖掘的候选，使用标题、摘要和 arXiv 元信息中的轻量启发式信号。

所有分数 0-100，综合分 = 加权和。不引入 citation count / venue / 作者 h-index。
排序结果不代表论文真实学术质量、真实引用影响力或真实 venue 等级。
"""

import re
from datetime import datetime, timezone

from modules.utils import extract_keywords


# ═══════════════════════════════════════════════════════════
# 权重配置
# ═══════════════════════════════════════════════════════════
# 三组权重对应三种“阅读意图”。这里不做动态学习，故意保持固定规则，
# 这样每个分数都能解释给用户听，也便于答辩时说明排序依据。

W_RELEVANCE = 0.35
W_CONTRIBUTION = 0.20
W_METHOD_CLARITY = 0.15
W_EVIDENCE = 0.15
W_FRESHNESS = 0.10
W_READABILITY = 0.05

UW_RELEVANCE = 0.18
UW_OVERVIEW = 0.18
UW_CLASSIC = 0.14
UW_AUTHORITY = 0.12
UW_PROBLEM = 0.14
UW_METHOD = 0.12
UW_BENCHMARK = 0.07
UW_READABILITY = 0.03
UW_FRESHNESS = 0.02

DRW_RELEVANCE = 0.15
DRW_CONTRIBUTION = 0.11
DRW_PROBLEM = 0.09
DRW_METHOD_RIGOR = 0.16
DRW_EVIDENCE_STRENGTH = 0.16
DRW_AUTHORITY = 0.12
DRW_REPRODUCIBILITY = 0.10
DRW_MAINSTREAM = 0.05
DRW_LIMITATION = 0.03
DRW_FRESHNESS = 0.03


# ═══════════════════════════════════════════════════════════
# 关键词术语库
# ═══════════════════════════════════════════════════════════

CONTRIBUTION_TERMS = [
    "propose", "present", "introduce", "develop", "design",
    "formulate", "construct", "build",
]

NOVELTY_TERMS = [
    "novel", "new", "first", "unified", "efficient",
    "scalable", "simple", "general", "robust",
]

ARTIFACT_TERMS = [
    "framework", "model", "algorithm", "method", "dataset",
    "benchmark", "theorem", "proof", "system", "architecture",
]

RESULT_TERMS = [
    "improve", "outperform", "achieve", "reduce", "increase",
    "demonstrate", "show", "validate",
]

PROBLEM_SIGNAL_TERMS = [
    "problem", "challenge", "task", "question", "issue",
    "limitation", "gap", "objective", "goal",
]

METHOD_SIGNAL_TERMS = [
    "method", "approach", "framework", "model", "algorithm",
    "pipeline", "architecture", "optimization", "training",
    "inference", "proof", "theorem", "analysis",
]

RESULT_SIGNAL_TERMS = [
    "experiment", "result", "evaluation", "demonstrate",
    "show", "outperform", "achieve", "improve", "validate",
]

EMPIRICAL_TERMS = [
    "experiment", "empirical", "evaluation", "benchmark",
    "dataset", "baseline", "ablation", "comparison",
    "performance", "accuracy", "result",
]

THEORY_TERMS = [
    "theorem", "proof", "lemma", "proposition", "bound",
    "convergence", "complexity", "analysis", "theoretical",
    "guarantee",
]

OVERVIEW_TERMS = [
    "survey", "review", "overview", "tutorial",
    "taxonomy", "roadmap", "systematic literature review",
    "comprehensive survey", "recent advances",
    "progress", "landscape", "perspective",
]

AUTHORITY_TERMS = [
    "neurips", "nips", "icml", "iclr",
    "acl", "emnlp", "naacl", "coling",
    "cvpr", "iccv", "eccv",
    "sigir", "www", "kdd", "aaai", "ijcai",
    "aistats", "uai", "wsdm", "cikm", "recsys",
    "icse", "fse", "esec-fse", "ase", "issta", "msr",
    "icsme", "saner", "oopsla", "pldi", "sosp", "osdi",
    "usenix", "asplos",
    "jmlr", "tacl", "tpami", "tse", "tosem",
    "nature", "science",
]

PROBLEM_CLARITY_TERMS = [
    "problem", "challenge", "task", "goal", "objective",
    "we study", "we investigate", "we address",
    "aims to", "focus on", "research question",
]

METHOD_COVERAGE_TERMS = [
    "methods", "approaches", "paradigms", "frameworks",
    "categories", "comparison", "compare", "classify",
    "taxonomy", "we categorize", "we classify",
    "existing methods", "prior work",
]

BENCHMARK_TERMS = [
    "benchmark", "dataset", "evaluation", "metric",
    "leaderboard", "baseline", "comparison",
    "experimental study", "empirical study",
    "testbed", "suite",
]

CLASSIC_SIGNAL_TERMS = [
    "foundational", "seminal", "classic", "foundation",
    "representative", "standard", "widely used",
]

NARROW_INCREMENT_TERMS = [
    "trick", "minor", "incremental", "simple modification",
    "small change", "case study",
]

METHOD_RIGOR_TERMS = [
    "objective function", "loss function", "architecture", "algorithm",
    "optimization", "training procedure", "inference procedure",
    "pipeline", "module", "component", "mechanism", "theorem", "proof",
    "complexity", "convergence", "implementation detail", "formalize",
    "formulation",
]

METHOD_SIGNAL_KEYWORDS = [
    "framework", "architecture", "model", "algorithm", "module",
    "pipeline", "training", "inference", "optimization",
    "method", "approach", "system",
]

EVIDENCE_STRENGTH_TERMS = [
    "experiment", "experimental results", "benchmark", "baseline",
    "comparison", "ablation", "ablation study", "evaluation",
    "empirical study", "multiple datasets", "multiple tasks",
    "human evaluation", "statistical significance", "theorem", "proof",
    "upper bound", "lower bound", "convergence",
]

EXPERIMENT_SIGNAL_KEYWORDS = [
    "experiment", "experiments", "evaluation", "evaluate",
    "benchmark", "dataset", "datasets", "metric", "metrics",
    "state-of-the-art", "sota", "comparison", "compare",
]

BASELINE_SIGNAL_KEYWORDS = [
    "baseline", "baselines", "strong baseline", "comparison",
    "compare with", "outperform", "state-of-the-art", "sota",
]

ABLATION_SIGNAL_KEYWORDS = [
    "ablation", "analysis", "case study", "error analysis",
    "sensitivity", "robustness", "generalization",
]

REPRODUCIBILITY_TERMS = [
    "source code", "code is available", "code available", "github",
    "repository", "open source", "open-source", "we release",
    "publicly available", "dataset is available", "implementation details",
    "hyperparameter", "hyperparameters", "training details",
    "experimental setup", "appendix", "supplementary material",
]

REPRODUCIBILITY_SIGNAL_KEYWORDS = [
    "code", "open-source", "open source", "github", "dataset",
    "release", "released", "implementation", "appendix",
    "reproducible", "replication",
]

LIMITATION_VALUE_TERMS = [
    "limitation", "limitations", "however", "future work", "future research",
    "challenge", "challenges", "open problem", "open question", "remain",
    "remains", "fails", "failure", "restricted", "constraint",
    "shortcoming", "drawback", "bias", "risk", "cost",
]

LIMITATION_SIGNAL_KEYWORDS = [
    "limitation", "limitations", "discussion", "future work",
    "failure case", "challenge", "challenges",
]

LIGHTWEIGHT_TRICK_KEYWORDS = [
    "simple trick", "prompting trick", "preliminary", "position paper",
    "demo paper", "short paper", "extended abstract",
]

VENUE_AUTHORITY_TERMS = {
    "conference": [
        "NeurIPS", "NIPS", "ICML", "ICLR", "ACL", "EMNLP", "NAACL",
        "COLING", "AAAI", "IJCAI", "CVPR", "ICCV", "ECCV", "KDD",
        "WWW", "TheWebConf", "SIGIR", "WSDM", "CIKM", "RecSys", "UAI",
        "AISTATS", "ICSE", "FSE", "ESEC-FSE", "ASE", "ISSTA", "MSR",
        "ICSME", "SANER", "OOPSLA", "PLDI", "SOSP", "OSDI", "USENIX",
        "ASPLOS",
    ],
    "journal": [
        "TSE", "TOSEM", "JMLR", "TPAMI", "TACL", "Nature", "Science",
        "ACM Transactions", "IEEE Transactions",
    ],
}

PUBLICATION_CONFIDENCE_TERMS = [
    "accepted", "published", "to appear", "proceedings", "conference",
    "journal", "doi", "oral", "spotlight", "best paper",
]

WORKSHOP_TERMS = ["workshop", "workshops"]

NON_ACCEPTED_PUBLICATION_TERMS = [
    "under review", "submitted", "submitted to", "in submission",
    "submission", "preprint", "arxiv only", "arxiv preprint",
]

# 深入了解模式的相关性门槛：先确认论文属于用户查询方向，再让实验/venue 等质量信号发挥作用。
QUERY_RELEVANCE_GATE_STRONG = 0.35
QUERY_RELEVANCE_GATE_MIN = 0.15

# query expansion 只放“主题等价表达”，不放 benchmark/evaluation/ablation 等质量词。
# 这样可以避免扩展搜索把无关的高质量 benchmark 论文误判为主题相关。
QUERY_EXPANSIONS = {
    "4dvar": [
        "4dvar",
        "4d-var",
        "4d var",
        "4dvariational",
        "4d variational",
        "four-dimensional variational",
        "four dimensional variational",
        "four-dimensional variational data assimilation",
        "four dimensional variational data assimilation",
        "variational data assimilation",
        "data assimilation",
    ],
    "4dvarassimilation": [
        "4dvar",
        "4d-var",
        "four-dimensional variational data assimilation",
        "four dimensional variational data assimilation",
        "variational data assimilation",
        "data assimilation",
    ],
    "fourdimensionalvariational": [
        "4dvar",
        "4d-var",
        "four-dimensional variational",
        "four dimensional variational",
        "variational data assimilation",
        "data assimilation",
    ],
    "variationaldataassimilation": [
        "4dvar",
        "4d-var",
        "four-dimensional variational",
        "four dimensional variational",
        "variational data assimilation",
        "data assimilation",
    ],
}

QUERY_RELEVANCE_QUALITY_TERMS = {
    "benchmark", "benchmarks", "evaluation", "evaluations", "evaluate",
    "evaluating", "ablation", "ablations", "comparison", "comparisons",
    "baseline", "baselines", "method", "methods", "framework",
    "frameworks", "implementation", "implementations", "code", "github",
    "analysis", "analyses", "survey", "review", "overview", "taxonomy",
}

GENERIC_RESEARCH_TERMS = {
    "the", "and", "for", "with", "that", "this", "from", "are", "was",
    "were", "will", "can", "could", "would", "should", "into", "onto",
    "than", "then", "such", "their", "there", "these", "those", "they",
    "them", "our", "ours", "your", "you", "its", "has", "have", "had",
    "using", "used", "use", "based", "via", "towards", "toward", "about",
    "between", "within", "without", "across", "through", "over", "under",
    "paper", "papers", "work", "works", "study", "studies", "research",
    "result", "results", "method", "methods", "approach", "approaches",
    "model", "models", "task", "tasks", "data", "dataset", "datasets",
    "system", "systems", "framework", "frameworks", "algorithm",
    "algorithms", "performance", "propose", "proposed", "present",
    "presents", "introduce", "introduces", "new", "novel", "large",
    "language", "learning", "deep", "neural", "paper", "show", "shows",
    "demonstrate", "demonstrates", "analysis", "also", "more", "most",
    "many", "some", "same", "different", "important", "problem",
    "problems", "challenge", "challenges", "which", "evaluation",
    "evaluations", "evaluating", "benchmark", "benchmarks", "baseline",
    "baselines", "comparison", "comparisons", "experiment", "experiments",
    "experimental", "metric", "metrics", "quality", "signal", "signals",
}


# ═══════════════════════════════════════════════════════════
# 核心函数
# ═══════════════════════════════════════════════════════════

def expand_query_terms(query: str) -> list[str]:
    """
    扩展用户原始查询词，用于“先相关、再深入”的相关性门控。

    这里只扩展主题词或领域同义表达，不加入 benchmark / evaluation /
    ablation 等质量信号词，避免质量信号误当主题相关性。
    """
    if not query or not query.strip():
        return []

    clean_query = re.sub(r"\s+", " ", query.strip().lower())
    terms: list[str] = [clean_query]
    query_key = _normalize_query_expansion_key(clean_query)

    # 先做整句 query 的扩展，例如 4dvar -> four-dimensional variational data assimilation。
    for expansion_key, expansions in QUERY_EXPANSIONS.items():
        if query_key == expansion_key or query_key.startswith(expansion_key) or expansion_key in query_key:
            terms.extend(expansions)

    # 再补充用户输入的核心词，但过滤质量信号词，避免把“benchmark”当成研究方向。
    for keyword in extract_keywords(clean_query):
        kw = keyword.lower().strip()
        if not kw or kw in QUERY_RELEVANCE_QUALITY_TERMS:
            continue
        if len(kw) < 2:
            continue
        terms.append(kw)

        kw_key = _normalize_query_expansion_key(kw)
        if kw_key in QUERY_EXPANSIONS:
            terms.extend(QUERY_EXPANSIONS[kw_key])

    return _dedupe_preserve_order([term for term in terms if term])


def score_query_relevance(paper: dict, query: str) -> dict:
    """
    计算论文与用户原始 query 的主题相关性（0.0-1.0）。

    该函数只看 query 和 query expansion 的命中，不把 benchmark、evaluation、
    ablation、venue、code 等质量信号当作相关性核心。
    """
    if not query or not query.strip():
        return {
            "score": 0.5,
            "matched_terms": [],
            "reasons": ["未提供明确查询词，相关性按中性处理。"],
        }

    title = paper.get("title", "") or ""
    abstract = paper.get("abstract", "") or ""
    metadata = _paper_metadata_text(paper)
    title_lower = title.lower()
    abstract_lower = abstract.lower()
    metadata_lower = metadata.lower()

    expanded_terms = expand_query_terms(query)
    if not expanded_terms:
        return {
            "score": 0.0,
            "matched_terms": [],
            "reasons": ["未能从查询中提取有效主题词，已按低相关处理。"],
        }

    score = 0.0
    matched_terms: list[str] = []
    title_matches: list[str] = []
    abstract_matches: list[str] = []
    metadata_matches: list[str] = []

    for term in expanded_terms:
        term_score = 0.0
        is_primary = _normalize_query_expansion_key(term) == _normalize_query_expansion_key(query)
        is_phrase = _is_query_phrase(term)

        # 标题命中最可信，摘要次之，元信息只作为弱证据。
        if _query_term_matches(term, title_lower):
            term_score = max(term_score, 0.45 if is_primary else (0.34 if is_phrase else 0.22))
            title_matches.append(term)
        if _query_term_matches(term, abstract_lower):
            term_score = max(term_score, 0.30 if is_primary else (0.22 if is_phrase else 0.14))
            abstract_matches.append(term)
        if _query_term_matches(term, metadata_lower):
            term_score = max(term_score, 0.08 if is_primary else 0.05)
            metadata_matches.append(term)

        if term_score > 0:
            score += term_score
            matched_terms.append(term)

    core_keywords = _query_core_keywords(query)
    if core_keywords:
        combined_text = f"{title_lower} {abstract_lower}"
        matched_core = [
            kw for kw in core_keywords
            if _query_term_matches(kw, combined_text)
        ]
        if matched_core:
            score += 0.18 * (len(matched_core) / len(core_keywords))
            matched_terms.extend(matched_core)

    matched_terms = _dedupe_preserve_order(matched_terms)
    score = round(min(max(score, 0.0), 1.0), 3)

    reasons: list[str] = []
    if title_matches:
        reasons.append("标题命中查询主题词：" + "、".join(_dedupe_preserve_order(title_matches)[:4]) + "。")
    if abstract_matches:
        reasons.append("摘要命中查询主题词：" + "、".join(_dedupe_preserve_order(abstract_matches)[:4]) + "。")
    if metadata_matches and not title_matches and not abstract_matches:
        reasons.append("元信息中命中查询主题词：" + "、".join(_dedupe_preserve_order(metadata_matches)[:3]) + "。")
    if not reasons:
        reasons.append("未检测到明确查询主题词命中，质量信号不会单独推高深入了解排序。")

    return {
        "score": score,
        "matched_terms": matched_terms,
        "reasons": reasons,
    }


def rank_papers(
    papers: list[dict],
    query: str,
    top_k: int | None = None,
    mode: str = "frontier",
) -> list[dict]:
    """
    对论文列表进行阅读优先级评分并排序。

    参数:
        papers: 论文列表，每篇需包含 title、abstract、published
        query:  用户搜索关键词
        top_k:  返回前 k 篇，None 返回全部
        mode:   "frontier" 前沿追踪模式；
                "understanding" 领域了解模式；
                "deep" 深入了解模式（兼容旧别名 "deep_research"）

    返回:
        排序后论文列表，新增 score_* 和 recommendation_* 字段
    """
    if not papers:
        return papers

    # mode 分发是兼容旧调用的关键：默认 frontier 不变，新模式只在显式选择时启用。
    if mode == "understanding":
        return _rank_papers_understanding(papers, query, top_k)
    if mode in ("deep", "deep_research", "deep_reading"):
        return _rank_papers_deep_research(papers, query, top_k)

    keywords = extract_keywords(query) if query else []
    full_query_lower = query.strip().lower() if query else ""

    scored = []
    for paper in papers:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        published = paper.get("published", "")

        s = {
            **paper,
            "score_relevance": _calc_relevance(title, abstract, full_query_lower, keywords),
            "score_contribution": _calc_contribution(title, abstract),
            "score_method_clarity": _calc_method_clarity(abstract),
            "score_evidence": _calc_evidence(abstract),
            "score_freshness": _calc_freshness(published),
            "score_readability": _calc_readability(abstract),
        }

        s["score_total"] = round(
            W_RELEVANCE * s["score_relevance"]
            + W_CONTRIBUTION * s["score_contribution"]
            + W_METHOD_CLARITY * s["score_method_clarity"]
            + W_EVIDENCE * s["score_evidence"]
            + W_FRESHNESS * s["score_freshness"]
            + W_READABILITY * s["score_readability"],
            1,
        )

        s["recommendation_level"] = _recommendation_label(s["score_total"])
        s["recommendation_reason"] = _generate_reason(s, title, abstract)

        # 保留旧字段名兼容 UI（后续阶段可逐步移除）
        s["score_keyword"] = s["score_relevance"]
        s["score_title"] = s["score_relevance"]  # 已合并
        s["score_abstract"] = s["score_readability"]

        scored.append(s)

    scored.sort(key=lambda p: p["score_total"], reverse=True)

    if top_k is not None and top_k > 0:
        scored = scored[:top_k]

    return scored


def _rank_papers_deep_research(
    papers: list[dict],
    query: str,
    top_k: int | None = None,
) -> list[dict]:
    """
    深入了解模式：筛选适合作为精读、复现、方法对比或研究空白分析的候选论文。

    该模式只使用标题、摘要和 arXiv 元信息的轻量启发式信号，不做真实引用、
    venue 等级或论文质量判断。
    """
    keywords = extract_keywords(query) if query else []
    # deep 模式先预计算 query relevance，后面既用于排序门控，也用于构建“共同术语”。
    relevance_by_object: dict[int, dict] = {}
    relevant_papers: list[dict] = []
    for paper in papers:
        query_relevance = score_query_relevance(paper, query)
        relevance_by_object[id(paper)] = query_relevance
        if query_relevance.get("score", 0.0) >= QUERY_RELEVANCE_GATE_MIN:
            relevant_papers.append(paper)

    # 路线代表性只从 query-relevant 论文中抽取，避免低相关论文污染 common terms。
    common_terms = _build_common_research_terms(
        relevant_papers,
        keywords,
        query_anchor_terms=_query_anchor_terms(query),
    )

    scored = []
    for paper in papers:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        published = paper.get("published", "")
        query_relevance = relevance_by_object.get(id(paper)) or score_query_relevance(paper, query)
        query_relevance_score = float(query_relevance.get("score", 0.0))
        matched_terms = _get_matched_mainstream_terms(title, abstract, common_terms)
        venue_info = score_venue_authority(paper)
        baseline_signal = _calc_baseline_signal(title, abstract)
        ablation_signal = _calc_ablation_analysis_signal(title, abstract)

        s = {
            **paper,
            "ranking_mode": "deep",
            "query_relevance_score": query_relevance_score,
            "query_relevance_reasons": query_relevance.get("reasons", []),
            "query_relevance_matched_terms": query_relevance.get("matched_terms", []),
            "query_relevance_weak": 0 < query_relevance_score < QUERY_RELEVANCE_GATE_MIN,
            "score_relevance": round(query_relevance_score * 100, 1),
            "score_contribution": _calc_contribution(title, abstract),
            "score_method_clarity": _calc_method_clarity(abstract),
            "score_evidence": _calc_evidence(abstract),
            "score_freshness": _calc_freshness(published),
            "score_readability": _calc_readability(abstract),
            "score_problem_clarity": _calc_problem_clarity(title, abstract),
            "score_method_rigor": _calc_method_rigor(title, abstract),
            "score_evidence_strength": _calc_evidence_strength(title, abstract),
            "score_venue_authority": venue_info["score"],
            "score_authority_signal": venue_info["score"],
            "venue_authority_info": venue_info,
            "score_baseline_signal": baseline_signal,
            "score_ablation_analysis_signal": ablation_signal,
            "score_reproducibility_signal": _calc_reproducibility_signal(paper),
            "score_mainstream_signal": _calc_mainstream_signal(title, abstract, matched_terms),
            "score_limitation_value": _calc_limitation_value(title, abstract),
            "score_deep_penalty": _calc_deep_reading_penalty(title, abstract, paper),
            "matched_mainstream_terms": matched_terms,
        }

        evidence_combo = min(
            100.0,
            0.65 * s["score_evidence_strength"]
            + 0.20 * baseline_signal
            + 0.15 * ablation_signal,
        )
        s["score_evidence_strength"] = round(evidence_combo, 1)

        # deep_quality_score 是“论文是否值得精读”的质量分；最终还要经过相关性门控。
        quality_score = (
            DRW_CONTRIBUTION * s["score_contribution"]
            + DRW_PROBLEM * s["score_problem_clarity"]
            + DRW_METHOD_RIGOR * s["score_method_rigor"]
            + DRW_EVIDENCE_STRENGTH * s["score_evidence_strength"]
            + DRW_AUTHORITY * s["score_authority_signal"]
            + DRW_REPRODUCIBILITY * s["score_reproducibility_signal"]
            + DRW_MAINSTREAM * s["score_mainstream_signal"]
            + DRW_LIMITATION * s["score_limitation_value"]
            + DRW_FRESHNESS * s["score_freshness"]
        ) / max(1.0 - DRW_RELEVANCE, 0.01)
        s["deep_quality_score"] = round(min(max(quality_score, 0.0), 100.0), 1)

        gated_score = _apply_deep_query_relevance_gate(s["deep_quality_score"], query_relevance_score)
        s["score_total"] = round(max(0.0, gated_score - s["score_deep_penalty"]), 1)
        s["deep_reading_score"] = s["score_total"]

        s["recommendation_level"] = _recommendation_label(s["score_total"])
        s["deep_reading_role"] = _assign_deep_research_role(s)
        s["deep_research_role"] = s["deep_reading_role"]
        s["deep_reading_signals"] = _collect_deep_reading_signals(s)
        s["deep_reading_reasons"] = _build_deep_reading_reason_list(s)
        s["recommendation_reason"] = _generate_deep_research_reason(s, title, abstract)

        # 保留旧字段名兼容 UI 和后续模块
        s["score_keyword"] = s["score_relevance"]
        s["score_title"] = s["score_relevance"]
        s["score_abstract"] = s["score_readability"]

        scored.append(s)

    scored.sort(key=lambda p: p["score_total"], reverse=True)

    if top_k is not None and top_k > 0:
        scored = scored[:top_k]

    return scored


def _rank_papers_understanding(
    papers: list[dict],
    query: str,
    top_k: int | None = None,
) -> list[dict]:
    """领域了解模式：优先推荐能帮助建立领域知识框架的论文。"""
    keywords = extract_keywords(query) if query else []
    full_query_lower = query.strip().lower() if query else ""

    scored = []
    for paper in papers:
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        published = paper.get("published", "")

        s = {
            **paper,
            "ranking_mode": "understanding",
            "score_relevance": _calc_relevance(title, abstract, full_query_lower, keywords),
            "score_contribution": _calc_contribution(title, abstract),
            "score_method_clarity": _calc_method_clarity(abstract),
            "score_evidence": _calc_evidence(abstract),
            "score_freshness": _calc_freshness(published),
            "score_readability": _calc_readability(abstract),
            "score_overview_value": _calc_overview_value(title, abstract),
            "score_classic_signal": _calc_classic_signal(title, abstract, published),
            "score_authority_signal": _calc_authority_signal(paper),
            "score_problem_clarity": _calc_problem_clarity(title, abstract),
            "score_method_coverage": _calc_method_coverage(title, abstract),
            "score_benchmark_value": _calc_benchmark_value(title, abstract),
        }

        s["score_total"] = round(
            UW_RELEVANCE * s["score_relevance"]
            + UW_OVERVIEW * s["score_overview_value"]
            + UW_CLASSIC * s["score_classic_signal"]
            + UW_AUTHORITY * s["score_authority_signal"]
            + UW_PROBLEM * s["score_problem_clarity"]
            + UW_METHOD * s["score_method_coverage"]
            + UW_BENCHMARK * s["score_benchmark_value"]
            + UW_READABILITY * s["score_readability"]
            + UW_FRESHNESS * s["score_freshness"],
            1,
        )

        s["recommendation_level"] = _recommendation_label(s["score_total"])
        s["understanding_role"] = _assign_understanding_role(s)
        s["recommendation_reason"] = _generate_understanding_reason(s, title, abstract)

        # 保留旧字段名兼容 UI 和后续模块
        s["score_keyword"] = s["score_relevance"]
        s["score_title"] = s["score_relevance"]
        s["score_abstract"] = s["score_readability"]

        scored.append(s)

    scored.sort(key=lambda p: p["score_total"], reverse=True)

    if top_k is not None and top_k > 0:
        scored = scored[:top_k]

    return scored


# ═══════════════════════════════════════════════════════════
# 维度 1：主题相关性（35%）
# ═══════════════════════════════════════════════════════════

def _calc_relevance(title: str, abstract: str, full_query: str, keywords: list[str]) -> float:
    """计算主题相关性分数（0-100）。"""
    if not full_query and not keywords:
        return 50.0

    title_lower = title.lower()
    abstract_lower = abstract.lower()

    score = 0.0

    # full_query 出现在标题/摘要
    if full_query and full_query in title_lower:
        score += 25
    if full_query and full_query in abstract_lower:
        score += 15

    # 关键词覆盖率
    if keywords:
        kw_count = len(keywords)
        title_matched = sum(1 for kw in keywords if _word_matches(kw, title_lower))
        abstract_matched = sum(1 for kw in keywords if _word_matches(kw, abstract_lower))
        title_cov = title_matched / kw_count
        abstract_cov = abstract_matched / kw_count
        score += title_cov * 30
        score += abstract_cov * 20

        # keyword_density_bonus
        total_hits = 0
        for kw in keywords:
            total_hits += _count_hits(kw, title_lower)
            total_hits += _count_hits(kw, abstract_lower)
        density = min(total_hits / max(kw_count, 1) * 3, 10)
        score += density

    return min(max(score, 0), 100)


# ═══════════════════════════════════════════════════════════
# 维度 2：潜在贡献价值（20%）
# ═══════════════════════════════════════════════════════════

def _calc_contribution(title: str, abstract: str) -> float:
    """计算潜在贡献价值分数（0-100）。"""
    text_lower = (title + " " + abstract).lower()
    score = 35.0

    # 贡献动词
    if _hit_any(CONTRIBUTION_TERMS, text_lower):
        score += 20
    # 新颖性
    if _hit_any(NOVELTY_TERMS, text_lower):
        score += 15
    # 产出物
    if _hit_any(ARTIFACT_TERMS, text_lower):
        score += 15
    # 结果表述
    if _hit_any(RESULT_TERMS, text_lower):
        score += 15
    # 贡献 + 产出物 同时出现
    if _hit_any(CONTRIBUTION_TERMS, text_lower) and _hit_any(ARTIFACT_TERMS, text_lower):
        score += 10

    # 摘要太短
    if len(abstract) < 300:
        score -= 10
    # 综述类信号
    if _is_survey(title, abstract):
        score = min(score, 65)  # 综述不因缺方法而太低，但设上限

    return min(max(score, 0), 100)


# ═══════════════════════════════════════════════════════════
# 维度 3：方法清晰度（15%）
# ═══════════════════════════════════════════════════════════

def _calc_method_clarity(abstract: str) -> float:
    """计算方法清晰度分数（0-100）。"""
    text_lower = abstract.lower()
    score = 25.0

    if _hit_any(PROBLEM_SIGNAL_TERMS, text_lower):
        score += 20
    if _hit_any(METHOD_SIGNAL_TERMS, text_lower):
        score += 30
    if _hit_any(RESULT_SIGNAL_TERMS, text_lower):
        score += 20

    # 句子数量适中
    sentences = _sent_count(abstract)
    if 4 <= sentences <= 10:
        score += 10

    # 长度惩罚
    if len(abstract) < 300:
        score -= 15
    elif len(abstract) > 2500:
        score -= 5

    return min(max(score, 0), 100)


# ═══════════════════════════════════════════════════════════
# 维度 4：实验/理论支撑（15%）
# ═══════════════════════════════════════════════════════════

def _calc_evidence(abstract: str) -> float:
    """计算证据支撑分数（0-100）。"""
    text_lower = abstract.lower()
    score = 35.0

    has_empirical = _hit_any(EMPIRICAL_TERMS, text_lower)
    has_theory = _hit_any(THEORY_TERMS, text_lower)

    if has_empirical:
        score += 20
    if _hit_any(["benchmark", "dataset", "baseline", "ablation"], text_lower):
        score += 15
    if has_theory:
        score += 20

    # 数字结果信号
    if _has_numeric_results(abstract):
        score += 15

    # 都没有
    if not has_empirical and not has_theory:
        score -= 10

    if len(abstract) < 300:
        score -= 10

    return min(max(score, 0), 100)


# ═══════════════════════════════════════════════════════════
# 维度 5：发布时间新鲜度（10%）
# ═══════════════════════════════════════════════════════════

def _calc_freshness(published: str) -> float:
    """计算新鲜度分数（0-100），固定区间，不归一化。"""
    if not published:
        return 50.0

    try:
        pub_date = datetime.strptime(published[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 50.0

    days = (datetime.now(timezone.utc) - pub_date).days
    if days < 0:
        days = 0

    if days <= 30:
        return 100.0
    elif days <= 90:
        return 90.0
    elif days <= 180:
        return 80.0
    elif days <= 365:
        return 70.0
    elif days <= 730:
        return 55.0
    elif days <= 1095:
        return 45.0
    else:
        return 35.0


# ═══════════════════════════════════════════════════════════
# 维度 6：可读性与摘要完整度（5%）
# ═══════════════════════════════════════════════════════════

def _calc_readability(abstract: str) -> float:
    """计算可读性分数（0-100）。"""
    length = len(abstract) if abstract else 0

    # 摘要长度评分
    if length == 0:
        len_score = 30.0
    elif length <= 300:
        len_score = 40.0 + (length / 300) * 25  # 40 → 65
    elif length <= 800:
        len_score = 65.0 + ((length - 300) / 500) * 25  # 65 → 90
    elif length <= 1600:
        len_score = 100.0
    elif length <= 2500:
        len_score = 90.0
    else:
        len_score = 75.0

    # 句子评分
    sent_count = _sent_count(abstract) if abstract else 0
    if 4 <= sent_count <= 10:
        sent_score = 100.0
    elif 2 <= sent_count <= 3:
        sent_score = 70.0
    elif 11 <= sent_count <= 15:
        sent_score = 75.0
    else:
        sent_score = 50.0

    return min(max(0.7 * len_score + 0.3 * sent_score, 0), 100)


# ═══════════════════════════════════════════════════════════
# 领域了解模式维度
# ═══════════════════════════════════════════════════════════

def _calc_overview_value(title: str, abstract: str) -> float:
    """识别 survey / review / taxonomy / roadmap 等领域入口价值。"""
    title_lower = title.lower()
    abstract_lower = abstract.lower()
    score = 25.0

    title_hits = _count_term_hits(OVERVIEW_TERMS, title_lower)
    abstract_hits = _count_term_hits(OVERVIEW_TERMS, abstract_lower)

    score += min(title_hits * 24, 55)
    score += min(abstract_hits * 10, 30)

    strong_title_terms = ["survey", "review", "overview", "taxonomy", "tutorial", "roadmap"]
    if _hit_any(strong_title_terms, title_lower):
        score += 20

    return min(max(score, 0), 100)


def _calc_classic_signal(title: str, abstract: str, published: str) -> float:
    """
    经典/代表性潜力信号。该分数不是 citation count，也不代表真实经典性。
    """
    combined = (title + " " + abstract).lower()
    score = 35.0

    age_days = _paper_age_days(published)
    if age_days is None:
        score += 15
    elif age_days <= 180:
        score += 0
    elif age_days <= 365 * 3:
        score += 15
    elif age_days <= 365 * 8:
        score += 25
    else:
        score += 15

    if _hit_any(CLASSIC_SIGNAL_TERMS, combined):
        score += 20
    if _hit_any(ARTIFACT_TERMS, combined):
        score += 15
    if _hit_any(PROBLEM_SIGNAL_TERMS, combined):
        score += 8
    if _hit_any(METHOD_SIGNAL_TERMS, combined):
        score += 8
    if _hit_any(RESULT_TERMS, combined):
        score += 8
    if _hit_any(NARROW_INCREMENT_TERMS, combined):
        score -= 15

    return min(max(score, 0), 100)


def _calc_authority_signal(paper: dict) -> float:
    """
    基于 arXiv journal_ref/comment 的保守权威元信息信号。
    缺失 venue 元信息时返回中性分，避免误伤 arXiv-only 论文。
    """
    meta = _paper_metadata_text(paper)

    if not meta.strip():
        return 50.0

    venue_info = score_venue_authority(paper)
    venue_score = venue_info.get("score", 0)
    label = venue_info.get("label", "")

    if venue_score >= 80:
        return 92.0
    if venue_score >= 40:
        return 72.0
    if label == "tentative":
        return 55.0
    return 50.0


def _calc_problem_clarity(title: str, abstract: str) -> float:
    """识别论文是否清楚说明研究问题或任务定义。"""
    title_lower = title.lower()
    abstract_lower = abstract.lower()
    score = 30.0

    score += min(_count_term_hits(PROBLEM_CLARITY_TERMS, title_lower) * 15, 25)
    score += min(_count_term_hits(PROBLEM_CLARITY_TERMS, abstract_lower) * 12, 45)

    if _hit_any(PROBLEM_SIGNAL_TERMS, abstract_lower) and _hit_any(METHOD_SIGNAL_TERMS, abstract_lower):
        score += 10
    if len(abstract) < 200:
        score -= 10

    return min(max(score, 0), 100)


def _calc_method_coverage(title: str, abstract: str) -> float:
    """识别论文是否覆盖多种方法路线、比较或分类已有工作。"""
    title_lower = title.lower()
    abstract_lower = abstract.lower()
    score = 25.0

    score += min(_count_term_hits(METHOD_COVERAGE_TERMS, title_lower) * 16, 35)
    score += min(_count_term_hits(METHOD_COVERAGE_TERMS, abstract_lower) * 10, 45)

    if _calc_overview_value(title, abstract) >= 70:
        score += 10
    if _hit_any(["method", "framework", "model", "algorithm"], abstract_lower):
        score += 8

    return min(max(score, 0), 100)


def _calc_benchmark_value(title: str, abstract: str) -> float:
    """识别 benchmark / dataset / evaluation 类论文的领域评价价值。"""
    title_lower = title.lower()
    abstract_lower = abstract.lower()
    score = 25.0

    score += min(_count_term_hits(BENCHMARK_TERMS, title_lower) * 22, 50)
    score += min(_count_term_hits(BENCHMARK_TERMS, abstract_lower) * 10, 40)

    if _hit_any(["benchmark", "dataset", "evaluation"], title_lower):
        score += 15
    if _has_numeric_results(abstract):
        score += 8

    return min(max(score, 0), 100)


def _assign_understanding_role(scores: dict) -> str:
    """给领域了解模式结果标注轻量阅读角色。"""
    if scores.get("score_overview_value", 0) >= 70:
        return "领域入口"
    if scores.get("score_benchmark_value", 0) >= 60:
        return "评价入口"
    if scores.get("score_method_coverage", 0) >= 65 or scores.get("score_contribution", 0) >= 75:
        return "代表方法"
    if scores.get("score_classic_signal", 0) >= 65:
        return "背景候选"
    return "入门候选"


# ═══════════════════════════════════════════════════════════
# 深入了解模式维度
# ═══════════════════════════════════════════════════════════

def score_venue_authority(paper: dict) -> dict:
    """
    基于论文元信息的权威发表信号。

    仅做本地字符串启发式匹配，不联网验证，也不代表真实 venue 等级。
    arXiv-only 论文返回 0 分加分，但不会被排除。
    """
    meta_text = _paper_metadata_text(paper)
    lower_text = meta_text.lower()
    doi = str(paper.get("doi") or "").strip()

    if not meta_text and not doi:
        return {
            "score": 0.0,
            "label": "unknown",
            "matched_venue": "",
            "reason": "未检测到明确正式发表 venue 信息，因此未获得发表可信度加分。",
        }

    matched_kind, matched_venue = _find_authority_venue(meta_text)
    has_non_accepted = _hit_any(NON_ACCEPTED_PUBLICATION_TERMS, lower_text)
    has_formal_signal = _hit_any(PUBLICATION_CONFIDENCE_TERMS, lower_text) or bool(doi)
    has_workshop = _hit_any(WORKSHOP_TERMS, lower_text)

    if has_non_accepted:
        # submitted / under review 不能当作正式接收，否则会夸大权威发表信号。
        if matched_venue:
            return {
                "score": 12.0,
                "label": "tentative",
                "matched_venue": matched_venue,
                "reason": f"检测到 {matched_venue} 名称，但元信息包含 under review/submitted/preprint 等非正式发表信号，未按正式接收处理。",
            }
        return {
            "score": 0.0,
            "label": "arxiv_only",
            "matched_venue": "",
            "reason": "当前仅检测到 arXiv 或预印本信息，仍可作为候选论文，但需要人工进一步确认发表状态和实验质量。",
        }

    if matched_venue and has_workshop:
        return {
            "score": 45.0,
            "label": "workshop",
            "matched_venue": matched_venue,
            "reason": f"检测到 workshop 发表信息：{matched_venue}，作为中等发表可信度信号处理。",
        }

    if matched_venue and has_formal_signal:
        if matched_kind == "journal":
            return {
                "score": 88.0,
                "label": "journal",
                "matched_venue": matched_venue,
                "reason": f"检测到正式期刊/Transactions 发表信号：{matched_venue}。",
            }
        return {
            "score": 82.0,
            "label": "conference",
            "matched_venue": matched_venue,
            "reason": f"检测到正式发表或 proceedings 信号：{matched_venue}。",
        }

    if matched_venue:
        return {
            "score": 25.0,
            "label": "unknown",
            "matched_venue": matched_venue,
            "reason": f"检测到 venue 名称：{matched_venue}，但未检测到明确 accepted/published/proceedings 信息，建议人工确认。",
        }

    if doi or _word_matches("doi", lower_text):
        return {
            "score": 32.0,
            "label": "publication",
            "matched_venue": "",
            "reason": "检测到 DOI 或正式出版标识，但未检测到明确会议/期刊名称。",
        }

    if _hit_any(["arxiv", "preprint"], lower_text):
        return {
            "score": 0.0,
            "label": "arxiv_only",
            "matched_venue": "",
            "reason": "当前仅检测到 arXiv 或预印本信息，未获得正式发表 venue 加分。",
        }

    return {
        "score": 0.0,
        "label": "unknown",
        "matched_venue": "",
        "reason": "未检测到明确正式发表 venue 信息，因此未获得发表可信度加分。",
    }


def _calc_method_rigor(title: str, abstract: str) -> float:
    """识别方法描述是否具备可精读的结构化和技术细节信号。"""
    combined = (title + " " + abstract).lower()
    score = 0.45 * _calc_method_clarity(abstract)

    score += min(_count_term_hits(METHOD_RIGOR_TERMS + METHOD_SIGNAL_KEYWORDS, combined) * 6, 38)

    if _hit_any(["objective function", "loss function", "optimization"], combined):
        score += 8
    if _hit_any(["framework", "algorithm", "model", "system", "method", "approach"], combined):
        score += 10
    if _hit_any(["architecture", "pipeline", "module", "component"], combined):
        score += 8
    if _hit_any(["theorem", "proof", "convergence", "complexity"], combined):
        score += 10
    if len(abstract) < 180:
        score -= 10

    return min(max(score, 0), 100)


def _calc_evidence_strength(title: str, abstract: str) -> float:
    """识别实验、对比、消融或理论证明等证据充分性信号。"""
    combined = (title + " " + abstract).lower()
    score = 0.50 * _calc_evidence(abstract)

    score += min(_count_term_hits(EVIDENCE_STRENGTH_TERMS + EXPERIMENT_SIGNAL_KEYWORDS, combined) * 5, 35)

    if _hit_any(["ablation", "ablation study"], combined):
        score += 12
    if _hit_any(["baseline", "comparison", "compare"], combined):
        score += 8
    if _hit_any(["multiple datasets", "multiple tasks", "across datasets", "across tasks"], combined):
        score += 8
    if _has_numeric_results(abstract):
        score += 8
    if _hit_any(["theorem", "proof", "upper bound", "lower bound", "convergence guarantee"], combined):
        score += 10
    if len(abstract) < 180:
        score -= 8

    return min(max(score, 0), 100)


def _calc_baseline_signal(title: str, abstract: str) -> float:
    """识别 baseline / comparison / SOTA 对比信号。"""
    combined = (title + " " + abstract).lower()
    score = 20.0

    score += min(_count_term_hits(BASELINE_SIGNAL_KEYWORDS, combined) * 15, 60)
    if _hit_any(["strong baseline", "strong baselines"], combined):
        score += 15
    if _hit_any(["compare with", "comparison", "outperform", "state-of-the-art", "sota"], combined):
        score += 10

    return min(max(score, 0), 100)


def _calc_ablation_analysis_signal(title: str, abstract: str) -> float:
    """识别 ablation / analysis / robustness 等深入实验分析信号。"""
    combined = (title + " " + abstract).lower()
    score = 20.0

    score += min(_count_term_hits(ABLATION_SIGNAL_KEYWORDS, combined) * 14, 62)
    if _hit_any(["ablation study", "error analysis", "case study"], combined):
        score += 12
    if _hit_any(["robustness", "sensitivity", "generalization"], combined):
        score += 8

    return min(max(score, 0), 100)


def _calc_reproducibility_signal(paper: dict) -> float:
    """基于标题、摘要和 arXiv comment/journal_ref 判断轻量可复现性信号。"""
    title = paper.get("title", "") or ""
    abstract = paper.get("abstract", "") or ""
    comment = paper.get("comment", "") or ""
    journal_ref = paper.get("journal_ref", "") or ""
    text = f"{title} {abstract} {comment} {journal_ref}".lower()

    score = 25.0
    score += min(_count_term_hits(REPRODUCIBILITY_TERMS + REPRODUCIBILITY_SIGNAL_KEYWORDS, text) * 9, 48)

    if _hit_any(["github", "source code", "code available", "code is available", "repository"], text):
        score += 20
    if _hit_any(["dataset is available", "we release", "publicly available", "public dataset"], text):
        score += 12
    if _hit_any(["implementation details", "hyperparameter", "hyperparameters", "experimental setup"], text):
        score += 10

    return min(max(score, 0), 100)


def _calc_mainstream_signal(title: str, abstract: str, matched_terms: list[str]) -> float:
    """
    当前结果集主流路线信号。

    这只表示论文与当前搜索结果中共同出现的术语相重合，不代表真实领域主流程度。
    """
    combined = (title + " " + abstract).lower()
    if not matched_terms:
        score = 50.0
    else:
        score = 35.0 + min(len(matched_terms) * 12, 50)

    if _hit_any(["benchmark", "baseline", "standard", "widely used", "state-of-the-art"], combined):
        score += 10

    return min(max(score, 0), 100)


def _calc_limitation_value(title: str, abstract: str) -> float:
    """识别是否能提示局限、开放问题或后续研究空间。"""
    combined = (title + " " + abstract).lower()
    score = 25.0

    score += min(_count_term_hits(LIMITATION_VALUE_TERMS + LIMITATION_SIGNAL_KEYWORDS, combined) * 8, 60)
    if _hit_any(["future work", "future research", "open problem", "open question"], combined):
        score += 15
    if _hit_any(["however", "remain", "remains", "challenge", "limitations"], combined):
        score += 8

    return min(max(score, 0), 100)


def _calc_deep_reading_penalty(title: str, abstract: str, paper: dict) -> float:
    """对简单 trick、demo/position/short paper 等不适合精读优先的信号做轻量惩罚。"""
    comment = paper.get("comment", "") or paper.get("comments", "") or ""
    combined = f"{title} {abstract} {comment}".lower()
    penalty = 0.0

    penalty += min(_count_term_hits(LIGHTWEIGHT_TRICK_KEYWORDS, combined) * 8, 20)
    if _hit_any(["simple trick", "prompting trick"], combined):
        penalty += 8
    if _hit_any(["position paper", "demo paper", "extended abstract", "short paper"], combined):
        penalty += 8
    if len(abstract) < 180:
        penalty += 4
    if _is_survey(title, abstract) and _calc_evidence_strength(title, abstract) < 55:
        penalty += 4

    return min(max(penalty, 0), 30)


def _apply_deep_query_relevance_gate(quality_score: float, query_relevance_score: float) -> float:
    """
    深入了解模式相关性门控。

    先计算方法/实验/venue/可复现等质量信号，再用 query relevance 限制其影响。
    零相关或弱相关论文不会因为 benchmark、ablation、venue 等质量词被推到前列。
    """
    quality_score = min(max(float(quality_score or 0.0), 0.0), 100.0)
    relevance = min(max(float(query_relevance_score or 0.0), 0.0), 1.0)

    # 分段门控比简单线性加权更强：零相关论文即使质量信号强，也不能靠前。
    if relevance <= 0:
        return min(quality_score * 0.10, 12.0)
    if relevance < QUERY_RELEVANCE_GATE_MIN:
        return min(quality_score * 0.25 + relevance * 20.0, 30.0)
    if relevance < QUERY_RELEVANCE_GATE_STRONG:
        return min(quality_score * 0.55 + relevance * 25.0, 58.0)

    return min(quality_score * (0.75 + 0.25 * relevance) + relevance * 8.0, 100.0)


def _build_common_research_terms(
    papers: list[dict],
    query_keywords: list[str],
    query_anchor_terms: list[str] | None = None,
) -> list[str]:
    """
    从当前搜索结果中提取共同术语，用于轻量判断论文是否贴近当前结果集常见路线。
    """
    # anchors 保留 data assimilation 这类 query phrase，让路线代表性仍能识别关键短语。
    anchors = _dedupe_preserve_order(query_anchor_terms or [])
    if len(papers) < 2:
        return anchors[:8]

    query_terms = {
        _normalize_research_term(kw)
        for kw in query_keywords
        if _normalize_research_term(kw)
    }
    doc_freq: dict[str, int] = {}

    for paper in papers:
        title = paper.get("title", "") or ""
        abstract = paper.get("abstract", "") or ""
        terms = set(_tokenize_research_terms(f"{title} {abstract}"))
        for term in terms:
            if len(term) < 3:
                continue
            if term in query_terms or term in GENERIC_RESEARCH_TERMS:
                continue
            doc_freq[term] = doc_freq.get(term, 0) + 1

    common = [
        term
        for term, freq in doc_freq.items()
        if freq >= 2
    ]
    common.sort(key=lambda term: (doc_freq[term], len(term), term), reverse=True)
    return _dedupe_preserve_order(anchors + common)[:20]


def _get_matched_mainstream_terms(
    title: str,
    abstract: str,
    common_terms: list[str],
) -> list[str]:
    """返回论文命中的当前结果集共同术语，最多 5 个。"""
    if not common_terms:
        return []

    combined = f"{title} {abstract}".lower()
    tokens = set(_tokenize_research_terms(f"{title} {abstract}"))
    matched = []
    for term in common_terms:
        if _is_query_phrase(term):
            if _query_term_matches(term, combined):
                matched.append(term)
        elif term in tokens:
            matched.append(term)
    return matched[:5]


def _assign_deep_research_role(scores: dict) -> str:
    """给深入了解模式结果标注轻量阅读角色。"""
    if scores.get("score_relevance", 0) < QUERY_RELEVANCE_GATE_MIN * 100:
        return "低相关候选"
    if scores.get("score_relevance", 0) < QUERY_RELEVANCE_GATE_STRONG * 100:
        return "弱相关候选"
    if scores.get("score_method_rigor", 0) >= 50 and scores.get("score_evidence_strength", 0) >= 65:
        return "重点精读候选"
    if scores.get("score_reproducibility_signal", 0) >= 70 and scores.get("score_evidence_strength", 0) >= 60:
        return "复现候选"
    if scores.get("score_mainstream_signal", 0) >= 70 or scores.get("score_contribution", 0) >= 70:
        return "方法对比候选"
    if scores.get("score_limitation_value", 0) >= 60:
        return "研究空白候选"
    return "深入阅读候选"


def _collect_deep_reading_signals(scores: dict) -> list[str]:
    """收集深入了解模式命中的主要信号标签。"""
    signals = []
    if scores.get("score_relevance", 0) >= 65:
        signals.append("high_relevance")
    if scores.get("score_problem_clarity", 0) >= 60:
        signals.append("problem_clarity")
    if scores.get("score_method_rigor", 0) >= 50:
        signals.append("method_completeness")
    if scores.get("score_evidence_strength", 0) >= 60:
        signals.append("evidence_strength")
    if scores.get("score_baseline_signal", 0) >= 55:
        signals.append("baseline_comparison")
    if scores.get("score_ablation_analysis_signal", 0) >= 55:
        signals.append("ablation_analysis")
    if scores.get("score_reproducibility_signal", 0) >= 50:
        signals.append("reproducibility")
    if scores.get("score_limitation_value", 0) >= 55:
        signals.append("limitation_discussion")
    if scores.get("score_venue_authority", 0) >= 40:
        signals.append("venue_authority")
    return signals


def _build_deep_reading_reason_list(scores: dict) -> list[str]:
    """生成 3-6 条深入阅读推荐理由。"""
    reasons = []
    venue_info = scores.get("venue_authority_info") or {}
    relevance = scores.get("score_relevance", 0)
    query_reasons = scores.get("query_relevance_reasons") or []

    if relevance >= 65:
        reasons.append(query_reasons[0] if query_reasons else "该论文与当前查询方向相关性较高，适合作为深入阅读候选。")
    elif relevance >= QUERY_RELEVANCE_GATE_STRONG * 100:
        reasons.append(query_reasons[0] if query_reasons else "该论文与当前查询有明确主题匹配，质量信号可作为深入阅读排序依据。")
    elif relevance >= QUERY_RELEVANCE_GATE_MIN * 100:
        reasons.append("仅检测到中等偏弱的查询相关信号，方法/实验/venue 等质量信号已受到相关性门控限制。")
    elif relevance > 0:
        reasons.append("仅检测到很弱的查询相关信号，已在深入了解模式中明显降权。")
    else:
        reasons.append("未检测到明确查询主题词命中，benchmark / evaluation / ablation / venue 等质量信号不会单独推高排序。")

    if venue_info.get("score", 0) >= 40:
        reasons.append(venue_info.get("reason") or "检测到正式发表或权威 venue 信号。")
    else:
        reasons.append(venue_info.get("reason") or "未检测到明确正式发表 venue 信息，建议人工进一步确认发表状态。")

    if scores.get("score_method_rigor", 0) >= 50:
        reasons.append("摘要中包含 framework / architecture / algorithm / pipeline 等方法完整性信号。")

    if scores.get("score_evidence_strength", 0) >= 60:
        reasons.append("检测到 evaluation / benchmark / baseline / ablation / analysis 等实验或深入分析信号。")
    elif scores.get("score_baseline_signal", 0) >= 55:
        reasons.append("检测到 baseline / comparison 等对比信号，适合进一步检查实验设计。")

    if scores.get("score_reproducibility_signal", 0) >= 50:
        reasons.append("检测到 code / dataset / implementation / appendix 等可复现线索，建议打开正文确认。")

    if scores.get("score_limitation_value", 0) >= 55:
        reasons.append("检测到 limitation / discussion / future work / challenge 等可用于批判分析的信号。")

    if not reasons:
        reasons.append("该论文可作为深入阅读候选，但当前标题、摘要和元信息中的质量信号有限，建议人工确认。")

    return reasons[:6]


# ═══════════════════════════════════════════════════════════
# 推荐理由 & 等级
# ═══════════════════════════════════════════════════════════

def _recommendation_label(total: float) -> str:
    if total >= 85:
        return "强烈推荐"
    elif total >= 70:
        return "推荐优先阅读"
    elif total >= 55:
        return "可作为候选"
    elif total >= 40:
        return "低优先级"
    else:
        return "暂不推荐优先读"


def _generate_reason(scores: dict, title: str, abstract: str) -> str:
    """生成中文推荐理由。"""
    dims = {
        "主题相关性": scores.get("score_relevance", 0),
        "贡献价值": scores.get("score_contribution", 0),
        "方法清晰度": scores.get("score_method_clarity", 0),
        "证据支撑": scores.get("score_evidence", 0),
        "新鲜度": scores.get("score_freshness", 0),
        "可读性": scores.get("score_readability", 0),
    }
    total = scores.get("score_total", 0)
    level = _recommendation_label(total)

    sorted_dims = sorted(dims.items(), key=lambda x: x[1], reverse=True)
    top2 = sorted_dims[:2]
    lowest = sorted_dims[-1]

    parts = [f"该论文【{level}】。"]

    # 最高 2 个维度
    top_labels = [n for n, s in top2 if s >= 55]
    if top_labels:
        parts.append(f"它在{'、'.join(top_labels)}方面表现较好。")

    # 最低维度提醒
    if lowest[1] < 45:
        if lowest[0] == "新鲜度" and lowest[1] < 45:
            parts.append("发布时间较早，因此更适合作为基础或背景阅读。")
        elif lowest[0] == "贡献价值" and lowest[1] < 40:
            parts.append("摘要中贡献信号较弱，建议结合 Introduction 判断价值。")
        elif lowest[0] == "证据支撑" and lowest[1] < 40:
            parts.append("当前摘要中实验/理论支撑信号不明显，建议阅读正文确认。")

    # 综述
    if _is_survey(title, abstract):
        parts.append("该论文可能是综述/概览类文章，适合作为领域背景阅读。")

    # 高 evidence
    if scores.get("score_evidence", 0) >= 70:
        parts.append("摘要中包含较明确的实验或理论支撑，适合作为重点阅读或复现参考。")

    # 高 method_clarity
    if scores.get("score_method_clarity", 0) >= 75:
        parts.append("摘要结构清晰，问题-方法-结果均有体现，适合快速理解核心思路。")

    # 低 relevance
    if scores.get("score_relevance", 0) < 50:
        parts.append("与当前搜索关键词匹配一般，建议确认是否与研究方向相关。")

    return "".join(parts)


def _generate_understanding_reason(scores: dict, title: str, abstract: str) -> str:
    """领域了解模式的保守中文推荐理由。"""
    dims = {
        "主题相关性": scores.get("score_relevance", 0),
        "综述/路线价值": scores.get("score_overview_value", 0),
        "经典/代表性信号": scores.get("score_classic_signal", 0),
        "权威元信息信号": scores.get("score_authority_signal", 0),
        "问题定义清晰度": scores.get("score_problem_clarity", 0),
        "方法覆盖度": scores.get("score_method_coverage", 0),
        "Benchmark/Dataset 价值": scores.get("score_benchmark_value", 0),
    }
    top_dims = [
        name for name, score in sorted(dims.items(), key=lambda item: item[1], reverse=True)[:3]
        if score >= 60
    ]

    role = scores.get("understanding_role", "入门候选")
    parts = [f"该论文适合作为领域了解的「{role}」候选。"]

    if top_dims:
        parts.append(f"它在{'、'.join(top_dims)}方面有较强启发式信号。")

    if scores.get("score_overview_value", 0) >= 70:
        parts.append("该论文具有 survey / review / overview / taxonomy 等综述或路线信号，可能适合作为建立领域知识框架的起点。")

    if scores.get("score_benchmark_value", 0) >= 70:
        parts.append("该论文包含 benchmark / dataset / evaluation 信号，适合帮助理解该领域如何评价方法。")

    if scores.get("score_authority_signal", 0) >= 75:
        parts.append("元信息中包含较强的权威发表信号，可作为重点阅读候选；但该判断基于 arXiv 元信息，仍需人工确认。")

    if scores.get("score_classic_signal", 0) >= 70:
        parts.append("该论文发布时间和贡献信号显示出一定代表性潜力，可能适合作为该方向的背景阅读候选。")

    if scores.get("score_relevance", 0) < 45:
        parts.append("但它与当前关键词匹配一般，建议先人工确认是否属于目标研究方向。")

    parts.append("这些判断均为轻量启发式排序信号，不等同于真实引用量、真实经典性或真实学术影响力评价。")
    return "".join(parts)


def _generate_deep_research_reason(scores: dict, title: str, abstract: str) -> str:
    """深入了解模式的保守中文推荐理由。"""
    role = scores.get("deep_reading_role") or scores.get("deep_research_role", "深入阅读候选")
    reasons = scores.get("deep_reading_reasons") or _build_deep_reading_reason_list(scores)
    relevance = scores.get("score_relevance", 0)

    if relevance < QUERY_RELEVANCE_GATE_MIN * 100:
        parts = [f"该论文与当前查询相关性较弱，在深入了解模式中已被明显降权，当前仅作为「{role}」。"]
    elif relevance < QUERY_RELEVANCE_GATE_STRONG * 100:
        parts = [f"该论文与当前查询只有中等偏弱的相关性，质量信号已被门控限制，当前作为「{role}」。"]
    else:
        parts = [f"该论文可作为深入了解的「{role}」。"]

    for reason in reasons[:5]:
        parts.append(reason)

    if scores.get("score_deep_penalty", 0) >= 8:
        parts.append("同时检测到轻量 trick、short/demo/position、摘要过短或综述类证据信号不足等不适合精读优先的信号，因此已做轻量降权。")

    if relevance < 45:
        parts.append("建议先人工确认它是否确实属于目标研究方向，再决定是否投入精读。")

    parts.append("上述判断仅基于标题、摘要和 arXiv 元信息，不等同于真实论文质量、真实引用影响力或真实 venue 等级评价。")
    return "".join(parts)


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def _normalize_query_expansion_key(text: str) -> str:
    """把 query 归一化成便于命中扩展表的 key。"""
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    """按出现顺序去重。"""
    seen: set[str] = set()
    deduped: list[str] = []
    for item in items:
        clean = re.sub(r"\s+", " ", str(item or "").strip().lower())
        if not clean or clean in seen:
            continue
        seen.add(clean)
        deduped.append(clean)
    return deduped


def _query_core_keywords(query: str) -> list[str]:
    """提取用于 query coverage 的核心词，过滤质量信号词。"""
    keywords: list[str] = []
    for keyword in extract_keywords(query or ""):
        kw = keyword.lower().strip()
        if not kw or kw in QUERY_RELEVANCE_QUALITY_TERMS:
            continue
        if len(kw) < 2:
            continue
        keywords.append(kw)
    return _dedupe_preserve_order(keywords)


def _query_anchor_terms(query: str) -> list[str]:
    """保留 data assimilation 等 query expansion 短语，供路线代表性做 phrase-level 匹配。"""
    anchors: list[str] = []
    for term in expand_query_terms(query):
        if not _is_query_phrase(term):
            continue
        if term in QUERY_RELEVANCE_QUALITY_TERMS:
            continue
        anchors.append(term)
    return _dedupe_preserve_order(anchors)[:8]


def _is_query_phrase(term: str) -> bool:
    """判断 query term 是否需要短语/连字符级匹配。"""
    clean = (term or "").strip()
    return " " in clean or "-" in clean or "_" in clean


def _query_term_matches(term: str, text_lower: str) -> bool:
    """query 相关性专用匹配，支持 4D-Var / 4dvar / 4d var 这类写法变体。"""
    if not term or not text_lower:
        return False

    clean = re.sub(r"\s+", " ", term.lower().strip())
    if not clean:
        return False

    pieces = [p for p in re.split(r"[\s\-_]+", clean) if p]
    if len(pieces) >= 2:
        pattern = r"(?<![A-Za-z0-9])" + r"[\s\-_]*".join(re.escape(p) for p in pieces) + r"(?![A-Za-z0-9])"
    else:
        pattern = r"(?<![A-Za-z0-9])" + re.escape(clean) + r"(?:s)?(?![A-Za-z0-9])"

    try:
        return re.search(pattern, text_lower, flags=re.IGNORECASE) is not None
    except re.error:
        return clean in text_lower


def _paper_metadata_text(paper: dict) -> str:
    """拼接用于 venue authority 的安全元信息文本。"""
    fields = [
        "journal_ref", "comment", "comments", "venue", "conference",
        "publication", "published_in", "doi", "arxiv_id", "id",
    ]
    values = []
    for field in fields:
        value = paper.get(field, "")
        if isinstance(value, (list, tuple)):
            values.extend(str(v) for v in value if v)
        elif value:
            values.append(str(value))
    return " ".join(values)


def _find_authority_venue(text: str) -> tuple[str, str]:
    """在集中 venue 列表中查找匹配项，返回 (kind, venue)。"""
    if not text:
        return "", ""

    for kind in ("journal", "conference"):
        for venue in VENUE_AUTHORITY_TERMS.get(kind, []):
            if _venue_term_matches(venue, text):
                return kind, venue
    return "", ""


def _venue_term_matches(venue: str, text: str) -> bool:
    """大小写不敏感的 venue 边界匹配，避免 ICSE 等缩写误匹配。"""
    if not venue or not text:
        return False

    escaped = re.escape(venue)
    escaped = escaped.replace(r"\ ", r"\s+")
    pattern = r"(?<![A-Za-z0-9])" + escaped + r"(?![A-Za-z0-9])"
    try:
        return re.search(pattern, text, flags=re.IGNORECASE) is not None
    except re.error:
        return venue.lower() in text.lower()

def _tokenize_research_terms(text: str) -> list[str]:
    """提取用于当前结果集共同术语统计的轻量英文 token。"""
    if not text:
        return []
    raw_terms = re.findall(r"[a-zA-Z][a-zA-Z0-9-]{2,}", text.lower())
    terms: list[str] = []
    for raw in raw_terms:
        term = _normalize_research_term(raw)
        if term:
            terms.append(term)
    return terms


def _normalize_research_term(term: str) -> str:
    """归一化共同术语 token，避免简单复数造成重复。"""
    term = (term or "").lower().strip("-_ ")
    if not term:
        return ""
    if len(term) > 5 and term.endswith("ies"):
        term = f"{term[:-3]}y"
    elif len(term) > 4 and term.endswith("s") and not term.endswith(("ss", "sis", "ous")):
        term = term[:-1]
    return term

def _word_matches(keyword: str, text_lower: str) -> bool:
    """单词型关键词用 \\b 边界匹配，短语用 substring。"""
    kw = keyword.lower().strip()
    if not kw:
        return False
    # 短语
    if " " in kw or "-" in kw:
        return kw in text_lower
    # 单侧边界匹配（允许 model/models 等合理变体）
    try:
        # 严格：\\b{kw}\\b
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
            return True
        # 复数
        if len(kw) >= 3 and re.search(r"\b" + re.escape(kw) + r"s\b", text_lower):
            return True
    except re.error:
        return kw in text_lower
    return False


def _count_hits(keyword: str, text_lower: str) -> int:
    """严谨的命中计数（单词边界）。"""
    kw = keyword.lower().strip()
    if not kw:
        return 0
    try:
        return len(re.findall(r"\b" + re.escape(kw) + r"(?:s)?\b", text_lower))
    except re.error:
        return text_lower.count(kw)


def _hit_any(terms: list[str], text_lower: str) -> bool:
    """检查文本中是否命中任意一个术语。"""
    for term in terms:
        if _word_matches(term, text_lower):
            return True
    return False


def _count_term_hits(terms: list[str], text_lower: str) -> int:
    """按术语列表统计命中数量，每个术语最多记一次。"""
    return sum(1 for term in terms if _word_matches(term, text_lower))


def _paper_age_days(published: str) -> int | None:
    """返回论文距今天数，无法解析时返回 None。"""
    if not published:
        return None
    try:
        pub_date = datetime.strptime(published[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    days = (datetime.now(timezone.utc) - pub_date).days
    return max(days, 0)


def _sent_count(text: str) -> int:
    """粗略估计句子数量。"""
    if not text:
        return 0
    return max(1, len(re.split(r"[.!?]+", text)))


def _has_numeric_results(text: str) -> bool:
    """检测摘要中是否出现数字结果表达。"""
    patterns = [
        r"\d+(?:\.\d+)?%",           # 12.5%
        r"\d+\.\d+x",                # 3.2x
        r"\d+\s*(?:datasets|benchmarks|tasks|domains)",  # 10 datasets
    ]
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def _is_survey(title: str, abstract: str) -> bool:
    """判断是否为综述/概览类论文。"""
    survey_kw = ["survey", "review", "overview", "literature", "tutorial"]
    combined = (title + " " + abstract).lower()
    for kw in survey_kw:
        if _word_matches(kw, combined):
            return True
    return False
