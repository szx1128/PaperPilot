"""
PaperPilot 论文追踪模块。

负责关注领域管理、论文刷新、去重、状态管理、筛选排序。
不负责 Streamlit UI。复用 arxiv_client 和 ranker。

依赖：
- modules/arxiv_client.py（搜索）
- modules/ranker.py（评分）
- modules/tracker_store.py（持久化）
"""

import hashlib
import re
import uuid
from datetime import datetime, timezone

from modules.arxiv_client import search_papers as _search_arxiv
from modules.ranker import rank_papers as _rank_papers
from modules.tracker_store import (
    load_paper_history,
    load_tracker_state,
    load_watchlist,
    save_paper_history,
    save_tracker_state,
    save_watchlist,
)

VALID_STATUSES = {"unread", "reading", "read", "starred", "ignored"}


# ═══════════════════════════════════════════════════════════
# 关注领域 CRUD
# ═══════════════════════════════════════════════════════════

def create_watch_item(
    name: str,
    query: str,
    categories: list[str] | None = None,
    max_results: int = 20,
    notes: str = "",
    enabled: bool = True,
) -> dict:
    """创建一个关注领域对象。"""
    # watch item 只保存检索配置，不保存论文实体；论文实体统一合并到 history。
    now = datetime.now(timezone.utc).isoformat()
    return {
        "id": f"watch_{uuid.uuid4().hex[:12]}",
        "name": name.strip(),
        "query": query.strip(),
        "categories": categories or [],
        "max_results": max_results,
        "sort_by": "submittedDate",
        "enabled": enabled,
        "notes": notes.strip(),
        "created_at": now,
        "updated_at": now,
        "last_checked_at": None,
    }


def add_watch_item(item: dict) -> bool:
    """将关注领域添加到 watchlist 并保存。"""
    watchlist = load_watchlist()
    watchlist.append(item)
    return save_watchlist(watchlist)


def update_watch_item(item_id: str, updates: dict) -> bool:
    """更新关注领域。"""
    watchlist = load_watchlist()
    for i, w in enumerate(watchlist):
        if w.get("id") == item_id:
            for key in ("name", "query", "categories", "max_results", "notes", "enabled"):
                if key in updates:
                    watchlist[i][key] = updates[key]
            watchlist[i]["updated_at"] = datetime.now(timezone.utc).isoformat()
            return save_watchlist(watchlist)
    return False


def delete_watch_item(item_id: str) -> bool:
    """删除关注领域。"""
    watchlist = load_watchlist()
    before = len(watchlist)
    watchlist = [w for w in watchlist if w.get("id") != item_id]
    if len(watchlist) == before:
        return False
    return save_watchlist(watchlist)


def get_watch_item(item_id: str) -> dict | None:
    """获取单个关注领域。"""
    watchlist = load_watchlist()
    for w in watchlist:
        if w.get("id") == item_id:
            return w
    return None


# ═══════════════════════════════════════════════════════════
# 论文 ID 与去重
# ═══════════════════════════════════════════════════════════

def normalize_paper_id(paper: dict) -> str:
    """生成稳定的论文唯一 ID。优先使用 arXiv ID，fallback 用标题 hash。"""
    arxiv_id = paper.get("id") or paper.get("arxiv_id") or ""
    if arxiv_id:
        # 去掉版本号后缀
        arxiv_id = re.sub(r"v\d+$", "", arxiv_id.strip())
        return f"arxiv_{arxiv_id}"
    title_hash = _normalize_title(paper.get("title", ""))
    return f"title_{title_hash}"


