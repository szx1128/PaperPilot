"""
PaperPilot 研究趋势分析模块。

基于已有论文元数据（标题、摘要、日期、分类、评分）生成结构化趋势分析，
包括关键词统计、时间分布、分类分布、热点/新兴/高分主题和代表性论文。

纯数据分析模块。不依赖 Streamlit，不引入外部 NLP/ML 库，不修改全局状态。

依赖：
- Python 标准库（re, collections, datetime）
- modules/paper_identity.py（get_paper_id）
"""

import hashlib
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from modules.paper_identity import get_paper_id

# ═══════════════════════════════════════════════════════════
# 停用词
# ═══════════════════════════════════════════════════════════

STOP_WORDS = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "shall", "not", "no", "but", "if", "then", "than", "that", "this",
    "these", "those", "it", "its", "they", "them", "their", "we", "our", "us",
    "you", "your", "he", "she", "his", "her", "as", "by", "from", "with",
    "about", "into", "through", "during", "before", "after", "above", "below",
    "between", "under", "also", "very", "well", "just", "now", "so", "how",
    "which", "what", "when", "where", "who", "while", "over", "out", "up",
    "only", "more", "most", "each", "every", "other", "some", "such", "all",
    "both", "one", "two",
}

GENERIC_TERMS = {
    "paper", "papers", "method", "methods", "model", "models", "approach",
    "approaches", "result", "results", "task", "tasks", "data", "dataset",
    "datasets", "performance", "learning", "neural", "using", "based",
    "propose", "proposed", "proposes", "show", "shows", "shown", "study",
    "studies", "analysis", "system", "systems", "framework", "frameworks",
    "work", "works", "state", "art", "recent", "various", "different",
    "improve", "improved", "improvement", "improvements", "better",
    "large", "small", "high", "low", "many", "much", "novel", "new",
    "existing", "current", "previous", "prior", "first", "use", "used",
    "uses", "demonstrate", "demonstrates", "demonstrated", "effect",
    "effective", "effectiveness", "efficient", "efficiency", "important",
    "key", "challenge", "challenges", "problem", "problems", "issue",
    "issues", "application", "applications", "setting", "experiment",
    "experiments", "experimental", "evaluation", "evaluations", "human",
    "humans", "language", "text", "image", "images", "video", "videos",
    "training", "train", "trained", "inference", "test", "testing",
    "benchmark", "benchmarks", "achieve", "achieves", "achieved",
    "compared", "comparison", "research", "researchers", "field",
    "domain", "domains", "level", "levels", "quality", "process",
    "processing", "information", "knowledge", "network", "networks",
    "design", "designed", "time", "real", "world", "significant",
    "single", "multiple", "specific", "general", "present", "presents",
    "presented", "focus", "focused", "focuses", "address", "addresses",
    "addressed", "explore", "explores", "explored", "introduce",
    "introduces", "introduced", "way", "ways", "need", "needs",
    "potential", "ability", "enable", "enables", "enabled", "support",
    "supported", "provide", "provides", "provided", "develop", "develops",
    "developed", "development", "set", "sets", "able",
}


# ═══════════════════════════════════════════════════════════
# 1. 纸归一化
# ═══════════════════════════════════════════════════════════

def normalize_paper_for_trend(paper: dict, source: str = "") -> dict | None:
    """统一不同来源 paper 的字段，缺失时降级不报错。manual_pdf 返回 None。"""
    # 趋势分析只处理论文元数据；手动 PDF 没有时间/分类/检索来源，无法参与集合趋势统计。
    if not isinstance(paper, dict):
        return None

    pid = get_paper_id(paper) if paper else "unknown"
    if pid == "manual_pdf":
        return None

    title = _safe_str(paper.get("title")) or "Untitled Paper"
    abstract = _safe_str(paper.get("abstract") or paper.get("summary") or "")
    categories = _normalize_categories(paper.get("categories", []))
    primary_cat = _safe_str(paper.get("primary_category") or paper.get("category") or (categories[0] if categories else ""))
    published = _parse_date(paper.get("published") or paper.get("published_date") or paper.get("updated") or "")
    month = published.strftime("%Y-%m") if published else None
    year = published.strftime("%Y") if published else None
    score = _extract_score(paper)

    return {
        "paper_id": pid,
        "title": title,
        "abstract": abstract,
        "text": f"{title} {abstract}".strip()[:3000],
        "published": published,
        "month": month,
        "year": year,
        "categories": categories,
        "primary_category": primary_cat,
        "score": score,
        "source": source or _safe_str(paper.get("source", "")),
        "raw": paper,
    }


