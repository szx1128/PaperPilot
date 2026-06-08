"""
PaperPilot: 从论文发现到知识沉淀的科研阅读助手
==============================================
Streamlit 主入口文件。

当前版本：v1.6.6（在线部署与可运行 Demo 补丁）
"""

import streamlit as st

from modules.arxiv_client import search_deep_research_papers, search_papers, search_overview_papers, get_sample_papers
from modules.llm_client import get_llm_info
from modules.note_generator import generate_note, save_note_to_file, make_note_filename
from modules.pdf_parser import extract_text_from_pdf, get_text_preview, split_text_into_chunks
from modules.qa_engine import answer_question
from modules.paper_identity import get_paper_id
from modules.reviewer import analyze_as_reviewer, format_review_markdown, is_review_for_current_paper
from modules.innovation_analyzer import analyze_innovation, format_innovation_markdown
from modules.literature_review import generate_literature_review
from modules.research_insight import generate_research_insight
from modules.paper_tracker import (
    add_watch_item,
    build_tracker_summary,
    create_watch_item,
    delete_watch_item,
    filter_tracked_papers,
    load_watchlist,
    refresh_all_watch_items as refresh_all_enabled_watch_items,
    refresh_watch_item,
    sort_tracked_papers,
    update_paper_status,
    update_watch_item,
)
from modules.ranker import rank_papers
from modules.summarizer import generate_summary
from modules.tracker_store import load_paper_history, load_tracker_state, load_watchlist as _load_wl
from modules.utils import save_papers_cache

