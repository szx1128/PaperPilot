"""
PaperPilot 公共工具函数模块。

提供跨模块使用的纯函数，包括：
- 文本清洗（去 HTML 标签、归一化空白）
- 分数归一化（0-100）
- 时间衰减计算
- 缓存读写（JSON 文件）
"""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── 路径工具 ──────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
PAPERS_JSON = DATA_DIR / "papers.json"


def ensure_data_dir() -> None:
    """确保 data 目录及其子目录存在。"""
    # 所有本地生成物集中放在 data 下，避免散落到项目根目录。
    (DATA_DIR / "notes").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)


# ── 文本清洗 ──────────────────────────────────────────────

def clean_text(text: str) -> str:
    """清洗文本：去除多余空白、统一换行。"""
    if not text:
        return ""
    # 去除 HTML 标签，arXiv Atom 摘要中偶尔会带简单标记。
    text = re.sub(r"<[^>]*>", "", text)
    # 将多个空白字符（包括换行）替换为单个空格
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def clean_abstract(text: str) -> str:
    """专门清洗 arXiv 摘要文本。"""
    # 去除 "Abstract:" 或 "Summary:" 前缀
    text = re.sub(r"^(Abstract|Summary)\s*[:：]\s*", "", text.strip(), flags=re.IGNORECASE)
    return clean_text(text)


# ── 分数归一化 ────────────────────────────────────────────

def normalize_score(value: float, min_val: float, max_val: float) -> float:
    """将值归一化到 0-1 区间。"""
    if max_val == min_val:
        # 没有区分度时返回中性值，避免除零，也避免偏向最高或最低。
        return 0.5
    return (value - min_val) / (max_val - min_val)


def scale_to_100(value: float, min_val: float, max_val: float) -> float:
    """将值归一化到 0-100 区间。"""
    return round(normalize_score(value, min_val, max_val) * 100, 1)


# ── 时间衰减 ──────────────────────────────────────────────

def compute_recency_weight(published_date: str, current_date: datetime | None = None) -> float:
    """
    根据发布时间计算新鲜度权重。

    使用指数衰减：越新的论文权重越高。
    衰减半衰期约为 180 天（~6 个月）。

    参数:
        published_date: 格式 "YYYY-MM-DD" 的日期字符串
        current_date: 当前日期，默认为现在

    返回:
        0-1 之间的新鲜度权重
    """
    if current_date is None:
        current_date = datetime.now(timezone.utc)

    try:
        pub_date = datetime.strptime(published_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return 0.5  # 无法解析时返回中性值

    days_diff = (current_date - pub_date).days
    if days_diff < 0:
        days_diff = 0

    # 指数衰减：半衰期 180 天，用于“前沿追踪”中的新鲜度启发式。
    half_life = 180.0
    weight = 2 ** (-days_diff / half_life)
    return round(weight, 4)


# ── 关键词匹配 ────────────────────────────────────────────

def count_keyword_hits(text: str, keywords: list[str]) -> int:
    """
    统计关键词在文本中的命中次数（大小写不敏感）。

    参数:
        text: 待搜索文本
        keywords: 关键词列表

    返回:
        命中总次数
    """
    if not text or not keywords:
        return 0
    text_lower = text.lower()
    count = 0
    for kw in keywords:
        # 简单 substring 匹配足够轻量；更严格的词边界由具体业务模块自行处理。
        count += text_lower.count(kw.lower())
    return count


def extract_keywords(keyword_string: str) -> list[str]:
    """
    从用户输入的关键词字符串中提取关键词列表。

    支持逗号、顿号、分号、空格分隔。

    参数:
        keyword_string: 用户输入的关键词字符串

    返回:
        关键词列表（已去重去空白）
    """
    if not keyword_string:
        return []
    # 按多种中英文分隔符拆分，适配用户输入中文顿号、逗号或空格。
    parts = re.split(r"[,，、;；\s]+", keyword_string.strip())
    return [p.strip() for p in parts if p.strip()]


# ── JSON 缓存 ─────────────────────────────────────────────

def load_papers_cache() -> list[dict[str, Any]]:
    """从本地 JSON 文件加载缓存的论文数据。"""
    if not PAPERS_JSON.exists():
        return []
    try:
        with open(PAPERS_JSON, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        # 缓存损坏时直接丢弃，不影响实时 arXiv 搜索和核心页面启动。
        return []


def save_papers_cache(papers: list[dict[str, Any]]) -> None:
    """将论文列表保存到本地 JSON 文件。"""
    ensure_data_dir()
    try:
        with open(PAPERS_JSON, "w", encoding="utf-8") as f:
            json.dump(papers, f, ensure_ascii=False, indent=2)
    except OSError:
        pass  # 写入失败不应阻塞流程
