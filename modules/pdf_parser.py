"""
PaperPilot PDF 解析模块。

使用 pypdf 从 Streamlit uploaded_file 中提取文本。
支持页码标记、基本文本清洗、错误降级处理。
不引入 OCR 或复杂依赖。

依赖：
- pypdf.PdfReader
"""

from io import BytesIO

from pypdf import PdfReader
from pypdf.errors import PdfReadError


# ── 常量 ──────────────────────────────────────────────────

# 文本预览最大字符数（页面展示用）
PREVIEW_MAX_CHARS = 1500

# 最小有效文本字符数（低于此值视为无文字层）
MIN_VALID_CHARS = 50


# ── 公共函数 ──────────────────────────────────────────────

def extract_text_from_pdf(uploaded_file) -> dict:
    """
    从 Streamlit uploaded_file 中提取 PDF 文本。

    参数:
        uploaded_file: Streamlit st.file_uploader 返回的 UploadedFile 对象

    返回:
        {
            "success":     bool  — 是否成功提取
            "filename":    str   — 原始文件名
            "page_count":  int   — 总页数
            "text":        str   — 提取的完整文本（含页码标记）
            "char_count":  int   — 文本总字符数
            "error":       str | None — 错误信息（成功时为 None）
        }
    """
    filename = getattr(uploaded_file, "name", "unknown.pdf")

    try:
        # Streamlit 的 UploadedFile 可能被前面的预览/解析读过，这里先归位再读，
        # 保证用户重复点击解析或切换页面回来时不会读到空内容。
        try:
            uploaded_file.seek(0)
        except (AttributeError, OSError):
            pass
        try:
            file_bytes = uploaded_file.getvalue()
        except AttributeError:
            file_bytes = uploaded_file.read()
        pdf_stream = BytesIO(file_bytes)
        reader = PdfReader(pdf_stream)

        page_count = len(reader.pages)
        if page_count == 0:
            return _make_error(filename, 0, "PDF 文件为空，没有可读取的页面。")

        # 逐页提取文本，并插入页码标记；后续 QA 引用片段时会复用这些标记。
        pages_text = []
        for i, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages_text.append(f"===== Page {i} =====")
                    pages_text.append(page_text.strip())
            except Exception as e:
                # 单页提取失败不中断，继续处理后续页面
                print(f"[pdf_parser] 第 {i} 页提取失败: {e}")
                continue

        if not pages_text:
            return _make_error(
                filename,
                page_count,
                "未能从 PDF 中提取到有效文本，可能是扫描版 PDF。当前版本暂不支持 OCR，"
                "请使用包含文字层的 PDF 文件。",
            )

        full_text = "\n\n".join(pages_text)

        # 基本清洗只处理 PDF 抽取常见噪声，不做 OCR 或语义改写，避免改变论文原意。
        full_text = _clean_text(full_text)

        char_count = len(full_text)
        if char_count < MIN_VALID_CHARS:
            return _make_error(
                filename,
                page_count,
                f"PDF 仅提取到 {char_count} 个字符，文本量过少，"
                "可能是扫描版 PDF 或图片型 PDF。当前版本暂不支持 OCR。",
            )

        return {
            "success": True,
            "filename": filename,
            "page_count": page_count,
            "text": full_text,
            "char_count": char_count,
            "error": None,
        }

    except PdfReadError as e:
        return _make_error(filename, 0, f"PDF 文件无法读取（可能已损坏或加密）: {e}")
    except Exception as e:
        print(f"[pdf_parser] 未知解析错误: {e}")
        return _make_error(filename, 0, f"PDF 解析时发生未知错误: {e}")


def get_text_preview(text: str, max_chars: int = PREVIEW_MAX_CHARS) -> str:
    """
    获取文本的前 N 字符预览。

    参数:
        text:     完整文本
        max_chars: 预览字符数，默认 1500

    返回:
        截断后的文本，末尾附加省略提示
    """
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"\n\n... (共 {len(text)} 字符，已截断显示前 {max_chars} 字符)"


# ── 内部辅助 ──────────────────────────────────────────────

def _clean_text(text: str) -> str:
    """
    清洗 PDF 提取文本。

    - 去除空字符（\\x00）
    - 合并 3 个以上的连续空行为 2 行
    - 去除首尾空白
    """
    if not text:
        return ""

    # 去除空字符
    text = text.replace("\x00", "")

    # 合并过多空行：将 3+ 个连续换行替换为 2 个换行
    import re
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 去除首尾空白
    text = text.strip()

    return text


def split_text_into_chunks(
    text: str,
    max_chars: int = 1200,
    overlap: int = 150,
) -> list[dict]:
    """
    将文本按段落切分为带 overlap 的 chunks。

    先按段落（双换行）切分，过长段落再按句子切分。
    每个 chunk 包含 start_char/end_char 便于定位。

    参数:
        text:      待切分文本
        max_chars: 每个 chunk 最大字符数
        overlap:   相邻 chunk 的重叠字符数

    返回:
        [{"chunk_id": "chunk_0", "text": "...", "start_char": 0, "end_char": 1200, "length": 1200}, ...]
    """
    if not text:
        return []

    import re

    # 先按双换行切分，尽量保持论文段落语义完整。
    paragraphs = re.split(r"\n\s*\n", text.strip())
    chunks = []
    current = ""
    current_start = 0
    pos = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # 段落不长 → 尝试合并
        if len(current) + len(para) + 2 <= max_chars:
            if current:
                current += "\n\n" + para
            else:
                current = para
                current_start = text.index(para, pos)
            pos = current_start + len(current)
        else:
            # 当前块已满 → 先保存
            if current:
                chunks.append({
                    "chunk_id": f"chunk_{len(chunks)}",
                    "text": current,
                    "start_char": current_start,
                    "end_char": current_start + len(current),
                    "length": len(current),
                })
                # 新块带 overlap，避免一个关键句刚好落在两个 chunk 边界时被问答检索漏掉。
                overlap_text = current[-overlap:] if len(current) > overlap else ""
                current = overlap_text + para if overlap_text else para
                # 重新定位
                para_start = text.index(para, pos) if para in text else pos
                current_start = para_start - len(overlap_text) if overlap_text else para_start
                pos = para_start + len(para)
            else:
                # 当前块为空但段落太长，按句子切分；这是对长公式/长段落 PDF 的兜底策略。
                sentences = re.split(r"(?<=[.!?])\s+", para)
                for sent in sentences:
                    if len(current) + len(sent) + 1 <= max_chars:
                        current = (current + " " + sent).strip() if current else sent
                    else:
                        if current:
                            chunks.append({
                                "chunk_id": f"chunk_{len(chunks)}",
                                "text": current,
                                "start_char": current_start,
                                "end_char": current_start + len(current),
                                "length": len(current),
                            })
                        current = sent
                        # 粗略定位
                        try:
                            current_start = text.index(sent, pos)
                        except ValueError:
                            current_start = pos
                        pos = current_start + len(sent)

    # 最后一块
    if current:
        chunks.append({
            "chunk_id": f"chunk_{len(chunks)}",
            "text": current,
            "start_char": current_start,
            "end_char": current_start + len(current),
            "length": len(current),
        })

    return chunks


def _make_error(filename: str, page_count: int, error_msg: str) -> dict:
    """构造错误返回结果。"""
    return {
        "success": False,
        "filename": filename,
        "page_count": page_count,
        "text": "",
        "char_count": 0,
        "error": error_msg,
    }