# ── 页面配置 ──────────────────────────────────────────────
st.set_page_config(
    page_title="PaperPilot - 科研论文阅读助手",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 会话状态初始化 ────────────────────────────────────────
# Streamlit 每次交互都会重新执行脚本，因此跨步骤数据必须放在 session_state。
# 这里把论文搜索、排序、PDF、QA、Reviewer、综述等状态分开存，避免一个功能覆盖另一个功能。
if "papers" not in st.session_state:
    st.session_state.papers = []
if "searched" not in st.session_state:
    st.session_state.searched = False
if "ranked_papers" not in st.session_state:
    st.session_state.ranked_papers = []
if "search_keyword_val" not in st.session_state:
    st.session_state.search_keyword_val = ""
if "selected_paper" not in st.session_state:
    st.session_state.selected_paper = None
if "summary" not in st.session_state:
    st.session_state.summary = None
if "note_md" not in st.session_state:
    st.session_state.note_md = None
if "note_saved_path" not in st.session_state:
    st.session_state.note_saved_path = None
if "show_sample_fallback" not in st.session_state:
    st.session_state.show_sample_fallback = False
if "last_search_error" not in st.session_state:
    st.session_state.last_search_error = None
if "reading_mode" not in st.session_state:
    st.session_state.reading_mode = "前沿追踪模式"
if "search_mode" not in st.session_state:
    st.session_state.search_mode = "frontier"
if "ranking_mode" not in st.session_state:
    st.session_state.ranking_mode = "frontier"
if "pdf_text" not in st.session_state:
                # pdf_text / paper_text / paper_chunks 三者共同组成后续总结、QA、Reviewer 的全文上下文。
                # 只在第一次进入页面时初始化，避免用户上传 PDF 后被重置。
                st.session_state.pdf_text = None
                st.session_state.paper_text = None
                st.session_state.paper_chunks = []
if "pdf_filename" not in st.session_state:
    st.session_state.pdf_filename = ""
if "pdf_page_count" not in st.session_state:
    st.session_state.pdf_page_count = 0
if "pdf_char_count" not in st.session_state:
    st.session_state.pdf_char_count = 0
if "pdf_parse_error" not in st.session_state:
    st.session_state.pdf_parse_error = None
if "qa_history" not in st.session_state:
    st.session_state.qa_history = []
if "reviewer_result" not in st.session_state:
    st.session_state.reviewer_result = None
if "reviewer_history" not in st.session_state:
    st.session_state.reviewer_history = []

# ── v1.1 统一状态 ──────────────────────────────────────
# current_paper/current_paper_id 是跨 Tab 的“当前论文锚点”。
# PDF、QA、Reviewer、创新点和笔记都通过 paper_id 判断是否属于同一篇论文。
if "current_paper" not in st.session_state:
    st.session_state.current_paper = None
if "current_paper_id" not in st.session_state:
    st.session_state.current_paper_id = None
if "paper_chunks" not in st.session_state:
    st.session_state.paper_chunks = []
if "pdf_meta" not in st.session_state:
    st.session_state.pdf_meta = {}
if "pdf_bound_paper_id" not in st.session_state:
    st.session_state.pdf_bound_paper_id = None
if "pdf_bound_paper_title" not in st.session_state:
    st.session_state.pdf_bound_paper_title = ""
if "summary_paper_id" not in st.session_state:
    st.session_state.summary_paper_id = None
if "summary_used_pdf" not in st.session_state:
    st.session_state.summary_used_pdf = False
if "qa_paper_id" not in st.session_state:
    st.session_state.qa_paper_id = None
if "reviewer_paper_id" not in st.session_state:
    st.session_state.reviewer_paper_id = None
if "reviewer_used_pdf" not in st.session_state:
    st.session_state.reviewer_used_pdf = False
if "innovation_analysis" not in st.session_state:
    st.session_state.innovation_analysis = None
if "innovation_paper_id" not in st.session_state:
    st.session_state.innovation_paper_id = None
if "innovation_used_pdf" not in st.session_state:
    st.session_state.innovation_used_pdf = False
if "literature_review_result" not in st.session_state:
    st.session_state.literature_review_result = None
if "literature_review_source" not in st.session_state:
    st.session_state.literature_review_source = None
if "literature_review_paper_ids" not in st.session_state:
    st.session_state.literature_review_paper_ids = []

# ── 趋势分析状态 ────────────────────────────────
if "trend_analysis_result" not in st.session_state:
    st.session_state.trend_analysis_result = None
if "trend_analysis_source" not in st.session_state:
    st.session_state.trend_analysis_source = None
if "trend_analysis_generated_at" not in st.session_state:
    st.session_state.trend_analysis_generated_at = None
if "trend_analysis_paper_ids" not in st.session_state:
    st.session_state.trend_analysis_paper_ids = []

# ── 关系图谱状态 ────────────────────────────────
if "paper_graph_result" not in st.session_state:
    st.session_state.paper_graph_result = None
if "paper_graph_source" not in st.session_state:
    st.session_state.paper_graph_source = None
if "paper_graph_paper_ids" not in st.session_state:
    st.session_state.paper_graph_paper_ids = []

# ── 辅助函数 ──────────────────────────────────────────────
def _set_current_paper(paper, source="unknown"):
    """设置当前论文并更新 ID。所有论文选择入口必须调用。"""
    # 统一使用 get_paper_id() 生成稳定 ID，避免不同 Tab 通过标题字符串猜测论文身份。
    st.session_state.current_paper = paper
    st.session_state.current_paper_id = get_paper_id(paper) if paper else "manual_pdf"
    st.session_state.current_paper_source = source
    return st.session_state.current_paper_id

# UI 显示中文，内部使用短 mode key，方便传给 ranker/arxiv_client。
# deep_research/deep_reading 是历史别名，保留是为了兼容旧状态或旧调用。
READING_MODE_KEYS = {
    "前沿追踪模式": "frontier",
    "领域了解模式": "understanding",
    "深入了解模式": "deep",
}

READING_MODE_LABELS = {
    "frontier": "前沿追踪模式",
    "understanding": "领域了解模式",
    "deep": "深入了解模式",
    "deep_research": "深入了解模式",
    "deep_reading": "深入了解模式",
}

def _reading_mode_key(label: str) -> str:
    return READING_MODE_KEYS.get(label, "frontier")

def _reading_mode_label(mode_key: str) -> str:
    return READING_MODE_LABELS.get(mode_key, "前沿追踪模式")

def _get_current_pdf_context():
    """统一获取当前 PDF 上下文。所有总结/QA/Reviewer 必须通过此函数获取 PDF 状态。"""
    # 默认认为 PDF 不可用；只有“已解析文本 + 已分块 + 绑定论文一致”时才开放给下游模块。
    ctx = {
        "available": False,
        "paper_text": None,
        "paper_chunks": [],
        "pdf_meta": st.session_state.pdf_meta if st.session_state.pdf_meta else {},
        "reason": "当前未上传 PDF",
        "bound_paper_id": st.session_state.pdf_bound_paper_id,
        "current_paper_id": st.session_state.current_paper_id,
        "bound_paper_title": st.session_state.pdf_bound_paper_title or "",
    }
    if not st.session_state.paper_text:
        return ctx
    if not st.session_state.paper_chunks:
        ctx["reason"] = "当前 PDF 未解析出有效文本片段"
        return ctx
    if st.session_state.pdf_bound_paper_id != st.session_state.current_paper_id:
        # 这是状态隔离的关键保护：切换论文后，旧 PDF 不会被误用于新论文。
        ctx["reason"] = "当前 PDF 绑定于另一篇论文"
        return ctx
    ctx["available"] = True
    ctx["paper_text"] = st.session_state.paper_text
    ctx["paper_chunks"] = st.session_state.paper_chunks
    ctx["reason"] = "PDF 可用"
    return ctx

def _is_pdf_bound():
    return _get_current_pdf_context()["available"]

# _is_pdf_bound 已在上面通过 _get_current_pdf_context 统一定义

def _pdf_bind_status_text():
    """返回 PDF 绑定状态文本（用于 UI 提示）。"""
    if not st.session_state.pdf_text:
        return "ℹ️ 当前未上传 PDF，系统将基于标题和摘要进行分析。"
    if _is_pdf_bound():
        return "✅ 当前 PDF 已绑定到本论文，可用于总结、问答和 Reviewer 分析。"
    return (
        "⚠️ 当前 PDF 绑定于另一篇论文（"
        f"{st.session_state.pdf_bound_paper_title or '未知'}）。"
        "为避免误用，系统不会将该 PDF 用于当前论文。请重新上传当前论文的 PDF。"
    )
def _get_pdf_context_for_paper_id(paper_id: str):
    """获取指定 paper_id 的 PDF 上下文（不修改全局状态）。"""
    # Reviewer / 笔记等功能可能分析的不是 current_paper，因此提供按 ID 查询的只读版本。
    if not paper_id:
        return {
            "available": False,
            "reason": "missing_paper_id",
            "paper_text": None,
            "chunks": [],
            "paper_id": paper_id,
            "bound_paper_id": None,
            "filename": None,
        }
    bound_id = st.session_state.get("pdf_bound_paper_id")
    paper_text = st.session_state.get("paper_text")
    chunks = st.session_state.get("paper_chunks") or []

    if bound_id == paper_id and paper_text:
        return {
            "available": True,
            "reason": "matched",
            "paper_id": paper_id,
            "bound_paper_id": bound_id,
            "paper_text": paper_text,
            "chunks": chunks,
            "filename": st.session_state.get("pdf_filename"),
        }
    return {
        "available": False,
        "reason": "pdf_bound_mismatch",
        "paper_id": paper_id,
        "bound_paper_id": bound_id,
        "paper_text": None,
        "chunks": [],
        "filename": st.session_state.get("pdf_filename"),
    }

if "tracker_watchlist" not in st.session_state:
    st.session_state.tracker_watchlist = _load_wl()
if "tracker_history" not in st.session_state:
    st.session_state.tracker_history = load_paper_history()
if "tracker_state" not in st.session_state:
    st.session_state.tracker_state = load_tracker_state()
if "last_refresh_result" not in st.session_state:
    st.session_state.last_refresh_result = None

# ── LLM 状态 ──────────────────────────────────────────────
llm_info = get_llm_info()

# ── 侧边栏 ────────────────────────────────────────────────
with st.sidebar:
    st.title("📄 PaperPilot")
    st.caption("科研论文阅读助手")
    st.divider()

    st.info("🔧 当前版本：v1.6.6（在线部署与可运行 Demo 补丁）")

    if llm_info["available"]:
        st.success(f"🤖 LLM 已就绪：{llm_info['model']}")
    else:
        st.warning("⚠️ 当前未检测到 LLM API Key，系统将以基础模式运行")
        st.caption("论文搜索、排序和基础展示仍可使用；摘要问答、Reviewer 等能力会降级或提示配置。")

    st.divider()

    st.subheader("📋 功能流程")
    status_markers = [
        ("1. 🔍 论文发现", True),
        ("2. 📊 论文排序", True),
        ("3. 📝 结构化总结", True),
        ("4. 📎 PDF 上传与解析", True),
        ("5. 💬 论文问答", True),
        ("6. 📒 阅读笔记生成", True),
    ]
    for label, done in status_markers:
        icon = "✅" if done else "⬜"
        st.markdown(f"{icon} {label}")

    st.divider()
    if st.session_state.searched and st.session_state.papers:
        st.caption(f"📚 已搜索到 {len(st.session_state.papers)} 篇论文")
    if st.session_state.ranked_papers:
        st.caption(f"📊 已排序 Top {len(st.session_state.ranked_papers)}")
    if st.session_state.summary:
        st.caption(f"📝 已生成总结（模式：{st.session_state.summary.get('mode', '?')}）")
    if st.session_state.note_md:
        st.caption("📒 已生成阅读笔记")
    if _is_pdf_bound():
        st.caption(f"📎 PDF: {st.session_state.pdf_filename} ({st.session_state.pdf_page_count} 页, {st.session_state.pdf_char_count} 字)")
    if st.session_state.qa_history:
        st.caption(f"💬 已提问 {len(st.session_state.qa_history)} 次")
    st.caption("Made with ❤️ for researchers")

# ── 主区域 ────────────────────────────────────────────────
st.title("📄 PaperPilot：从论文发现到知识沉淀的科研阅读助手")

st.markdown(
    "面向科研人员的论文阅读助手，覆盖从 **发现论文** 到 **筛选论文**、"
    "再到 **理解论文、提问论文、沉淀笔记、持续追踪** 的完整流程。"
)
st.info(
    "PaperPilot 是一个科研论文阅读辅助原型系统。当前 Demo 支持论文搜索、阅读意图排序、PDF 阅读、"
    "摘要问答、趋势分析、关系图谱、文献综述和科研洞察等功能。若未配置 LLM API Key，"
    "部分智能分析能力将以基础模式运行或显示配置提示。"
)

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(["📖 论文阅读", "📡 关注追踪", "🔍 Reviewer 分析", "💡 创新点分析", "📈 趋势分析", "🕸️ 关系图谱", "📚 文献综述"])

# ============================================================
# TAB 1：论文阅读（已有功能）
# ============================================================
with tab1:
    # ============================================================
    # 步骤 1：论文发现
    # ============================================================
    st.divider()
    st.subheader("🔍 步骤 1：论文发现")
    
    col1, col2, col3, col4 = st.columns([3, 1.4, 1, 1])
    with col1:
        keyword = st.text_input(
            "输入研究方向或关键词",
            placeholder="例如：large language model reasoning",
            key="search_keyword",
    )
    with col2:
        reading_mode_options = ["前沿追踪模式", "领域了解模式", "深入了解模式"]
        if st.session_state.reading_mode not in reading_mode_options:
            st.session_state.reading_mode = "前沿追踪模式"
        reading_mode = st.selectbox(
            "阅读模式",
            options=reading_mode_options,
            key="reading_mode",
        )
        mode_key = _reading_mode_key(reading_mode)
    with col3:
        max_results = st.selectbox(
            "搜索数量",
            options=[5, 10, 15, 20, 30, 50],
            index=3,
            key="max_results",
        )
    with col4:
        st.markdown("&nbsp;")
        search_btn = st.button("🔍 搜索论文", type="primary", use_container_width=True)

    if mode_key == "understanding":
        st.info(
            "领域了解模式适合刚进入某一方向、希望建立领域知识框架的用户。"
            "系统会优先关注 survey、review、taxonomy、benchmark、dataset、代表性方法和权威元信息信号，而不是单纯追求最新论文。"
        )
    elif mode_key == "deep":
        st.info(
            "深入了解模式适合已有基础后筛选值得精读、复现和批判分析的重点阅读候选论文。"
            "系统会优先考虑问题定义、方法完整性、实验充分性、baseline/ablation、可复现信号和权威发表信息。"
        )
        st.caption(
            "权威发表信息只是加分项，不是一票否决项；arXiv-only 论文仍会作为候选展示，并建议人工确认发表状态和实验质量。"
        )
    else:
        st.info(
            "前沿追踪模式适合已经了解该方向、希望快速跟踪最近论文和新趋势的用户。"
            "排序会更重视主题相关性、贡献信号、方法/证据和适度的新鲜度。"
        )

    if (
        st.session_state.get("papers")
        and st.session_state.get("search_mode")
        and st.session_state.get("search_mode") != mode_key
    ):
        st.warning("当前论文集合来自另一种阅读模式。由于不同模式的搜索扩展策略不同，建议重新点击搜索。")
    
    if search_btn:
        if not keyword.strip():
            # 空关键词：只提示，不访问 result，不清空已有结果
            st.warning("⚠️ 请输入研究方向或关键词后再搜索。")
        else:
            # 新搜索开始前先关闭上一次的降级提示，避免旧错误影响本次搜索体验。
            st.session_state.show_sample_fallback = False
            st.session_state.last_search_error = None
    
            with st.spinner("正在 arXiv 搜索中，请稍候..."):
                # 三种阅读模式不只影响排序，也影响搜索召回策略。
                # 领域了解会扩展 survey/review 等；深入了解会扩展方法/实验词并做相关性门控。
                if mode_key == "understanding":
                    result = search_overview_papers(keyword.strip(), max_results=max_results)
                elif mode_key == "deep":
                    result = search_deep_research_papers(keyword.strip(), max_results=max_results)
                else:
                    result = search_papers(keyword.strip(), max_results=max_results)
    
            if result["error"] is not None:
                # 搜索失败：不清空已有结果，记录错误 + 开启降级选项
                st.error(f"❌ {result['error']}")
                st.session_state.show_sample_fallback = True
                st.session_state.last_search_error = result["error"]
            elif not result["papers"]:
                st.warning("⚠️ 未找到相关论文，请尝试更换关键词（例如使用更通用的术语）。")
            else:
                # 搜索成功：清空下游状态，更新结果
                # 搜索结果换了以后，旧排序、旧总结、旧笔记都不再可信，需要主动清空。
                st.session_state.ranked_papers = []
                st.session_state.selected_paper = None
                st.session_state.summary = None
                st.session_state.note_md = None
                st.session_state.note_saved_path = None
                st.session_state.search_keyword_val = keyword.strip()
                st.session_state.search_mode = mode_key
                st.session_state.papers = result["papers"]
                st.session_state.searched = True
                _set_current_paper(result["papers"][0] if result["papers"] else None, source="search_refresh")
                save_papers_cache(result["papers"])
                st.success(f"✅ 搜索完成，共找到 {len(result['papers'])} 篇论文")
    
    # ── 示例论文降级按钮（在 search_btn 外部，靠 session_state 驱动） ──
    if st.session_state.show_sample_fallback:
        st.divider()
        st.markdown("### 🔄 降级方案")
        st.info(
            "arXiv API 连接超时。这不一定代表本机网络异常，"
            "可能是 arXiv API 国际链路不稳定。"
            "你可以稍后重试，或使用内置示例论文继续演示。"
        )
        if st.button("📋 使用内置示例论文继续演示", use_container_width=True, key="sample_fallback_btn"):
            sample_papers = get_sample_papers()
            st.session_state.ranked_papers = []
            st.session_state.selected_paper = None
            st.session_state.summary = None
            st.session_state.note_md = None
            st.session_state.note_saved_path = None
            st.session_state.search_keyword_val = keyword.strip() if keyword else "LLM"
            st.session_state.search_mode = mode_key
            st.session_state.papers = sample_papers
            _set_current_paper(sample_papers[0] if sample_papers else None, source="sample_fallback")
            st.session_state.searched = True
            st.session_state.show_sample_fallback = False
            st.session_state.last_search_error = None
            save_papers_cache(sample_papers)
            st.success(f"✅ 已加载 {len(sample_papers)} 篇内置示例论文（LLM 相关经典论文）")
            st.rerun()
    
    if st.session_state.searched and st.session_state.papers:
        papers = st.session_state.papers
        st.caption(f"共 {len(papers)} 篇论文（未排序）")
    
        with st.expander("📋 查看原始搜索结果", expanded=False):
            for i, paper in enumerate(papers, start=1):
                authors_str = ", ".join(paper.get("authors", [])[:5])
                if len(paper.get("authors", [])) > 5:
                    authors_str += " et al."
                title = paper.get("title", "Unknown Title")
                published = paper.get("published", "Unknown")
                st.markdown(
                    f"**#{i}** {title}  |  {published}  |  {authors_str}"
                )
                abstract = paper.get("abstract", "")
                if abstract:
                    st.markdown(f"> {abstract[:300]}{'...' if len(abstract) > 300 else ''}")
                if st.session_state.get("search_mode") in ("deep", "deep_research", "deep_reading"):
                    query_rel = paper.get("query_relevance_score")
                    if query_rel is not None:
                        rel_label = f"{float(query_rel) * 100:.1f}/100"
                        weak_note = "（弱相关兜底）" if paper.get("query_relevance_weak") else ""
                        st.caption(f"查询相关性门控：{rel_label}{weak_note}")
                    matched_terms = paper.get("query_relevance_matched_terms") or []
                    if matched_terms:
                        st.caption("命中主题词：" + "、".join(matched_terms[:6]))
                col_a, col_b = st.columns(2)
                with col_a:
                    arxiv_url = paper.get("arxiv_url", "")
                    if arxiv_url:
                        st.markdown(f"[📄 arXiv 页面]({arxiv_url})")
                with col_b:
                    pdf_url = paper.get("pdf_url", "")
                    if pdf_url:
                        st.markdown(f"[📥 下载 PDF]({pdf_url})")
                st.markdown("---")
    
    elif st.session_state.searched and not st.session_state.papers:
        st.info("💡 没有找到匹配的论文，请尝试更换搜索关键词。")
    
    # ============================================================
    # 步骤 2：论文排序
    # ============================================================
    st.divider()
    st.subheader("📊 步骤 2：论文排序")
    
    if not st.session_state.searched or not st.session_state.papers:
        st.info("👆 请先在步骤 1 中搜索论文，再对结果进行排序。")
    else:
        # ── 评分说明 ──────────────────────────────────────────
        with st.expander("📐 评分公式说明", expanded=False):
            if mode_key == "understanding":
                st.markdown(
                    "领域了解分 = 0.18 × 主题相关性 + 0.18 × 综述/路线价值 "
                    "+ 0.14 × 经典/代表性信号 + 0.12 × 权威元信息信号 "
                    "+ 0.14 × 问题定义清晰度 + 0.12 × 方法覆盖度 "
                    "+ 0.07 × Benchmark/Dataset 价值 + 0.03 × 可读性 + 0.02 × 新鲜度"
                )
                st.caption(
                    "领域了解模式用于建立领域知识框架，优先推荐 survey、review、taxonomy、benchmark、dataset、"
                    "代表性方法和带有权威元信息信号的论文。经典性和权威性均为启发式信号，"
                    "不等同于真实引用量或真实学术影响力评价。"
                )
            elif mode_key == "deep":
                st.markdown(
                    "深入了解质量分 = 0.11 × 贡献价值 "
                    "+ 0.09 × 问题定义清晰度 + 0.16 × 方法完整性 "
                    "+ 0.16 × 实验/证据充分性 + 0.12 × 权威发表信号 "
                    "+ 0.10 × 可复现性信号 + 0.05 × 方法路线代表性 "
                    "+ 0.03 × 局限与讨论信号 "
                    "+ 0.03 × 新鲜度；最终分再经过查询相关性门控。"
                )
                st.caption(
                    "深入了解模式采用“先相关、再深入”：先判断论文是否命中用户原始 query 或扩展主题词，"
                    "再让方法完整性、实验充分性、venue、可复现等质量信号发挥作用。"
                    "benchmark / evaluation / ablation 等质量词不会单独作为主题相关性证据。"
                    "权威发表信号基于 journal_ref/comment/venue/doi 等元信息启发式判断，不联网验证，也不代表真实论文质量。"
                )
            else:
                st.markdown(
                    "综合分 = 0.35 × 主题相关性 + 0.20 × 贡献价值 + 0.15 × 方法清晰度 "
                    "+ 0.15 × 证据支撑 + 0.10 × 新鲜度 + 0.05 × 可读性"
                )
                st.caption(
                    "该评分用于估计「阅读优先级」，基于启发式规则计算，不是论文真实学术质量评价。"
                    "评分不涉及引用数、作者影响力、venue 信息。"
                )
    
        col1, col2, col3 = st.columns([2, 1, 3])
        with col1:
            top_k = st.selectbox(
                "展示数量（Top K）",
                options=[5, 10, 15, 20],
                index=1,
                key="top_k",
            )
        with col2:
            st.markdown("&nbsp;")
            rank_btn = st.button("📊 对搜索结果排序", type="primary", use_container_width=True)
        with col3:
            st.markdown("&nbsp;")
    
        if rank_btn:
            # 重新排序会改变默认精读论文，因此同步清空依赖旧论文的总结和笔记。
            st.session_state.selected_paper = None
            st.session_state.summary = None
            st.session_state.note_md = None
            st.session_state.note_saved_path = None
    
            query = st.session_state.search_keyword_val
            with st.spinner("正在综合打分排序中..."):
                # mode_key 是排序语义的核心：同一批论文在三种阅读目标下会得到不同优先级。
                ranked = rank_papers(st.session_state.papers, query, top_k=top_k, mode=mode_key)
                st.session_state.ranked_papers = ranked
                st.session_state.ranking_mode = mode_key
                _set_current_paper(ranked[0] if ranked else None, source="rerank")
            st.success(f"✅ 排序完成，展示 Top {len(ranked)}")
    
        if st.session_state.ranked_papers:
            ranked_papers = st.session_state.ranked_papers
            ranked_mode = st.session_state.get("ranking_mode", "frontier")
            st.caption(f"当前排序模式：{_reading_mode_label(ranked_mode)} | 按综合分降序展示 Top {len(ranked_papers)}")
            if ranked_mode != mode_key:
                st.warning("⚠️ 当前排序结果来自另一种阅读模式。点击「对搜索结果排序」可按当前阅读模式重新排序。")
            st.markdown("---")
            for i, paper in enumerate(ranked_papers, start=1):
                score_total = paper.get("score_total", 0)
                title = paper.get("title", "Unknown Title")
                published = paper.get("published", "Unknown")
                expander_title = f"#{i} | 综合分 {score_total} | {title}"
                with st.expander(expander_title):
                    authors_str = ", ".join(paper.get("authors", [])[:5])
                    if len(paper.get("authors", [])) > 5:
                        authors_str += " et al."
                    st.markdown(f"**作者：** {authors_str}")
                    st.markdown(f"**发布时间：** {published}")
                    st.markdown("**📊 各维度评分：**")
                    if ranked_mode == "understanding":
                        col_a, col_b, col_c, col_d, col_e = st.columns(5)
                        with col_a:
                            st.metric("综合分", f"{score_total}")
                        with col_b:
                            st.metric("主题相关性", f"{paper.get('score_relevance', 0)}")
                        with col_c:
                            st.metric("综述/路线价值", f"{paper.get('score_overview_value', 0)}")
                        with col_d:
                            st.metric("经典/代表性", f"{paper.get('score_classic_signal', 0)}")
                        with col_e:
                            st.metric("权威元信息", f"{paper.get('score_authority_signal', 0)}")
                        col_f, col_g, col_h, col_i, col_j = st.columns(5)
                        with col_f:
                            st.metric("问题定义", f"{paper.get('score_problem_clarity', 0)}")
                        with col_g:
                            st.metric("方法覆盖", f"{paper.get('score_method_coverage', 0)}")
                        with col_h:
                            st.metric("Benchmark/Dataset", f"{paper.get('score_benchmark_value', 0)}")
                        with col_i:
                            st.metric("可读性", f"{paper.get('score_readability', 0)}")
                        with col_j:
                            st.metric("新鲜度", f"{paper.get('score_freshness', 0)}")
                        st.markdown(f"**建议阅读角色：** {paper.get('understanding_role', '入门候选')}")
                    elif ranked_mode in ("deep", "deep_research", "deep_reading"):
                        col_a, col_b, col_c, col_d, col_e = st.columns(5)
                        with col_a:
                            st.metric("综合分", f"{score_total}")
                        with col_b:
                            st.metric("主题相关性", f"{paper.get('score_relevance', 0)}")
                        with col_c:
                            st.metric("贡献价值", f"{paper.get('score_contribution', 0)}")
                        with col_d:
                            st.metric("方法完整性", f"{paper.get('score_method_rigor', 0)}")
                        with col_e:
                            st.metric("证据充分性", f"{paper.get('score_evidence_strength', 0)}")
                        col_f, col_g, col_h, col_i, col_j = st.columns(5)
                        with col_f:
                            st.metric("权威发表", f"{paper.get('score_venue_authority', paper.get('score_authority_signal', 0))}")
                        with col_g:
                            st.metric("可复现性", f"{paper.get('score_reproducibility_signal', 0)}")
                        with col_h:
                            st.metric("路线代表性", f"{paper.get('score_mainstream_signal', 0)}")
                        with col_i:
                            st.metric("局限/讨论", f"{paper.get('score_limitation_value', 0)}")
                        with col_j:
                            st.metric("新鲜度", f"{paper.get('score_freshness', 0)}")
                        st.markdown(f"**建议阅读角色：** {paper.get('deep_reading_role', paper.get('deep_research_role', '深入阅读候选'))}")
                        venue_info = paper.get("venue_authority_info") or {}
                        if venue_info.get("reason"):
                            st.caption(f"发表可信度信号：{venue_info.get('reason')}")
                        query_reasons = paper.get("query_relevance_reasons") or []
                        if query_reasons:
                            st.caption("查询相关性：" + "；".join(query_reasons[:2]))
                        query_terms = paper.get("query_relevance_matched_terms") or []
                        if query_terms:
                            st.caption("命中主题词：" + "、".join(query_terms[:6]))
                        deep_reasons = paper.get("deep_reading_reasons") or []
                        if deep_reasons:
                            st.markdown("**深入阅读推荐理由：**")
                            for item in deep_reasons[:5]:
                                st.markdown(f"- {item}")
                        mainstream_terms = paper.get("matched_mainstream_terms") or []
                        if mainstream_terms:
                            st.caption("当前结果集共同术语：" + "、".join(mainstream_terms[:5]))
                        st.caption("路线代表性表示当前结果集中的共同术语和方法信号，不代表真实领域主流程度。")
                    else:
                        # 第一行
                        col_a, col_b, col_c, col_d = st.columns(4)
                        with col_a:
                            st.metric("综合分", f"{score_total}")
                        with col_b:
                            st.metric("主题相关性", f"{paper.get('score_relevance', 0)}")
                        with col_c:
                            st.metric("贡献价值", f"{paper.get('score_contribution', 0)}")
                        with col_d:
                            st.metric("方法清晰度", f"{paper.get('score_method_clarity', 0)}")
                        # 第二行
                        col_e, col_f, col_g, col_h = st.columns(4)
                        with col_e:
                            st.metric("证据支撑", f"{paper.get('score_evidence', 0)}")
                        with col_f:
                            st.metric("新鲜度", f"{paper.get('score_freshness', 0)}")
                        with col_g:
                            st.metric("可读性", f"{paper.get('score_readability', 0)}")
                        with col_h:
                            level = paper.get("recommendation_level", "-")
                            st.metric("推荐等级", level)
                    reason = paper.get("recommendation_reason", "")
                    if reason:
                        st.markdown(f"> 💡 **推荐理由：** {reason}")
                    st.markdown("---")
                    abstract = paper.get("abstract", "")
                    if abstract:
                        st.markdown("**摘要：**")
                        st.markdown(f"> {abstract}")
                    col_a, col_b = st.columns(2)
                    with col_a:
                        arxiv_url = paper.get("arxiv_url", "")
                        if arxiv_url:
                            st.markdown(f"[📄 查看 arXiv 页面]({arxiv_url})")
                    with col_b:
                        pdf_url = paper.get("pdf_url", "")
                        if pdf_url:
                            st.markdown(f"[📥 下载 PDF]({pdf_url})")
    
    # ============================================================
    # 步骤 3：结构化总结
    # ============================================================
    st.divider()
    st.subheader("📝 步骤 3：结构化总结")
    
    if not st.session_state.ranked_papers:
        st.info("👆 请先完成步骤 1（搜索）和步骤 2（排序），再生成总结。")
    else:
        ranked_papers = st.session_state.ranked_papers
        paper_options = [
            f"#{i} | 综合分 {p.get('score_total', 0)} | {p.get('title', 'Unknown')[:80]}"
            for i, p in enumerate(ranked_papers, start=1)
        ]
        selected_idx = st.selectbox(
            "选择要总结的论文",
            options=range(len(paper_options)),
            format_func=lambda i: paper_options[i],
            key="summary_paper_idx",
        )
        if ranked_papers:
            st.session_state.selected_paper = ranked_papers[selected_idx]
            # selectbox 切换论文时同步 current_paper，后续 PDF/QA/笔记都基于这个 ID 判断归属。
            _set_current_paper(ranked_papers[selected_idx], source="summary_selectbox")
    
        col1, col2, col3 = st.columns([2, 1, 3])
        with col1:
            st.markdown("&nbsp;")
            summary_btn = st.button("📝 生成结构化总结", type="primary", use_container_width=True)
        with col2:
            st.markdown("&nbsp;")
        with col3:
            st.markdown("&nbsp;")
    
        if summary_btn:
            # 重新生成总结时清空旧笔记（但不清空 QA，QA 按 paper_id 隔离）
            st.session_state.note_md = None
            st.session_state.note_saved_path = None
    
            selected_paper = ranked_papers[selected_idx]
            st.session_state.selected_paper = selected_paper; _set_current_paper(selected_paper)
    
            with st.spinner("正在生成结构化总结..."):
                # 只有 PDF 绑定当前论文时才传 full_text；否则 summarizer 只基于标题和摘要。
                pdf_ctx = _get_current_pdf_context(); full_text = pdf_ctx["paper_text"] if pdf_ctx["available"] else None
                summary = generate_summary(selected_paper, full_text=full_text)
                st.session_state.summary = summary
                st.session_state.summary_paper_id = st.session_state.current_paper_id
                st.session_state.summary_used_pdf = pdf_ctx["available"]
    
            mode_label = "LLM 生成" if summary.get("mode") == "llm" else "模板生成"
            if summary.get("mode") == "llm":
                st.success(f"✅ 总结生成完成（🤖 {mode_label}）")
            else:
                st.warning(f"✅ 总结生成完成（📋 {mode_label}）")
    
        if st.session_state.summary:
            summary = st.session_state.summary
            mode = summary.get("mode", "?")
            if mode == "llm":
                st.success("🤖 **生成模式：LLM 生成**")
            else:
                st.warning("📋 **生成模式：模板生成（未调用 LLM，分析深度有限）**")
    
            # PDF 增强提示（基于生成时刻的实际状态）
            if st.session_state.summary_used_pdf:
                st.success("✅ 本次总结已结合上传 PDF 文本进行增强。")
            else:
                st.info("ℹ️ 当前未上传 PDF，系统基于标题和摘要生成总结。")

            # 检查总结是否属于当前论文
            # 用户可能在生成总结后又切换论文，这里提醒但不强行删除旧总结，便于回看。
            if st.session_state.summary_paper_id and st.session_state.summary_paper_id != st.session_state.current_paper_id:
                st.warning("⚠️ 当前显示的是另一篇论文的总结，请重新生成当前论文总结。")
    
            st.markdown("---")
            for field_key, icon, label in [
                ("one_sentence", "💡", "一句话总结"),
                ("background", "📖", "研究背景"),
                ("core_problem", "❓", "核心问题"),
                ("method", "🔧", "方法思路"),
                ("contributions", "🏆", "主要贡献"),
                ("limitations", "⚠️", "局限性"),
                ("reading_suggestion", "📖", "阅读建议"),
            ]:
                content = summary.get(field_key, "")
                if content:
                    st.markdown(f"### {icon} {label}")
                    if field_key == "one_sentence":
                        st.markdown(f"> {content}")
                    else:
                        st.markdown(content)
    
    # ============================================================
    # 步骤 4：PDF 上传与解析
    # ============================================================
    st.divider()
    st.subheader("📎 步骤 4：PDF 上传与解析")
    
    uploaded_file = st.file_uploader(
        "上传论文 PDF 文件（可选，用于增强总结质量）",
        type=["pdf"],
        key="pdf_uploader",
        help="上传 PDF 后点击“解析 PDF”按钮。仅支持含文字层的 PDF，不支持扫描版。",
    )
    
    col1, col2, col3 = st.columns([2, 1, 3])
    with col1:
        st.markdown("&nbsp;")
        parse_btn = st.button("📎 解析 PDF", use_container_width=True)
    with col2:
        st.markdown("&nbsp;")
    with col3:
        st.markdown("&nbsp;")
    
    if parse_btn:
        if uploaded_file is None:
            st.warning("⚠️ 请先选择一个 PDF 文件再点击解析。")
        else:
            # 解析新 PDF 时覆盖旧结果
            with st.spinner("正在解析 PDF 文件..."):
                result = extract_text_from_pdf(uploaded_file)
    
            if result["success"]:
                if not st.session_state.current_paper_id:
                    _set_current_paper(None, source="manual_pdf")
                # 同一份 PDF 文本同时保存为 pdf_text 和 paper_text，兼容旧模块调用与新绑定逻辑。
                st.session_state.pdf_text = result["text"]
                st.session_state.paper_text = result["text"]
                st.session_state.paper_chunks = split_text_into_chunks(result["text"])
                st.session_state.pdf_filename = result["filename"]
                st.session_state.pdf_page_count = result["page_count"]
                st.session_state.pdf_char_count = result["char_count"]
                st.session_state.pdf_parse_error = None
                cpid = st.session_state.current_paper_id or "manual_pdf"
                cptitle = (st.session_state.current_paper or {}).get("title") if st.session_state.current_paper else ""
                cptitle = cptitle or st.session_state.pdf_filename or "手动上传 PDF"
                # 绑定当前论文，避免后续切换论文后继续误用这份 PDF。
                st.session_state.pdf_bound_paper_id = cpid
                st.session_state.pdf_bound_paper_title = cptitle
                st.session_state.pdf_meta = {"file_name": result["filename"], "page_count": result["page_count"], "text_length": result["char_count"], "chunk_count": len(st.session_state.paper_chunks), "upload_time": __import__("datetime").datetime.now().isoformat(), "bound_paper_id": cpid, "bound_paper_title": cptitle}
                st.success(
                    f"✅ PDF 解析成功：{result['filename']} "
                    f"（{result['page_count']} 页，{result['char_count']} 字符）"
                )
            else:
                st.session_state.pdf_text = None; st.session_state.paper_text = None; st.session_state.paper_chunks = []
                st.session_state.pdf_filename = result["filename"]
                st.session_state.pdf_page_count = result["page_count"]
                st.session_state.pdf_char_count = 0
                st.session_state.pdf_parse_error = result["error"]
                st.error(f"❌ PDF 解析失败：{result['error']}")
    
    # ── PDF 解析结果展示 ──────────────────────────────────
    if _is_pdf_bound():
        st.markdown("---")
        st.markdown("**📎 PDF 解析结果：**")
        st.markdown(
            f"- 文件名：{st.session_state.pdf_filename}\n"
            f"- 页数：{st.session_state.pdf_page_count}\n"
            f"- 字符数：{st.session_state.pdf_char_count}"
        )
        with st.expander("📄 文本预览（前 1500 字符）", expanded=False):
            preview = get_text_preview(st.session_state.pdf_text, max_chars=1500)
            st.text_area("PDF 文本预览", preview, height=300, disabled=True)
    
    elif st.session_state.pdf_parse_error:
        st.markdown("---")
        st.warning(f"⚠️ 上次解析失败：{st.session_state.pdf_parse_error}")
    
    # ============================================================
    # 步骤 5：论文问答
    # ============================================================
    st.divider()
    st.subheader("💬 步骤 5：论文问答")
    
    if not st.session_state.selected_paper or not st.session_state.summary:
        st.info("👆 请先完成步骤 1（搜索）、步骤 2（排序）和步骤 3（总结），再进行提问。")
    else:
        # ── 输入区域 ──────────────────────────────────────────
        pdf_ctx_qa = _get_current_pdf_context()
        if pdf_ctx_qa["available"]:
            st.success("✅ 当前 PDF 已绑定到本论文，可用于全文问答。")
        elif pdf_ctx_qa.get("bound_paper_id") and pdf_ctx_qa.get("bound_paper_id") != pdf_ctx_qa.get("current_paper_id"):
            st.warning("⚠️ 当前 PDF 绑定于另一篇论文。为避免误用，系统不会用它回答当前论文问题。请重新上传当前论文的 PDF。")
        else:
            st.info("ℹ️ 当前论文没有可用 PDF。全文问答需要上传当前论文 PDF。")
    
        col1, col2 = st.columns([5, 1])
        with col1:
            question = st.text_area(
                "输入您的问题",
                placeholder="例如：这篇论文的主要创新点是什么？方法与其他工作有什么区别？实验结果说明了什么？",
                key="qa_question_input",
                height=80,
            )
            ask_btn = st.button("💬 提交问题", type="primary", use_container_width=True)
            clear_btn = st.button("🗑️ 清空历史", use_container_width=True)

            if clear_btn:
                all_qa = st.session_state.qa_history
                cpid_qa = st.session_state.current_paper_id
                if len(all_qa) > 0:
                    # QA 历史全局保存，但清空时只删除当前论文的记录，保留其他论文问答。
                    kept = [q for q in all_qa if q.get("paper_id") != cpid_qa]
                    removed = len(all_qa) - len(kept)
                    st.session_state.qa_history = kept
                    if removed > 0:
                        st.success(f"已清空当前论文 {removed} 条问答" + (f"（保留 {len(kept)} 条其他论文问答）" if kept else ""))
                    else:
                        st.info("当前论文暂无问答记录")
                st.rerun()

            if ask_btn:
                if not question.strip():
                    st.warning("⚠️ 请输入您想了解的问题。")
                else:
                    with st.spinner("正在分析论文并生成回答..."):
                        pdf_ctx = _get_current_pdf_context()
                        if not pdf_ctx["available"]:
                            st.warning(f"⚠️ {pdf_ctx['reason']}。全文问答需要当前论文的 PDF。")
                        else:
                            cpid_qa2 = st.session_state.current_paper_id
                            # 总结也按 paper_id 校验，避免拿别的论文总结参与当前问答。
                            summary_for_qa2 = (st.session_state.summary
                                if st.session_state.summary_paper_id == cpid_qa2 else None)
                            result = answer_question(
                                question=question.strip(),
                                paper=st.session_state.current_paper,
                                summary=summary_for_qa2,
                                paper_text=pdf_ctx["paper_text"],
                                chunks=pdf_ctx["paper_chunks"],
                            )

                            if result["success"]:
                                # 每条 QA 都记录 paper_id，笔记生成时可精确筛选当前论文问答。
                                qa_record = {
                                    "question": question.strip(),
                                    "answer": result["answer"],
                                    "citations": result["citations"],
                                    "mode": result["mode"],
                                    "paper_id": st.session_state.current_paper_id,
                                    "paper_title": (st.session_state.current_paper or {}).get("title", "") if st.session_state.current_paper else "",
                                }
                                st.session_state.qa_history.append(qa_record)
                                st.session_state.qa_paper_id = st.session_state.current_paper_id
                                mode_display = result["mode"]
                                st.success(f"✅ 已回答（模式：{mode_display}）")
                            else:
                                st.error(f"❌ 回答失败：{result['error']}")
    
        # ── 问答历史展示 ──────────────────────────────────────
        if st.session_state.qa_history:
            cpid = st.session_state.current_paper_id
            current_qa = [q for q in st.session_state.qa_history if q.get("paper_id") == cpid]
            other_count = len(st.session_state.qa_history) - len(current_qa)
            st.markdown("---")
            if not current_qa:
                st.info("当前论文暂无问答记录。" + (f"（另有 {other_count} 条其他论文问答）" if other_count else ""))
            else:
                st.markdown(f"### 📝 问答记录（当前论文共 {len(current_qa)} 条）")
                if other_count:
                    st.caption(f"另有 {other_count} 条其他论文问答未展示")
                for i, qa in enumerate(reversed(current_qa), 1):
                    idx = len(current_qa) - i + 1
                    mode_label = "LLM" if qa["mode"] == "llm" else "关键词匹配"
                    with st.expander(f"Q{idx}: {qa['question'][:60]}...  ({mode_label})", expanded=(i == 1)):
                        st.markdown(f"**Q{idx}:** {qa['question']}")
                        st.markdown("---")
                        st.markdown(qa["answer"])
                        if qa.get("citations"):
                            st.markdown("---")
                            st.markdown("**📖 引用片段：**")
                            for j, cit in enumerate(qa["citations"], 1):
                                page = cit.get("page", "PDF")
                                snippet = cit.get("snippet", "")
                                with st.expander(f"引用 {j} — {page}", expanded=False):
                                    st.markdown(f"> {snippet}")
# ============================================================
    # 步骤 6：阅读笔记生成（v1.1 绑定修复）
    # ============================================================
    st.divider()
    st.subheader("📒 步骤 6：阅读笔记生成")

    # 构建笔记论文对象（以 current_paper/current_paper_id 为主）
    # 笔记是最终沉淀物，必须以当前论文 ID 为准，不能只依赖 selected_paper。
    current_paper = st.session_state.get("current_paper")
    current_paper_id = st.session_state.get("current_paper_id")
    if current_paper:
        paper_for_note = current_paper
        note_paper_id = current_paper_id or get_paper_id(paper_for_note)
    elif current_paper_id == "manual_pdf" and st.session_state.get("pdf_bound_paper_id") == "manual_pdf":
        paper_for_note = {
            "paper_id": "manual_pdf",
            "title": st.session_state.get("pdf_filename", "手动上传 PDF"),
            "abstract": "",
            "summary": "",
            "authors": [],
            "published": "",
            "arxiv_url": "",
            "pdf_url": "",
        }
        note_paper_id = "manual_pdf"
    else:
        paper_for_note = None
        note_paper_id = None

    if not paper_for_note or not note_paper_id:
        st.info("👆 请先在步骤 1-3 中选择论文并生成总结（或上传 PDF 作为 manual_pdf），再生成笔记。")
    else:
        col1, col2, col3 = st.columns([2, 1, 3])
        with col1:
            st.markdown("&nbsp;")
            note_btn = st.button("📒 生成 Markdown 阅读笔记", type="primary", use_container_width=True)
        with col2:
            st.markdown("&nbsp;")
        with col3:
            st.markdown("&nbsp;")

        if note_btn:
            with st.spinner("正在生成阅读笔记..."):
                tracker_summary = build_tracker_summary(st.session_state.tracker_watchlist, st.session_state.tracker_history)
                # 汇总材料全部按 note_paper_id 过滤，避免跨论文混入总结、QA、Reviewer 或创新点。
                summary_for_note = (st.session_state.summary if st.session_state.summary_paper_id == note_paper_id else None)
                qa_for_note = [q for q in st.session_state.qa_history if q.get("paper_id") == note_paper_id]
                reviewer_for_note = (st.session_state.reviewer_result if st.session_state.reviewer_paper_id == note_paper_id else None)
                innovation_for_note = (st.session_state.innovation_analysis if st.session_state.innovation_paper_id == note_paper_id else None)
                note_md = generate_note(paper_for_note, summary_for_note, qa_for_note, tracker_summary, reviewer_for_note, innovation_for_note)
                st.session_state.note_md = note_md
                saved_path = save_note_to_file(note_md, paper_for_note)
                st.session_state.note_saved_path = saved_path
            st.success("✅ 阅读笔记生成完成")

        if st.session_state.note_md:
            filename = make_note_filename(paper_for_note)
            st.download_button(label="📥 下载 Markdown 笔记", data=st.session_state.note_md, file_name=filename, mime="text/markdown", type="primary")
            if st.session_state.note_saved_path:
                st.caption(f"💾 已保存到：{st.session_state.note_saved_path}")
            else:
                st.caption("⚠️ 本地保存失败，但仍可下载。")
            st.markdown("---")
            st.markdown("### 📄 笔记预览")
            st.markdown(st.session_state.note_md)


# ============================================================
with tab2:
    st.subheader("📡 关注领域追踪与最新论文发现")
    st.caption("管理关注方向，一键刷新最新论文，追踪新发现论文。")
    _t_col1, _t_col2 = st.columns([2, 1])
    with _t_col1:
        with st.expander("➕ 新增关注领域", expanded=False):
            with st.form("watch_form", clear_on_submit=True):
                w_name = st.text_input("领域名称", placeholder="例如：LLM Agents")
                w_query = st.text_input("arXiv 搜索关键词", placeholder='"large language model" AND agent')
                w_cats = st.text_input("arXiv 分类（可选）", placeholder="cs.CL, cs.AI")
                w_max = st.number_input("每次获取数量", min_value=1, max_value=50, value=10)
                w_notes = st.text_input("备注（可选）")
                w_enabled = st.checkbox("启用", value=True)
                if st.form_submit_button("✅ 新增关注领域", use_container_width=True):
                    if not w_name.strip() or not w_query.strip():
                        st.warning("⚠️ 领域名称和搜索关键词为必填项。")
                    else:
                        cats = [c.strip() for c in w_cats.split(",") if c.strip()] if w_cats else None
                        item = create_watch_item(name=w_name.strip(), query=w_query.strip(), categories=cats, max_results=w_max, notes=w_notes.strip(), enabled=w_enabled)
                        if add_watch_item(item):
                            st.session_state.tracker_watchlist = _load_wl()
                            st.success(f"✅ 已新增「{w_name}」")
                            st.rerun()
        if st.session_state.tracker_watchlist:
            enabled_count = len([w for w in st.session_state.tracker_watchlist if w.get("enabled", True)])
            st.caption(f"已启用 {enabled_count}/{len(st.session_state.tracker_watchlist)} 个关注领域")
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                if st.button("🔄 刷新所有启用领域", use_container_width=True):
                    with st.spinner("正在获取最新论文..."):
                        # 追踪刷新会写入本地 JSON；刷新完成后重新 load，保证 UI 展示的是持久化后的状态。
                        result = refresh_all_enabled_watch_items(st.session_state.tracker_watchlist, st.session_state.tracker_history)
                        st.session_state.last_refresh_result = result
                        st.session_state.tracker_watchlist = _load_wl()
                        st.session_state.tracker_history = load_paper_history()
                        st.session_state.tracker_state = load_tracker_state()
                    st.rerun()
            with col_r2:
                if st.session_state.tracker_watchlist:
                    wids = [w["id"] for w in st.session_state.tracker_watchlist]
                    wnames = [w["name"] for w in st.session_state.tracker_watchlist]
                    refresh_single_id = st.selectbox("选择领域", options=wids, format_func=lambda wid: next((w["name"] for w in st.session_state.tracker_watchlist if w["id"] == wid), wid), key="refresh_single_select")
                    if st.button("🔄 刷新选中领域", use_container_width=True):
                        item = next((w for w in st.session_state.tracker_watchlist if w["id"] == refresh_single_id), None)
                        if item:
                            with st.spinner(f"正在刷新「{item['name']}」..."):
                                r = refresh_watch_item(item, st.session_state.tracker_history)
                                st.session_state.last_refresh_result = {"results": [r], "total_fetched": r["fetched_count"], "total_new": r["new_count"], "error_count": 0 if r["success"] else 1, "message": r.get("message")}
                            st.session_state.tracker_watchlist = _load_wl()
                            st.session_state.tracker_history = load_paper_history()
                            st.session_state.tracker_state = load_tracker_state()
                            st.rerun()
        if st.session_state.last_refresh_result:
            lr = st.session_state.last_refresh_result
            st.markdown("---")
            if lr.get("message"):
                st.warning(f"⚠️ {lr['message']}")
            else:
                st.markdown(f"**📊 上次刷新：** 获取 {lr.get('total_fetched', 0)} 篇，新发现 {lr.get('total_new', 0)} 篇")
            if lr.get("error_count", 0) > 0:
                for r in lr.get("results", []):
                    if not r.get("success"):
                        wname = "?"
                        for w in st.session_state.tracker_watchlist:
                            if w.get("id") == r.get("watch_id"):
                                wname = w.get("name", "?")
                                break
                        st.caption(f"- {wname}: {r.get('message', '未知错误')}")
    with _t_col2:
        if st.session_state.tracker_watchlist:
            for w in st.session_state.tracker_watchlist:
                with st.expander(f"{'✅' if w.get('enabled') else '⏸️'} {w.get('name', '?')}", expanded=False):
                    st.caption(f"Query: `{w.get('query', '')}`")
                    if w.get("categories"):
                        st.caption(f"分类: {', '.join(w['categories'])}")
                    st.caption(f"每次 {w.get('max_results', 20)} 篇")
                    if w.get("notes"):
                        st.caption(f"备注: {w['notes']}")
                    ce1, ce2, ce3 = st.columns(3)
                    with ce1:
                        if st.button("⏸️ 停用" if w["enabled"] else "▶️ 启用", key=f"toggle_{w['id']}"):
                            update_watch_item(w["id"], {"enabled": not w.get("enabled", True)})
                            st.session_state.tracker_watchlist = _load_wl()
                            st.rerun()
                    with ce2:
                        if st.button("✏️ 编辑", key=f"editbtn_{w['id']}"):
                            st.session_state[f"edit_open_{w['id']}"] = True
                    with ce3:
                        dk = f"delc_{w['id']}"
                        if not st.session_state.get(dk):
                            if st.button("🗑️ 删除", key=f"del_{w['id']}"):
                                st.session_state[dk] = True
                                st.rerun()
                        else:
                            cl1, cl2 = st.columns(2)
                            with cl1:
                                if st.button("✅ 确认", key=f"delok_{w['id']}"):
                                    delete_watch_item(w["id"])
                                    st.session_state.tracker_watchlist = _load_wl()
                                    st.session_state[dk] = False
                                    st.rerun()
                            with cl2:
                                if st.button("❌ 取消", key=f"delcancel_{w['id']}"):
                                    st.session_state[dk] = False
                                    st.rerun()
                    if st.session_state.get(f"edit_open_{w['id']}"):
                        with st.form(f"edit_form_{w['id']}"):
                            e_n = st.text_input("名称", value=w.get("name", ""))
                            e_q = st.text_input("Query", value=w.get("query", ""))
                            e_c = st.text_input("分类", value=", ".join(w.get("categories", [])))
                            e_m = st.number_input("数量", min_value=1, max_value=50, value=w.get("max_results", 20))
                            e_note = st.text_input("备注", value=w.get("notes", ""))
                            e_en = st.checkbox("启用", value=w.get("enabled", True))
                            if st.form_submit_button("💾 保存"):
                                cats = [c.strip() for c in e_c.split(",") if c.strip()] if e_c else []
                                update_watch_item(w["id"], {"name": e_n, "query": e_q, "categories": cats, "max_results": e_m, "notes": e_note, "enabled": e_en})
                                st.session_state.tracker_watchlist = _load_wl()
                                st.session_state[f"edit_open_{w['id']}"] = False
                                st.rerun()
        else:
            st.info("👆 尚未添加任何关注领域。")

    st.markdown("---")
    st.subheader("📚 追踪论文库")
    all_hist = st.session_state.tracker_history
    all_ps = list(all_hist.get("papers", {}).values())
    if not all_ps:
        st.info("📭 暂无追踪论文。")
    else:
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            wopts = ["全部"] + [w["id"] for w in st.session_state.tracker_watchlist]
            wnames = ["全部"] + [w["name"] for w in st.session_state.tracker_watchlist]
            fw = st.selectbox("按领域", options=wopts, format_func=lambda x: wnames[wopts.index(x)] if x in wopts else x, key="tfilt1")
        with c2:
            fs = st.selectbox("按状态", options=["全部","unread","reading","read","starred","ignored"], format_func=lambda x: {"unread":"未读","reading":"阅读中","read":"已读","starred":"⭐","ignored":"🚫","全部":"全部"}.get(x,x), key="tfilt2")
        with c3:
            fk = st.text_input("关键词", placeholder="标题/摘要/作者", key="tfilt3")
        with c4:
            fn = st.checkbox("仅新发现", key="tfilt4")
        with c5:
            sm = st.selectbox("排序", options=["score_desc","date_desc","date_asc","title_asc"], format_func=lambda x: {"score_desc":"评分↓","date_desc":"最新↓","date_asc":"最早↑","title_asc":"A-Z"}.get(x,x), key="tfilt5")
        filt = filter_tracked_papers(all_hist, watch_item_id=None if fw=="全部" else fw, status=None if fs=="全部" else fs, only_new=fn, keyword=fk.strip() if fk else None)
        filt = sort_tracked_papers(filt, sm)
        st.caption(f"共 {len(filt)} 篇（总计 {len(all_ps)} 篇）")
        for i, p in enumerate(filt[:50], 1):
            title = p.get("title") or "未命名论文"
            pub = p.get("published") or "未知"
            score = p.get("score") or 0
            pid = p.get("paper_id", "")
            is_new = p.get("is_new", False)
            authors = p.get("authors") or ["未知"]
            sources = p.get("source_watch_names") or ["未知"]
            summary = (p.get("summary") or "") or "暂无摘要"
            reason = p.get("rank_reason") or ""
            bd = p.get("score_breakdown") or {}
            with st.expander(f"#{i} | {'🆕' if is_new else ''} 评分{score} | {title[:80]}"):
                st.markdown(f"**作者：** {', '.join(authors[:5])}")
                st.markdown(f"**时间：** {pub}  |  **来源：** {', '.join(sources)}")
                cs = p.get("status", "unread")
                ns = st.selectbox("状态", options=["unread","reading","read","starred","ignored"], index=["unread","reading","read","starred","ignored"].index(cs) if cs in ["unread","reading","read","starred","ignored"] else 0, format_func=lambda x: {"unread":"未读","reading":"阅读中","read":"已读","starred":"⭐","ignored":"🚫"}.get(x,x), key=f"ts_{pid}_{i}")
                if ns != cs:
                    hist = update_paper_status(pid, ns, st.session_state.tracker_history)
                    st.session_state.tracker_history = hist
                    st.rerun()
                if bd:
                    c1, c2, c3, c4, c5, c6 = st.columns(6)
                    c1.metric("综合", f"{score}")
                    c2.metric("相关性", f"{bd.get('relevance',0)}")
                    c3.metric("贡献", f"{bd.get('contribution',0)}")
                    c4.metric("方法", f"{bd.get('method_clarity',0)}")
                    c5.metric("证据", f"{bd.get('evidence',0)}")
                    c6.metric("新鲜度", f"{bd.get('freshness',0)}")
                if reason:
                    st.markdown(f"> 💡 {reason}")
                st.markdown(f"> {summary[:300]}{'...' if len(summary) > 300 else ''}")
                cl, cr = st.columns(2)
                with cl:
                    if p.get("arxiv_url"):
                        st.markdown(f"[📄 arXiv]({p['arxiv_url']})")
                with cr:
                    if p.get("pdf_url"):
                        st.markdown(f"[📥 PDF]({p['pdf_url']})")

# ============================================================
# TAB 3：Reviewer 分析（v1.2.3 状态隔离修复）
# ============================================================
with tab3:
    st.subheader("🔍 Reviewer 视角分析")
    st.caption("从审稿人角度分析论文。Reviewer 选择不影响当前阅读论文。")
    from modules.llm_client import get_llm_info as _glli
    source_type = st.radio("选择分析来源", options=["当前搜索结果", "关注追踪历史", "当前上传 PDF"], horizontal=True, key="rev_src")
    selected_rev = None
    selected_rev_id = None

    if source_type == "当前搜索结果":
        if st.session_state.get("ranked_papers"):
            opts = [f"#{i} | {p.get('title','')[:80]}" for i, p in enumerate(st.session_state.ranked_papers, 1)]
            idx = st.selectbox("从排序结果中选择", range(len(opts)), format_func=lambda i: opts[i], key="rev_sel1")
            selected_rev = st.session_state.ranked_papers[idx]
            selected_rev_id = get_paper_id(selected_rev)
            # 不在 selectbox 阶段修改全局 current_paper
        else:
            st.info("👆 请先在「论文阅读」中搜索并排序论文。")
    elif source_type == "关注追踪历史":
        hist = st.session_state.tracker_history
        aps = list(hist.get("papers", {}).values())
        if aps:
            opts = [f"{p.get('title','')[:80]} | 评分 {p.get('score',0)}" for p in aps[:50]]
            idx = st.selectbox("从追踪历史中选择", range(len(opts)), format_func=lambda i: opts[i], key="rev_sel2")
            selected_rev = aps[idx]
            selected_rev_id = selected_rev.get("paper_id") or get_paper_id(selected_rev)
            # 不在 selectbox 阶段修改全局 current_paper
        else:
            st.info("👆 请先在「关注追踪」中刷新论文。")
    elif source_type == "当前上传 PDF":
        if st.session_state.pdf_text:
            bound_id = st.session_state.get("pdf_bound_paper_id")
            filename = st.session_state.get("pdf_filename", "手动上传 PDF")
            if bound_id == "manual_pdf":
                # manual_pdf 场景：使用 manual_pdf id，不读取 current_paper
                selected_rev_id = "manual_pdf"
                selected_rev = {
                    "paper_id": "manual_pdf",
                    "title": filename,
                    "abstract": "",
                    "summary": "",
                }
            elif st.session_state.current_paper:
                # 有 current_paper 且有匹配的 PDF：使用 current_paper
                selected_rev = st.session_state.current_paper
                selected_rev_id = get_paper_id(selected_rev)
            else:
                # 兜底
                selected_rev_id = bound_id or st.session_state.get("current_paper_id") or "manual_pdf"
                selected_rev = {
                    "paper_id": selected_rev_id,
                    "title": st.session_state.get("pdf_bound_paper_title", filename),
                    "abstract": "",
                    "summary": "",
                }
            if selected_rev:
                st.caption(f"当前论文：{selected_rev.get('title','')[:80]}")
        else:
            st.info("👆 请先上传并解析 PDF。")

    if selected_rev:
        # PDF 绑定状态（针对 selected_rev_id，不是 current_paper_id）
        rev_pdf_ctx = _get_pdf_context_for_paper_id(selected_rev_id) if selected_rev_id else {"available": False}
        if rev_pdf_ctx["available"]:
            st.success("✅ 当前 PDF 已绑定到所选论文，可用于 Reviewer 分析。")
        elif rev_pdf_ctx["reason"] == "pdf_bound_mismatch":
            st.warning("⚠️ 当前 PDF 绑定于另一篇论文。分析将仅基于摘要和元信息。")
        else:
            st.info("ℹ️ 未上传 PDF，分析将基于标题、摘要和元信息。")

        llm_info2 = _glli()
        use_llm = st.checkbox("🤖 使用 LLM 增强分析", value=llm_info2["available"], key="rev_llm") if llm_info2["available"] else False
        c1, c2 = st.columns([2, 3])
        with c1:
            if st.button("🔍 生成 Reviewer 分析", type="primary", use_container_width=True, key="rev_btn"):
                # 不修改 current_paper / current_paper_id
                # 使用局部 selected_rev / selected_rev_id
                srcl = source_type.replace("当前", "").replace(" ", "_").strip("_") or "unknown"

                if rev_pdf_ctx["available"]:
                    usep = rev_pdf_ctx["paper_text"]
                    use_chunks = rev_pdf_ctx["chunks"]
                else:
                    usep = None
                    use_chunks = None

                # summary/QA 只按 selected_rev_id 过滤（不依赖 current_paper_id）
                uses = (st.session_state.summary if st.session_state.summary_paper_id == selected_rev_id else None)
                useq = [q for q in st.session_state.qa_history if q.get("paper_id") == selected_rev_id] if selected_rev_id else None

                with st.spinner("正在生成审稿分析..."):
                    result = analyze_as_reviewer(
                        paper=selected_rev,
                        paper_text=usep, chunks=use_chunks,
                        summary=uses, qa_history=useq,
                        ranking_info=selected_rev,
                        source_type=srcl,
                        force_fallback=not use_llm,
                    )
                    st.session_state.reviewer_result = result
                    st.session_state.reviewer_paper_id = selected_rev_id
                    st.session_state.reviewer_used_pdf = rev_pdf_ctx["available"]
                    st.session_state.reviewer_history.append({
                        "paper_title": selected_rev.get("title") or "?" if selected_rev else "PDF",
                        "generated_at": __import__("datetime").datetime.now().isoformat(),
                        "review_result": result,
                    })
                    st.success(f"✅ 完成（模式：{result['mode']}）")

        if st.session_state.reviewer_result:
            r = st.session_state.reviewer_result
            if st.session_state.reviewer_paper_id and st.session_state.reviewer_paper_id != selected_rev_id:
                st.warning("⚠️ 当前显示的是另一篇论文的分析，请重新生成。")
            pdf_note = "（已结合 PDF）" if st.session_state.reviewer_used_pdf else "（基于摘要/元信息）"
            st.caption(f"模式：{'🤖 LLM' if r['mode'] == 'llm' else '⚠️ Fallback'} | 置信度：{r.get('confidence','?')} | PDF：{pdf_note}")
            st.markdown("---")
            st.markdown(format_review_markdown(r))
    else:
        st.info("💡 请先选择一个分析来源。")

# ============================================================
# TAB 4：创新点分析（v1.2）
# ============================================================
with tab4:
    st.subheader("💡 创新点分析")
    st.caption("分析当前论文的核心创新、主要贡献、新颖性、方法差异和潜在影响。")

    if not st.session_state.current_paper:
        if st.session_state.current_paper_id == "manual_pdf" and _is_pdf_bound():
            # manual_pdf 场景：有 PDF，可以分析
            st.caption(f"当前论文：{st.session_state.pdf_filename}（手动上传 PDF）")
        else:
            st.info("👆 请先在「论文阅读」中选择一篇论文，或上传 PDF 后作为手动论文分析。")
            st.stop()
    if True:  # 继续执行（保证缩进一致）
        disp_paper = st.session_state.current_paper
        if disp_paper:
            st.caption(f"当前论文：{disp_paper.get('title','')[:80]}")
        else:
            st.caption(f"当前论文：{st.session_state.get('pdf_filename','手动上传 PDF')}（manual_pdf）")
        pdf_ctx_in = _get_current_pdf_context()
        if pdf_ctx_in["available"]:
            st.success("✅ 当前 PDF 已绑定，创新点分析将结合全文进行。")
        elif pdf_ctx_in.get("bound_paper_id") and pdf_ctx_in.get("bound_paper_id") != pdf_ctx_in.get("current_paper_id"):
            st.warning("⚠️ 当前 PDF 绑定于另一篇论文，分析将仅基于标题和摘要。")
        else:
            st.info("ℹ️ 未上传 PDF，分析将基于标题、摘要和元信息。")

        col1, col2 = st.columns([2, 3])
        with col1:
            if st.button("💡 生成创新点分析", type="primary", use_container_width=True, key="innovation_btn"):
                cpid = st.session_state.current_paper_id
                summary_in = (st.session_state.summary if st.session_state.summary_paper_id == cpid else None)
                qa_in = [q for q in st.session_state.qa_history if q.get("paper_id") == cpid]
                if pdf_ctx_in["available"]:
                    paper_in, chunks_in, used_in = pdf_ctx_in["paper_text"], pdf_ctx_in["paper_chunks"], True
                else:
                    paper_in, chunks_in, used_in = None, None, False

                with st.spinner("正在分析论文创新点..."):
                    result_in = analyze_innovation(
                        paper=st.session_state.current_paper,
                        paper_text=paper_in, chunks=chunks_in,
                        summary=summary_in, qa_history=qa_in,
                    )
                    st.session_state.innovation_analysis = result_in
                    st.session_state.innovation_paper_id = cpid
                    st.session_state.innovation_used_pdf = used_in
                    st.session_state.innovation_pdf_meta = pdf_ctx_in["pdf_meta"] if used_in else {}
                st.success(f"✅ 创新点分析完成（模式：{result_in['mode']}）")

        if st.session_state.innovation_analysis:
            r = st.session_state.innovation_analysis
            if st.session_state.innovation_paper_id != st.session_state.current_paper_id:
                st.warning("⚠️ 当前显示的是另一篇论文的创新点分析，请重新生成。")
            pdf_note = "（已结合 PDF）" if st.session_state.innovation_used_pdf else "（基于摘要/元信息）"
            st.caption(f"模式：{'🤖 LLM' if r['mode']=='llm' else '⚠️ Fallback'} | 置信度：{r.get('confidence','?')} | PDF：{pdf_note}")
            st.markdown("---")
            st.markdown(format_innovation_markdown(r))

# ============================================================
# TAB 5：研究趋势分析（v1.3.1）
# ============================================================
with tab5:
    st.subheader("📈 研究趋势分析")
    st.caption(
        "基于当前搜索/排序结果和关注追踪历史，统计关键词、时间分布、分类分布与代表论文。"
        "该分析仅反映当前项目数据范围，不代表全领域结论。"
    )
    from modules.trend_analyzer import analyze_research_trends, collect_trend_papers

    source_option = st.radio(
        "选择趋势分析数据来源",
        options=["当前搜索/排序结果", "关注追踪历史", "合并分析"],
        horizontal=True,
        key="trend_source",
    )

    trend_papers_raw = []
    trend_source_label = ""

    if source_option == "当前搜索/排序结果":
        # 优先 ranked_papers，fallback 到 papers/search_results
        rp = st.session_state.get("ranked_papers") or []
        sp = st.session_state.get("papers") or []
        sr = st.session_state.get("search_results") or []
        if rp:
            trend_papers_raw = collect_trend_papers(ranked_papers=rp)
            trend_source_label = "当前搜索/排序结果"
        elif sp:
            trend_papers_raw = collect_trend_papers(papers=sp)
            trend_source_label = "当前搜索结果（未排序）"
        elif sr:
            trend_papers_raw = collect_trend_papers(papers=sr)
            trend_source_label = "当前搜索结果（未排序）"
        else:
            st.info("👆 请先在「论文阅读」中搜索论文。")
    elif source_option == "关注追踪历史":
        th = st.session_state.get("tracker_history") or {}
        all_ps = list(th.get("papers", {}).values()) if isinstance(th.get("papers"), dict) else []
        if all_ps:
            trend_papers_raw = collect_trend_papers(tracked_papers=all_ps)
            trend_source_label = "关注追踪历史"
        else:
            st.info("👆 请先在「关注追踪」中刷新论文。")
    elif source_option == "合并分析":
        rp = st.session_state.get("ranked_papers") or []
        sp = st.session_state.get("papers") or []
        sr = st.session_state.get("search_results") or []
        th = st.session_state.get("tracker_history") or {}
        all_ps = list(th.get("papers", {}).values()) if isinstance(th.get("papers"), dict) else []
        if rp or sp or sr or all_ps:
            trend_papers_raw = collect_trend_papers(
                ranked_papers=rp,
                papers=(sp or sr),
                tracked_papers=all_ps,
            )
            trend_source_label = "合并分析"
        else:
            st.info("👆 请先在「论文阅读」中搜索论文，或在「关注追踪」中刷新论文。")

    if trend_papers_raw:
        st.caption(f"数据来源：{trend_source_label}（去重后 {len(trend_papers_raw)} 篇）")

        # 参数
        c_params1, c_params2 = st.columns(2)
        with c_params1:
            top_k_kw = st.slider("关键词展示数量", min_value=5, max_value=40, value=20, step=5, key="trend_topk")
        with c_params2:
            recent_mo = st.slider("新兴主题窗口（月，用于区分近期与早期论文）", min_value=3, max_value=12, value=6, step=1,
                                     key="trend_recmonths",
                                     help="论文时间不足时，系统会自动回退到前后半段比较。")

        c1, c2, c3 = st.columns([2, 1, 3])
        with c1:
            if st.button("📈 生成趋势分析", type="primary", use_container_width=True, key="trend_btn"):
                with st.spinner("正在分析趋势..."):
                    result = analyze_research_trends(
                        trend_papers_raw,
                        source_name=trend_source_label,
                        top_k_keywords=top_k_kw,
                        recent_months=recent_mo,
                    )
                    st.session_state.trend_analysis_result = result
                    st.session_state.trend_analysis_source = trend_source_label
                    st.session_state.trend_analysis_generated_at = __import__("datetime").datetime.now().isoformat()
                    st.session_state.trend_analysis_paper_ids = [
                        p.get("paper_id") for p in trend_papers_raw if p.get("paper_id")
                    ]
                if result.get("paper_count", 0) > 0:
                    st.success(f"✅ 趋势分析完成（{result.get('paper_count', 0)} 篇论文）")
                else:
                    st.warning("⚠️ 趋势分析完成但无有效论文数据。")

        # 展示结果
        if st.session_state.trend_analysis_result:
            r = st.session_state.trend_analysis_result
            if r.get("paper_count", 0) == 0:
                st.info(r.get("trend_summary", "暂无可分析论文。"))
                for w in r.get("warnings", []):
                    st.caption(f"⚠️ {w}")
            else:
                # 上次生成提示
                if st.session_state.trend_analysis_source:
                    st.caption(f"📌 当前展示的是「{st.session_state.trend_analysis_source}」的趋势分析结果。切换数据源后请重新生成。")

                # 总览指标
                st.markdown("---")
                st.markdown("### 📊 总览指标")
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    st.metric("论文数量", r.get("paper_count", 0))
                with m2:
                    td = r.get("time_distribution", [])
                    span = f"{td[0]['month']} ~ {td[-1]['month']}" if len(td) >= 2 else (td[0]['month'] if td else "未知")
                    st.metric("时间跨度", span)
                with m3:
                    cd = r.get("category_distribution", [])
                    top_cat = cd[0]["category"] if cd else "未知"
                    st.metric("主要分类", top_cat[:20])
                with m4:
                    hs = r.get("high_score_topics", [])
                    top_hs = hs[0]["topic"] if hs else "暂无"
                    st.metric("高分主题", top_hs[:20])

                # 趋势总结
                st.markdown("---")
                st.markdown("### 📝 趋势总结")
                st.info(r.get("trend_summary", "无法生成趋势总结。"))

                # 时间分布
                st.markdown("---")
                st.markdown("### 📅 时间分布")
                td = r.get("time_distribution", [])
                if td:
                    chart_data = {t["month"]: t["count"] for t in td}
                    st.bar_chart(chart_data)
                else:
                    st.info("当前数据缺少发布时间，无法生成时间分布。")

                # 关键词分布
                st.markdown("---")
                st.markdown("### 🔑 关键词分布")
                kd = r.get("keyword_distribution", [])
                if kd:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(kd[:15]), use_container_width=True, hide_index=True)
                else:
                    st.info("暂无足够文本用于关键词统计。")

                # 热点主题 + 新兴主题 两列
                col_hot, col_em = st.columns(2)
                with col_hot:
                    st.markdown("### 🔥 热点主题")
                    ht = r.get("hot_topics", [])
                    if ht:
                        import pandas as pd
                        st.dataframe(pd.DataFrame(ht[:10]), use_container_width=True, hide_index=True)
                    else:
                        st.info("暂无热点主题数据。")
                with col_em:
                    st.markdown("### 🆕 新兴主题")
                    et = r.get("emerging_topics", [])
                    if et:
                        import pandas as pd
                        st.dataframe(pd.DataFrame(et[:10]), use_container_width=True, hide_index=True)
                    else:
                        st.info("样本不足，暂无法判断新兴主题。")

                # 高分主题
                st.markdown("---")
                st.markdown("### ⭐ 高分论文主题")
                hs = r.get("high_score_topics", [])
                if hs:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(hs[:10]), use_container_width=True, hide_index=True)
                else:
                    st.info("暂无分数字段，无法生成高分主题。")

                # 分类分布
                st.markdown("---")
                st.markdown("### 📂 分类分布")
                cd = r.get("category_distribution", [])
                if cd:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(cd[:12]), use_container_width=True, hide_index=True)
                    if len(cd) >= 2:
                        cat_chart = {c["category"]: c["count"] for c in cd[:10]}
                        st.bar_chart(cat_chart, horizontal=True)
                else:
                    st.info("暂无分类数据。")

                # 代表性论文
                st.markdown("---")
                st.markdown("### 🏆 代表性论文")
                reps = r.get("representative_papers", [])
                if reps:
                    import pandas as pd
                    st.dataframe(pd.DataFrame(reps[:5]), use_container_width=True, hide_index=True)
                else:
                    st.info("暂无代表性论文。")

                # 警告
                for w in r.get("warnings", []):
                    st.caption(f"⚠️ {w}")

