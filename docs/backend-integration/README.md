# 백엔드에 R2 Agent + R3 RAG 연결하기 (R4·infra용, QA INT-07)

> **2026-10-25 반영됨:** backend `a355b32`가 아래 방안 A 패치를 적용했습니다. 이 문서는 적용 기록과 방안 B(MCP) 참고용으로 남깁니다.

QA가 P0로 남긴 **INT-07**("Backend 기본 RuleAgent/NoVision, 실제 Agent/Vision 주입, R3 검색 교체")에서 R3 몫을 정리한 자료입니다. R3는 백엔드·infra 레포를 수정하지 않았습니다.

## 먼저 정할 것: 구조 (2026-10-23 기준)

코드와 팀에서 들은 구조가 아직 다릅니다.

| 출처 | 내용 |
| --- | --- |
| 설계서 v0.2 2.3, API 명세 v0.3 3장 | 단일 백엔드 프로세스 안에서 Agent·RAG를 **함수 호출**로 연결 (분리하면 내부 HTTP) |
| 지금 코드 (backend `b1aa5f5`, agent `eca420e`) | 백엔드 안에서 LLMAgent·LLMVision을 조립함(방안 A로 진행 중). **검색만 `MockKnowledgeSearch()`** |
| 팀 답변 (RQ-30) | **백엔드와 LangGraph(Agent)는 분리**, Agent가 **MCP 도구 호출**로 RAG를 부름, 서버 안 Docker의 내부 HTTP |

두 가지 방안이 있습니다. R2·R4가 정하면 R3가 자료를 맞춥니다.

| | 방안 A: 백엔드 안 조립 | 방안 B: Agent 별도 서비스 + RAG MCP |
| --- | --- | --- |
| 백엔드 | `create_app(agent=LLMAgent(...))` (아래 패치) | 백엔드가 Agent 서비스를 HTTP로 부르는 클라이언트 필요 (R4·R2가 새로 정함) |
| Agent → RAG | 함수 `hangil_rag.search_knowledge` | MCP `http://rag:8000/mcp` (R3 준비 완료, 아래 compose 예) |
| 백엔드 의존성 | `hangil-rag`, `oneload-agent` (둘 다 압축 파일 주소) | 없음 |
| 근거 | 설계서와 같고, R3가 패치·API 시험 완료 | 팀 답변과 같고, 아직 코드 없음 |

## 방안 A: 백엔드 안 조립 (패치 초안)

**2026-10-23 갱신 (backend `b1aa5f5`):** R4·R2가 운영 조립(`production_ai()`)에 LLMAgent·LLMVision을 넣었습니다. 남은 건 검색이 `MockKnowledgeSearch()`인 것 하나입니다(QA INT-07 partial). 패치는 그 부분만 바꿉니다.

- 패치: [`backend-ai-wiring.patch`](backend-ai-wiring.patch)
- `app/main.py`: `MockKnowledgeSearch()` → `hangil_rag.search_knowledge`
- `pyproject.toml`: `hangil-rag`를 태그 압축 파일 주소(`v0.3.0`)로 추가
  - 백엔드 이미지(`python:3.12-slim`)에 git이 없어서 git 주소는 빌드가 실패합니다.
  - `scripts/pin_agent.sh`는 `oneload-agent`만 바꾸므로 이 주소와 충돌하지 않습니다.

```sh
cd oneload-backend
git apply ../oneload-rag/docs/backend-integration/backend-ai-wiring.patch
uv lock && uv run ruff check . && uv run pytest -q
```

**R3가 확인한 것 (backend `b1aa5f5`, agent `eca420e`, 복제본에서)**

| 확인 | 결과 |
| --- | --- |
| `git apply --check` | ✅ |
| ruff·백엔드 테스트 | ✅ 68 passed |
| `OPENAI_API_KEY`가 있을 때 운영 조립 | ✅ LLMAgent·LLMVision, `agent.search_knowledge is hangil_rag.search_knowledge` |
| Docker 이미지 (`pin_agent.sh` 후 `docker build`) | ✅ 이미지 안에서도 같은 조립, RAG 문서 13개 |

(가짜 키로 조립만 확인. 실제 OpenAI 호출은 하지 않았습니다.)

## 방안 B: RAG를 compose 서비스로 띄우기 (R3 준비 완료)

`oneload-rag`의 `Dockerfile`이 MCP 서버 이미지입니다. infra `macserver/compose.yaml`에 서비스 하나를 추가하는 예입니다.

```yaml
  rag:
    image: hangil-rag:latest
    build:
      context: ${RAG_DIR:-.}   # oneload-rag checkout
    restart: unless-stopped
    # 기본은 DB 없는 메모리 검색이라 설정이 필요 없음. 포트는 공개하지 않고 compose 네트워크 안에서만 씀.
    # Agent → http://rag:8000/mcp , 상태 확인은 이미지의 HEALTHCHECK(/health)
```

- pgvector로 바꿀 때만 다음이 필요합니다.
  - 설정: `RAG_BACKEND=pgvector`, `RAG_DATABASE_URL=postgresql://hangil:hangil@db:5432/hangil`, `OPENAI_API_KEY`
  - 적재: `python -m hangil_rag.ingest` 1회
  - 다만 R3 평가에서는 메모리 검색이 더 나았습니다(`eval/README.md`).
- Agent 쪽 연결 예(R2): README의 `MultiServerMCPClient` 예시
  - `langchain-mcp-adapters` 0.3.2로 확인했습니다.

## 연결한 뒤 확인

```sh
# 방안 A: 백엔드 API 단위 연결 (FakeLLM, 키 불필요, 로컬 compose DB 필요)
cd oneload-rag
# 패치를 적용한 백엔드라면 Agent·RAG가 의존성으로 이미 들어 있음
uv run --project ../oneload-backend --with-editable ../oneload-rag python scripts/e2e_backend.py

# 방안 B: RAG MCP 서버 (CI가 매번 확인하는 것과 같음)
docker build -t hangil-rag . && docker run -p 127.0.0.1:8000:8000 hangil-rag
curl http://127.0.0.1:8000/health
```

QA(R6)는 지금 Mock 검색으로 검사합니다. 연결한 뒤에는 실제 RAG 경로로 다시 검사해야 합니다(QA handoff 97·99행).
