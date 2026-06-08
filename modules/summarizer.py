"""
PaperPilot 结构化总结模块。

基于论文标题和摘要生成中文结构化总结，支持两种模式：
1. LLM 模式：调用 LLM API 生成更自然、更完整的总结
2. Fallback 模式：使用模板规则从摘要中提取关键句

依赖：
- modules/llm_client.py（LLM 调用）
"""

import json
import re

from modules.llm_client import call_llm, is_llm_available


# ── LLM 提示词 ────────────────────────────────────────────

SYSTEM_PROMPT = """你是一个专业的学术论文阅读助手。请根据提供的论文标题和摘要，生成一份结构化的中文总结。

重要规则：
1. 所有输出必须使用中文
2. 严格基于提供的标题和摘要内容，不要编造任何摘要中不存在的信息
3. 如果摘要中某部分信息不足，请明确说明"摘要中未提供"
4. 输出必须是合法的 JSON 格式

请按以下 JSON 结构输出：

{
  "one_sentence": "用一句话概括这篇论文的研究内容（中文，50字以内）",
  "background": "研究背景：该论文解决什么问题，为什么重要（2-3句话）",
  "core_problem": "核心问题：论文试图解决的具体研究问题是什么",
  "method": "方法思路：论文提出的方法或技术路线是什么",
  "contributions": "主要贡献：论文的核心贡献和创新点（列表形式）",
  "limitations": "潜在局限：基于摘要可以推断的局限性，如果不足以判断请说明",
  "reading_suggestion": "阅读建议：建议的阅读顺序和重点关注部分"
}

只输出 JSON，不要输出任何其他内容。"""

USER_PROMPT_TEMPLATE = """请为以下论文生成结构化总结：

论文标题：
{title}

作者：
{authors}

发布时间：
{published}

摘要：
{abstract}

{extra_context}请输出 JSON："""


# ── Fallback 关键词 ──────────────────────────────────────

PROBLEM_KEYWORDS = [
    "problem", "challenge", "difficulty", "issue", "limitation",
    "address", "tackle", "solve", "study", "investigate", "explore",
    "focus", "aim", "goal", "objective", "question",
]

METHOD_KEYWORDS = [
    "propose", "present", "introduce", "develop", "design",
    "method", "approach", "framework", "model", "architecture",
    "algorithm", "technique", "strategy", "scheme", "pipeline",
    "based on", "using", "via", "through",
]

CONTRIBUTION_KEYWORDS = [
    "improve", "achieve", "outperform", "surpass", "exceed",
    "show", "demonstrate", "indicate", "reveal", "find",
    "contribute", "contribution", "result", "performance",
    "state-of-the-art", "sota", "better than", "superior",
    "effective", "efficient", "novel", "new", "first",
]


# ── 公共函数 ──────────────────────────────────────────────

def generate_summary(paper: dict, full_text: str | None = None) -> dict:
    """
    生成论文的结构化中文总结。

    优先使用 LLM，不可用时降级到模板 Fallback。

    参数:
        paper:     论文信息 dict，需包含 title、authors、published、abstract
        full_text: PDF 全文（可选，阶段 3 暂不使用，保留接口）

    返回:
        结构化总结 dict，包含以下字段：
        - mode:              "llm" 或 "fallback"
        - one_sentence:      一句话总结
        - background:        研究背景
        - core_problem:      核心问题
        - method:            方法思路
        - contributions:     主要贡献
        - limitations:       局限性
        - reading_suggestion: 阅读建议
    """
    # 优先尝试 LLM；任何调用失败、解析失败或字段缺失都会退回 fallback，保证主流程不中断。
    if is_llm_available():
        summary = _try_llm_summary(paper, full_text)
        if summary is not None:
            return summary

    # 降级到 Fallback 模式：只基于标题和摘要做规则总结。
    return _fallback_summary(paper)


# ── LLM 模式 ──────────────────────────────────────────────

