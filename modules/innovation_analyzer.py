"""
PaperPilot 创新点分析模块。

从论文标题、摘要、PDF 文本、已有总结和问答历史中提取结构化创新性分析。
支持 LLM 和 Fallback 双模式，不引入向量数据库或复杂 NLP。

依赖：
- modules/llm_client.py（LLM 调用）
- modules/utils.py（关键词提取）
"""

import json
import re
from modules.llm_client import call_llm, is_llm_available
from modules.utils import extract_keywords

# ── 创新关键词 ────────────────────────────────────────────

INNOVATION_KEYWORDS = [
    "novel", "propose", "proposed", "introduce", "first", "new",
    "improve", "improvement", "outperform", "contribution",
    "method", "framework", "architecture", "dataset", "benchmark",
    "evaluation", "efficient", "robust", "scalable",
    "retrieval", "reasoning", "agent", "multimodal",
    "generation", "training", "inference", "optimization",
    "transformer", "attention", "diffusion", "reinforcement",
]

# ── LLM Prompts ───────────────────────────────────────────

INNOVATION_SYSTEM = """你是一个严谨的学术论文创新点分析专家。请根据提供的论文内容生成结构化创新分析。

必须遵守：
1. 只能基于提供的文本分析，不要编造任何信息；
2. 如果依据不足，明确说明「当前文本中未找到足够依据」；
3. 使用中文输出；
4. 输出必须是合法 JSON；
5. 不要把 Reviewer 接收建议混入创新分析；
6. 不要生成趋势分析或综述。

输出 JSON 结构：
{
  "innovation_summary": "一段话总结该论文的核心创新（中文）",
  "main_contributions": ["贡献1", "贡献2", "贡献3"],
  "novelty_points": ["新颖性1", "新颖性2"],
  "method_innovation": ["方法创新点1", "方法创新点2"],
  "technical_differences": ["与已有工作差异1", "差异2"],
  "comparison_with_existing_work": ["对比说明1"],
  "potential_impact": ["潜在影响1", "影响2"],
  "limitations": ["局限1", "局限2"],
  "confidence": "high / medium / low"
}

只输出 JSON。"""

INNOVATION_USER = """## 论文信息
标题：{title}
作者：{authors}

## 论文摘要
{abstract}

## PDF 文本（前 {text_chars} 字）
{pdf_text}

## 已有总结
{summary_text}

## 问答历史
{qa_text}

请基于以上信息生成创新点分析 JSON。"""


# ── 公共函数 ──────────────────────────────────────────────

def analyze_innovation(
    paper: dict | None = None,
    paper_text: str | None = None,
    chunks: list[dict] | None = None,
    summary: dict | None = None,
    qa_history: list[dict] | None = None,
) -> dict:
    """主入口。返回结构化创新点分析。"""
    # 与 Reviewer 类似：LLM 可用时生成结构化 JSON，不可用时走规则兜底。
    context = _build_context(paper, paper_text, chunks, summary, qa_history)

    if is_llm_available():
        result = _try_llm_innovation(context)
        if result is not None:
            return result

    return _fallback_innovation(context)


def _build_context(
    paper: dict | None,
    paper_text: str | None,
    chunks: list[dict] | None,
    summary: dict | None,
    qa_history: list[dict] | None,
) -> dict:
    if paper is None:
        paper = {}
    title = paper.get("title") or ""
    authors = ", ".join(paper.get("authors", [])[:3]) if paper.get("authors") else "未知"
    abstract = paper.get("abstract") or paper.get("summary") or ""
    max_chars = 6000
    # 上下文优先级：全文 > chunks > 摘要。全文越完整，创新点判断的置信度越高。
    if paper_text:
        pdf_text = paper_text[:max_chars]
    elif chunks:
        pdf_text = "\n\n".join(c["text"][:500] for c in chunks[:10])
    else:
        pdf_text = "（未提供 PDF 文本）"

    if isinstance(summary, dict):
        parts = []
        for k in ["one_sentence", "core_problem", "method", "contributions", "limitations"]:
            v = summary.get(k, "")
            if v:
                parts.append(f"- {v[:300]}")
        summary_text = "\n".join(parts) if parts else "（暂无）"
    elif isinstance(summary, str):
        summary_text = summary[:2000]
    else:
        summary_text = "（暂无）"

    if qa_history:
        qa_parts = []
        for qa in qa_history[-3:]:
            qa_parts.append(f"Q: {qa.get('question','')[:200]}\nA: {qa.get('answer','')[:300]}")
        qa_text = "\n---\n".join(qa_parts)
    else:
        qa_text = "（暂无）"

    return {
        "title": title, "authors": authors, "abstract": abstract,
        "pdf_text": pdf_text, "text_chars": len(pdf_text),
        "summary_text": summary_text, "qa_text": qa_text,
        "_has_pdf": bool(paper_text) or bool(chunks),
    }


