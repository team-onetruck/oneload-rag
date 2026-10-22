"""한길 R3 RAG — R2 Agent 의 search_knowledge 도구 (oneload_agent hangil_r2/knowledge.py KnowledgeSearch).

백엔드 연결 예 (MockKnowledgeSearch 자리):
    from hangil_rag import search_knowledge
    agent = LLMAgent(llm, search_knowledge=search_knowledge, fallback=RuleAgent())

RAG_BACKEND=pgvector 이면 pgvector 하이브리드 검색, 아니면 DB 없는 메모리 키워드 검색.
"""

from __future__ import annotations

import os
from functools import cache

from .schemas import KnowledgeHit, SearchUnavailable
from .search_memory import MemorySearch


def search_knowledge(query: str, language: str, context: dict) -> list[KnowledgeHit]:
    return _default()(query, language, context)


@cache
def _default():
    if os.environ.get("RAG_BACKEND", "memory") == "pgvector":
        from .search_pgvector import PgVectorSearch

        return PgVectorSearch()
    return MemorySearch()


__all__ = ["KnowledgeHit", "MemorySearch", "SearchUnavailable", "search_knowledge"]
