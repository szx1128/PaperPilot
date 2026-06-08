"""
PaperPilot 论文发现模块。

通过 requests 直接调用 arXiv API（Atom XML），支持超时控制和错误降级。
当网络不可用时，提供本地示例论文作为兜底，保证演示流程不中断。

依赖：
- requests（HTTP 请求）
- xml.etree.ElementTree（Atom XML 解析）
- modules/utils.py（文本清洗）
"""

import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests

from modules.paper_identity import get_paper_id
from modules.ranker import score_query_relevance
from modules.utils import clean_text

# ── 常量 ──────────────────────────────────────────────────

ARXIV_API_URL = "https://export.arxiv.org/api/query"
ARXIV_TIMEOUT = 15  # 请求超时秒数
DEFAULT_MAX_RESULTS = 20
MIN_MAX_RESULTS = 1
MAX_MAX_RESULTS = 50

# Atom XML 命名空间
ATOM_NS = "http://www.w3.org/2005/Atom"
OPENSEARCH_NS = "http://a9.com/-/spec/opensearch/1.1/"
ARXIV_NS = "http://arxiv.org/schemas/atom"


# ── 示例论文（网络不可用时的兜底数据） ────────────────────

SAMPLE_PAPERS = [
    {
        "id": "2211.01910v1",
        "title": "Large Language Models Are Human-Level Prompt Engineers",
        "authors": ["Yongchao Zhou", "Andrei Ioan Muresanu", "Ziwen Han", "Keiran Paster",
                     "Silviu Pitis", "Harris Chan", "Jimmy Ba"],
        "published": "2022-11-03",
        "abstract": (
            "By conditioning on natural language instructions, large language models (LLMs) "
            "have displayed impressive capabilities as general-purpose computers. However, "
            "the task of programming LLMs through natural language prompts remains a difficult "
            "and poorly understood challenge. We propose Automatic Prompt Engineer (APE), "
            "a framework for automatic instruction generation and selection. In our method, "
            "we treat the instruction as a \"program,\" and use an LLM to generate a set of "
            "candidate solutions, then select the best one based on a score function. "
            "Experiments show that APE-engineered prompts outperform human-engineered prompts "
            "on 21 of 24 NLP tasks, including language understanding, reading comprehension, "
            "and arithmetic reasoning. Our results demonstrate that machines can be better "
            "at generating effective prompts than humans, suggesting an exciting future "
            "where AI systems can automatically improve themselves."
        ),
        "arxiv_url": "https://arxiv.org/abs/2211.01910",
        "pdf_url": "https://arxiv.org/pdf/2211.01910",
    },
    {
        "id": "2305.10601v1",
        "title": "Tree of Thoughts: Deliberate Problem Solving with Large Language Models",
        "authors": ["Shunyu Yao", "Dian Yu", "Jeffrey Zhao", "Izhak Shafran",
                     "Thomas L. Griffiths", "Yuan Cao", "Karthik Narasimhan"],
        "published": "2023-05-17",
        "abstract": (
            "Language models are increasingly being deployed for general problem solving "
            "across a wide range of tasks, but are still confined to token-level, left-to-right "
            "decision-making processes during inference. This means they can fall short in "
            "tasks that require exploration, strategic lookahead, or where initial decisions "
            "play a pivotal role. To overcome these challenges, we introduce a new framework "
            "for language model inference, Tree of Thoughts (ToT), which generalizes over "
            "the popular Chain of Thought approach to prompting language models, and enables "
            "exploration over coherent units of text (thoughts) that serve as intermediate "
            "steps toward problem solving. ToT allows LMs to perform deliberate decision "
            "making by considering multiple different reasoning paths, and to look ahead or "
            "backtrack as necessary to make global choices. Our experiments show that ToT "
            "significantly enhances language models' problem-solving abilities on three novel "
            "tasks requiring non-trivial planning or search."
        ),
        "arxiv_url": "https://arxiv.org/abs/2305.10601",
        "pdf_url": "https://arxiv.org/pdf/2305.10601",
    },
    {
        "id": "2005.14165v4",
        "title": "Language Models are Few-Shot Learners",
        "authors": ["Tom B. Brown", "Benjamin Mann", "Nick Ryder", "Melanie Subbiah",
                     "Jared Kaplan", "Prafulla Dhariwal", "Arvind Neelakantan",
                     "Pranav Shyam", "Girish Sastry", "Amanda Askell"],
        "published": "2020-05-28",
        "abstract": (
            "Recent work has demonstrated substantial gains on many NLP tasks and benchmarks "
            "by pre-training on a large corpus of text followed by fine-tuning on a specific "
            "task. While typically task-agnostic in architecture, this method still requires "
            "task-specific fine-tuning datasets of thousands or tens of thousands of examples. "
            "By contrast, humans can generally perform a new language task from only a few "
            "examples or from simple instructions. Here we show that scaling up language "
            "models greatly improves task-agnostic, few-shot performance, sometimes even "
            "reaching competitiveness with prior state-of-the-art fine-tuning approaches. "
            "Specifically, we train GPT-3, an autoregressive language model with 175 billion "
            "parameters, and test its performance in the few-shot setting. GPT-3 achieves "
            "strong performance on many NLP datasets, including translation, question-answering, "
            "and cloze tasks, as well as several tasks that require on-the-fly reasoning."
        ),
        "arxiv_url": "https://arxiv.org/abs/2005.14165",
        "pdf_url": "https://arxiv.org/pdf/2005.14165",
    },
    {
        "id": "2303.08774v3",
        "title": "GPT-4 Technical Report",
        "authors": ["OpenAI"],
        "published": "2023-03-15",
        "abstract": (
            "We report the development of GPT-4, a large-scale, multimodal model which can "
            "accept image and text inputs and produce text outputs. While less capable than "
            "humans in many real-world scenarios, GPT-4 exhibits human-level performance on "
            "various professional and academic benchmarks, including passing a simulated bar "
            "exam with a score around the top 10% of test takers. We report on the "
            "development of GPT-4 and characterize its performance on a variety of tasks."
        ),
        "arxiv_url": "https://arxiv.org/abs/2303.08774",
        "pdf_url": "https://arxiv.org/pdf/2303.08774",
    },
    {
        "id": "2203.15556v1",
        "title": "Training Compute-Optimal Large Language Models",
        "authors": ["Jordan Hoffmann", "Sebastian Borgeaud", "Arthur Mensch",
                     "Elena Buchatskaya", "Trevor Cai", "Eliza Rutherford",
                     "Diego de Las Casas", "Lisa Anne Hendricks"],
        "published": "2022-03-29",
        "abstract": (
            "We investigate the optimal model size and number of tokens for training a "
            "transformer language model under a given compute budget. We find that current "
            "large language models are significantly undertrained, as a consequence of the "
            "recent focus on scaling language models whilst keeping the amount of training "
            "data constant. By training over 400 language models ranging from 70 million "
            "to over 16 billion parameters on 5 to 500 billion tokens, we find that for "
            "compute-optimal training, the model size and the number of training tokens "
            "should be scaled equally: for every doubling of model size the number of "
            "training tokens should also be doubled. The resulting model, Chinchilla, "
            "outperforms Gopher (280B), GPT-3 (175B), and Megatron-Turing NLG (530B) "
            "using only 70 billion parameters."
        ),
        "arxiv_url": "https://arxiv.org/abs/2203.15556",
        "pdf_url": "https://arxiv.org/pdf/2203.15556",
    },
]


