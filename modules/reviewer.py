"""
PaperPilot Reviewer 视角分析模块。

从审稿人角度分析论文的优点、缺点、创新性、方法可靠性、实验充分性、
潜在审稿问题和接收风险。支持 LLM 和 Fallback 双模式。
追踪论文字段兼容（summary/score/score_breakdown）。
来源隔离（PDF/搜索结果/追踪 独立上下文）。

不依赖向量数据库、趋势分析、关系图谱、文献综述。
"""

import hashlib
import json
import re
from datetime import datetime, timezone

from modules.llm_client import call_llm, is_llm_available
from modules.utils import extract_keywords

VALID_DECISIONS = {"strong_accept", "weak_accept", "borderline", "weak_reject", "strong_reject", "unknown"}
VALID_CONFIDENCES = {"high", "medium", "low"}
VALID_MODES = {"llm", "fallback"}
VALID_SCOPES = {"full_text", "abstract_only", "metadata_only"}

# ── Reviewer 证据关键词 ───────────────────────────────────

REVIEWER_EVIDENCE_KEYWORDS = [
    "contribution", "novel", "novelty",
    "propose", "proposed", "proposes",
    "method", "approach", "framework", "model", "architecture", "algorithm",
    "experiment", "evaluation", "benchmark", "dataset", "baseline", "ablation",
    "result", "performance", "comparison", "compare",
    "limitation", "failure", "future work", "discussion", "analysis",
    "theorem", "proof", "convergence", "bound",
    "training", "inference", "optimization", "loss",
]

# ── LLM Prompts ───────────────────────────────────────────

REVIEWER_SYSTEM = """你是一个严谨的学术审稿人。请根据给定论文内容生成结构化审稿分析。

必须遵守：
1. 只能基于提供的论文内容分析，不得编造任何信息；
2. 不得虚构实验、baseline、dataset、指标或数值结果；
3. 如果信息不足，明确指出「信息不足，无法判断」；
4. 必须区分全文分析和仅摘要分析；
5. 使用中文输出；
6. 每个重要判断尽量关联依据；
7. 输出必须是合法 JSON，不要输出 Markdown 表格或自由文本；
8. 模拟接收倾向只是辅助判断，不代表真实会议结果。

输出 JSON 结构：
{
  "overall_assessment": "总体评价（2-3句话）",
  "strengths": ["优点1", "优点2"],
  "weaknesses": ["不足1", "不足2"],
  "novelty_analysis": "创新性分析",
  "methodology_analysis": "方法合理性分析",
  "experiment_analysis": "实验充分性分析",
  "clarity_analysis": "写作清晰度分析",
  "potential_questions": ["审稿人可能追问的问题1"],
  "risk_flags": ["接收风险点1"],
  "improvement_suggestions": ["改进建议1"],
  "recommendation": {"decision": "weak_accept", "reason": "...", "score": 7},
  "confidence": "high"
}

只输出 JSON。"""

REVIEWER_USER = """## 论文信息
标题：{title}
作者：{authors}
发布时间：{published}
分类：{categories}

## 论文摘要
{abstract}

## PDF 提取文本（前 {text_chars} 字）
{pdf_text}

## 已有结构化总结
{summary_text}

## 论文评分
综合分：{score_total}，主题相关性：{score_relevance}，贡献价值：{score_contribution}，方法清晰度：{score_method_clarity}，证据支撑：{score_evidence}
评分说明：{rank_reason}

## 用户问答历史
{qa_text}

请基于以上信息生成审稿分析 JSON。"""


# ═══════════════════════════════════════════════════════════
# 公共函数
# ═══════════════════════════════════════════════════════════

def analyze_as_reviewer(
    paper: dict | None = None,
    paper_text: str | None = None,
    chunks: list[dict] | None = None,
    summary: dict | str | None = None,
    qa_history: list[dict] | None = None,
    ranking_info: dict | None = None,
    source_type: str = "unknown",
    force_fallback: bool = False,
) -> dict:
    """主入口。force_fallback=True 时跳过 LLM，直接使用规则分析。"""
    # Reviewer 模块只消费当前论文上下文，不主动读取全局状态，避免 PDF/QA 串论文。
    context = build_review_context(
        paper=paper, paper_text=paper_text, chunks=chunks,
        summary=summary, qa_history=qa_history, ranking_info=ranking_info,
    )

    paper_id = _get_paper_id(paper) if paper else ""
    paper_title = _get_paper_title(paper) if paper else "未知"

    if not force_fallback and is_llm_available():
        result = _try_llm_review(context)
        if result is not None:
            return _enrich_result(result, paper_id, paper_title, source_type, context)

    return _enrich_result(
        analyze_as_reviewer_fallback(context),
        paper_id, paper_title, source_type, context,
    )


