# 백엔드에 R2 Agent + R3 RAG 연결하기 (R4·infra용, QA INT-07)

QA가 P0로 남긴 **INT-07**("Backend 기본 RuleAgent/NoVision, 실제 Agent/Vision 주입, R3 검색 교체")에서 R3 몫을 정리한 자료입니다. R3는 백엔드·infra 레포를 수정하지 않았습니다.

## 먼저 정할 것: 구조 (2026-10-23 기준)

코드와 팀에서 들은 구조가 아직 다릅니다.

| 출처 | 내용 |
| --- | --- |
| 설계서 v0.2 2.3, API 명세 v0.3 3장 | 단일 백엔드 프로세스 안에서 Agent·RAG를 **함수 호출**로 연결 (분리하면 내부 HTTP) |
| 지금 코드 (backend `493884f`, infra `8587d3b`) | 백엔드는 `app = create_app()` 그대로라 **RuleAgent/NoVision**. compose에는 `db`·`api`·`caddy`만 있고 Agent·RAG 서비스는 없음 |
| 팀 답변 (RQ-30) | **백엔드와 LangGraph(Agent)는 분리**, Agent가 **MCP 도구 호출**로 RAG를 부름, 서버 안 Docker의 내부 HTTP |

두 가지 방안이 있습니다. R2·R4가 정하면 R3가 자료를 맞춥니다.

| | 방안 A: 백엔드 안 조립 | 방안 B: Agent 별도 서비스 + RAG MCP |
| --- | --- | --- |
| 백엔드 | `create_app(agent=LLMAgent(...))` (아래 패치) | 백엔드가 Agent 서비스를 HTTP로 부르는 클라이언트 필요 (R4·R2가 새로 정함) |
| Agent → RAG | 함수 `hangil_rag.search_knowledge` | MCP `http://rag:8000/mcp` (R3 준비 완료, 아래 compose 예) |
| 백엔드 의존성 | `hangil-rag`, `langgraph`, `langchain-openai`, `python-dotenv` + Agent 코드 | 없음 |
| 근거 | 설계서와 같고, R3가 패치·API 시험 완료 | 팀 답변과 같고, 아직 코드 없음 |

## 방안 A: 백엔드 안 조립 (패치 초안)

- 패치: [`backend-ai-wiring.patch`](backend-ai-wiring.patch)
- `app/config.py`: `ai_mode: Literal["rule", "llm"] = "rule"`
- `app/main.py`: `llm`이면 `LLMAgent` + 같은 `LLMVision` + `hangil_rag.search_knowledge` + fallback `RuleAgent`를 조립합니다. **기본 `rule`은 지금과 같습니다.**
- `pyproject.toml`: `hangil-rag`를 **GitHub 태그 압축 파일 주소**(`…/archive/refs/tags/v0.1.0.tar.gz`)로 받습니다.
  - 백엔드 이미지(`python:3.12-slim`)에는 git이 없어서 git 주소로 받으면 `docker build`가 "Git executable not found"로 실패합니다(R3 확인).

```sh
cd oneload-backend
git apply ../oneload-rag/docs/backend-integration/backend-ai-wiring.patch
uv lock && uv run ruff check . && uv run pytest -q
```

**R3가 확인한 것**

| 확인 | 결과 |
| --- | --- |
| backend `493884f`에 `git apply --check` | ✅ |
| 기본값(rule)에서 백엔드 테스트 (`a82b7be` 기준) | ✅ 44 passed |
| `AI_MODE=llm` 조립 | ✅ LLMAgent + 같은 LLMVision + hangil_rag + fallback RuleAgent, `/health` 200 |
| 백엔드 Docker 이미지 빌드 (`493884f`의 Dockerfile + 패치) | ✅ 압축 파일 주소로 빌드됨. 이미지 안에서 `hangil_rag`(문서 13개)·`langgraph` import |
| 백엔드 API 단위 연결 (`scripts/e2e_backend.py`, FakeLLM) | ✅ 6/6 |

**방안 A에 남은 일:** Agent 코드(`hangil_r2/`와 옆의 `prompts/`)가 백엔드 이미지 안에 있어야 합니다. Agent에 `pyproject.toml`이 없어 의존성으로 넣을 수 없으니(RQ-07), 둘 중 하나가 필요합니다.
- R2가 패키지로 만들기 → `hangil-rag`처럼 압축 파일 주소 의존성으로 받기
- 이미지 빌드 때 Agent 레포를 함께 받아 `COPY`하기 (infra의 compose build에 Agent 소스 추가)

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
uv run --project ../oneload-backend --with langgraph==1.2.16 --with python-dotenv==1.2.4 --with ../oneload-rag \
  python scripts/e2e_backend.py

# 방안 B: RAG MCP 서버 (CI가 매번 확인하는 것과 같음)
docker build -t hangil-rag . && docker run -p 127.0.0.1:8000:8000 hangil-rag
curl http://127.0.0.1:8000/health
```

QA(R6)는 지금 Mock 검색으로 검사합니다. 연결한 뒤에는 실제 RAG 경로로 다시 검사해야 합니다(QA handoff 97·99행).