# ── 公共函数 ──────────────────────────────────────────────

def search_papers(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    categories: list[str] | None = None,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
) -> dict:
    """
    在 arXiv 上搜索论文。

    参数:
        query:       搜索关键词
        max_results: 最大返回数量（5/10/20/30）
        categories:  可选，arXiv 分类列表，如 ["cs.CL", "cs.AI"]
        sort_by:     排序字段
        sort_order:  排序方向

    返回:
        {"papers": [...], "error": None | "错误描述字符串"}
    """
    if not query or not query.strip():
        return {"papers": [], "error": "搜索关键词为空，请输入研究方向或关键词。"}

    if max_results < MIN_MAX_RESULTS:
        max_results = MIN_MAX_RESULTS
    elif max_results > MAX_MAX_RESULTS:
        max_results = MAX_MAX_RESULTS

    # 构建搜索查询：普通搜索只负责 arXiv 调用，不混入具体阅读模式的排序逻辑。
    search_query = _build_search_query(query.strip(), categories)

    try:
        # 所有 search_* 变体最终都复用这套请求和解析逻辑，保证错误处理一致。
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": sort_by,
            "sortOrder": sort_order,
        }
        response = requests.get(
            ARXIV_API_URL,
            params=params,
            timeout=ARXIV_TIMEOUT,
        )
        response.raise_for_status()

        papers = _parse_arxiv_xml(response.text)
        if not papers:
            return {"papers": [], "error": None}
        return {"papers": papers, "error": None}

    except requests.exceptions.Timeout:
        return {
            "papers": [],
            "error": (
                "arXiv API 连接超时。这不一定代表本机网络异常，"
                "可能是 arXiv API 国际链路不稳定。"
                "你可以稍后重试，或使用内置示例论文继续演示。"
            ),
        }
    except requests.exceptions.ConnectionError:
        return {
            "papers": [],
            "error": (
                "无法连接 arXiv 服务器。"
                "这不一定代表本机网络异常，可能是 arXiv API 国际链路不稳定。"
                "你可以稍后重试，或使用内置示例论文继续演示。"
            ),
        }
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        return {
            "papers": [],
            "error": f"arXiv API 返回 HTTP {status} 错误，请稍后重试。",
        }
    except Exception as e:
        print(f"[arxiv_client] 搜索时发生未知错误: {e}")
        return {
            "papers": [],
            "error": "arXiv 搜索时发生未知错误，请稍后重试或使用示例数据。",
        }