def build_review_context(
    paper: dict | None = None,
    paper_text: str | None = None,
    chunks: list[dict] | None = None,
    summary: dict | str | None = None,
    qa_history: list[dict] | None = None,
    ranking_info: dict | None = None,
    max_chars: int = 8000,
) -> dict:
    """构建 Reviewer 分析上下文。兼容追踪论文字段。"""
    if paper is None:
        paper = {}

    title = paper.get("title") or ""
    authors = ", ".join(paper.get("authors", [])[:5]) if paper.get("authors") else "未知"
    published = paper.get("published") or "未知"
    abstract = _compat_abstract(paper)
    categories = ", ".join(paper.get("categories", [])) if paper.get("categories") else "未知"

    score_total = (
        paper.get("score_total")
        or paper.get("score")
        or 0
    )
    score_breakdown = paper.get("score_breakdown", {}) or {}
    score_relevance = score_breakdown.get("relevance", paper.get("score_relevance", 0))
    score_contribution = score_breakdown.get("contribution", paper.get("score_contribution", 0))
    score_method = score_breakdown.get("method_clarity", paper.get("score_method_clarity", 0))
    score_evidence = score_breakdown.get("evidence", paper.get("score_evidence", 0))
    rank_reason = (
        paper.get("recommendation_reason")
        or paper.get("rank_reason")
        or paper.get("score_reason")
        or ""
    )

    if ranking_info is None:
        ranking_info = {
            "score_relevance": score_relevance,
            "score_contribution": score_contribution,
            "score_method_clarity": score_method,
            "score_evidence": score_evidence,
        }

    # PDF 全文优先，其次使用 chunks，最后退回摘要/元数据，分析范围会在结果中标明。
    if paper_text:
        pdf_text = paper_text[:max_chars]
    elif chunks:
        pdf_text = "\n\n".join(c["text"][:500] for c in chunks[:10])
    else:
        pdf_text = "（未提供 PDF 文本）"

    if isinstance(summary, dict):
        parts = []
        for k, label in [
            ("one_sentence", "一句话"), ("core_problem", "核心问题"),
            ("method", "方法"), ("contributions", "贡献"), ("limitations", "局限"),
        ]:
            v = summary.get(k, "")
            if v:
                parts.append(f"- {label}: {v[:300]}")
        summary_text = "\n".join(parts) if parts else "（暂无）"
    elif isinstance(summary, str):
        summary_text = summary[:2000]
    else:
        summary_text = "（暂无）"

    # 只取最近 3 条问答，避免 prompt 过长，同时保留用户精读过程中的关键信息。
    if qa_history:
        qa_parts = []
        for qa in qa_history[-3:]:
            qa_parts.append(f"Q: {qa.get('question','')[:200]}\nA: {qa.get('answer','')[:300]}")
        qa_text = "\n---\n".join(qa_parts)
    else:
        qa_text = "（暂无问答历史）"

    return {
        "title": title,
        "authors": authors,
        "published": published,
        "categories": categories,
        "abstract": abstract,
        "pdf_text": pdf_text,
        "text_chars": len(pdf_text),
        "summary_text": summary_text,
        "qa_text": qa_text,
        "score_total": score_total,
        "score_relevance": ranking_info.get("score_relevance", 0),
        "score_contribution": ranking_info.get("score_contribution", 0),
        "score_method_clarity": ranking_info.get("score_method_clarity", 0),
        "score_evidence": ranking_info.get("score_evidence", 0),
        "rank_reason": rank_reason,
        "_has_pdf": bool(paper_text) or bool(chunks),
        "_has_full_text": bool(paper_text) or (bool(chunks) and len(chunks) > 1),
    }


