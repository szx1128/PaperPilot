"""
PaperPilot 追踪数据持久化模块。

负责本地 JSON 文件的读写，不负责 UI 和业务逻辑。
所有读写操作均有容错：文件不存在/为空/损坏时返回默认值，不崩溃。

数据文件：
- data/watchlist.json      关注领域列表
- data/paper_history.json  论文历史记录
- data/tracker_state.json  追踪状态与统计
"""

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ── 路径 ──────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent.parent / "data"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
PAPER_HISTORY_PATH = DATA_DIR / "paper_history.json"
TRACKER_STATE_PATH = DATA_DIR / "tracker_state.json"


# ── 目录 ──────────────────────────────────────────────────

def ensure_data_dir() -> None:
    """确保 data 目录及子目录存在。"""
    # 追踪、笔记、上传文件都写入 data 下，启动时统一创建可减少后续保存失败。
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "notes").mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "uploads").mkdir(parents=True, exist_ok=True)


# ── Safety helpers ────────────────────────────────────────

def _backup_json_file(path: Path) -> None:
    """写入前备份旧文件，防止数据损坏。"""
    # JSON 是演示阶段的轻量持久化方案；写前备份可以在异常退出时保住上一版数据。
    if path.exists() and path.stat().st_size > 0:
        backup = path.with_suffix(".backup.json")
        try:
            shutil.copy2(path, backup)
        except OSError:
            pass


def safe_read_json(path: Path, default: Any) -> Any:
    """安全读取 JSON。文件不存在/为空/损坏时返回 default。"""
    # 读失败返回默认结构，不让损坏的本地数据拖垮整个 Streamlit 页面。
    if not path.exists():
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if data is not None else default
    except (json.JSONDecodeError, OSError):
        return default


def safe_write_json(path: Path, data: Any) -> bool:
    """安全写入 JSON。失败返回 False，不抛异常。"""
    # 写失败只返回 False，由上层决定是否提示；底层保持无 UI 依赖。
    ensure_data_dir()
    try:
        _backup_json_file(path)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except OSError as e:
        print(f"[tracker_store] 写入 {path} 失败: {e}")
        return False


# ── Watchlist ─────────────────────────────────────────────

def load_watchlist() -> list[dict]:
    """读取关注领域列表。文件不存在时返回空列表。"""
    return safe_read_json(WATCHLIST_PATH, [])


def save_watchlist(watchlist: list[dict]) -> bool:
    """保存关注领域列表。成功返回 True，失败返回 False。"""
    return safe_write_json(WATCHLIST_PATH, watchlist)


# ── Paper History ─────────────────────────────────────────

def load_paper_history() -> dict:
    """读取论文历史记录。"""
    default = {"papers": {}, "updated_at": ""}
    data = safe_read_json(PAPER_HISTORY_PATH, default)
    if not isinstance(data, dict):
        return default
    if "papers" not in data:
        data["papers"] = {}
    if "updated_at" not in data:
        data["updated_at"] = ""
    return data


def save_paper_history(history: dict) -> bool:
    """保存论文历史记录。"""
    history["updated_at"] = datetime.now(timezone.utc).isoformat()
    return safe_write_json(PAPER_HISTORY_PATH, history)


# ── Tracker State ─────────────────────────────────────────

def load_tracker_state() -> dict:
    """读取追踪状态。"""
    default = {
        "last_refresh_at": "",
        "last_refresh_summary": {
            "enabled_watch_count": 0,
            "fetched_total": 0,
            "new_total": 0,
            "error_count": 0,
        },
        "recent_new_paper_ids": [],
    }
    data = safe_read_json(TRACKER_STATE_PATH, default)
    # 兼容旧格式：早期版本可能没有 summary 或 recent_new_paper_ids 字段。
    if not isinstance(data, dict):
        return default
    if "last_refresh_summary" not in data or data["last_refresh_summary"] is None:
        data["last_refresh_summary"] = default["last_refresh_summary"]
    if "recent_new_paper_ids" not in data:
        data["recent_new_paper_ids"] = []
    return data


def save_tracker_state(state: dict) -> bool:
    """保存追踪状态。"""
    return safe_write_json(TRACKER_STATE_PATH, state)


# ── Convenience ──────────────────────────────────────────

def load_all() -> tuple[list[dict], dict, dict]:
    """一次性加载所有追踪数据。"""
    return load_watchlist(), load_paper_history(), load_tracker_state()
