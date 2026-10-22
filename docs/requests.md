# R3가 다른 역할에 요청·합의할 것

R3(RAG·데이터)가 작업하면서 다른 역할에 요청하거나 함께 정해야 할 것을 모은 문서입니다. 새로 생기면 계속 추가합니다.

- **상태 값**
  - `제안`: R3가 꺼낸 상태
  - `합의`: 상대 역할이 동의함
  - `반영`: 코드나 문서에 들어감
  - `보류`: 지금은 하지 않음
- **기준 코드**: `oneload-backend` `a82b7be`, `oneload_agent` `250271e` (2026-10-22)
- **확인 방법**: 상대 레포의 코드와 문서만 읽었고, 다른 레포는 수정하지 않았습니다.

## 한눈에 보기

| ID | 대상 | 요약 | 상태 |
| --- | --- | --- | --- |
| RQ-01 | R4 | 백엔드·`oneload-data`가 인용하는 AREX 공식 URL이 404 | 제안 |
| RQ-02 | R4 | `MockKnowledgeSearch` → `hangil_rag.search_knowledge` 교체 | 제안 |
| RQ-03 | R4 | 같은 Postgres의 `rag` 스키마 사용, 확장 권한, 적재 시점 | 제안 |
| RQ-04 | R4 | `RuleAgent` 데모 출처 제목·URL이 실제 문서와 다름 | 제안 |
| RQ-05 | R4 | "도움받을 곳" POI 추가 (고객안내센터, 트래블센터, 환승통로 등) | 제안 |
| RQ-06 | R2 | 검색 예외는 `ToolUnavailable`만 잡힘 | 제안 |
| RQ-07 | R2 | Agent를 pip으로 설치할 수 있게 패키지화 | 제안 |
| RQ-08 | R2·R6 | 실제 검색은 출처가 mock보다 많이 붙을 수 있음 | 제안 |
| RQ-09 | R2 | 문제 해결 문서(`scope: help`)와 "그곳으로 가기" 버튼 | 제안 |
| RQ-10 | R2·R6·R1 | 커뮤니티 후기를 어디까지 데이터로 쓸지 | 제안 |
| RQ-11 | R2·R6 | 요금 문서(`scope: fare`)를 넣을지 | 제안 |
| RQ-12 | R6 | 검색 임계값 확정 | 제안 |
| RQ-13 | R6 | `service_gold.csv`의 정답 근거 열 채우기 | 제안 |
| RQ-14 | R1 | CI용 `TEAM_REPO_TOKEN` 등록 | 제안 |
| RQ-15 | R1·R4 | 설계서 v0.2와 실제 코드가 다른 부분 정리 | 제안 |

## R4 (Backend · 공간 데이터)

### RQ-01 공식 출처 URL 404
- **현상**
  - `app/ai/rule_agent.py`의 `_SOURCES["floors"]`가 `https://www.airportrailroad.com/co/steUsfGud.do`를 인용합니다.
  - `oneload-data`의 README와 `maps/seoul-station.json`의 `provenance`, 설계서 v0.2 3.1도 같은 URL을 씁니다.
  - 이 URL이 2026-10-22 현재 404를 반환합니다. AREX 사이트가 개편된 것으로 보입니다.