def extract_evidence_for_review(
    question: str,
    context: dict,
    top_k: int = 8,
) -> list[dict]:
    """
    从上下文中提取与 Reviewer 分析相关的依据片段。
    使用审稿相关关键词，覆盖标题、摘要、PDF、总结、QA。
    """
    # 证据提取是规则检索，不是引用网络；用于解释“为什么给出这些审稿建议”。
    keywords = REVIEWER_EVIDENCE_KEYWORDS
    if question and question != "review":
        for kw in extract_keywords(question):
            if kw not in keywords:
                keywords.append(kw)

    sources = []
    title = context.get("title", "")
    if title:
        sources.append(("metadata", title))
    if context.get("abstract"):
        sources.append(("abstract", context["abstract"]))
    pdf = context.get("pdf_text", "")
    if pdf and not pdf.startswith("（未提供"):
        # 按段落拆分 PDF
        for para in pdf.split("\n\n"):
            para = para.strip()
            if len(para) > 50:
                sources.append(("pdf_chunk", para[:800]))
    if context.get("summary_text") and not context["summary_text"].startswith("（暂无"):
        sources.append(("summary", context["summary_text"]))
    qa = context.get("qa_text", "")
    if qa and not qa.startswith("（暂无"):
        sources.append(("qa_history", qa))

    scored = []
    for src_name, src_text in sources:
        score = 0
        matched = set()
        for kw in keywords:
            count = src_text.lower().count(kw.lower())
            if count > 0:
                score += count
                matched.add(kw)
        if score > 0:
            snippet = src_text[:500]
            reason = f"命中关键词: {', '.join(list(matched)[:5])}"
            scored.append({
                "source": src_name,
                "text": snippet,
                "reason": reason,
                "chunk_id": src_name,
                "_score": score,
            })

    scored.sort(key=lambda x: x["_score"], reverse=True)
    result = []
    for e in scored[:top_k]:
        del e["_score"]
        result.append(e)

    if not result:
        result = [{
            "source": "system",
            "text": "当前论文文本中未找到足够审稿依据。",
            "reason": "缺少可解析的 PDF 文本或摘要信息，请尝试上传 PDF 或选择包含摘要的论文。",
            "chunk_id": "system",
        }]

    return result


# ── LLM 模式 ──────────────────────────────────────────────

def _try_llm_review(context: dict) -> dict | None:
    """尝试 LLM 分析，失败返回 None。"""
    user_prompt = REVIEWER_USER.format(
        title=context["title"],
        authors=context["authors"],
        published=context["published"],
        categories=context["categories"],
        abstract=context["abstract"],
        text_chars=context["text_chars"],
        pdf_text=context["pdf_text"],
        summary_text=context["summary_text"],
        score_total=context["score_total"],
        score_relevance=context["score_relevance"],
        score_contribution=context["score_contribution"],
        score_method_clarity=context["score_method_clarity"],
        score_evidence=context["score_evidence"],
        rank_reason=context["rank_reason"],
        qa_text=context["qa_text"],
    )

    response = call_llm(REVIEWER_SYSTEM, user_prompt, temperature=0.3)
    if response is None:
        return None
    parsed = _parse_review_json(response)
    if parsed is None:
        return None
    return parsed


def _parse_review_json(response: str) -> dict | None:
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass
    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    m = re.search(r"\{[\s\S]*\}", response)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


# ── Fallback 模式 ─────────────────────────────────────────