# ============================================================
# TAB 6：论文关系图谱（v1.4.0）
# ============================================================
with tab6:
    st.subheader("🕸️ 论文关系图谱")
    st.caption(
        "基于当前搜索/排序结果和关注追踪历史，构建论文间关系网络（关键词相似度、共享分类、共享作者等）。"
        "如无真实引用字段，图谱为基于元信息和相似度的推断关系图谱。"
    )
    from modules.paper_graph import build_paper_graph, collect_graph_papers

    graph_source_option = st.radio(
        "选择图谱数据来源",
        options=["当前搜索/排序结果", "关注追踪历史", "合并数据"],
        horizontal=True,
        key="graph_source",
    )

    graph_papers_raw: list[dict] = []
    graph_source_label = ""

    if graph_source_option == "当前搜索/排序结果":
        rp = st.session_state.get("ranked_papers") or []
        sp = st.session_state.get("papers") or []
        sr = st.session_state.get("search_results") or []
        if rp:
            graph_papers_raw = collect_graph_papers(ranked_papers=rp)
            graph_source_label = "当前搜索/排序结果"
        elif sp:
            graph_papers_raw = collect_graph_papers(papers=sp)
            graph_source_label = "当前搜索结果（未排序）"
        elif sr:
            graph_papers_raw = collect_graph_papers(papers=sr)
            graph_source_label = "当前搜索结果（未排序）"
        else:
            st.info("👆 请先在「论文阅读」中搜索论文。")
    elif graph_source_option == "关注追踪历史":
        th = st.session_state.get("tracker_history") or {}
        all_ps = list(th.get("papers", {}).values()) if isinstance(th.get("papers"), dict) else []
        if all_ps:
            graph_papers_raw = collect_graph_papers(tracked_papers=all_ps)
            graph_source_label = "关注追踪历史"
        else:
            st.info("👆 请先在「关注追踪」中刷新论文。")
    elif graph_source_option == "合并数据":
        rp = st.session_state.get("ranked_papers") or []
        sp = st.session_state.get("papers") or []
        sr = st.session_state.get("search_results") or []
        th = st.session_state.get("tracker_history") or {}
        all_ps = list(th.get("papers", {}).values()) if isinstance(th.get("papers"), dict) else []
        if rp or sp or sr or all_ps:
            graph_papers_raw = collect_graph_papers(
                ranked_papers=rp,
                papers=(sp or sr),
                tracked_papers=all_ps,
            )
            graph_source_label = "合并数据"
        else:
            st.info("👆 请先在「论文阅读」中搜索论文，或在「关注追踪」中刷新论文。")

    if graph_papers_raw:
        st.caption(f"数据来源：{graph_source_label}（去重后 {len(graph_papers_raw)} 篇）")

        # 参数
        cg1, cg2, cg3 = st.columns(3)
        with cg1:
            max_nodes = st.slider("最大节点数", min_value=5, max_value=80, value=30, step=5, key="graph_maxn")
        with cg2:
            min_sim = st.slider("最小相似度", min_value=0.05, max_value=0.50, value=0.12, step=0.01, key="graph_minsim")
        with cg3:
            st.markdown("&nbsp;")
            st.caption("参数调整后需重新生成")

        col_inc1, col_inc2, col_inc3, col_inc4 = st.columns(4)
        with col_inc1:
            inc_content = st.checkbox("内容相似边", value=True, key="graph_inc_content")
        with col_inc2:
            inc_category = st.checkbox("分类共享边", value=True, key="graph_inc_cat")
        with col_inc3:
            inc_author = st.checkbox("作者共享边", value=True, key="graph_inc_auth")
        with col_inc4:
            inc_ref = st.checkbox("引用字段边", value=True, key="graph_inc_ref")

        cg_btn1, cg_btn2, cg_btn3 = st.columns([2, 1, 3])
        with cg_btn1:
            if st.button("🕸️ 生成论文关系图谱", type="primary", use_container_width=True, key="graph_btn"):
                with st.spinner("正在构建关系图谱..."):
                    result = build_paper_graph(
                        graph_papers_raw,
                        source_name=graph_source_label,
                        max_nodes=max_nodes,
                        min_similarity=min_sim,
                        include_content_edges=inc_content,
                        include_category_edges=inc_category,
                        include_author_edges=inc_author,
                        include_reference_edges=inc_ref,
                    )
                    st.session_state.paper_graph_result = result
                    st.session_state.paper_graph_source = graph_source_label
                    st.session_state.paper_graph_paper_ids = [
                        n["id"] for n in result.get("nodes", []) if n.get("id")
                    ]
                if result.get("success"):
                    st.success(f"✅ 图谱构建完成（{result.get('node_count', 0)} 节点, {result.get('edge_count', 0)} 边）")
                else:
                    st.warning(f"⚠️ {result.get('graph_summary', '图谱构建失败')}")

        # 展示
        if st.session_state.paper_graph_result:
            r = st.session_state.paper_graph_result
            if not r.get("success"):
                st.warning(r.get("graph_summary", "图谱构建未成功。"))
                for w in r.get("warnings", []):
                    st.caption(f"⚠️ {w}")
            else:
                # 上次生成提示
                if st.session_state.paper_graph_source:
                    st.caption(f"📌 当前展示的是「{st.session_state.paper_graph_source}」的图谱。切换数据源后请重新生成。")

                # 总览
                st.markdown("---")
                st.markdown("### 📊 图谱总览")
                gm1, gm2, gm3, gm4 = st.columns(4)
                with gm1:
                    st.metric("论文总数", r.get("paper_count", 0))
                with gm2:
                    st.metric("节点数", r.get("node_count", 0))
                with gm3:
                    st.metric("边数", r.get("edge_count", 0))
                with gm4:
                    clusters = r.get("clusters", [])
                    big_c = sum(1 for c in clusters if c["size"] >= 2)
                    st.metric("主题簇", f"{big_c} 个")

                # 图谱总结
                st.markdown("---")
                st.markdown("### 📝 图谱总结")
                st.info(r.get("graph_summary", "无法生成图谱总结。"))

                # Graphviz
                st.markdown("---")
                st.markdown("### 🕸️ 关系图")
                dot = r.get("dot_graph", "")
                if dot:
                    try:
                        st.graphviz_chart(dot)
                    except Exception:
                        st.warning("⚠️ Graphviz 渲染失败，以下为 DOT 源码。")
                        st.code(dot, language="dot")
                else:
                    st.info("无法生成关系图。")

                # 中心论文
                st.markdown("---")
                st.markdown("### ⭐ 中心论文")
                cp = r.get("central_papers", [])
                if cp:
                    import pandas as pd
                    cp_data = [{
                        "标题": c.get("title", "")[:60],
                        "中心度": c.get("centrality_score", 0),
                        "连接数": c.get("degree", 0),
                        "评分": c.get("score"),
                        "原因": c.get("reason", ""),
                    } for c in cp[:5]]
                    st.dataframe(pd.DataFrame(cp_data), use_container_width=True, hide_index=True)
                else:
                    st.info("暂无中心论文数据。")

                # 主题簇
                st.markdown("---")
                st.markdown("### 🏷️ 主题簇")
                clusters = r.get("clusters", [])
                big_clusters = [c for c in clusters if c["size"] >= 2]
                if big_clusters:
                    for c in big_clusters:
                        with st.expander(f"{c['cluster_id']} — {c['size']} 篇论文（中心: {c.get('central_paper_title','')[:40]}）"):
                            st.caption(f"关键词：{', '.join(c.get('top_keywords', [])[:5])}")
                            st.caption(f"论文 ID：{', '.join(c.get('paper_ids', [])[:8])}")
                elif clusters:
                    st.info("当前图谱中所有节点均为孤立节点，未形成主题簇。")
                else:
                    st.info("暂无主题簇数据。")

                # 边表
                st.markdown("---")
                st.markdown("### 🔗 关系边")
                edges = r.get("edges", [])
                if edges:
                    import pandas as pd
                    node_id_to_title = {n["id"]: n.get("short_title", n.get("title", "?"))
                                         for n in r.get("nodes", [])}
                    ed_data = []
                    for e in edges[:50]:
                        ed_data.append({
                            "Source": node_id_to_title.get(e["source"], e["source"])[:35],
                            "Target": node_id_to_title.get(e["target"], e["target"])[:35],
                            "权重": e.get("weight", 0),
                            "关系类型": ", ".join(e.get("relation_types", [])),
                            "原因": (e.get("reason", "") or "")[:80],
                        })
                    st.dataframe(pd.DataFrame(ed_data), use_container_width=True, hide_index=True)
                else:
                    st.info("当前样本未形成关系边，所有节点为孤立节点。")

                # 节点表
                st.markdown("---")
                st.markdown("### 📋 节点列表")
                nodes = r.get("nodes", [])
                if nodes:
                    import pandas as pd
                    nd_data = [{
                        "标题": n.get("short_title", n.get("title", "?"))[:50],
                        "分类": ", ".join(n.get("categories", [])[:3]),
                        "发布日期": n.get("published", ""),
                        "评分": n.get("score"),
                    } for n in nodes]
                    st.dataframe(pd.DataFrame(nd_data), use_container_width=True, hide_index=True)

                for w in r.get("warnings", []):
                    st.caption(f"⚠️ {w}")