def _try_llm_summary(paper: dict, full_text: str | None) -> dict | None:
    """
    尝试使用 LLM 生成结构化总结。

    返回:
        成功时返回 dict，失败时返回 None（触发调用方降级到 fallback）
    """
    title = paper.get("title", "")
    abstract = paper.get("abstract", "")
    authors = ", ".join(paper.get("authors", [])[:5])
    published = paper.get("published", "")

    # 构建额外上下文：如果有 PDF 全文，截取前 6000 字符加入 prompt。
    # 这里主动截断，避免超长 PDF 造成 prompt 过大或接口超时。
    extra_context = ""
    if full_text:
        extra_context = (
            "\n重要：以下提供了论文 PDF 提取文本的前 6000 字。"
            "请优先结合全文文本进行分析，但不要编造文本中没有的信息。"
            "如果全文文本与摘要信息有冲突，以全文文本为准。\n\n"
            f"===== PDF 全文文本（前 6000 字）=====\n{full_text[:6000]}\n"
            f"===== PDF 文本结束（共 {len(full_text)} 字，可能已截断）=====\n"
        )

    user_prompt = USER_PROMPT_TEMPLATE.format(
        title=title,
        authors=authors,
        published=published,
        abstract=abstract if abstract else "（无摘要）",
        extra_context=extra_context,
    )

    response = call_llm(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        temperature=0.3,
    )

    if response is None:
        return None

    # 解析 JSON：LLM 可能返回裸 JSON、代码块或带解释文本，因此解析函数做了多策略兜底。
    parsed = _parse_llm_json(response)
    if parsed is None:
        return None

    # 字段校验：缺少关键字段时退回 fallback
    if not _validate_summary_fields(parsed):
        print("[summarizer] LLM 返回缺少关键字段，退回 fallback")
        return None

    # 统一字段类型：list → Markdown bullet
    parsed = _normalize_summary_fields(parsed)
    parsed["mode"] = "llm"
    return parsed


def _parse_llm_json(response: str) -> dict | None:
    """
    从 LLM 返回文本中解析 JSON。

    尝试多种策略：
    1. 直接解析
    2. 提取 ```json ... ``` 代码块
    3. 提取 { ... } 包裹部分
    """
    # 策略 1：直接解析
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    # 策略 2：提取 ```json ... ``` 代码块
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # 策略 3：提取最外层 { ... }
    match = re.search(r"\{[\s\S]*\}", response)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def _validate_summary_fields(parsed: dict) -> bool:
    """
    校验 LLM 返回的 JSON 是否包含全部 7 个必要字段。

    参数:
        parsed: LLM 解析后的 dict

    返回:
        True 表示字段完整，False 表示缺失关键字段
    """
    required_fields = [
        "one_sentence",
        "background",
        "core_problem",
        "method",
        "contributions",
        "limitations",
        "reading_suggestion",
    ]
    for field in required_fields:
        if field not in parsed or not parsed[field]:
            print(f"[summarizer] LLM 返回缺少字段: {field}")
            return False
    return True


def _normalize_summary_fields(parsed: dict) -> dict:
    """
    统一字段类型：将 list 类型字段转换为 Markdown bullet 格式。

    避免 app.py 中 st.markdown 显示异常（如直接显示 Python list repr）。

    参数:
        parsed: LLM 解析后的 dict

    返回:
        字段类型归一化后的 dict
    """
    for key in list(parsed.keys()):
        value = parsed[key]
        if isinstance(value, list):
            # 将列表转换为 Markdown bullet 格式
            lines = []
            for item in value:
                if isinstance(item, str):
                    lines.append(f"- {item}")
            parsed[key] = "\n".join(lines) if lines else str(value)
        elif not isinstance(value, str):
            # 其他非字符串类型统一转换
            parsed[key] = str(value)
    return parsed


# ── Fallback 模式 ─────────────────────────────────────────

def _fallback_summary(paper: dict) -> dict:
    """
    基于规则模板生成结构化总结。

    从摘要中提取关键句，填充到预定义模板中。
    不依赖任何外部 API。
    """
    title = paper.get("title", "未知标题")
    abstract = paper.get("abstract", "")

    # fallback 的核心思想：从摘要中按关键词抽句，而不是凭空生成结论。
    sentences = _split_sentences(abstract) if abstract else []

    summary = {
        "mode": "fallback",
        "one_sentence": _fallback_one_sentence(title, abstract, sentences),
        "background": _fallback_background(sentences),
        "core_problem": _fallback_match_sentence(sentences, PROBLEM_KEYWORDS, "core_problem"),
        "method": _fallback_match_sentence(sentences, METHOD_KEYWORDS, "method"),
        "contributions": _fallback_match_sentence(sentences, CONTRIBUTION_KEYWORDS, "contribution"),
        "limitations": _fallback_limitations(),
        "reading_suggestion": _fallback_reading_suggestion(),
    }
    return summary


def _split_sentences(text: str) -> list[str]:
    """
    将文本按句子分割。

    按句号、问号、感叹号分割，保留有意义的句子（至少 5 个字符）。
    """
    if not text:
        return []
    # 保护常见缩写不被误分割（如 "e.g." "i.e." "et al."）
    protected = text.replace("e.g.", "e_g_").replace("i.e.", "i_e_").replace("et al.", "et_al_")
    raw = re.split(r"[.!?\n]+", protected)
    sentences = []
    for s in raw:
        # 恢复保护词
        s = s.replace("e_g_", "e.g.").replace("i_e_", "i.e.").replace("et_al_", "et al.")
        s = s.strip()
        if len(s) > 5:  # 过滤太短的片段
            sentences.append(s)
    return sentences