# ═══════════════════════════════════════════════════════════
# 2. 多来源收集 & 去重
# ═══════════════════════════════════════════════════════════

def collect_trend_papers(
    ranked_papers: list[dict] | None = None,
    papers: list[dict] | None = None,
    tracked_papers: list[dict] | None = None,
    tracking_history: dict | None = None,
) -> list[dict]:
    """从搜索/排序/追踪中收集论文，按 paper_id 去重，保留更完整版本。"""
    collected: dict[str, dict] = {}

    def _add(paper: dict, source: str):
        # 多入口论文可能重复出现，统一使用 get_paper_id 去重，并保留信息更完整的版本。
        if not isinstance(paper, dict):
            return
        pid = get_paper_id(paper)
        if not pid or pid == "manual_pdf" or pid == "unknown":
            return
        norm = normalize_paper_for_trend(paper, source)
        if norm is None:
            return
        if pid in collected:
            existing = collected[pid]
            if _is_better(norm, existing):
                norm["source"] = existing.get("source", "") + "+" + source
                collected[pid] = norm
        else:
            collected[pid] = norm

    if ranked_papers:
        for p in ranked_papers:
            _add(p, "ranked")
    if papers:
        for p in papers:
            _add(p, "search")
    if tracked_papers:
        for p in tracked_papers:
            _add(p, "tracking")
    if tracking_history and isinstance(tracking_history, dict):
        hist_papers = tracking_history.get("papers", {})
        if isinstance(hist_papers, dict):
            for p in hist_papers.values():
                _add(p, "tracking")
        elif isinstance(hist_papers, list):
            for p in hist_papers:
                _add(p, "tracking")

    result = list(collected.values())
    result.sort(key=lambda p: (p.get("score") or 0), reverse=True)
    return result


# ═══════════════════════════════════════════════════════════
# 3. 关键词统计 → keyword_distribution
# ═══════════════════════════════════════════════════════════

def _extract_keywords_from_papers(papers: list[dict], top_k: int = 20) -> list[dict]:
    """从 title + abstract 提取关键词计数。"""
    if not papers:
        return []
    all_text = " ".join(_safe_str(p.get("text", "")) for p in papers if isinstance(p, dict)).lower()
    if not all_text.strip():
        return []

    tokens = _tokenize_text(all_text)

    # unigrams 负责捕捉单个技术词，后面的 bigrams 负责捕捉更像“研究主题”的短语。
    unigram_counter = Counter()
    for t in tokens:
        unigram_counter[t] += 1

    # bigrams（常用短语）
    bigram_counter = Counter()
    for i in range(1, len(tokens)):
        bigram_counter[tokens[i - 1] + " " + tokens[i]] += 1

    # 保留有意义的 bigrams，避免只展示 method/model/data 这种泛词。
    results = []
    for phrase, count in bigram_counter.most_common(top_k * 3):
        if count >= 2:
            results.append({"keyword": phrase, "count": count})

    # 补充高频 unigrams（去重）
    seen_words = set()
    for r in results:
        for w in r["keyword"].split():
            seen_words.add(w)

    for word, count in unigram_counter.most_common(top_k * 2):
        if count >= 2 and word not in seen_words:
            results.append({"keyword": word, "count": count})

    results.sort(key=lambda x: x["count"], reverse=True)
    return results[:top_k]


# ═══════════════════════════════════════════════════════════
# 4. 时间分布
# ═══════════════════════════════════════════════════════════

def _analyze_time_distribution(papers: list[dict]) -> list[dict]:
    """按月统计论文数量，升序排列。"""
    counter: dict[str, int] = {}
    for p in papers:
        if not isinstance(p, dict):
            continue
        m = p.get("month")
        if m:
            counter[m] = counter.get(m, 0) + 1
    return [{"month": m, "count": c} for m, c in sorted(counter.items())]


# ═══════════════════════════════════════════════════════════
# 5. 分类分布
# ═══════════════════════════════════════════════════════════

def _analyze_category_distribution(papers: list[dict]) -> list[dict]:
    """统计 arXiv 分类分布，降序。"""
    counter = Counter()
    for p in papers:
        if not isinstance(p, dict):
            continue
        cats = p.get("categories", [])
        if not cats:
            counter["Unknown"] += 1
        else:
            for c in cats:
                c = _safe_str(c)
                if c:
                    counter[c] += 1
    if not counter:
        return []
    return [{"category": cat, "count": cnt} for cat, cnt in counter.most_common()]