# ── LLM 模式 ──────────────────────────────────────────────

def _try_llm_innovation(context: dict) -> dict | None:
    user = INNOVATION_USER.format(
        title=context["title"], authors=context["authors"],
        abstract=context["abstract"], text_chars=context["text_chars"],
        pdf_text=context["pdf_text"], summary_text=context["summary_text"],
        qa_text=context["qa_text"],
    )
    resp = call_llm(INNOVATION_SYSTEM, user, temperature=0.3)
    if resp is None:
        return None
    parsed = _parse_json(resp)
    if parsed is None:
        return None
    result = _normalize_result(parsed)
    result["mode"] = "llm"
    result["evidence_chunks"] = _extract_evidence(context, parsed)
    result["confidence"] = _calc_confidence(context)
    return result


# ── Fallback 模式 ─────────────────────────────────────────

def _fallback_innovation(context: dict) -> dict:
    # Fallback 只抽取包含创新/方法/对比/局限关键词的句子，不主动编造贡献。
    abstract = context["abstract"]
    pdf = context["pdf_text"]
    combined = (abstract + " " + pdf).lower() if pdf else abstract.lower()
    has_pdf = context["_has_pdf"]

    def _extract_sentences(text: str, keywords: list[str], limit: int = 3) -> list[str]:
        if not text:
            return []
        sents = re.split(r"[.!?\n]+", text)
        found = []
        for sent in sents:
            sent_lower = sent.lower().strip()
            if len(sent_lower) < 20:
                continue
            if any(kw in sent_lower for kw in keywords):
                found.append(sent.strip()[:200])
                if len(found) >= limit:
                    break
        return found

    contrib_sents = _extract_sentences(
        abstract + " " + (pdf if has_pdf else ""),
        ["propose", "proposed", "introduce", "present", "novel", "new method", "new approach", "contribution", "framework", "architecture"],
        3,
    )

    novelty_sents = _extract_sentences(
        combined,
        ["novel", "first", "new", "unprecedented", "unlike prior", "different from", "improve upon"],
        2,
    )

    method_sents = _extract_sentences(
        combined,
        ["method", "approach", "framework", "model", "algorithm", "architecture", "training", "inference", "optimization"],
        3,
    )

    tech_diff_sents = _extract_sentences(
        combined,
        ["compared to", "unlike", "in contrast", "previous work", "prior method", "existing", "baseline", "outperform"],
        2,
    )

    impact_sents = _extract_sentences(
        combined,
        ["improve", "outperform", "reduce", "increase", "demo", "application", "potential", "impact", "enable", "benefit"],
        2,
    )

    limit_sents = _extract_sentences(
        combined,
        ["limitation", "future work", "remains", "challenge", "difficult", "fail", "cannot", "not yet", "requires", "assume"],
        2,
    )

    # evidence 用于说明规则分析依据来自标题、摘要、PDF 或总结中的哪些片段。
    evidence = _extract_evidence(context, None)

    result = {
        "innovation_summary": f"该论文关注「{context['title']}」方向。基于当前可用文本，以下为规则级创新分析。⚠️ 当前为 fallback 模式，不等价于专家判断。",
        "main_contributions": contrib_sents if contrib_sents else ["当前文本中未找到充分的主要贡献依据。建议上传 PDF 全文。"],
        "novelty_points": novelty_sents if novelty_sents else ["当前文本中未找到充分的新颖性依据。"],
        "method_innovation": method_sents if method_sents else ["当前文本中未找到充分的方法创新依据。"],
        "technical_differences": tech_diff_sents if tech_diff_sents else ["当前文本中未找到充分的技术差异对比依据。"],
        "comparison_with_existing_work": tech_diff_sents if tech_diff_sents else ["当前文本中未找到充分的已有工作比较依据。"],
        "potential_impact": impact_sents if impact_sents else ["当前文本中未找到充分的潜在影响依据。"],
        "limitations": limit_sents if limit_sents else ["当前文本中未找到充分的局限性讨论依据。建议阅读全文。"],
        "evidence_chunks": evidence,
        "confidence": "low" if not has_pdf else "medium",
        "mode": "fallback",
    }
    return _normalize_result(result)