def analyze_as_reviewer_fallback(context: dict) -> dict:
    # Fallback 审稿分析只根据关键词和已有排序分数生成保守判断，不替代真实审稿。
    abstract = context.get("abstract", "")
    pdf_text = context.get("pdf_text", "")
    combined = (abstract + " " + pdf_text).lower() if pdf_text else abstract.lower()
    s_cont = context.get("score_contribution", 0)
    s_evid = context.get("score_evidence", 0)
    s_meth = context.get("score_method_clarity", 0)
    s_total = context.get("score_total", 0)

    strengths = []
    if _has_any(["propose", "introduce", "present", "novel", "new method"], combined):
        strengths.append("该论文提出了新的方法/框架/模型。")
    if s_cont >= 60:
        strengths.append("摘要中贡献信号较为明确，可能具有较好的学术价值。")
    if _has_any(["experiment", "evaluation", "benchmark", "dataset"], combined):
        strengths.append("论文包含实验/评测/数据集验证。")
    if s_evid >= 50:
        strengths.append("论文展示了较好的实验或理论支撑。")
    if not strengths:
        strengths.append("基于已有信息难以判断论文的主要优点，建议阅读全文。")

    weaknesses = []
    if not _has_any(["experiment", "evaluation"], combined):
        weaknesses.append("摘要或论文文本中未检测到明确的实验/评测描述，可能缺乏实证验证。")
    if not _has_any(["baseline", "comparison", "compare"], combined):
        weaknesses.append("未检测到与基线方法的明确对比，可能缺乏对比实验。")
    if not _has_any(["limitation", "failure", "weakness"], combined):
        weaknesses.append("未检测到对方法局限性或失败案例的讨论。")
    if s_evid < 30:
        weaknesses.append("证据支撑评分较低，论文的实验或理论论证可能不足。")
    if not weaknesses:
        weaknesses.append("基于已有信息难以判断论文的主要不足，建议阅读全文。")

    novelty = (
        "基于分析，该论文可能具有较好的创新性。" if s_cont >= 70
        else "论文可能具有一定的创新性，但基于已有信息无法确定其与前沿工作的区别。" if s_cont >= 40
        else "当前信息不足以充分判断论文的创新性。建议对比 Introduction 和 Related Work。"
    )
    method_analysis = (
        "摘要中方法描述较为清晰，包含了问题-方法-结果的结构化信息。" if s_meth >= 60
        else "摘要中包含方法相关描述，但细节不够充分。" if _has_any(["method", "approach", "framework", "algorithm"], combined)
        else "当前文本中未找到足够的方法描述，无法判断方法合理性。建议阅读全文。"
    )
    experiment_analysis = (
        "论文文本中检测到实验/评测相关描述，可能包含一定的实证验证。" if _has_any(["experiment", "evaluation", "benchmark", "dataset", "result", "accuracy", "performance"], combined)
        else "当前文本中未检测到实验或评测相关描述。无法评估实验充分性。"
    )
    clarity = (
        "摘要长度适中，可能包含较好的结构化信息。" if len(abstract) >= 800
        else "摘要长度一般，信息量可能有限。" if len(abstract) >= 300
        else "摘要较短或缺失，写作清晰度难以判断。"
    )

    questions = [
        "与最相关工作的本质区别是什么？",
        "方法的泛化性和鲁棒性如何？在不同数据集/场景下的表现如何？",
        "是否有充分的 ablation study 来验证各组件的贡献？",
        "计算成本和实际部署限制是什么？",
        "方法的失败案例和局限性是什么？",
    ]

    risks = []
    if not _has_any(["experiment", "benchmark", "dataset"], combined):
        risks.append("缺少实验验证或基准测试，可能被审稿人质疑。")
    if not _has_any(["baseline", "comparison"], combined):
        risks.append("缺少与 baseline 的对比，方法效果的显著性存疑。")
    if s_evid < 30:
        risks.append("证据支撑评分较低，论文可能难以说服审稿人。")
    if len(abstract) < 300 and not context.get("_has_pdf"):
        risks.append("摘要过短且未提供全文，可能在初审阶段被直接拒稿。")
    if not risks:
        risks.append("基于已有信息暂未发现明确的接收风险，但需阅读全文确认。")

    if s_total >= 75 and s_evid >= 50:
        decision, rec_reason, rec_score = "weak_accept", "综合评分较高，摘要中方法描述和证据支撑信号较好。", 7
    elif s_total >= 55:
        decision, rec_reason, rec_score = "borderline", "评分中等，需进一步确认方法和实验细节。", 5
    elif s_total >= 35:
        decision, rec_reason, rec_score = "weak_reject", "评分较低，证据或方法描述不足。", 4
    else:
        decision, rec_reason, rec_score = "unknown", "信息严重不足，无法给出有意义的推荐。", 3

    suggestions = []
    if not _has_any(["experiment", "evaluation"], combined):
        suggestions.append("建议补充充分的实验验证，包括多个数据集和基线对比。")
    if not _has_any(["ablation"], combined):
        suggestions.append("建议增加 ablation study 以验证各组件的贡献。")
    if not _has_any(["limitation", "failure"], combined):
        suggestions.append("建议在论文中明确讨论方法的局限性和失败案例。")
    if len(abstract) < 300:
        suggestions.append("建议完善摘要，清晰包含研究问题、方法、实验和结论。")
    suggestions.append("建议与更多 related work 进行深入对比和讨论。")

    return {
        "overall_assessment": f"该论文综合评分 {s_total}/100。基于当前可用的论文信息，以下为自动生成的审稿分析。⚠️ 当前为 fallback 模式，分析基于规则模板，精度有限。",
        "strengths": strengths,
        "weaknesses": weaknesses,
        "novelty_analysis": novelty,
        "methodology_analysis": method_analysis,
        "experiment_analysis": experiment_analysis,
        "clarity_analysis": clarity,
        "potential_questions": questions,
        "risk_flags": risks,
        "improvement_suggestions": suggestions,
        "recommendation": {"decision": decision, "reason": rec_reason, "score": rec_score},
        "confidence": _calc_confidence(combined, context),
    }


