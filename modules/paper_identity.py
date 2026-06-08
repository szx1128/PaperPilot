"""
PaperPilot 论文唯一标识模块。

为论文生成稳定的唯一 ID，供 app.py、summarizer、reviewer、note_generator
等模块统一使用。同一篇论文在不同页面/时间生成的 ID 必须稳定，
不能因为排序或列表位置变化而改变。
"""

import hashlib


def get_paper_id(paper: dict | None) -> str:
    """
    生成稳定的论文唯一 ID。

    优先级：
    1. arxiv_id（如 "2401.12345"）
    2. entry_id / id
    3. paper_id（追踪历史使用）
    4. arXiv URL 的最后部分
    5. title + first_author + published 的 hash
    6. "manual_pdf"（paper 为空时）

    参数:
        paper: 论文信息 dict，可为 None

    返回:
        稳定唯一 ID 字符串
    """
    if not paper:
        return "manual_pdf"

    # 0. manual_pdf — 手动上传 PDF 没有 arXiv 元数据，必须使用固定 ID 做状态绑定。
    pid_val = paper.get("paper_id") or ""
    if pid_val == "manual_pdf":
        return "manual_pdf"

    # 1. paper_id（追踪历史格式）优先保留，避免历史状态、笔记和阅读状态断开。
    if pid_val and str(pid_val).startswith("arxiv_"):
        return str(pid_val)

    # 2. arxiv_id 是最稳定的论文标识；去掉 v2/v3 可把同一论文不同版本合并。
    arxiv_id = paper.get("arxiv_id") or paper.get("id") or ""
    if arxiv_id:
        # 去掉版本号
        import re
        clean = re.sub(r"v\d+$", "", arxiv_id.strip())
        if clean:
            return f"arxiv_{clean}"

    # 3. arXiv URL
    url = paper.get("arxiv_url") or paper.get("entry_id") or ""
    if url and "arxiv.org/abs/" in url:
        import re
        m = re.search(r"arxiv\.org/abs/([^/\s]+)", url)
        if m:
            return f"arxiv_{m.group(1)}"

    # 4. title + authors + published hash 是最后兜底，用于没有 arXiv ID 的外部/手动论文。
    title = (paper.get("title") or "").strip().lower()
    authors = paper.get("authors") or []
    first_author = authors[0] if authors else ""
    published = paper.get("published") or ""

    if title:
        raw = f"{title}|{first_author}|{published}"
        h = hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]
        return f"hash_{h}"

    return "unknown"


def get_paper_id_short(paper: dict | None) -> str:
    """返回短 ID（最后 8 位），用于 UI 显示。"""
    full = get_paper_id(paper)
    return full[-8:] if len(full) > 8 else full