# ═══════════════════════════════════════════════════════════
# 6. hot_topics / emerging_topics / high_score_topics
# ═══════════════════════════════════════════════════════════

def _analyze_hot_topics(papers: list[dict], top_n: int = 10) -> list[dict]:
    """整体高频主题（基于关键词短语聚合）。"""
    kw = _extract_keywords_from_papers(papers, top_k=top_n * 3)
    # 聚合相似主题
    merged = _merge_similar_keywords(kw)
    return merged[:top_n]


def _analyze_emerging_topics(papers: list[dict], recent_months: int = 6) -> list[dict]:
    """新兴主题：按 recent_months 窗口切分近期/早期，比较关键词频率变化。"""
    from datetime import timedelta
    dated = [p for p in papers if isinstance(p, dict) and p.get("published")]
    if len(dated) < 5:
        # 样本过少，从最新论文中提取近似
        latest = papers[:max(len(papers) // 2, 3)] if papers else []
        kw = _extract_keywords_from_papers(latest, top_k=10)
        return [{
            "topic": k["keyword"],
            "recent_count": k["count"],
            "previous_count": 0,
            "reason": "样本过少（< 5 篇有日期），基于最新论文近似分析",
        } for k in kw[:5]]

    dated.sort(key=lambda p: p["published"])
    latest_date = dated[-1]["published"]

    # 用 recent_months 窗口切分
    try:
        cutoff = latest_date - timedelta(days=recent_months * 30)
    except Exception:
        cutoff = None

    if cutoff:
        recent = [p for p in dated if p["published"] >= cutoff]
        older = [p for p in dated if p["published"] < cutoff]
    else:
        recent = dated
        older = []

    # 如果 recent 或 older 太少，回退到前后半段比较，保证小样本也有可解释输出。
    if len(recent) < 3 or len(older) < 3:
        mid = len(dated) // 2
        recent = dated[mid:]
        older = dated[:mid]

    recent_kw = {k["keyword"]: k["count"] for k in _extract_keywords_from_papers(recent, top_k=50)}
    older_kw = {k["keyword"]: k["count"] for k in _extract_keywords_from_papers(older, top_k=50)}

    emerging = []
    for kw, rc in recent_kw.items():
        oc = older_kw.get(kw, 0)
        if rc > oc and rc >= 2:
            emerging.append({
                "topic": kw,
                "recent_count": rc,
                "previous_count": oc,
                "reason": "近期论文中出现频率明显高于早期样本",
            })

    emerging.sort(key=lambda x: x["recent_count"] - x["previous_count"], reverse=True)
    if not emerging:
        return []
    return emerging[:10]


def _analyze_high_score_topics(papers: list[dict]) -> list[dict]:
    """高分论文集中的关键词主题。"""
    scored = [p for p in papers if isinstance(p, dict) and p.get("score") is not None]
    if not scored:
        return []

    scored.sort(key=lambda p: p["score"], reverse=True)
    top_n = max(5, len(scored) // 5)
    top_papers = scored[:top_n]

    kw = _extract_keywords_from_papers(top_papers, top_k=10)
    return [{"topic": k["keyword"], "count": k["count"]} for k in kw]


# ═══════════════════════════════════════════════════════════
# 7. 代表性论文
# ═══════════════════════════════════════════════════════════

def _select_representative_papers(papers: list[dict], limit: int = 5) -> list[dict]:
    """选出代表性论文：优先高分，其次新发布。"""
    # 代表论文不是“领域经典”，只是当前样本中的高分/较新候选。
    valid = [p for p in papers if isinstance(p, dict)]
    valid.sort(
        key=lambda p: (
            1 if (p.get("score") or 0) > 0 else 0,
            p.get("score") or 0,
            p.get("published") or datetime(2000, 1, 1, tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    reps = []
    for p in valid[:limit]:
        pub = p.get("published")
        reps.append({
            "paper_id": p.get("paper_id", ""),
            "title": (p.get("title", "Untitled") or "Untitled")[:120],
            "published": pub.strftime("%Y-%m-%d") if isinstance(pub, datetime) else _safe_str(pub or p.get("month", "")),
            "score": p.get("score"),
            "categories": p.get("categories", []),
            "url": (_safe_str((p.get("raw") or {}).get("arxiv_url") or (p.get("raw") or {}).get("url") or "")),
        })
    return reps


# ═══════════════════════════════════════════════════════════
# 8. 趋势总结
# ═══════════════════════════════════════════════════════════

def _generate_trend_summary(result: dict) -> str:
    """规则型中文趋势总结，不依赖 LLM。"""
    # 这里生成的是样本趋势描述，不做未来预测，也不声称覆盖完整研究领域。
    parts = []
    paper_count = result.get("paper_count", 0)

    if paper_count == 0:
        return "当前没有可分析的论文。"

    parts.append(f"本次共分析 {paper_count} 篇论文。")

    # 时间分布
    td = result.get("time_distribution", [])
    if td:
        months = [t["month"] for t in td if t.get("count", 0) >= 2]
        if months:
            parts.append(f"从时间分布看，{months[0]} 至 {months[-1]} 的论文数量较集中，说明该方向近期活跃度较高。")

    # 关键词
    kw = result.get("keyword_distribution", [])
    if kw:
        top3 = [k["keyword"] for k in kw[:3]]
        parts.append(f"关键词统计显示，{'、'.join(top3)} 等主题出现频率较高。")

    # 新兴
    em = result.get("emerging_topics", [])
    if em:
        parts.append(f"其中 {em[0]['topic']} 在近期样本中增长明显，可能是值得继续跟踪的方向。")

    # 分类
    cd = result.get("category_distribution", [])
    if cd:
        top_cats = [c["category"] for c in cd[:3] if c["category"] != "Unknown"]
        if top_cats:
            parts.append(f"从 arXiv 分类看，论文主要集中在 {' 和 '.join(top_cats)}。")

    # 高分
    hs = result.get("high_score_topics", [])
    if hs:
        parts.append(f"高分论文集中关注 {'、'.join(h['topic'] for h in hs[:3])} 等方向。")

    # 建议
    if paper_count >= 5:
        parts.append("建议后续重点关注高分论文中的方法改进、评测设置和跨任务泛化能力。")
    else:
        parts.append("由于样本较少，趋势仅供参考。")

    return "".join(parts)


# ═══════════════════════════════════════════════════════════
# 9. 总入口
# ═══════════════════════════════════════════════════════════

def analyze_research_trends(
    papers: list[dict],
    source_name: str = "当前论文集合",
    top_k_keywords: int = 20,
    recent_months: int = 6,
) -> dict:
    """
    主入口。输入论文列表，输出结构化趋势分析。

    参数:
        papers:          论文列表
        source_name:     数据来源名称
        top_k_keywords:  关键词展示数量
        recent_months:   新兴主题时间窗口（月）

    返回:
        dict，包含 success / paper_count / time_distribution / category_distribution
        / keyword_distribution / hot_topics / emerging_topics / high_score_topics
        / representative_papers / trend_summary / warnings
    """
    warnings = []

    # 空数据
    if not papers:
        return {
            "success": True,
            "source_name": source_name,
            "paper_count": 0,
            "time_distribution": [],
            "category_distribution": [],
            "keyword_distribution": [],
            "hot_topics": [],
            "emerging_topics": [],
            "high_score_topics": [],
            "representative_papers": [],
            "trend_summary": "当前没有可分析的论文。",
            "warnings": ["输入论文列表为空"],
        }

    # 归一化：把搜索结果、追踪结果、历史结果统一成同一字段结构后再统计。
    try:
        papers = [
            norm for p in papers if isinstance(p, dict)
            for norm in [normalize_paper_for_trend(p)]
            if norm is not None
        ]
    except Exception as e:
        warnings.append(f"论文归一化过程出现异常: {e}")
        papers = []

    valid = [p for p in papers if isinstance(p, dict)]
    paper_count = len(valid)

    if paper_count == 0:
        return {
            "success": True,
            "source_name": source_name,
            "paper_count": 0,
            "time_distribution": [],
            "category_distribution": [],
            "keyword_distribution": [],
            "hot_topics": [],
            "emerging_topics": [],
            "high_score_topics": [],
            "representative_papers": [],
            "trend_summary": "当前没有可分析的论文。",
            "warnings": warnings + ["归一化后无有效论文"],
        }

    if paper_count < 5:
        warnings.append("样本较少（< 5 篇），趋势仅供参考")

    # 时间分布
    time_dist = []
    try:
        time_dist = _analyze_time_distribution(valid)
    except Exception as e:
        warnings.append(f"时间分布分析异常: {e}")

    # 分类分布
    cat_dist = []
    try:
        cat_dist = _analyze_category_distribution(valid)
    except Exception as e:
        warnings.append(f"分类分布分析异常: {e}")

    # 关键词
    keyword_dist = []
    try:
        keyword_dist = _extract_keywords_from_papers(valid, top_k=top_k_keywords)
    except Exception as e:
        warnings.append(f"关键词提取异常: {e}")

    # hot topics
    hot_topics = []
    try:
        hot_topics = _analyze_hot_topics(valid, top_n=10)
    except Exception as e:
        warnings.append(f"热点主题分析异常: {e}")

    # emerging topics
    emerging = []
    try:
        emerging = _analyze_emerging_topics(valid, recent_months=recent_months)
    except Exception as e:
        warnings.append(f"新兴主题分析异常: {e}")

    # high-score topics
    high_score = []
    try:
        high_score = _analyze_high_score_topics(valid)
    except Exception as e:
        warnings.append(f"高分主题分析异常: {e}")

    # representative papers
    reps = []
    try:
        reps = _select_representative_papers(valid, limit=5)
    except Exception as e:
        warnings.append(f"代表论文选择异常: {e}")

    # 组装结构化结果，UI 可以分别展示时间、分类、关键词和代表论文。
    result = {
        "success": True,
        "source_name": source_name,
        "paper_count": paper_count,
        "time_distribution": time_dist,
        "category_distribution": cat_dist,
        "keyword_distribution": keyword_dist,
        "hot_topics": hot_topics,
        "emerging_topics": emerging,
        "high_score_topics": high_score,
        "representative_papers": reps,
        "trend_summary": "",
        "warnings": warnings,
    }

    # trend_summary
    try:
        result["trend_summary"] = _generate_trend_summary(result)
    except Exception as e:
        result["trend_summary"] = "趋势总结生成失败。"
        result["warnings"].append(f"总结生成异常: {e}")

    return result


# ═══════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════

def _safe_str(val: Any) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    return str(val).strip()


def _normalize_categories(val: Any) -> list[str]:
    if isinstance(val, list):
        return [_safe_str(c) for c in val if _safe_str(c)]
    if isinstance(val, str):
        parts = re.split(r"[,\s]+", val.strip())
        return [p.strip() for p in parts if p.strip()]
    return []


def _parse_date(val: Any) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = _safe_str(val)
    if not s or s.lower() == "unknown":
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


def _extract_score(paper: dict, depth: int = 0) -> float | None:
    if depth > 2:
        return None
    for key in ("score", "score_total", "total_score", "final_score", "rank_score"):
        v = paper.get(key)
        if v is not None and isinstance(v, (int, float)):
            return float(v)
    # 兼容追踪历史中的 score（可能是 int）
    s = paper.get("score")
    if s is not None and isinstance(s, (int, float)):
        return float(s)
    raw = paper.get("raw")
    if isinstance(raw, dict) and raw is not paper:
        return _extract_score(raw, depth + 1)
    return None


def _tokenize_text(text: str) -> list[str]:
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9\-]*[a-zA-Z0-9]|[a-zA-Z]", text.lower())
    out = []
    for w in words:
        w = w.strip("-")
        if len(w) < 3 or w.isdigit() or w in STOP_WORDS or w in GENERIC_TERMS:
            continue
        out.append(w)
    return out


def _merge_similar_keywords(keywords: list[dict]) -> list[dict]:
    """简单合并相似关键词（如 'retrieval augmented' 和 'augmented generation'）。"""
    merged = {}
    for kw in keywords:
        word = kw["keyword"]
        # 用空格分词后的第一个词作为聚合键
        parts = word.split()
        base = parts[0] if parts else word
        if base in merged:
            if kw["count"] > merged[base]["count"]:
                merged[base] = {"topic": word, "count": kw["count"]}
        else:
            merged[base] = {"topic": word, "count": kw["count"]}
    result = list(merged.values())
    result.sort(key=lambda x: x["count"], reverse=True)
    return result


def _is_better(new_paper: dict, existing_paper: dict) -> bool:
    new_abs = len(new_paper.get("abstract", ""))
    old_abs = len(existing_paper.get("abstract", ""))
    new_has_date = new_paper.get("published") is not None
    old_has_date = existing_paper.get("published") is not None
    new_score = new_paper.get("score") or 0
    old_score = existing_paper.get("score") or 0

    if new_has_date and not old_has_date:
        return True
    if new_has_date == old_has_date:
        if new_abs > old_abs:
            return True
        if new_abs == old_abs and new_score > old_score:
            return True
    return False