# ═══════════════════════════════════════════════════════════
# 结果增强
# ═══════════════════════════════════════════════════════════

def _enrich_result(raw: dict, paper_id: str, paper_title: str, source_type: str, context: dict) -> dict:
    """补全标准化字段。"""
    # 所有模式统一补 paper_id、分析范围和证据，方便 app.py 与笔记模块复用。
    result = normalize_review_result(raw)

    result["paper_id"] = paper_id
    result["paper_title"] = paper_title
    result["source_type"] = source_type
    result["analysis_scope"] = _determine_scope(context)
    result["evidence"] = extract_evidence_for_review(
        " ".join(REVIEWER_EVIDENCE_KEYWORDS[:20]), context,
    )
    result["created_at"] = datetime.now(timezone.utc).isoformat()
    result["success"] = True
    result["message"] = (
        "LLM 分析完成" if result.get("mode") == "llm" else "Fallback 规则分析完成"
    )
    return result


def normalize_review_result(result: dict) -> dict:
    """统一字段，补默认值。"""
    # LLM 输出可能缺字段或类型不稳定，归一化后 UI 才能稳定渲染。
    merged = {
        "overall_assessment": "",
        "strengths": [],
        "weaknesses": [],
        "novelty_analysis": "",
        "methodology_analysis": "",
        "experiment_analysis": "",
        "clarity_analysis": "",
        "potential_questions": [],
        "risk_flags": [],
        "improvement_suggestions": [],
        "recommendation": {"decision": "unknown", "reason": "", "score": 5},
        "confidence": "low",
        "evidence": [],
        "mode": "fallback",
    }
    merged.update(result)

    for arr_key in ["strengths", "weaknesses", "potential_questions", "risk_flags", "improvement_suggestions"]:
        val = merged.get(arr_key, [])
        if not isinstance(val, list):
            val = [str(val)]
        if not val:
            val = ["基于已有信息无法判断。"]
        merged[arr_key] = val
    for str_key in ["overall_assessment", "novelty_analysis", "methodology_analysis", "experiment_analysis", "clarity_analysis"]:
        if not merged.get(str_key):
            merged[str_key] = "信息不足，无法给出有意义的分析。建议上传 PDF 全文或提供更完整的论文信息。"
    rec = merged.get("recommendation", {})
    if not isinstance(rec, dict):
        rec = {}
    if rec.get("decision") not in VALID_DECISIONS:
        rec["decision"] = "unknown"
    if not isinstance(rec.get("score"), (int, float)) or rec["score"] < 1 or rec["score"] > 10:
        rec["score"] = 5
    if not rec.get("reason"):
        rec["reason"] = "基于已有信息推断。"
    merged["recommendation"] = rec
    if merged.get("confidence") not in VALID_CONFIDENCES:
        merged["confidence"] = "low"
    if merged.get("mode") not in VALID_MODES:
        merged["mode"] = "fallback"
    if not merged.get("evidence") or not isinstance(merged.get("evidence"), list):
        merged["evidence"] = [{
            "source": "system",
            "text": "当前论文文本中未找到足够审稿依据。",
            "reason": "缺少可解析的 PDF 文本或摘要信息，请尝试上传 PDF 或选择包含摘要的论文。",
            "chunk_id": "system",
        }]
    merged.setdefault("success", True)
    merged.setdefault("message", "")
    merged.setdefault("paper_id", "")
    merged.setdefault("paper_title", "")
    merged.setdefault("source_type", "unknown")
    merged.setdefault("analysis_scope", "metadata_only")
    merged.setdefault("created_at", "")
    return merged


# ═══════════════════════════════════════════════════════════
# Markdown
# ═══════════════════════════════════════════════════════════