- **대체 출처**
  - [AREX 서울역 안내](https://www.airportrailroad.com/train/normal/info/010/0): 지하 2층 직통열차 표, 지하 3층 일반열차 표, 지하 7층 승강장을 문장으로 확인할 수 있습니다.
  - [서울역 안내도 PDF](https://www.airportrailroad.com/static/file/emergency_seoul.pdf): 같은 내용과 함께 영문 시설명이 있습니다.
- **요청**: 출처 URL을 바꾸고 확인일을 갱신해 주세요.

### RQ-02 RAG 연결
- `create_app()`에서 `MockKnowledgeSearch()`를 `hangil_rag.search_knowledge`로 바꿉니다. 코드는 레포 README의 "백엔드 연결"에 있습니다.
- 백엔드 의존성에 `hangil-rag @ git+https://github.com/team-onetruck/oneload-rag@<tag>`를 추가합니다.
- 기본은 DB가 필요 없는 메모리 검색입니다. pgvector는 `RAG_BACKEND=pgvector`로 켭니다.

### RQ-03 pgvector 저장 위치
- **R3 제안**
  - 백엔드와 같은 Postgres의 `rag` 스키마에 둡니다.
  - 테이블 생성은 RAG의 `ingest.py`가 직접 합니다. 백엔드 alembic에는 넣지 않습니다.
  - 근거: 색인은 `knowledge/`로 언제든 다시 만들 수 있는 파생 데이터입니다. 또 백엔드 alembic은 `public` 스키마만 비교하므로 서로 간섭하지 않습니다.
- **필요한 것**
  - 배포 DB에서 `CREATE EXTENSION vector`, `pg_trgm`을 실행할 권한
  - 적재를 언제 할지 정하기 (예: 배포 스크립트에서 `python -m hangil_rag.ingest` 실행)
  - 서버 비밀값에 `OPENAI_API_KEY`(이미 있음)와 `RAG_*` 변수 추가

### RQ-04 RuleAgent 데모 출처
- `RuleAgent._SOURCES`의 문서 4개는 제목이 "(demo doc)"이고 `source_url`이 `None`입니다. 실제 문서는 제목이 다르고 공식 URL이 있습니다.
- `RuleAgent`가 LLM 장애 시 대신 답하는 역할(fallback)로 남는다면, 둘 중 하나를 골라 주세요.
  - 제목과 URL을 실제 문서에 맞추기
  - `hangil_rag`에서 읽어 오기

### RQ-05 "도움받을 곳" POI 추가
- **목적**: "카드가 안 돼요", "보증금은 어디서 돌려받아요?" 같은 문제에 근거 문장과 함께 "그곳으로 안내" 버튼을 주려면 지도에 그 장소가 있어야 합니다.
- **공식 자료로 층까지 확인된 장소**

  | 장소 | 위치 | 출처 |
  | --- | --- | --- |
  | 직통열차 표 사는 곳 `Express Train Tickets` | B2 | 서울역 안내, 안내도 PDF |
  | 트래블센터 `Travel Center` | B2 중앙 | 같음 |
  | 도심공항터미널 `City Airport Terminal` | B2 | 같음 |
  | 일반열차 표 사는 곳 `All-stop Train Ticket Office` | B3 | 같음 |
  | 고객안내센터 `Customer Information Center` | B3 중앙 | 같음 |
  | 1·4호선 갈아타는 곳 `Transfer to Line 1, Line 4` | B3에서 이어짐 | 같음 |

- 보증금 환급기는 "3대"라는 것만 확인했고 위치는 미확인입니다. 현장 확인 후 추가하겠습니다.
- **요청**: 위 장소를 `oneload-data`의 POI로 추가할지 정해 주세요. 노드 위치와 통로는 답사 전 값입니다.

## R2 (Agent)

### RQ-06 검색 장애 예외
- **현상**: Agent의 `_search`는 `ToolUnavailable`만 잡습니다. 그 밖의 예외가 나면 `cannot_answer`가 아니라 요청 실패(500)가 됩니다.
- **R3 쪽 처리**: `SearchUnavailable`을 던지되, `hangil_r2`가 같은 프로세스에 있으면 `ToolUnavailable`도 상속하도록 던지는 순간에 클래스를 고릅니다. `compat.py`와 같은 규칙입니다.
- **합의할 것**: 이 방식을 유지할지, 아니면 Agent가 `RuntimeError` 등 더 넓게 잡을지.

### RQ-07 Agent 패키지화
- `oneload_agent`에는 `pyproject.toml`이 없어 pip으로 설치할 수 없습니다. 지금은 백엔드가 `sys.path`로 불러와야 합니다.
- RAG는 `pip install git+...@tag`로 설치할 수 있습니다. Agent도 같은 방식이면 백엔드 의존성 관리가 쉬워집니다.

### RQ-08 출처 개수 (R6와 함께)
- mock은 키워드가 맞는 문서만 돌려줬습니다. 실제 검색은 관련 문서를 최대 3개까지 돌려줍니다. 예: 직통열차 구매 질문에 "열차 종류" 문서도 함께 붙습니다.
- 계약 테스트(A-02/04/07/08/10/14/21)는 통과합니다.
- 평가 문항에서 "출처가 정확히 이것 하나"를 기대하는 곳이 있으면 알려 주세요.

### RQ-09 문제 해결 문서와 "그곳으로 가기"
- **R3 제안**
  - "카드 결제가 안 될 때", "보증금 돌려받기", "1·4호선에서 공항철도로 갈아타기" 같은 문제 해결 문서를 `scope: help`로 추가합니다.
  - 지금 Agent는 `scope == "fare"`만 특별 취급하므로, 새 값을 넣어도 기존 동작은 바뀌지 않습니다.
- **요청**: 승차권 질문에서 "표 사는 곳으로 가기" 버튼을 주는 것처럼(`_arex_poi`), `help` 문서를 근거로 답할 때 RQ-05의 POI로 가는 버튼을 줄 수 있는지 검토해 주세요.

### RQ-10 커뮤니티 후기 사용 범위 (R6·R1과 함께)
- **배경**
  - Reddit, 국내 커뮤니티, 블로그, 영상 후기에는 외국인 여행객이 실제로 막히는 지점과 해결 팁이 많습니다.
  - 하지만 D-20(확정)은 요금, 운행 시간, 버튼 이름을 "R3 공식 자료에서만" 쓰도록 정했습니다.
  - 후기는 기기 교체나 정책 변경으로 낡았을 수 있고, 검증할 수도 없습니다.
- **R3 제안**
  - 후기는 **문제를 찾는 데만** 씁니다. 실제 질문 문장, 막히는 지점, 해결 팁 후보를 모읍니다.
  - 답변 근거(RAG 문서)에는 공식 자료나 현장에서 확인한 사실만 넣습니다.
  - 후기에서만 나온 팁은 확인할 일(TODO)로 남깁니다.
  - 모은 문제 목록은 R6 평가 문항과 RAG 문서 작성 목록으로 씁니다.
- **필요하면 다음 단계로**: 후기에서만 나온 팁을 "확인되지 않음"(`unverified_notes`)으로 보여 주려면 `source_kind: community`와 Agent 처리가 필요합니다. MVP에서는 하지 않기를 권합니다.

## R2 · R6

### RQ-11 요금 문서
- 지금은 요금 문서가 없습니다. 그래서 "요금 질문 → `cannot_answer`"가 정답입니다(Agent A-08, QA Q10).
- 공식 요금은 [직통열차 소개](https://www.airportrailroad.com/train/express/introduce)와 [일반열차 운임](https://www.airportrailroad.com/train/normal/fare) 페이지에 있습니다.
- 요금 문서(`scope: fare`)를 넣으면 A-08과 Q10의 기대 결과가 바뀝니다. 넣을지 정해 주세요.

## R6 (QA)

### RQ-12 검색 임계값
- 초기값
  - 메모리 검색: 최소 점수 0.2, 그리고 1위 점수의 50% 미만은 제외
  - pgvector: 0.3 (`RAG_MIN_SCORE`)
- 결과가 비면 `rag_empty reason=no_match|below_threshold top_score=…` 로그를 남깁니다. 평가셋으로 값을 확정해 주세요.

### RQ-13 정답 근거 열
- `eval/service_gold.csv`의 `source_doc`, `source_locator` 열이 아직 "R3 공식 근거 추가 필요"로 남아 있습니다.
- 문서 ID와 공식 URL은 `oneload-rag/knowledge/*.md` 머리말에 있습니다. 문항별 매핑을 같이 채우면 좋겠습니다.

## R1 (PM) · 레포 관리자

### RQ-14 CI 토큰
- `oneload-rag` CI가 private인 `oneload_agent`와 `oneload-backend`를 읽어 계약 테스트를 돌리려면, 레포 secret `TEAM_REPO_TOKEN`(두 레포 읽기 전용)이 필요합니다.
- 토큰이 없으면 계약 테스트는 skip으로 표시되고, 통과로 처리되지 않습니다.

### RQ-15 설계서 v0.2와 실제 코드가 다른 부분
R3는 실제 코드를 따랐습니다. 설계서를 고칠지 정해 주세요.

| 설계서 v0.2 | 실제 코드 / R3 구현 |
| --- | --- |
| 6.4 `KnowledgeHit`: `language`, `source_kind`, `score` 포함, `scope`가 객체 `{station, train_type}` | 6개 필드(`document_id`, `title`, `excerpt`, `source_url`, `verified_at`, `scope`), `scope`는 문자열 |
| 3.2 문서는 언어별 파일(`language: ko`), `question_types` 있음, ID 예시 `doc-arex-express-ticket` | 한 파일에 `## ko`/`## en`, ID는 백엔드 데모 4개(`doc-express-ticket` 등) |
| 5.3 검색 결과 k=4 | Agent는 상위 3개만 씀. RAG도 3개 반환 |
| 4장 Agent: 직접 구현한 tool-calling 루프, LangGraph 기각 | Agent는 LangGraph 사용 |
| 3.1 층 정보 출처 `…/co/steUsfGud.do` | 404, RQ-01 참고 |

## 변경 이력

- 2026-10-22: 처음 작성. RQ-01~RQ-15
