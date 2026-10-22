"""R2 Agent 와의 계약 (oneload_agent hangil_r2/knowledge.py 와 같은 모양).

- KnowledgeHit : Agent KnowledgeHit 과 같은 필드 · 타입. scope 는 Agent 에서 None 허용이지만 여기서는 항상 채운다.
- SearchUnavailable : 검색 저장소 장애. Agent 는 자기 ToolUnavailable 만 잡으므로 (agent.py _search),
  Agent 가 같은 프로세스에 있으면 그 클래스도 상속한 예외를 던진다. 고르는 시점은 던지는 순간
  (hangil_r2/compat.py 와 같은 규칙: import 순서에 따라 결과가 달라지지 않게).
"""

from __future__ import annotations

from functools import cache

from pydantic import BaseModel


class KnowledgeHit(BaseModel):
    document_id: str
    title: str
    excerpt: str
    source_url: str | None = None
    verified_at: str
    scope: str


class SearchUnavailable(RuntimeError):
    """검색 저장소(DB · 임베딩 API) 장애. Agent 는 이 예외를 받으면 cannot_answer 로 보류한다."""


def unavailable(message: str) -> SearchUnavailable:
    """던질 예외. hangil_r2 가 import 되면 SearchUnavailable 이면서 ToolUnavailable 인 예외."""
    try:
        from hangil_r2.knowledge import ToolUnavailable  # Agent 와 같은 프로세스에서만 존재
    except ImportError:
        return SearchUnavailable(message)
    # 이름만 같은 다른 패키지일 수도 있으니 예외 클래스인지 확인
    if not (isinstance(ToolUnavailable, type) and issubclass(ToolUnavailable, Exception)):
        return SearchUnavailable(message)
    return _with_agent_base(ToolUnavailable)(message)


@cache
def _with_agent_base(base: type[Exception]) -> type[SearchUnavailable]:
    return type("SearchUnavailable", (SearchUnavailable, base), {"__module__": __name__})
