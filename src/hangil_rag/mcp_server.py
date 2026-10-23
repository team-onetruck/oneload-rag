"""R3 RAG MCP 서버 — search_knowledge 를 MCP 도구로 연다 (R2 Agent 가 LLM 도구 호출로 부른다, RQ-30).

    python -m hangil_rag.mcp_server     # streamable HTTP, 0.0.0.0:8000/mcp (Docker 안에서 내부 HTTP 로 호출)

환경 변수: RAG_MCP_HOST · RAG_MCP_PORT, 검색 설정은 search_knowledge 와 같다 (RAG_BACKEND 등).
GET /health 는 Docker healthcheck 용. 세션을 쓰지 않는(stateless) JSON 응답이라 여러 개를 띄워도 된다.
"""

from __future__ import annotations

import os
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import JSONResponse

from . import search_knowledge as _search
from .schemas import KnowledgeHit, SearchUnavailable

server = MCPServer(
    name="hangil-rag",
    instructions=(
        "Official guidance for foreign travelers at Seoul Station: AREX Express/All-stop trains, tickets, fares, "
        "transit cards and passes, deposit refunds, where to get help. Answer only from returned excerpts and cite "
        "document_id with verified_at; if nothing is returned, say the information is not confirmed."
    ),
)


@server.tool(
    description=(
        "Search verified Seoul Station / AREX guidance documents. Returns up to 3 hits with document_id, title, "
        "excerpt, source_url, verified_at and scope (ticket, card, fare, help, transit). Only scope='fare' hits are "
        "evidence for prices. Pass train_type when the user chose a train so documents for the other train are "
        "excluded. An empty list means no confirmed information: do not guess."
    )
)
def search_knowledge(
    query: str,
    language: Literal["ko", "en"] = "ko",
    train_type: Literal["express", "allstop"] | None = None,
) -> list[KnowledgeHit]:
    try:
        return _search(query, language, {"slots": {"train_type": train_type}})
    except SearchUnavailable as exc:  # Agent 는 오류 결과를 받으면 근거 없음으로 보류한다
        raise ToolError(f"knowledge search unavailable: {exc}") from exc


@server.custom_route("/health", methods=["GET"])
async def health(_: Request) -> JSONResponse:
    return JSONResponse({"status": "ok"})


def main() -> None:
    server.run(
        "streamable-http",
        host=os.environ.get("RAG_MCP_HOST") or "0.0.0.0",
        port=int(os.environ.get("RAG_MCP_PORT") or 8000),
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