def normalize_title(title: str) -> str:
    """标题归一化，用于去重 hash。"""
    t = title.lower().strip()
    t = re.sub(r"[^a-z0-9\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return hashlib.md5(t.encode("utf-8")).hexdigest()[:16]


_normalize_title = normalize_title  # internal alias


def merge_papers_into_history(
    papers: list[dict],
    watch_item: dict,
    history: dict,
) -> tuple[dict, list[dict]]:
    """将本次获取的论文合并进历史。返回 (updated_history, new_papers)。"""
    return _merge_papers_into_history(papers, watch_item, history)


def is_new_paper(paper: dict, history: dict | None = None) -> bool:
    """判断论文是否在历史中不存在。"""
    if history is None:
        history = load_paper_history()
    pid = normalize_paper_id(paper)
    return pid not in history.get("papers", {})


# ═══════════════════════════════════════════════════════════
# 刷新
# ═══════════════════════════════════════════════════════════

def refresh_watch_item(watch_item: dict, history: dict | None = None) -> dict:
    """
    刷新单个关注领域，返回刷新结果。
    刷新前会将本领域历史论文的 is_new 重置为 False。
    """
    if history is None:
        history = load_paper_history()

    now = datetime.now(timezone.utc).isoformat()
    wid = watch_item.get("id", "?")
    result = {
        "watch_id": wid,
        "success": False,
        "message": "",
        "fetched_count": 0,
        "new_count": 0,
        "new_papers": [],
        "all_papers": [],
        "checked_at": now,
    }

    query = watch_item.get("query", "").strip()
    if not query:
        result["message"] = "搜索关键词为空，请先设置关注领域的 query。"
        return result

    # 刷新前：重置本领域历史论文的 is_new，避免旧的新论文提示一直残留。
    _reset_is_new_for_watch_item(wid, history)

    max_results = watch_item.get("max_results", 20)
    categories = watch_item.get("categories", [])

    # 调用现有 arXiv 搜索（直接传 categories，不二次包装），追踪默认仍是前沿追踪逻辑。
    search_result = _search_arxiv(
        query,
        max_results=max_results,
        categories=categories if categories else None,
        sort_by="submittedDate",
    )
    papers = search_result.get("papers", [])
    error = search_result.get("error")

    if error:
        result["message"] = error
        return result

    if not papers:
        result["success"] = True
        result["message"] = "未找到新论文。"
        # 仍然更新时间戳
        _update_watch_last_checked(watch_item["id"], now)
        return result

    result["fetched_count"] = len(papers)

    # 评分（复用 ranker）。评分失败不影响论文入库，避免排序模块问题阻塞追踪刷新。
    try:
        papers = _rank_papers(papers, query, top_k=None)
    except Exception:
        pass  # 评分失败不阻塞

    # 合并进历史 & 标记新论文；这里保留已有阅读状态，避免刷新覆盖用户操作。
    history, new_papers = _merge_papers_into_history(papers, watch_item, history)
    save_paper_history(history)

    result["success"] = True
    result["new_count"] = len(new_papers)
    result["new_papers"] = new_papers
    result["all_papers"] = papers
    result["message"] = (
        f"获取 {len(papers)} 篇论文，其中 {len(new_papers)} 篇为新发现。"
    )

    # 更新 watch item 的 last_checked_at
    _update_watch_last_checked(watch_item["id"], now)

    # 更新 tracker state
    _update_tracker_state_after_refresh(result)

    return result


def refresh_all_watch_items(
    watchlist: list[dict] | None = None,
    history: dict | None = None,
) -> dict:
    """刷新所有 enabled=True 的关注领域。"""
    if watchlist is None:
        watchlist = load_watchlist()
    if history is None:
        history = load_paper_history()
    enabled = [w for w in watchlist if w.get("enabled", True)]

    if not enabled:
        msg = "当前没有启用的关注领域，请先启用至少一个领域。"
        return {
            "results": [],
            "total_fetched": 0,
            "total_new": 0,
            "error_count": 0,
            "message": msg,
            "refreshed_at": datetime.now(timezone.utc).isoformat(),
        }

    all_results = []
    total_fetched = 0
    total_new = 0
    error_count = 0
    all_new_ids = set()

    # 逐个领域刷新，同一篇论文可能来自多个关注领域，后续合并时会保留来源列表。
    for w in enabled:
        r = refresh_watch_item(w, history)
        all_results.append(r)
        total_fetched += r["fetched_count"]
        total_new += r["new_count"]
        if not r["success"]:
            error_count += 1
        # 累加每个领域的新论文 ID，供 UI 显示“最近新发现”。
        for p in r.get("new_papers", []):
            all_new_ids.add(normalize_paper_id(p))

    summary = {
        "results": all_results,
        "total_fetched": total_fetched,
        "total_new": total_new,
        "error_count": error_count,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
    }

    state = load_tracker_state()
    state["last_refresh_at"] = summary["refreshed_at"]
    state["last_refresh_summary"] = {
        "enabled_watch_count": len(enabled),
        "fetched_total": total_fetched,
        "new_total": total_new,
        "error_count": error_count,
    }
    state["recent_new_paper_ids"] = list(all_new_ids)  # 累积所有领域的新 ID
    save_tracker_state(state)

    return summary


# ═══════════════════════════════════════════════════════════
# 论文状态
# ═══════════════════════════════════════════════════════════

def update_paper_status(
    paper_id: str,
    status: str,
    history: dict | None = None,
) -> dict:
    """更新论文状态。只允许 unread/reading/read/starred/ignored。返回更新后的 history。"""
    if history is None:
        history = load_paper_history()
    if status not in VALID_STATUSES:
        return history
    papers = history.get("papers", {})
    if paper_id in papers:
        papers[paper_id]["status"] = status
        papers[paper_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_paper_history(history)
    return history


def get_papers_by_watch_item(
    watch_item_id: str,
    history: dict | None = None,
) -> list[dict]:
    """按关注领域获取历史论文。"""
    if history is None:
        history = load_paper_history()
    return [
        p for p in history.get("papers", {}).values()
        if watch_item_id in p.get("source_watch_ids", [])
    ]


def filter_papers(
    history: dict,
    watch_item_id: str | None = None,
    status: str | None = None,
    only_new: bool = False,
    keyword: str | None = None,
) -> list[dict]:
    """根据领域、状态、新论文、关键词筛选论文。"""
    return filter_tracked_papers(
        history=history,
        watch_item_id=watch_item_id,
        status=status,
        only_new=only_new,
        keyword=keyword,
    )


# alias for backward compatibility
refresh_all_enabled_watch_items = refresh_all_watch_items


# ═══════════════════════════════════════════════════════════
# 筛选与排序
# ═══════════════════════════════════════════════════════════

def filter_tracked_papers(
    history: dict | None = None,
    watch_item_id: str | None = None,
    status: str | None = None,
    only_new: bool = False,
    keyword: str | None = None,
) -> list[dict]:
    """根据领域/状态/新论文/关键词筛选追踪论文。"""
    if history is None:
        history = load_paper_history()

    papers = list(history.get("papers", {}).values())

    if watch_item_id:
        papers = [
            p for p in papers
            if watch_item_id in p.get("source_watch_ids", [])
        ]

    if status and status in VALID_STATUSES:
        papers = [p for p in papers if p.get("status") == status]

    if only_new:
        # 优先使用 tracker_state 中记录的最近一次刷新新论文 ID
        state = load_tracker_state()
        recent_ids = set(state.get("recent_new_paper_ids", []))
        if recent_ids:
            papers = [p for p in papers if p.get("paper_id") in recent_ids]
        else:
            papers = [p for p in papers if p.get("is_new", False)]

    if keyword:
        kw = keyword.lower()
        filtered = []
        for p in papers:
            # 标题
            if kw in (p.get("title") or "").lower():
                filtered.append(p)
                continue
            # 摘要
            if kw in (p.get("summary") or "").lower():
                filtered.append(p)
                continue
            # 作者（list → join）
            authors = p.get("authors") or []
            if isinstance(authors, list):
                authors_str = " ".join(authors).lower()
            else:
                authors_str = str(authors).lower()
            if kw in authors_str:
                filtered.append(p)
                continue
            # 来源领域
            sources = p.get("source_watch_names") or []
            if isinstance(sources, list):
                sources_str = " ".join(sources).lower()
            else:
                sources_str = str(sources).lower()
            if kw in sources_str:
                filtered.append(p)
                continue
        papers = filtered

    return papers


def sort_tracked_papers(papers: list[dict], sort_mode: str = "score_desc") -> list[dict]:
    """排序追踪论文。"""
    if sort_mode == "score_desc":
        return sorted(papers, key=lambda p: p.get("score", 0), reverse=True)
    elif sort_mode == "date_desc":
        return sorted(papers, key=lambda p: p.get("published", ""), reverse=True)
    elif sort_mode == "date_asc":
        return sorted(papers, key=lambda p: p.get("published", ""))
    elif sort_mode == "title_asc":
        return sorted(papers, key=lambda p: p.get("title", "").lower())
    return papers


# ═══════════════════════════════════════════════════════════
# 追踪摘要（供笔记用）
# ═══════════════════════════════════════════════════════════

def build_tracker_summary(
    watchlist: list[dict] | None = None,
    history: dict | None = None,
    limit: int = 5,
) -> dict | None:
    """
    构建追踪摘要。无数据时返回 None。

    返回:
        {
            "watchlist": [...],
            "top_papers": [...],
            "total_papers": int,
            "last_refresh": str,
            "recent_new_count": int,
            "recent_new_paper_ids": [...],
            "recent_new_papers": [...],
        }
    """
    if watchlist is None:
        watchlist = load_watchlist()
    if history is None:
        history = load_paper_history()

    state = load_tracker_state()
    enabled = [w for w in watchlist if w.get("enabled", True)]
    papers = list(history.get("papers", {}).values())

    # 完全没有 watchlist 且没有历史论文时才返回 None
    if not watchlist and not papers:
        return None
    if not enabled and not papers:
        # 有 watchlist 但全部停用，且无历史：仍返回摘要让 UI 显示"暂无追踪记录"
        return {
            "watchlist": enabled,
            "top_papers": [],
            "total_papers": 0,
            "last_refresh": state.get("last_refresh_at"),
            "recent_new_count": 0,
            "recent_new_paper_ids": [],
            "recent_new_papers": [],
        }
    top_papers = sorted(papers, key=lambda p: p.get("score", 0), reverse=True)[:limit]

    # 最近新发现论文
    recent_ids = state.get("recent_new_paper_ids", [])
    recent_new_papers = [
        p for p in papers
        if p.get("paper_id") in recent_ids
    ]

    return {
        "watchlist": enabled,
        "top_papers": top_papers,
        "total_papers": len(papers),
        "last_refresh": state.get("last_refresh_at"),
        "recent_new_count": len(recent_ids),
        "recent_new_paper_ids": recent_ids,
        "recent_new_papers": recent_new_papers,
    }


# ═══════════════════════════════════════════════════════════
# 内部辅助
# ═══════════════════════════════════════════════════════════

def _merge_papers_into_history(
    papers: list[dict],
    watch_item: dict,
    history: dict,
) -> tuple[dict, list[dict]]:
    """将论文合并进历史，返回 (updated_history, new_papers)。"""
    hist_papers = history.get("papers", {})
    new_papers = []
    now = datetime.now(timezone.utc).isoformat()

    # 将 ranker 的字段映射到历史格式，让追踪列表可以脱离当前搜索结果独立展示。
    for p in papers:
        pid = normalize_paper_id(p)
        is_new = pid not in hist_papers

        entry = {
            "paper_id": pid,
            "arxiv_id": p.get("id", ""),
            "title": p.get("title", ""),
            "authors": p.get("authors", []),
            "summary": p.get("abstract", ""),
            "published": p.get("published", ""),
            "updated": now,
            "categories": p.get("categories", []),
            "primary_category": p.get("primary_category", ""),
            "arxiv_url": p.get("arxiv_url", ""),
            "pdf_url": p.get("pdf_url", ""),
            "score": p.get("score_total", 0),
            "score_breakdown": {
                "relevance": p.get("score_relevance", 0),
                "contribution": p.get("score_contribution", 0),
                "method_clarity": p.get("score_method_clarity", 0),
                "evidence": p.get("score_evidence", 0),
                "freshness": p.get("score_freshness", 0),
                "readability": p.get("score_readability", 0),
            },
            "rank_reason": p.get("recommendation_reason", ""),
            "recommendation_level": p.get("recommendation_level", ""),
            "is_new": is_new,
            "status": "unread",
        }

        # 来源追踪
        wid = watch_item.get("id", "")
        if pid in hist_papers:
            # 已存在：追加来源，保留已有 status/read/starred 等人工状态。
            existing = hist_papers[pid]
            entry["status"] = existing.get("status", "unread")
            entry["first_seen_at"] = existing.get("first_seen_at", now)
            entry["last_seen_at"] = now
            sources = set(existing.get("source_watch_ids", []))
            sources.add(wid)
            entry["source_watch_ids"] = list(sources)
            source_names = list(existing.get("source_watch_names", []))
            if watch_item.get("name") and watch_item["name"] not in source_names:
                source_names.append(watch_item["name"])
            entry["source_watch_names"] = source_names
        else:
            entry["source_watch_ids"] = [wid]
            entry["source_watch_names"] = [watch_item.get("name", "")]
            entry["first_seen_at"] = now
            entry["last_seen_at"] = now
            new_papers.append(entry)

        hist_papers[pid] = entry

    history["papers"] = hist_papers
    return history, new_papers


def _update_watch_last_checked(watch_id: str, timestamp: str) -> None:
    """更新 watch item 的 last_checked_at。"""
    watchlist = load_watchlist()
    for i, w in enumerate(watchlist):
        if w.get("id") == watch_id:
            watchlist[i]["last_checked_at"] = timestamp
            break
    save_watchlist(watchlist)


def _reset_is_new_for_watch_item(watch_id: str, history: dict) -> None:
    """刷新前：将指定领域所有历史论文的 is_new 重置为 False。"""
    for pid, p in history.get("papers", {}).items():
        if watch_id in p.get("source_watch_ids", []):
            p["is_new"] = False


def _update_tracker_state_after_refresh(result: dict, accumulate: bool = False) -> None:
    """刷新后更新 tracker_state。accumulate=True 时累加多个领域的new IDs。"""
    # tracker_state 只保存最近刷新摘要，不保存完整论文，完整数据仍在 paper_history。
    state = load_tracker_state()
    state["last_refresh_at"] = result.get("checked_at")
    new_ids = [normalize_paper_id(p) for p in result.get("new_papers", [])]
    if accumulate:
        existing = set(state.get("recent_new_paper_ids", []))
        existing.update(new_ids)
        state["recent_new_paper_ids"] = list(existing)
    else:
        state["recent_new_paper_ids"] = new_ids
    save_tracker_state(state)