def format_review_markdown(review_result: dict | None = None) -> str:
    if not review_result:
        return "暂无 Reviewer 视角分析。"
    r = normalize_review_result(review_result)
    mode_note = "（⚠️ Fallback 模式）" if r["mode"] == "fallback" else "（🤖 LLM 生成）"

    parts = [
        f"**分析论文：** {r.get('paper_title', '未知')}",
        f"**来源类型：** {r.get('source_type', '未知')}",
        f"**分析范围：** {_scope_label(r.get('analysis_scope', 'metadata_only'))}",
        f"**生成模式：** {mode_note}",
        f"**置信度：** {r['confidence']}",
        "",
        "### 总体评价",
        r["overall_assessment"],
        "",
        "### 主要优点",
    ]
    for s in r["strengths"]:
        parts.append(f"- {s}")
    parts.extend(["", "### 主要不足"])
    for w in r["weaknesses"]:
        parts.append(f"- {w}")
    parts.extend(["", "### 创新性分析", r["novelty_analysis"], "",
         "### 方法合理性分析", r["methodology_analysis"], "",
         "### 实验充分性分析", r["experiment_analysis"], "",
         "### 写作清晰度分析", r["clarity_analysis"], "",
         "### 审稿人可能追问的问题"])
    for q in r["potential_questions"]:
        parts.append(f"- {q}")
    parts.extend(["", "### 接收风险"])
    for rf in r["risk_flags"]:
        parts.append(f"- {rf}")
    parts.extend(["", "### 改进建议"])
    for s in r["improvement_suggestions"]:
        parts.append(f"- {s}")
    parts.append("")
    rec = r["recommendation"]
    decision_labels = {
        "strong_accept": "Strong Accept", "weak_accept": "Weak Accept",
        "borderline": "Borderline", "weak_reject": "Weak Reject",
        "strong_reject": "Strong Reject", "unknown": "Unknown",
    }
    parts.append("### 模拟审稿倾向")
    parts.append(f"- 决定：{decision_labels.get(rec.get('decision','unknown'), rec.get('decision','unknown'))}")
    parts.append(f"- 评分：{rec.get('score', 5)}/10")
    parts.append(f"- 理由：{rec.get('reason', '')}")
    parts.append("")
    evidence = r.get("evidence", [])
    if evidence:
        parts.append("### 依据片段")
        for i, e in enumerate(evidence, 1):
            src = e.get("source", "?")
            txt = e.get("text", "")
            reason = e.get("reason", "")
            parts.append(f"**证据 {i}**（{src}）")
            parts.append(f"> {txt[:300]}")
            if reason:
                parts.append(f"*{reason}*")
            parts.append("")
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def is_review_for_current_paper(review_result: dict | None, current_paper: dict | None) -> bool:
    """判断 Reviewer 分析是否与当前笔记论文一致。"""
    # 保存笔记前再次核对，避免把上一篇论文的审稿分析写进当前笔记。
    if not review_result:
        return False
    if not current_paper:
        return True
    r_id = review_result.get("paper_id", "")
    c_id = (
        current_paper.get("paper_id")
        or current_paper.get("arxiv_id")
        or current_paper.get("id")
        or ""
    )
    if r_id and c_id:
        return r_id == c_id
    return review_result.get("paper_title", "").strip() == current_paper.get("title", "").strip()


def _determine_scope(context: dict) -> str:
    if context.get("_has_full_text"):
        return "full_text"
    if context.get("abstract") and len(context["abstract"]) > 50:
        return "abstract_only"
    return "metadata_only"


def _scope_label(scope: str) -> str:
    return {
        "full_text": "全文分析（含 PDF 正文）",
        "abstract_only": "仅摘要分析（未提供 PDF 正文，结论仅供初步筛选参考）",
        "metadata_only": "仅元数据分析（缺少摘要和正文，结论仅供参考）",
    }.get(scope, scope)


def _get_paper_id(paper: dict) -> str:
    pid = paper.get("paper_id") or paper.get("arxiv_id") or paper.get("id") or ""
    if pid:
        return pid
    title = paper.get("title") or ""
    if title:
        return "title_" + hashlib.md5(title.lower().strip().encode()).hexdigest()[:12]
    return "unknown"


def _get_paper_title(paper: dict) -> str:
    return paper.get("title") or paper.get("paper_title") or "未知标题"


def _compat_abstract(paper: dict) -> str:
    return (
        paper.get("abstract")
        or paper.get("summary")
        or paper.get("description")
        or ""
    )


def _has_any(terms: list[str], text: str) -> bool:
    for t in terms:
        try:
            if re.search(r"\b" + re.escape(t) + r"\b", text):
                return True
        except re.error:
            if t in text:
                return True
    return False


def _calc_confidence(combined: str, context: dict) -> str:
    has_pdf = context.get("_has_pdf", False)
    has_abstract = len(context.get("abstract", "")) > 200
    has_exp = _has_any(["experiment", "evaluation", "benchmark"], combined)
    if has_pdf and has_exp:
        return "high"
    if has_abstract or has_pdf:
        return "medium"
    return "low"
