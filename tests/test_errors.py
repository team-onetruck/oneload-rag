"""검색 장애 → 예외 (Agent 가 cannot_answer 로 보류). Agent 가 없어도 · 있어도 맞는 클래스."""

import sys
import types

import pytest

from hangil_rag.schemas import SearchUnavailable, unavailable


def test_without_agent_it_is_plain_search_unavailable(monkeypatch):
    monkeypatch.setitem(sys.modules, "hangil_r2.knowledge", None)  # import 하면 ImportError
    exc = unavailable("down")
    assert type(exc) is SearchUnavailable and isinstance(exc, RuntimeError)


def test_with_agent_it_is_also_tool_unavailable(monkeypatch):
    fake = types.ModuleType("hangil_r2.knowledge")

    class ToolUnavailable(RuntimeError):
        pass

    fake.ToolUnavailable = ToolUnavailable
    monkeypatch.setitem(sys.modules, "hangil_r2.knowledge", fake)
    with pytest.raises(ToolUnavailable) as info:  # Agent 의 except ToolUnavailable 에 잡힘
        raise unavailable("down")
    assert isinstance(info.value, SearchUnavailable) and str(info.value) == "down"


def test_pgvector_errors_become_search_unavailable():
    pytest.importorskip("psycopg")
    from hangil_rag.search_pgvector import PgVectorSearch

    class Broken:
        dim = 3

        def embed(self, texts):
            raise TimeoutError("embedding api timeout")

    class Ok:
        dim = 3

        def embed(self, texts):
            return [[1.0, 0.0, 0.0]]

    with pytest.raises(SearchUnavailable, match="embedding"):
        PgVectorSearch(dsn="postgresql://x@127.0.0.1:1/x", embedder=Broken())("보증금", "ko", {})
    with pytest.raises(SearchUnavailable, match="rag db"):
        PgVectorSearch(dsn="postgresql://x@127.0.0.1:1/x", embedder=Ok())("보증금", "ko", {})  # 닫힌 포트
