# R3 RAG MCP 서버 (RQ-30). 서버 안 Docker 네트워크에서 Agent 가 http://<이 컨테이너>:8000/mcp 로 부른다.
#   docker build -t hangil-rag .
#   docker run -p 127.0.0.1:8000:8000 hangil-rag          # 기본: DB 없는 메모리 검색
#   (pgvector) -e RAG_BACKEND=pgvector -e RAG_DATABASE_URL=... -e OPENAI_API_KEY=...
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.31 /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY knowledge ./knowledge
# 휠로 설치해 knowledge/ 가 패키지 안에 들어간다 (editable 아님)
RUN uv sync --frozen --no-dev --no-editable --extra mcp --extra pgvector --extra openai \
    && rm -rf /root/.cache

ENV PATH="/app/.venv/bin:$PATH" RAG_MCP_HOST=0.0.0.0 RAG_MCP_PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)"
CMD ["python", "-m", "hangil_rag.mcp_server"]