# ── 证据提取 ──────────────────────────────────────────────

def _extract_evidence(context: dict, parsed: dict | None) -> list[dict]:
    # 从多来源文本中找创新相关关键词，作为 UI 中“依据片段”的轻量解释。
    sources = []
    title = context.get("title", "")
    if title:
        sources.append(("metadata", title))
    abstract = context.get("abstract", "")
    if abstract:
        sources.append(("abstract", abstract))
    pdf = context.get("pdf_text", "")
    if pdf and not pdf.startswith("（未提供"):
        for para in pdf.split("\n\n"):
            para = para.strip()
            if len(para) > 50:
                sources.append(("pdf_chunk", para[:800]))
    summary = context.get("summary_text", "")
    if summary and not summary.startswith("（暂无"):
        sources.append(("summary", summary))

    keywords = INNOVATION_KEYWORDS
    scored = []
    for src_name, src_text in sources:
        score = sum(src_text.lower().count(kw) for kw in keywords)
        if score > 1:
            scored.append({"chunk_id": src_name, "text": src_text[:500], "source": src_name, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    result = scored[:8]
    if not result:
        result = [{"chunk_id": "system", "text": "当前文本中未找到充分的创新点依据。建议上传 PDF 全文或选择包含丰富摘要的论文。", "source": "system", "score": 0}]
    return result


# ── 结果归一化 ────────────────────────────────────────────

def _normalize_result(raw: dict) -> dict:
    # LLM / fallback 都归一化成同一字段结构，笔记生成和页面展示可以共用。
    defaults = {
        "innovation_summary": "", "main_contributions": [], "novelty_points": [],
        "method_innovation": [], "technical_differences": [],
        "comparison_with_existing_work": [], "potential_impact": [],
        "limitations": [], "evidence_chunks": [],
        "confidence": "low", "mode": "fallback",
    }
    merged = dict(defaults)
    merged.update(raw)
    for key in defaults:
        if key.endswith("_chunks") or key == "confidence" or key == "mode":
            continue
        if isinstance(defaults[key], list) and not isinstance(merged.get(key), list):
            merged[key] = [str(merged[key])]
        if isinstance(defaults[key], list) and not merged[key]:
            merged[key] = ["当前文本中未找到足够依据。"]
    return merged


def _parse_json(response: str) -> dict | None:
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


def _calc_confidence(context: dict) -> str:
    has_pdf = context["_has_pdf"]
    has_abstract = len(context.get("abstract", "")) > 200
    if has_pdf:
        return "high"
    if has_abstract:
        return "medium"
    return "low"


# ── Markdown 格式化 ───────────────────────────────────────

def format_innovation_markdown(result: dict | None) -> str:
    """将创新点分析转为 Markdown。"""
    if not result:
        return "暂无当前论文创新点分析。"
    r = _normalize_result(result)
    mode_note = "（⚠️ Fallback 模式）" if r["mode"] == "fallback" else "（🤖 LLM 生成）"
    parts = [
        f"**置信度：** {r['confidence']}  |  **模式：** {mode_note}",
        "",
        "### 创新点概述",
        r["innovation_summary"],
        "",
        "### 主要贡献",
    ]
    for c in r["main_contributions"]:
        parts.append(f"- {c}")
    parts.extend(["", "### 新颖性要点"])
    for n in r["novelty_points"]:
        parts.append(f"- {n}")
    parts.extend(["", "### 方法创新"])
    for m in r["method_innovation"]:
        parts.append(f"- {m}")
    parts.extend(["", "### 技术差异"])
    for d in r["technical_differences"]:
        parts.append(f"- {d}")
    parts.extend(["", "### 与已有工作的比较"])
    for cw in r["comparison_with_existing_work"]:
        parts.append(f"- {cw}")
    parts.extend(["", "### 潜在影响"])
    for pi in r["potential_impact"]:
        parts.append(f"- {pi}")
    parts.extend(["", "### 局限性"])
    for lm in r["limitations"]:
        parts.append(f"- {lm}")
    parts.append("")
    ev = r.get("evidence_chunks", [])
    if ev:
        parts.append("### 依据片段")
        for i, e in enumerate(ev, 1):
            parts.append(f"**证据 {i}**（{e.get('source','?')}）")
            parts.append(f"> {e.get('text','')[:300]}")
            parts.append("")
    return "\n".join(parts)
