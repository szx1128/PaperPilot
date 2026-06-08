"""
PaperPilot 笔记生成模块。

基于论文信息和结构化总结生成 Markdown 格式的阅读笔记，
支持预览和下载。生成逻辑纯本地计算，不依赖任何外部服务。

依赖：
- modules/utils.py 中的路径工具
"""

import os
import re

from modules.utils import ensure_data_dir

# ── 常量 ──────────────────────────────────────────────────

NOTES_DIR_NAME = "notes"


# ── 公共函数 ──────────────────────────────────────────────

def generate_note(
    paper: dict,
    summary: dict,
    qa_history: list | None = None,
    tracker_summary: dict | None = None,
    reviewer_result: dict | None = None,
    innovation_analysis: dict | None = None,
) -> str:
    """
    基于论文信息、总结、问答历史、追踪摘要和 Reviewer 分析生成 Markdown 阅读笔记。

    参数:
        paper:            论文信息 dict
        summary:          结构化总结 dict
        qa_history:       问答历史列表
        tracker_summary:  追踪摘要 dict（可选）
        reviewer_result:  Reviewer 分析结果 dict（可选）

    返回:
        Markdown 格式的笔记字符串
    """
    title = paper.get("title", "Unknown Title")
    authors = _format_authors(paper.get("authors", []))
    published = paper.get("published", "Unknown")
    arxiv_url = paper.get("arxiv_url", "")
    pdf_url = paper.get("pdf_url", "")

    # 笔记按固定 Markdown 结构生成，便于下载、复习，也便于答辩展示工作流闭环。
    lines = [
        "# Paper Note",
        "",
        "---",
        "",
        "## 基本信息",
        "",
        f"- **Title:** {title}",
        f"- **Authors:** {authors}",
        f"- **Published:** {published}",
    ]
    if arxiv_url:
        lines.append(f"- **arXiv:** [{arxiv_url}]({arxiv_url})")
    if pdf_url:
        lines.append(f"- **PDF:** [{pdf_url}]({pdf_url})")

    # 安全处理 summary=None：没有生成总结时仍可导出基本阅读笔记。
    _sum = summary if isinstance(summary, dict) else {}

    lines.extend([
        "",
        "---",
        "",
        "## 一句话总结",
        "",
        _sum.get("one_sentence", "（暂无当前论文总结。）"),
        "",
        "## 研究背景",
        "",
        _sum.get("background", "（暂无）"),
        "",
        "## 核心问题",
        "",
        _sum.get("core_problem", "（暂无）"),
        "",
        "## 方法思路",
        "",
        _sum.get("method", "（暂无）"),
        "",
        "## 主要贡献",
        "",
        _sum.get("contributions", "（暂无）"),
        "",
        "## 局限性",
        "",
        _sum.get("limitations", "（暂无）"),
        "",
        "## 阅读建议",
        "",
        _sum.get("reading_suggestion", "（暂无）"),
        "",
        "---",
        "",
    ])
    # ── 问答历史 ──────────────────────────────────────
    if qa_history and len(qa_history) > 0:
        lines.append("## 论文问答记录")
        lines.append("")
        for i, qa in enumerate(qa_history, 1):
            lines.append(f"### Q{i}: {qa.get('question', '未知问题')}")
            lines.append("")
            lines.append(qa.get("answer", ""))
            lines.append("")
            citations = qa.get("citations", [])
            if citations:
                lines.append("**引用片段：**")
                for _j, cit in enumerate(citations, 1):
                    page = cit.get("page", "PDF")
                    snippet = cit.get("snippet", "")
                    lines.append(f"- {page}: {snippet[:200]}")
                lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.extend([
            "## 我的疑问",
            "",
            "- 暂无，后续可在论文问答阶段补充。",
            "",
        ])

    lines.extend([
        "## 后续阅读建议",
        "",
        "- 阅读 Introduction 理解研究动机；",
        "- 阅读 Method 把握核心方法；",
        "- 阅读 Experiments 判断实验效果；",
        "- 阅读 Conclusion 和 Discussion 关注局限与未来工作。",
        "",
        "---",
        "",
        f"*生成模式：{_sum.get('mode', 'unknown')}*",
    ])

    # ── 追踪摘要（始终包含）：把单篇阅读放回用户关注领域的大背景里。 ──
    lines.append("")
    lines.append("## 关注追踪摘要")
    lines.append("")
    lines.append(generate_tracker_section(tracker_summary))
    lines.append("")

    # ── Reviewer 分析（始终包含）：app.py 已负责按 paper_id 过滤，避免串论文。 ──
    lines.append("")
    lines.append("## Reviewer 视角分析")
    lines.append("")
    lines.append(_generate_reviewer_section(reviewer_result))
    lines.append("")

    # ── 创新点分析（始终包含，按 paper_id 过滤应由 app.py 完成） ──
    lines.append("")
    lines.append("## 创新点分析")
    lines.append("")
    if innovation_analysis is not None:
        try:
            from modules.innovation_analyzer import format_innovation_markdown
            lines.append(format_innovation_markdown(innovation_analysis))
        except ImportError:
            lines.append("创新点分析模块不可用。")
    else:
        lines.append("暂无当前论文创新点分析。")
    lines.append("")

    return "\n".join(lines)


