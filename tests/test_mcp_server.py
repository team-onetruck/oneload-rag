"""MCP 서버 (RQ-30): 도구 모양 · 검색 결과 · 열차 필터 · 장애 · /health. `[mcp]` extra 가 없으면 skip."""

import pytest

pytest.importorskip("mcp")

from mcp import Client  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from hangil_rag import mcp_server  # noqa: E402
from hangil_rag.schemas import unavailable  # noqa: E402

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend():
    return "asyncio"


async def call(args: dict):
    async with Client(mcp_server.server) as c:
        return await c.call_tool("search_knowledge", args)


def ids(result) -> list[str]:
    return [h["document_id"] for h in result.structured_content["result"]]


async def test_tool_is_listed_with_llm_friendly_arguments():
    async with Client(mcp_server.server) as c:
        tool = next(t for t in (await c.list_tools()).tools if t.name == "search_knowledge")
    props = tool.input_schema["properties"]
    assert set(props) == {"query", "language", "train_type"} and tool.input_schema["required"] == ["query"]
    assert "fare" in tool.description and tool.output_schema


async def test_search_returns_hits_with_sources():
    r = await call({"query": "How do I get my deposit back?", "language": "en"})
    hit = r.structured_content["result"][0]
    assert not r.is_error and hit["document_id"] == "doc-deposit-refund"
    assert hit["title"] == "Getting the single-journey ticket deposit back" and hit["verified_at"] and hit["source_url"]


async def test_train_type_filter():  # A-21
    r = await call({"query": "일반열차 승차권 구매 방법", "train_type": "allstop"})
    assert "doc-allstop-ticket" in ids(r) and "doc-express-ticket" not in ids(r)


async def test_nothing_relevant_is_empty():
    assert ids(await call({"query": "내일 날씨 어때?"})) == []


async def test_outage_is_a_tool_error(monkeypatch):
    def down(*_):
        raise unavailable("db down")

    monkeypatch.setattr(mcp_server, "_search", down)
    r = await call({"query": "보증금 환급"})
    assert r.is_error and "unavailable" in r.content[0].text


def test_health_route():
    with TestClient(mcp_server.server.streamable_http_app(stateless_http=True, json_response=True)) as http:
        assert http.get("/health").json() == {"status": "ok"}
