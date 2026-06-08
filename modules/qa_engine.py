"""
PaperPilot 论文问答模块。

支持两种模式：
1. LLM 模式：调用 LLM API 基于论文片段回答，带引用
2. Fallback 模式：关键词匹配检索相关片段，组织为可读回答

不引入向量数据库、LangChain、LlamaIndex 等复杂依赖。

依赖：
- modules/llm_client.py（LLM 调用）
- modules/utils.py（文本清洗、关键词提取）
"""

from modules.llm_client import call_llm, is_llm_available
from modules.utils import extract_keywords, clean_text


# ── 常量 ──────────────────────────────────────────────────

DEFAULT_MAX_CONTEXT_CHARS = 5000
DEFAULT_TOP_K = 4


# ── LLM Prompts ───────────────────────────────────────────

QA_SYSTEM_PROMPT = """你是一个严谨的学术论文阅读助手。请根据给定论文片段回答用户问题。

必须遵守以下规则：
1. 使用中文回答；
2. 只能基于提供的论文片段、论文摘要和已有总结；
3. 不要编造上下文中没有的信息；
4. 如果给出的片段不足以回答，请明确说明"根据当前片段无法判断"；
5. 回答要清晰，适合科研人员阅读理解；
6. 如果多个片段都相关，请综合回答，并指出主要依据来自哪些片段。

回答格式：
先用 1-3 段话直接回答问题，然后在末尾用 [引用] 标记列出依据的片段编号。"""

QA_USER_PROMPT_TEMPLATE = """## 论文信息

标题：{title}
作者：{authors}

## 已有总结

{summary_text}

## 论文摘要

{abstract}

## 相关论文片段

{passages}

## 用户问题

{question}

请基于以上信息回答用户问题。"""


# ── 公共函数 ──────────────────────────────────────────────

def answer_question(
    question: str,
    paper: dict | None = None,
    summary: dict | None = None,
    pdf_text: str | None = None,
    max_context_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    paper_text: str | None = None,
    chunks: list[dict] | None = None,
    qa_history: list[dict] | None = None,
) -> dict:
    """
    回答用户关于论文的问题。

    参数:
        question:          用户问题
        paper:             论文信息 dict
        summary:           已生成的结构化总结
        pdf_text:          已解析的 PDF 全文（兼容旧调用，优先用 paper_text）
        max_context_chars: 送入 LLM 的最大上下文字符数
        paper_text:        新的 PDF 全文（优先于 pdf_text）
        chunks:            预分段的段落列表（优先于内部分段）
        qa_history:        问答历史

    返回:
        {
            "success":    bool,
            "mode":       "llm" | "fallback",
            "answer":     str,
            "citations":  [{"page": str, "snippet": str}, ...],
            "error":      str | None
        }
    """
    if not question or not question.strip():
        return _make_error("问题为空，请输入您想了解的问题。")

    # 统一文本来源：paper_text 是新状态字段，pdf_text 保留用于兼容旧调用。
    effective_text = paper_text or pdf_text

    # 检索相关片段：优先使用 app.py 已经切好的 chunks，避免重复切分导致引用位置漂移。
    if chunks:
        # 使用预分段的 chunks
        relevant = _retrieve_relevant_chunks(question, chunks, top_k=DEFAULT_TOP_K)
        context_text = "\n\n".join([c["text"][:1000] for c in relevant])
    elif effective_text:
        chunks = _segment_pdf_text(effective_text)
        relevant = _retrieve_relevant_chunks(question, chunks, top_k=DEFAULT_TOP_K)
        context_text = "\n\n".join([c["text"][:1000] for c in relevant])
    else:
        relevant = []
        context_text = "（未提供 PDF 全文，仅可使用摘要和总结信息）"

    # 截断上下文，控制 LLM 输入长度；Fallback 模式仍会展示检索到的原始片段。
    if len(context_text) > max_context_chars:
        context_text = context_text[:max_context_chars] + "\n... (上下文已截断)"

    # 构建论文信息
    paper_info = _build_paper_info(paper, summary)

    # 尝试 LLM；不可用或失败时自动降级，保证没有 API Key 时问答功能仍可演示。
    if is_llm_available():
        result = _try_llm_qa(question, paper_info, context_text)
        if result is not None:
            return result

    # 降级到 fallback：只做关键词检索和片段展示，不伪装成语义推理。
    return _fallback_qa(question, paper, summary, relevant, effective_text)


# ── 文本分段 ──────────────────────────────────────────────