def _generate_reviewer_section(review_result: dict | None = None) -> str:
    """生成 Reviewer 分析 Markdown 片段。"""
    if not review_result:
        return "暂无 Reviewer 视角分析。"
    try:
        from modules.reviewer import format_review_markdown
        return format_review_markdown(review_result)
    except ImportError:
        return "Reviewer 分析模块不可用。"


def generate_tracker_section(tracker_summary: dict | None = None) -> str:
    """
    生成关注追踪 Markdown 片段。
    如果 tracker_summary 为空，返回"暂无关注追踪记录。"

    参数:
        tracker_summary: build_tracker_summary() 的返回值

    返回:
        Markdown 字符串
    """
    if not tracker_summary:
        return "暂无关注追踪记录。"

    parts = []

    # 关注领域列表
    watchlist = tracker_summary.get("watchlist", [])
    if watchlist:
        parts.append("### 关注领域")
        parts.append("")
        for w in watchlist:
            name = w.get("name", "未知")
            last_check = w.get("last_checked_at", "从未刷新")
            if last_check and isinstance(last_check, str) and len(last_check) > 16:
                last_check = last_check[:16]
            parts.append(f"- **{name}**")
            parts.append(f"  - 最近刷新：{last_check or '从未刷新'}")
            parts.append(f"  - 关键词：`{w.get('query', '')}`")
            parts.append("")

    # Top 论文
    top_papers = tracker_summary.get("top_papers", [])
    if top_papers:
        parts.append(f"### 近期 Top 论文（共 {tracker_summary.get('total_papers', 0)} 篇追踪论文）")
        parts.append("")
        for i, p in enumerate(top_papers, 1):
            title = p.get("title", "未知标题")
            url = p.get("arxiv_url", "")
            source = ", ".join(p.get("source_watch_names", []))
            published = p.get("published", "未知")
            score = p.get("score", 0)
            summary_text = p.get("summary", "")[:200]
            reason = p.get("rank_reason", "")

            if url:
                parts.append(f"{i}. [{title}]({url})")
            else:
                parts.append(f"{i}. {title}")
            parts.append(f"   - 来源领域：{source or '未知'}")
            parts.append(f"   - 发布时间：{published}")
            parts.append(f"   - 综合评分：{score}")
            if summary_text:
                parts.append(f"   - 摘要：{summary_text}...")
            if reason:
                parts.append(f"   - 评分理由：{reason[:150]}")
            parts.append("")

    # 最近新发现
    new_count = tracker_summary.get("recent_new_count", 0)
    new_papers = tracker_summary.get("recent_new_papers", [])
    last_refresh = tracker_summary.get("last_refresh", "")

    parts.append(f"### 统计概览")
    parts.append("")
    parts.append(f"- 累计追踪论文：{tracker_summary.get('total_papers', 0)} 篇")
    parts.append(f"- 最近新发现：{new_count} 篇")
    if last_refresh and isinstance(last_refresh, str) and len(last_refresh) > 10:
        parts.append(f"- 最近刷新：{last_refresh[:16]}")
    parts.append("")

    if new_papers:
        parts.append(f"### 最近新发现论文（{new_count} 篇）")
        parts.append("")
        for i, p in enumerate(new_papers[:3], 1):
            title = p.get("title", "未知标题")
            url = p.get("arxiv_url", "")
            if url:
                parts.append(f"{i}. [{title}]({url})")
            else:
                parts.append(f"{i}. {title}")
            parts.append("")
    parts.append("")

    return "\n".join(parts) if parts else "暂无关注追踪记录。"


