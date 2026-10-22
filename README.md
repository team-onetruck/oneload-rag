# 한길 (Hangil) RAG

R3가 맡은 이용 안내 검색 모듈입니다. Agent(R2)의 `search_knowledge` 도구로 쓰이며, 지금 Agent가 쓰는 `MockKnowledgeSearch`와 백엔드 `RuleAgent`의 고정 출처 자리에 그대로 들어갑니다.

| 경로 | 내용 |
| --- | --- |
| `knowledge/*.md` | 지식 문서. 문서 1건 = Markdown 1개 + YAML 머리말, 본문은 `## ko` / `## en`. 작성 규칙은 [knowledge/README.md](knowledge/README.md) |
| `src/hangil_rag/schemas.py` | `KnowledgeHit`(Agent와 같은 필드), 장애 예외 `SearchUnavailable` |
| `src/hangil_rag/loader.py` | 문서 파싱·검증(필수 필드, ID 중복, scope·train_type 값), 헤딩 단위 분할 |
| `src/hangil_rag/search_memory.py` | DB 없는 키워드 검색 (기본값, 테스트·로컬 시연용) |
| `src/hangil_rag/search_pgvector.py` | pgvector 하이브리드 검색 초안 (메타데이터 필터 → 벡터 + 키워드) |
| `src/hangil_rag/ingest.py` | 분할 → 임베딩 → `rag.chunks` 적재 |
| `localization/` | 사진 위치 인식용 임시 데이터 (답사 전 특징 카드 + 합성 케이스 + 매처 비교). [localization/README.md](localization/README.md) |
| `docs/requests.md` | 다른 역할에 요청·합의할 것 |

## 설치

```sh
pip install git+https://github.com/team-onetruck/oneload-rag@<tag>                                 # 메모리 검색만
pip install "hangil-rag[pgvector,openai] @ git+https://github.com/team-onetruck/oneload-rag@<tag>"  # pgvector + 임베딩
```

- Python 3.12 (백엔드와 같음)
- 지식 문서는 패키지 안에 함께 설치됩니다. 태그를 바꾸면 문서 버전도 바뀝니다.

## 백엔드 연결 (R4)

