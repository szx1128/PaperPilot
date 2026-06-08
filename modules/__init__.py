"""
PaperPilot 核心模块包。

模块列表：
- arxiv_client: 论文发现（arXiv API 封装）
- ranker:       论文排序（多维打分）
- pdf_parser:   PDF 解析（文本提取与分段）
- summarizer:   结构化总结（LLM + 模板 fallback）
- qa_engine:    论文问答（LLM + 关键词检索 fallback）
- note_generator: 笔记生成（Markdown 组装）
- llm_client:   LLM 统一调用（API 封装 + fallback 判断）
- utils:        公共工具函数
"""

__version__ = "0.1.0"