def make_note_filename(paper: dict) -> str:
    """
    根据论文信息生成安全的文件名。

    格式：{first_author}_{year}_{title_slug}.md

    参数:
        paper: 论文信息 dict

    返回:
        安全文件名，如 "Smith_2026_Graph_Neural_Networks.md"
    """
    # 提取第一作者姓氏
    first_author = "Unknown"
    authors = paper.get("authors", [])
    if authors:
        # 取第一作者的姓氏（空格前最后一个单词）
        full_name = authors[0].strip()
        parts = full_name.split()
        first_author = parts[-1] if parts else full_name

    # 提取年份
    published = paper.get("published", "")
    year = "Unknown"
    if published and len(published) >= 4:
        year = published[:4]

    # 从标题生成 slug
    title = paper.get("title", "Untitled")
    title_slug = _slugify(title)

    # 限制总长度
    filename = f"{first_author}_{year}_{title_slug}"
    if len(filename) > 150:
        filename = filename[:150]
    return f"{filename}.md"


def save_note_to_file(note_md: str, paper: dict) -> str | None:
    """
    将笔记内容保存到 data/notes/ 目录。

    参数:
        note_md: Markdown 笔记字符串
        paper:   论文信息 dict

    返回:
        保存成功时返回文件路径，失败返回 None（不抛异常）
    """
    ensure_data_dir()
    filename = make_note_filename(paper)

    # 获取 notes 目录的绝对路径；笔记统一落到 data/notes，便于提交/演示时查找。
    import os
    from pathlib import Path

    notes_dir = Path(__file__).parent.parent / "data" / NOTES_DIR_NAME
    notes_dir.mkdir(parents=True, exist_ok=True)

    filepath = notes_dir / filename

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(note_md)
        return str(filepath)
    except OSError as e:
        print(f"[note_generator] 保存笔记失败: {e}")
        return None


# ── 内部工具 ──────────────────────────────────────────────

def _format_authors(authors: list[str]) -> str:
    """格式化作者列表为逗号分隔字符串。"""
    if not authors:
        return "Unknown"
    return ", ".join(authors)


def _slugify(text: str) -> str:
    """
    将文本转换为 URL 友好的 slug。

    规则：
    - 转小写
    - 替换非字母/数字/下划线/连字符为空格
    - 多个空格合并
    - 空格替换为下划线
    - 截断到合理长度
    """
    # 保留字母、数字、空格、连字符
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    # 合并空白
    slug = re.sub(r"[-\s]+", "_", slug)
    # 去掉首尾下划线
    slug = slug.strip("_")
    # 截断
    if len(slug) > 100:
        # 尝试在单词边界截断
        truncated = slug[:100].rsplit("_", 1)[0]
        slug = truncated if truncated else slug[:100]
    return slug or "untitled"