[oneload_agent docs/handoff.md](https://github.com/team-onetruck/oneload_agent/blob/main/docs/handoff.md)의 연결 코드에서 `MockKnowledgeSearch()` 한 곳만 바꾸면 됩니다.

```python
from hangil_r2 import LLMAgent, LLMVision, OpenAILLM
from hangil_rag import search_knowledge  # MockKnowledgeSearch 대신
from app.ai.rule_agent import RuleAgent

llm = OpenAILLM()
app.state.agent = LLMAgent(llm, search_knowledge=search_knowledge, fallback=RuleAgent())
app.state.vision = LLMVision(llm)
```

- **검색 방식 선택:** 기본은 메모리 검색입니다. `RAG_BACKEND=pgvector`이면 pgvector를 쓰며, 이때는 먼저 [적재](#pgvector-적재)해야 합니다.
- **장애 처리:** 검색 장애가 나면 `SearchUnavailable`을 던집니다. Agent(`hangil_r2`)가 같은 프로세스에 있으면 이 예외는 Agent의 `ToolUnavailable`이기도 합니다. 따라서 Agent는 감싸는 코드 없이 `cannot_answer`로 보류합니다.

## 검색

```python
from hangil_rag import search_knowledge

hits = search_knowledge("일반열차 승차권 구매 방법", "ko", {"slots": {"train_type": "allstop"}})
# [KnowledgeHit(document_id="doc-allstop-ticket", title="일반열차 타는 방법 - ...", scope="ticket", ...), ...]
```

- 질문 언어와 상관없이 두 언어 절을 모두 검색하고, 제목과 발췌는 `language`(`ko`/`en`)에 맞춰 돌려줍니다.
- `context["slots"]["train_type"]`이 `express`나 `allstop`이면 다른 열차 전용 문서는 뺍니다.
- 관련 문서가 없거나 점수가 임계값보다 낮으면 빈 목록을 돌려줍니다. 둘 중 어느 경우인지는 로그로만 구분합니다(`rag_empty reason=no_match|below_threshold top_score=…`). R6가 임계값을 정할 때 이 로그를 씁니다.

## pgvector 적재

같은 Postgres(백엔드 `compose.yaml`, `127.0.0.1:54329`)의 **`rag` 스키마**에 적재합니다. 백엔드 테이블과 섞이지 않고, 백엔드 alembic(public 스키마만 비교)도 이 스키마를 건드리지 않습니다.

```sh
uv sync --all-extras
uv run python -m hangil_rag.ingest --dry-run      # 분할 결과만 확인 (DB·API 불필요)
OPENAI_API_KEY=... uv run python -m hangil_rag.ingest
```

- 적재할 때마다 `rag.chunks`를 한 트랜잭션 안에서 새로 만듭니다. 색인은 `knowledge/`로 언제든 다시 만들 수 있으므로 마이그레이션 이력을 두지 않습니다.
- `vector`와 `pg_trgm` 확장을 만들 권한이 필요합니다. 로컬 compose DB에는 권한이 있습니다.
- 임베딩은 `Embedder` 인터페이스(`dim`, `embed(texts)`)로 주입합니다. 테스트는 가짜 임베더만 쓰므로 유료 API를 부르지 않습니다.

## 환경 변수

이름은 [.env.example](.env.example)에 있습니다. 값은 `.env`(git 제외)나 서버 비밀값에 넣고, 레포에는 쓰지 않습니다.

| 이름 | 기본값 | 용도 |
| --- | --- | --- |
| `RAG_BACKEND` | `memory` | `pgvector`로 전환 |
| `RAG_KNOWLEDGE_DIR` | 패키지 안 `knowledge/` | 문서 폴더 |
| `RAG_INCLUDE_COMMUNITY` | 꺼짐 | `1`이면 이용자 후기 기반 문서(`source_kind: community`)도 검색. **초기 개발용**, 시연·배포에서는 끔 |
| `RAG_DATABASE_URL` | 로컬 compose DB | pgvector 접속 |
| `RAG_MIN_SCORE` | `0.3` | pgvector 점수 임계값 (초기값) |
| `RAG_EMBEDDING_MODEL`, `RAG_EMBEDDING_DIM` | `text-embedding-3-small`, `1536` | 임베딩 모델 |
| `OPENAI_API_KEY` | — | 임베딩 API 키 |

## 테스트

```sh
uv sync --all-extras
uv pip install -r ../oneload_agent/requirements.txt   # 계약 테스트용 Agent 의존성
uv run pytest -q
```

- **계약 테스트**(`tests/test_contract.py`)는 옆 폴더의 `oneload_agent`, `oneload-backend`를 import합니다.
  - 찾는 위치: `RAG_AGENT_DIR`, `RAG_BACKEND_DIR` 환경변수 → 옆 폴더 → zip을 푼 `*-main` 폴더 순서
  - 확인하는 것: 결과가 Agent `KnowledgeHit`과 백엔드 `Source`로 그대로 바뀌는지, 문서 ID가 백엔드 `rule_agent.py`와 같은지, Agent 흐름(A-02, A-04, A-07, A-08, A-10, A-14, A-21)을 이 검색으로 돌렸을 때 통과하는지
  - 옆 레포가 없으면 skip합니다.
- **pgvector 연동 테스트**는 `RAG_TEST_DATABASE_URL`(지워도 되는 DB)이 있을 때만 돕니다.
- **CI**(`.github/workflows/ci.yml`)는 pgvector 서비스 컨테이너와 두 레포 checkout으로 전부 실행합니다.
  - 두 레포가 private이라 **레포 secret `TEAM_REPO_TOKEN`**(두 레포 읽기 전용 토큰)이 필요합니다.
  - 토큰이 없으면 계약 테스트는 skip으로 표시됩니다(통과로 처리하지 않음).

## 다른 레포와의 계약

다른 역할에 요청하거나 합의할 것은 [docs/requests.md](docs/requests.md)에 따로 모읍니다.

| 상대 | 계약 | 기준 코드 |
| --- | --- | --- |
| R2 Agent | `search_knowledge(query, language, context) -> list[KnowledgeHit]` | `oneload_agent/hangil_r2/knowledge.py` (`KnowledgeSearch`) |
| R2 Agent | `KnowledgeHit`: `document_id`, `title`, `excerpt`, `source_url`(None 가능), `verified_at`(필수), `scope`(문자열) | 같은 파일 |
| R2 Agent | `context` = `{"map_id", "slots": Slots.model_dump()}`. `train_type`으로 전용 문서 필터 (A-21) | `hangil_r2/agent.py` `_search` |
| R2 Agent | 요금 문서는 `scope="fare"`. Agent는 요금 질문에 이 문서만 근거로 씀 | `agent.py` `_answer` |
| R2 Agent | 장애 시 `ToolUnavailable` 계열 예외 → `cannot_answer` | `agent.py` `_search` |
| R4 Backend | 결과가 `Source(document_id, title, source_url, verified_at)`로 바뀜. 출처는 이번 턴에 검색된 ID만 통과 | `app/ai/contracts.py`, `app/ai/guard.py` |
| R4 Backend | 문서 ID: `doc-arex-train-types`, `doc-express-ticket`, `doc-allstop-ticket`, `doc-deposit-refund` | `app/ai/rule_agent.py` `_SOURCES` |
| R4 Backend | 같은 Postgres의 `rag` 스키마만 사용 | `compose.yaml` |
| R6 QA | 요금 근거 없음 → `cannot_answer` (Q10). 현재 요금 문서 없음 | `oneload-qa/eval/service_gold.csv` |

## 문서 현황

- 문서 4개는 아래 공식 페이지를 2026-10-22에 열어 확인한 내용만 담았습니다. `verified_by: claude-draft`는 사람이 다시 확인하기 전이라는 표시입니다.
  - [AREX 직통열차 소개](https://www.airportrailroad.com/train/express/introduce)
  - [AREX 일반열차 소개](https://www.airportrailroad.com/train/normal/introduce)
  - [AREX 서울역 안내](https://www.airportrailroad.com/train/normal/info/010/0)
  - [AREX 서울역 안내도 PDF](https://www.airportrailroad.com/static/file/emergency_seoul.pdf) (영문 시설명)
  - [서울시 1회용 교통카드 안내](https://news.seoul.go.kr/traffic/archives/1763)
  - [서울교통공사 승차권 안내](http://www.seoulmetro.co.kr/kr/page.do?menuIdx=355)
- 확인하지 못한 항목(결제 수단, 버튼 이름, 개찰구·환급기 위치, 역 이름 영문 표기)은 `TODO(R3)` 주석으로 남겼습니다.
- 요금은 공식 페이지에 있지만, 요금 문서를 둘지 R2·R6가 합의하기 전이라 넣지 않았습니다.
- `doc-seoul-transit-basics`(`scope: transit`)는 서울 지하철·버스 이용법을 다룹니다(교통카드 태그, 환승 할인, 2026년 3월부터 1~8호선 신형 발매기의 해외 카드 결제).
- `doc-climate-card-short-term`은 여행객용 기후동행카드 단기권을 다룹니다. **2026년 10월 1일 바뀐 이용 범위**를 반영했고, 인천공항역은 내리기만 되고 타기는 안 된다는 점을 담았습니다. 가격은 RQ-11 결정 뒤에 넣습니다.
- `doc-seoul-help-desks`(`scope: help`)는 문제가 생겼을 때 도움받을 곳을 순서대로 안내합니다. 역 안의 창구(B3 고객안내센터, B2)가 먼저이고, 외국인용 1330, 공항철도 콜센터가 그다음이며, 분실물과 긴급 상황은 마지막입니다.
- `source_kind: community` 문서는 이용자 후기에서 모은 **미확인** 정보입니다. 초기 개발용이라 `RAG_INCLUDE_COMMUNITY=1`일 때만 검색되고, 결과 3개 중 마지막 한 자리까지만 차지합니다. 출처별 근거는 [research/community-2026-10-22.md](research/community-2026-10-22.md)에 있고, 답사나 공식 확인 후 공식 문서로 옮깁니다.