def search_overview_papers(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    categories: list[str] | None = None,
) -> dict:
    """
    领域了解模式搜索。

    使用少量扩展 query，并改用 arXiv relevance 排序，以提高 survey / review /
    benchmark / taxonomy 等领域入口论文的召回。该函数不改变 search_papers()
    的原有行为。
    """
    if not query or not query.strip():
        return {"papers": [], "error": "搜索关键词为空，请输入研究方向或关键词。"}

    clean_query = query.strip()
    # 领域了解模式通过少量扩展 query 提高 survey/review/benchmark/taxonomy 召回。
    # 注意这里只扩展搜索，不在这里打最终分，排序仍交给 ranker。
    overview_queries = [
        clean_query,
        f"{clean_query} survey",
        f"{clean_query} review",
        f"{clean_query} benchmark",
        f"{clean_query} taxonomy",
    ]
    per_query = max(5, max_results // len(overview_queries))

    merged: list[dict] = []
    seen_ids: set[str] = set()
    errors: list[str] = []

    for q in overview_queries:
        result = search_papers(
            q,
            max_results=per_query,
            categories=categories,
            sort_by="relevance",
            sort_order="descending",
        )
        if result.get("error"):
            errors.append(result["error"])
            continue

        for paper in result.get("papers", []):
            # 多个扩展 query 可能命中同一篇论文，用稳定 paper_id 去重。
            pid = get_paper_id(paper)
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)
            merged.append(paper)

    if merged:
        return {"papers": merged[: max_results * 2], "error": None}

    if errors:
        return {"papers": [], "error": errors[0]}

    return {"papers": [], "error": None}


