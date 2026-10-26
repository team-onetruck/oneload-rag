"""한길 R3 RAG — R2 Agent 의 search_knowledge 도구 (oneload_agent hangil_r2/knowledge.py KnowledgeSearch).

백엔드 연결 (oneload-backend app/main.py production_ai() 가 이렇게 쓴다. Vision 은 Agent 와 create_app 양쪽에):
    from hangil_rag import search_knowledge
    vision = LLMVision(llm)
    agent = LLMAgent(llm, search_knowledge=search_knowledge, vision=vision, fallback=RuleAgent())
    app = create_app(agent=agent, vision=vision)

RAG_BACKEND=pgvector 이면 pgvector 하이브리드 검색, 아니면 DB 없는 메모리 키워드 검색(기본).
검색기는 프로세스마다 한 번 만들어 재사용한다 (_default 캐시). 문서를 고치면 프로세스를 다시 띄운다.
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