def _segment_pdf_text(pdf_text: str) -> list[dict]:
    """
    将 PDF 文本按页码标记分割为段落。

    参数:
        pdf_text: 含 "===== Page N =====" 标记的 PDF 文本

    返回:
        [{"page": "Page 1", "text": "段落文本..."}, ...]
    """
    if not pdf_text:
        return []

    import re
    # 按页码标记分割
    parts = re.split(r"={5}\s*Page (\d+)\s*={5}", pdf_text)

    chunks = []
    # parts[0] 是第一个标记之前的内容（通常为空）
    # 之后每两个元素一对：(页码, 内容)
    for i in range(1, len(parts) - 1, 2):
        try:
            page_num = int(parts[i])
            page_text = parts[i + 1].strip()
            if page_text:
                # 每页再按段落分割为更小的 chunks
                paragraphs = _split_into_paragraphs(page_text)
                for para in paragraphs:
                    if len(para) >= 20:  # 过滤太短的
                        chunks.append({
                            "page": f"Page {page_num}",
                            "text": para,
                        })
        except (ValueError, IndexError):
            continue

    return chunks


def _split_into_paragraphs(text: str, max_chars: int = 500) -> list[str]:
    """
    将文本按段落分割，过长段落再按句子切分。

    参数:
        text:     待分割文本
        max_chars: 每段最大字符数

    返回:
        段落列表
    """
    import re

    # 先按双换行分割，尽量保持论文自然段；过长段落再拆句。
    raw_paras = re.split(r"\n\s*\n", text.strip())
    result = []
    for para in raw_paras:
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chars:
            result.append(para)
        else:
            # 按句号切分长段落
            sentences = re.split(r"(?<=[.!?])\s+", para)
            current = ""
            for sent in sentences:
                if len(current) + len(sent) <= max_chars:
                    current += " " + sent if current else sent
                else:
                    if current:
                        result.append(current.strip())
                    current = sent
            if current:
                result.append(current.strip())
    return result


# ── 关键词检索 ────────────────────────────────────────────