# ============================================================
# TAB 7：文献综述（v1.5）
# ============================================================
with tab7:
    st.subheader("📚 自动文献综述")
    st.caption("基于当前论文集合自动生成结构化中文文献综述，包括主题分组、方法对比、代表论文、研究空白和未来方向。")

    source_choice = st.radio("选择数据源", options=["当前搜索/排序结果", "关注追踪历史", "合并数据"], horizontal=True, key="review_src")

    if source_choice == "当前搜索/排序结果":
        src_papers = st.session_state.get("ranked_papers") or st.session_state.get("papers") or st.session_state.get("search_results") or []
        src_label = "当前搜索/排序结果"
    elif source_choice == "关注追踪历史":
        hist = st.session_state.tracker_history
        src_papers = list(hist.get("papers", {}).values()) if hist else []
        src_label = "关注追踪历史"
    else:
        ranked = st.session_state.get("ranked_papers") or st.session_state.get("papers") or st.session_state.get("search_results") or []
        hist = st.session_state.tracker_history
        tracked = list(hist.get("papers", {}).values()) if hist else []
        seen_ids = set()
        merged_papers = []
        for pp in ranked + tracked:
            pid = get_paper_id(pp)
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                merged_papers.append(pp)
        src_papers = merged_papers
        src_label = "合并数据"

    if not src_papers:
        st.info("👆 请先搜索论文或刷新关注领域以获得论文数据。")
    else:
        st.caption(f"当前数据源包含 {len(src_papers)} 篇候选论文。")
        col1, col2 = st.columns([3, 1])
        with col1:
            review_topic = st.text_input("综述主题", value=src_label, key="review_topic_input")
        with col2:
            max_p = st.number_input("最大论文数", min_value=5, max_value=50, value=20, key="review_max")

        use_trend = st.checkbox("结合趋势分析结果（辅助）", value=False, key="review_use_trend")
        use_graph = st.checkbox("结合关系图谱结果（辅助）", value=False, key="review_use_graph")

        trend_in = st.session_state.get("trend_analysis_result") if use_trend else None
        graph_in = st.session_state.get("paper_graph_result") if use_graph else None

        if use_trend and not trend_in:
            st.caption("⚠️ 暂无趋势分析结果，将仅基于论文集合生成。请先在趋势分析 Tab 生成。")
        if use_graph and not graph_in:
            st.caption("⚠️ 暂无关系图谱结果，将仅基于论文集合生成。请先在关系图谱 Tab 生成。")

        if st.button("📚 生成文献综述", type="primary", use_container_width=True, key="review_gen_btn"):
            with st.spinner("正在生成文献综述..."):
                review_result = generate_literature_review(
                    papers=src_papers, source_name=src_label,
                    review_topic=review_topic, max_papers=max_p,
                    trend_result=trend_in, graph_result=graph_in,
                )
                st.session_state.literature_review_result = review_result
                st.session_state.literature_review_source = src_label
                st.session_state.literature_review_paper_ids = review_result.get("paper_ids", [])
            st.success("✅ 综述生成完成（规则版）")

        if st.session_state.literature_review_result:
            lr = st.session_state.literature_review_result
            if lr.get("warnings"):
                for w in lr["warnings"]:
                    st.warning(w)
            if lr["success"]:
                st.markdown("---")
                uc = lr['used_paper_count']; pc = lr['paper_count']
                st.markdown(f"**样本：** {uc}/{pc} 篇")
                st.download_button("📥 下载文献综述 Markdown", data=lr["review_markdown"], file_name="literature_review.md", mime="text/markdown", key="review_dl")
                st.markdown("---")
                col_a, col_b = st.columns(2)
                with col_a:
                    with st.expander("📊 主题分组", expanded=True):
                        for tg in lr.get("theme_groups", []):
                            st.markdown(f"**{tg['theme']}**（{tg['paper_count']} 篇）")
                            st.caption(tg.get("summary",""))
                with col_b:
                    with st.expander("🔬 方法路线对比", expanded=True):
                        for mc in lr.get("method_comparison", []):
                            st.markdown(f"**{mc['method_family']}**（{mc['paper_count']} 篇）")
                            st.caption(f"优势：{mc.get('strengths','')}")
                col_c, col_d = st.columns(2)
                with col_c:
                    with st.expander("⚠️ 研究空白"):
                        for rg in lr.get("research_gaps", []):
                            st.markdown(f"- {rg}")
                with col_d:
                    with st.expander("🔮 未来方向"):
                        for fd in lr.get("future_directions", []):
                            st.markdown(f"- {fd}")
                with st.expander("📄 完整 Markdown 综述", expanded=False):
                    st.markdown(lr["review_markdown"])
            else:
                st.info("暂无综述结果。请先生成文献综述。")

        st.markdown("---")
        st.subheader("📌 科研洞察与后续选题建议")
        st.caption("基于当前论文集合、趋势分析、关系图谱和文献综述结果，生成启发式科研洞察。该分析为启发式辅助，不代表完整领域结论。")
        insight_papers = src_papers if src_papers else []
        if st.button("💡 生成科研洞察", use_container_width=True, key="insight_btn"):
            if not insight_papers:
                st.info("请先生成文献综述或先获取论文数据。")
            else:
                with st.spinner("正在生成科研洞察..."):
                    insight_result = generate_research_insight(
                        papers=insight_papers, trend_result=trend_in, graph_result=graph_in,
                        literature_review_result=lr if lr and lr.get("success") else None,
                    )
                    st.session_state.research_insight_result = insight_result
                    pids = [get_paper_id(p) for p in insight_papers if get_paper_id(p)]
                    st.session_state.research_insight_dataset_key = "|".join(sorted(set(pids)))
                st.success("✅ 科研洞察生成完成")
        if st.session_state.get("research_insight_result"):
            rir = st.session_state.research_insight_result
            st.caption(f"样本：{rir.get('used_paper_count',0)}/{rir.get('paper_count',0)} 篇")
            st.markdown(rir.get("markdown",""))
            if rir.get("markdown"):
                st.download_button("📥 下载科研洞察 Markdown", data=rir["markdown"], file_name="research_insight.md", mime="text/markdown", key="insight_dl")


# ── 底部信息 ──────────────────────────────────────────────
st.divider()
st.caption("💡 提示：所有 LLM 依赖模块均有 Fallback 模式。PDF 绑定确保不会误用论文 A 的 PDF 到论文 B。")