def _fallback_one_sentence(title: str, abstract: str, sentences: list[str]) -> str:
    """生成一句话总结：优先用摘要第一句，否则用标题。"""
    if sentences:
        first = sentences[0]
        # 截断过长的句子
        if len(first) > 100:
            first = first[:100] + "..."
        return f"本文研究了与「{title}」相关的问题。{first}"
    return f"本文探讨了「{title}」相关的研究问题。"


def _fallback_background(sentences: list[str]) -> str:
    """从摘要前 1-2 句提取背景。"""
    if len(sentences) >= 2:
        return f"{sentences[0]} {sentences[1]}"
    elif len(sentences) == 1:
        return sentences[0]
    else:
        return "摘要中未提供足够的背景信息，建议阅读 Introduction 部分了解研究背景。"


def _fallback_match_sentence(
    sentences: list[str], keywords: list[str], field: str
) -> str:
    """
    从句子列表中匹配包含关键词的句子。

    对单个单词使用正则单词边界匹配（\\bword\\b），避免误匹配。
    对短语（包含空格）使用子串匹配。

    参数:
        sentences: 句子列表
        keywords:  关键词列表
        field:     字段名（用于生成 fallback 消息）

    返回:
        匹配到的句子，或 fallback 提示
    """
    if not sentences:
        return _fallback_message(field)

    for sentence in sentences:
        sentence_lower = sentence.lower()
        for kw in keywords:
            if _keyword_matches(kw, sentence_lower):
                return sentence

    return _fallback_message(field)


def _keyword_matches(keyword: str, text_lower: str) -> bool:
    """
    检查关键词是否匹配文本。

    对单个单词使用 \\b 边界匹配 + 仅匹配复数变体（-s/-es），
    避免误匹配如：
    - 'model' 不匹配 'submodel' 或 'modeling'
    - 'method' 不匹配 'methodology'
    - 'model' 匹配 'model' 和 'models'（仅复数）

    对短语（含空格或连字符如 'state-of-the-art'）使用子串匹配。

    参数:
        keyword:    单个关键词
        text_lower: 已转小写的文本

    返回:
        是否匹配
    """
    # 短语型关键词：包含空格或连字符 → 子串匹配
    if " " in keyword or "-" in keyword:
        return keyword in text_lower

    # 单词型关键词：使用单词边界匹配
    try:
        # 主匹配：精确词边界（\\bword\\b）
        pattern = r"\b" + re.escape(keyword) + r"\b"
        if re.search(pattern, text_lower):
            return True
        # 仅对长度 >= 3 的词匹配常见英文复数形式（-s, -es）
        # 不做更宽松的变体匹配，避免 'model' 误匹配 'modeling' 等
        if len(keyword) >= 3:
            plural_pattern = r"\b" + re.escape(keyword) + r"(?:s|es)\b"
            if re.search(plural_pattern, text_lower):
                return True
    except re.error:
        # 关键词中有特殊字符可能导致正则错误，回退到子串匹配
        return keyword in text_lower

    return False


def _fallback_message(field: str) -> str:
    """生成各字段的默认 fallback 提示。"""
    messages = {
        "core_problem": "摘要中未明确说明核心研究问题，建议阅读 Introduction 部分了解。",
        "method": "摘要中未明确给出方法细节，建议阅读 Method 部分。",
        "contribution": "摘要中未明确列出贡献，建议结合正文的实验结果和 Discussion 进一步判断。",
    }
    return messages.get(field, "摘要中未提供相关信息。")


def _fallback_limitations() -> str:
    """生成局限性字段的固定 fallback 提示。"""
    return (
        "⚠️ 当前为模板生成模式，未调用 LLM，分析深度有限。\n\n"
        "仅基于标题和摘要无法充分判断论文的局限性。"
        "建议结合实验部分、消融实验（Ablation Study）和 Discussion / Conclusion 进一步分析。"
    )


def _fallback_reading_suggestion() -> str:
    """生成阅读建议的固定模板。"""
    return (
        "建议阅读顺序：\n"
        "1. 先阅读 Abstract 和 Introduction，理解问题背景与研究动机；\n"
        "2. 再阅读 Method / Approach，把握核心方法和技术路线；\n"
        "3. 接着阅读 Experiments，关注实验设置、基线对比和消融实验；\n"
        "4. 最后阅读 Conclusion 和 Discussion，了解作者对结果的分析和对未来工作的展望。"
    )