def retrieve_relevant_chunks(
    question: str,
    pdf_text: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """
    从 PDF 文本中检索与问题最相关的段落。

    对外暴露供调试使用，内部问答流程直接调用 _retrieve_relevant_chunks。

    参数:
        question: 用户问题
        pdf_text: PDF 全文文本
        top_k:    返回 top k 个片段

    返回:
        [{"page": "...", "text": "...", "score": ...}, ...]
    """
    chunks = _segment_pdf_text(pdf_text)
    return _retrieve_relevant_chunks(question, chunks, top_k)


def _retrieve_relevant_chunks(
    question: str,
    chunks: list[dict],
    top_k: int = DEFAULT_TOP_K,
) -> list[dict]:
    """
    关键词命中分数检索最相关段落。

    参数:
        question: 用户问题
        chunks:   已分段的 chunk 列表
        top_k:    返回 top k

    返回:
        带 score 的 chunk 列表，按分数降序
    """
    keywords = extract_keywords(question)
    if not keywords:
        keywords = question.lower().split()

    scored = []
    for i, chunk in enumerate(chunks):
        text_lower = chunk.get("text", "").lower()
        score = 0
        for kw in keywords:
            kw_lower = kw.lower()
            score += text_lower.count(kw_lower)

        if score > 0:
            scored.append({
                "page": _get_chunk_label(chunk, i),
                "source": _get_chunk_label(chunk, i),
                "text": chunk.get("text", ""),
                "score": score,
            })

    # 按分数降序
    scored.sort(key=lambda x: x["score"], reverse=True)

    # Top K
    top = scored[:top_k]

    # 如果没有命中任何关键词，兜底返回前几个 chunk，让用户知道系统有读到文本但证据不足。
    if not top:
        for i, chunk in enumerate(chunks[:top_k]):
            snippet = chunk.get("text", "")[:300]
            top.append({
                "page": _get_chunk_label(chunk, i),
                "source": _get_chunk_label(chunk, i),
                "text": snippet,
                "score": 0,
            })

    return top


def _get_chunk_label(chunk: dict, index: int) -> str:
    """安全获取 chunk 的页面/位置标识。兼容多种 chunk 格式。"""
    page = chunk.get("page") or chunk.get("page_num")
    if page is not None:
        if isinstance(page, int) or (isinstance(page, str) and page.strip().isdigit()):
            return f"Page {page}"
        # \"Page 1\" 这种字符串已经是最终格式，直接返回
        if isinstance(page, str) and page.lower().startswith("page"):
            return page
    cid = chunk.get("chunk_id")
    if cid:
        return str(cid)
    start = chunk.get("start_char")
    end = chunk.get("end_char")
    if start is not None and end is not None:
        return f"chars {start}-{end}"
    return f"chunk {index + 1}"


# ── LLM 问答 ──────────────────────────────────────────────

def _try_llm_qa(question: str, paper_info: dict, context_text: str) -> dict | None:
    """
    尝试使用 LLM 回答。

    返回:
        成功返回 answer dict，失败返回 None
    """
    user_prompt = QA_USER_PROMPT_TEMPLATE.format(
        title=paper_info.get("title", "Unknown"),
        authors=paper_info.get("authors", "Unknown"),
        summary_text=paper_info.get("summary_text", "（暂无总结）"),
        abstract=paper_info.get("abstract", "（无摘要）"),
        passages=context_text,
        question=question,
    )

    response = call_llm(
        system_prompt=QA_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,
    )

    if response is None:
        return None

    # 引用片段来自实际送入模型的上下文，避免回答依据和界面展示不一致。
    citations = _extract_citations_from_text(context_text)

    return {
        "success": True,
        "mode": "llm",
        "answer": response.strip(),
        "citations": citations,
        "evidence_chunks": citations,
        "error": None,
    }


def _extract_citations_from_text(context_text: str) -> list[dict]:
    """
    从上下文中提取引用片段。
    简单策略：取前 3 个非空段落作为引用展示。
    """
    if not context_text:
        return []

    paragraphs = [p.strip() for p in context_text.split("\n\n") if p.strip()]
    citations = []
    for p in paragraphs[:3]:
        snippet = p[:500] + ("..." if len(p) > 500 else "")
        citations.append({
            "page": "PDF",
            "snippet": snippet,
        })
    return citations


# ── Fallback 问答 ─────────────────────────────────────────

def _fallback_qa(
    question: str,
    paper: dict | None,
    summary: dict | None,
    relevant: list[dict],
    pdf_text: str | None,
) -> dict:
    """
    Fallback 模式：基于关键词匹配结果组织回答。
    """
    relevant = relevant or []
    has_text = bool(pdf_text)
    has_evidence = bool(relevant)
    has_pdf = has_text or has_evidence

    if not has_pdf or not relevant:
        # 只有摘要和总结时明确提醒：当前不是全文问答，不能过度推断。
        answer_parts = [
            "> ⚠️ 当前为关键词匹配模式，系统未调用 LLM。回答仅基于论文摘要和已有总结。\n",
        ]
        if paper:
            title = paper.get("title", "")
            if title:
                answer_parts.append(f"根据论文「{title}」的已有信息：\n")
        if summary:
            for label, key in [
                ("一句话总结", "one_sentence"),
                ("方法思路", "method"),
                ("主要贡献", "contributions"),
            ]:
                val = summary.get(key, "")
                if val:
                    answer_parts.append(f"- {label}：{val[:300]}\n")
        if paper:
            abstract = paper.get("abstract", "")
            if abstract:
                answer_parts.append(f"- 摘要：{abstract[:500]}\n")
        answer_parts.append("\n由于当前为 Fallback 模式且未上传 PDF，建议：\n")
        answer_parts.append("1. 上传论文 PDF 后重新提问以获得更精准的回答\n")
        answer_parts.append("2. 配置 LLM API Key 以获得智能推理回答\n")

        return {
            "success": True,
            "mode": "fallback",
            "answer": "".join(answer_parts),
            "citations": [],
            "evidence_chunks": [],
            "error": None,
        }

    # 有 PDF 文本：基于检索片段组织回答
    answer_parts = [
        "> ⚠️ 当前为关键词匹配模式，系统未调用 LLM。以下是基于关键词检索到的最相关论文片段：\n\n",
    ]

    citations = []
    for i, chunk in enumerate(relevant, start=1):
        snippet = (chunk.get("text") or "")[:400]
        label = _get_chunk_label(chunk, i - 1)
        citations.append({
            "page": label,
            "snippet": snippet,
        })
        answer_parts.append(f"**片段 {i}**（{label}）：\n")
        answer_parts.append(f"> {snippet}\n\n")

    answer_parts.append(
        "---\n"
        "由于当前模式只进行关键词匹配，以上片段仅供参考。"
        "建议配置 LLM API Key 以获得智能推理回答，"
        "或结合原文进一步确认。"
    )

    return {
        "success": True,
        "mode": "fallback",
        "answer": "".join(answer_parts),
        "citations": citations,
        "evidence_chunks": relevant or citations,
        "error": None,
    }


# ── 内部辅助 ──────────────────────────────────────────────

def _build_paper_info(paper: dict | None, summary: dict | None) -> dict:
    """构建论文信息字典供 prompt 使用。"""
    if paper is None:
        paper = {}
    if summary is None:
        summary = {}

    # 构建总结文本摘要
    summary_parts = []
    for key, label in [
        ("one_sentence", "一句话"),
        ("core_problem", "核心问题"),
        ("method", "方法"),
        ("contributions", "贡献"),
        ("limitations", "局限"),
    ]:
        val = summary.get(key, "")
        if val:
            summary_parts.append(f"- {label}：{val[:200]}")
    summary_text = "\n".join(summary_parts) if summary_parts else "（暂无总结）"

    return {
        "title": paper.get("title", "Unknown"),
        "authors": ", ".join(paper.get("authors", [])[:3]) if paper.get("authors") else "Unknown",
        "abstract": paper.get("abstract", ""),
        "summary_text": summary_text,
    }


def _make_error(error_msg: str) -> dict:
    """构造错误返回。"""
    return {
        "success": False,
        "mode": "none",
        "answer": "",
        "citations": [],
        "evidence_chunks": [],
        "error": error_msg,
    }