def search_deep_research_papers(
    query: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    categories: list[str] | None = None,
) -> dict:
    """
    深入了解模式搜索。

    使用少量扩展 query，并改用 arXiv relevance 排序，以提高方法细节、
    benchmark/evaluation、ablation/comparison 和 code/implementation 相关论文
    的候选召回。该函数不改变 search_papers() 的原有行为。
    """
    if not query or not query.strip():
        return {"papers": [], "error": "搜索关键词为空，请输入研究方向或关键词。"}

    clean_query = query.strip()
    # 深入了解模式会扩展 method/benchmark/ablation/code 等质量相关词。
    # 这些词用于召回“可能适合精读”的论文，但不能直接当成主题相关性证据。
    deep_queries = [
        clean_query,
        f"{clean_query} method framework",
        f"{clean_query} benchmark evaluation",
        f"{clean_query} ablation comparison",
        f"{clean_query} code implementation",
    ]
    per_query = max(5, max_results // len(deep_queries))

    main_pool: list[dict] = []
    weak_pool: list[dict] = []
    seen_ids: set[str] = set()
    errors: list[str] = []
    had_success = False

    for q in deep_queries:
        result = search_papers(
            q,
            max_results=per_query,
            categories=categories,
            sort_by="relevance",
            sort_order="descending",
        )
        if result.get("error"):
            errors.append(result["error"])
            continue
        had_success = True

        for paper in result.get("papers", []):
            pid = get_paper_id(paper)
            if not pid or pid in seen_ids:
                continue
            seen_ids.add(pid)
            # v1.6.5 关键补丁：用原始 query 做相关性门控，过滤掉零相关论文。
            relevance_info = score_query_relevance(paper, clean_query)
            relevance_score = float(relevance_info.get("score", 0.0))
            if relevance_score <= 0:
                continue

            # 相关性字段写回 paper，后续 UI 和 ranker 可以直接展示/复用解释。
            paper = {
                **paper,
                "query_relevance_score": relevance_score,
                "query_relevance_reasons": relevance_info.get("reasons", []),
                "query_relevance_matched_terms": relevance_info.get("matched_terms", []),
                "query_relevance_weak": relevance_score < 0.15,
            }

            if relevance_score >= 0.15:
                main_pool.append(paper)
            else:
                weak_pool.append(paper)

    if main_pool or weak_pool:
        # 主相关结果优先；弱相关只在相关候选不足时放到末尾兜底。
        main_pool.sort(key=lambda p: p.get("query_relevance_score", 0), reverse=True)
        weak_pool.sort(key=lambda p: p.get("query_relevance_score", 0), reverse=True)
        merged = main_pool
        if len(merged) < max_results:
            merged = merged + weak_pool
        elif not merged:
            merged = weak_pool
        return {"papers": merged[:max_results], "error": None}

    if errors and not had_success:
        return {"papers": [], "error": errors[0]}

    return {"papers": [], "error": None}


def fetch_paper_by_id(paper_id: str) -> dict | None:
    """
    根据 arXiv ID 获取单篇论文。

    参数:
        paper_id: arXiv 论文 ID

    返回:
        标准化论文信息 dict，失败返回 None
    """
    clean_id = paper_id.strip()
    try:
        params = {
            "id_list": clean_id,
            "max_results": 1,
        }
        response = requests.get(ARXIV_API_URL, params=params, timeout=ARXIV_TIMEOUT)
        response.raise_for_status()
        papers = _parse_arxiv_xml(response.text)
        return papers[0] if papers else None
    except Exception as e:
        print(f"[arxiv_client] 获取论文 {paper_id} 失败: {e}")
        return None


def get_sample_papers() -> list[dict]:
    """返回内置示例论文列表。"""
    return list(SAMPLE_PAPERS)


# ── 内部解析函数 ──────────────────────────────────────────

def _parse_arxiv_xml(xml_text: str) -> list[dict]:
    """
    解析 arXiv Atom XML 响应，提取标准化论文列表。

    参数:
        xml_text: arXiv API 返回的 XML 字符串

    返回:
        标准化论文信息列表
    """
    root = ET.fromstring(xml_text)
    papers = []

    for entry in root.findall(f"{{{ATOM_NS}}}entry"):
        try:
            # 单篇 entry 解析失败不影响整批结果，避免一个脏记录导致整次搜索失败。
            paper = _parse_entry(entry)
            if paper:
                papers.append(paper)
        except Exception as e:
            print(f"[arxiv_client] 解析 entry 失败: {e}")
            continue

    return papers


def _parse_entry(entry: ET.Element) -> dict | None:
    """解析单个 Atom entry 为标准化 dict。"""
    id_url = entry.findtext(f"{{{ATOM_NS}}}id", "")
    paper_id = id_url.rsplit("/", 1)[-1] if id_url else "unknown"

    title = entry.findtext(f"{{{ATOM_NS}}}title", "")
    authors = []
    for author_elem in entry.findall(f"{{{ATOM_NS}}}author"):
        name = author_elem.findtext(f"{{{ATOM_NS}}}name", "")
        if name:
            authors.append(name)

    published = entry.findtext(f"{{{ATOM_NS}}}published", "")
    if published:
        published = _format_date(published)

    abstract = entry.findtext(f"{{{ATOM_NS}}}summary", "")
    # journal_ref/comment 是 arXiv 可选字段，后续用于保守判断发表可信度。
    journal_ref = entry.findtext(f"{{{ARXIV_NS}}}journal_ref", "")
    comment = entry.findtext(f"{{{ARXIV_NS}}}comment", "")

    # 分类
    categories = []
    primary_category = ""
    for cat_elem in entry.findall(f"{{{ARXIV_NS}}}primary_category"):
        primary_category = cat_elem.get("term", "")
    for cat_elem in entry.findall(f"{{{ARXIV_NS}}}category"):
        term = cat_elem.get("term", "")
        if term and term not in categories:
            categories.append(term)
    if primary_category and primary_category not in categories:
        categories.insert(0, primary_category)

    arxiv_url = id_url
    pdf_url = ""
    for link in entry.findall(f"{{{ATOM_NS}}}link"):
        if link.get("title") == "pdf":
            pdf_url = link.get("href", "")
            break
    if not pdf_url and paper_id != "unknown":
        pdf_url = f"https://arxiv.org/pdf/{paper_id}"

    paper = {
        "id": paper_id,
        "title": clean_text(title),
        "authors": authors,
        "published": published,
        "abstract": clean_text(abstract),
        "arxiv_url": arxiv_url,
        "pdf_url": pdf_url,
        "categories": categories,
        "primary_category": primary_category,
        "journal_ref": clean_text(journal_ref),
        "comment": clean_text(comment),
    }
    return paper


def _build_search_query(query: str, categories: list[str] | None) -> str:
    """构建含分类过滤的 arXiv 搜索查询。"""
    parts = [f"all:{query}"]
    if categories:
        cat_parts = " OR ".join(f"cat:{c}" for c in categories)
        parts.append(f"({cat_parts})")
    return " AND ".join(parts)


def _format_date(date_str: str) -> str:
    """将 ISO 日期格式化为 YYYY-MM-DD。"""
    if not date_str:
        return "Unknown"
    # arXiv 返回的日期格式通常是 "2023-01-30T00:00:00Z"
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except (ValueError, AttributeError):
        try:
            dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return dt.strftime("%Y-%m-%d")
        except (ValueError, AttributeError):
            return "Unknown"
