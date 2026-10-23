# 백엔드에 R2 Agent + R3 RAG 연결하기 (R4용, QA INT-07)

QA가 P0로 남긴 **INT-07**("Backend 기본 RuleAgent/NoVision, 실제 Agent/Vision 주입, R3 검색 교체")을 풀기 위한 패치 초안입니다. R3가 백엔드 **복사본**에 적용해 시험했고, 백엔드 레포 자체는 고치지 않았습니다. 적용 여부와 방식은 R4가 정합니다.

## 무엇이 바뀌나

| 파일 | 변경 |
| --- | --- |
| `app/config.py` | `ai_mode: Literal["rule", "llm"] = "rule"` 설정 추가 |
| `app/main.py` | `ai_mode == "llm"`이면 `LLMAgent`, `LLMVision`, `hangil_rag.search_knowledge`를 조립해 `create_app(agent=..., vision=...)`에 넣음. **기본값 `rule`은 지금과 똑같이** `RuleAgent`/`NoVision` |
| `pyproject.toml` | `hangil-rag`(git 태그 `v0.1.0`), `langgraph==1.2.16`, `langchain-openai==1.7.2`, `python-dotenv==1.2.4` 추가 |

- 같은 Vision 하나를 Agent(`/messages` 첨부 사진)와 `create_app`(`/localizations`) 양쪽에 넣습니다. RAG 이슈 #2와 Agent 이슈 #2에서 나온 방식입니다.
- AI 패키지는 `ai_mode == "llm"`일 때만 import합니다. 그래서 테스트와 로컬 실행은 AI 패키지가 없어도 됩니다.

## 적용 방법

```sh
cd oneload-backend
git apply ../oneload-rag/docs/backend-integration/backend-ai-wiring.patch
uv lock                      # 패치에는 uv.lock 이 없어서 새로 만든다
uv run ruff check . && uv run pytest -q
```

## 확인한 것 (2026-10-23, 백엔드 `a82b7be` · Agent `250271e` · RAG `v0.1.0`)

| 확인 | 결과 |
| --- | --- |
| 패치를 실제 백엔드 최신 코드에 적용할 수 있는지 (`git apply --check`) | ✅ |
| 기본값(`rule`)에서 백엔드 테스트 | ✅ 44 passed, ruff 통과 |
| `AI_MODE=llm`일 때 조립 | ✅ `LLMAgent` + `LLMVision`(Agent와 같은 객체) + `hangil_rag.search_knowledge` + 실패 시 `RuleAgent`, `/health` 200 |
| 설정이 없을 때 | ✅ `RuleAgent` / `NoVision` (지금과 같음) |
| 백엔드 API 단위 연결 (`oneload-rag/scripts/e2e_backend.py`, FakeLLM) | ✅ 6/6: RAG 근거(출처 URL·확인일), 요금 질문 → 요금 문서만, 일반열차 흐름에 직통 문서 없음(A-21), 영어 제목, `/messages` 첨부 사진 읽기, `/localizations`가 같은 Vision 사용 |
| Python 버전 | 백엔드와 같은 3.12에서 시험 (Agent는 3.13에서 개발됨) |

`AI_MODE=llm` 조립 확인에서는 실제 LLM을 부르지 않았습니다(`/health`만 호출). 실제 OpenAI로 대화하는 시험은 키와 비용이 드니 배포 전에 한 번 따로 하면 됩니다.

## 남은 문제: 서버에서 Agent 코드를 불러오는 방법

`oneload_agent`에는 `pyproject.toml`이 없어서 pip이나 uv로 설치할 수 없습니다(RQ-07). 시험에서는 `PYTHONPATH`로 불러왔습니다. 서버에 올릴 방법은 두 가지입니다.

### 방법 A: 지금 바로 (배포 때 복사)

서버는 `~/hangil-api`(백엔드 복사본)에서 `uv run uvicorn app.main:app`으로 뜹니다. uvicorn은 실행 폴더를 import 경로에 넣으므로, Agent의 **`hangil_r2/`와 `prompts/`**를 그 폴더에 함께 복사하면 됩니다. Agent는 `hangil_r2/` 옆의 `prompts/`에서 프롬프트를 읽습니다.

1. **백엔드 CI의 deploy 작업**에서 Agent 레포도 받아 옵니다. 비공개 레포라 읽기 토큰 secret이 필요합니다(예: `oneload-rag`의 `TEAM_REPO_TOKEN`과 같은 종류).

   ```yaml
   - uses: actions/checkout@v4
     with:
       repository: team-onetruck/oneload_agent
       path: agent
       token: ${{ secrets.TEAM_REPO_TOKEN }}
   - run: infra/macserver/deploy.sh backend data agent
     env:
       APP_OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
       APP_AI_MODE: ${{ secrets.AI_MODE }}   # 값: llm
   ```

2. **`oneload-infra/macserver/deploy.sh`**에서 세 번째 인수로 받은 Agent 폴더를 복사합니다. 백엔드 rsync(`--delete`) **뒤에** 넣어야 지워지지 않습니다.

   ```bash
   AGENT_SRC="$(cd "$3" && pwd)"
   rsync -a --delete "$AGENT_SRC/hangil_r2" "$AGENT_SRC/prompts" "$APP/"
   ```

3. 백엔드 레포 secret에 `AI_MODE=llm`을 추가합니다. `deploy.sh`가 `APP_` 접두사를 떼서 `~/hangil-api.env`에 `AI_MODE=llm`으로 씁니다.

### 방법 B: 나중에 (R2가 패키지로 만들면)

R2가 `oneload_agent`에 `pyproject.toml`을 추가하면(RQ-07) `hangil-rag`처럼 git 의존성으로 넣을 수 있습니다. 다만 비공개 레포라 서버의 `uv sync`에도 읽기 권한이 필요합니다.

## 연결한 뒤 확인

```sh
# 백엔드 API 단위 연결 (FakeLLM, 키 불필요, 로컬 compose DB 필요)
cd oneload-rag
uv run --project ../oneload-backend --with langgraph==1.2.16 --with python-dotenv==1.2.4 --with ../oneload-rag \
  python scripts/e2e_backend.py

# R2 쪽 호환 점검 (Agent README)
cd ../oneload_agent
DATABASE_URL=postgresql+psycopg://hangil:hangil@localhost:54329/hangil_test \
uv run --project ../oneload-backend --with langgraph==1.2.16 --with python-dotenv==1.2.4 \
  python scripts/check_backend_compat.py ../oneload-backend --e2e
```

QA(R6)는 지금 Mock 검색으로 검사합니다. 연결 후 R3 검색 상태로 다시 검사하려면 QA 쪽 Agent 조립에서 `MockKnowledgeSearch()`를 `hangil_rag.search_knowledge`로 바꾸면 됩니다(`pip install "hangil-rag @ git+https://github.com/team-onetruck/oneload-rag@v0.1.0"`).
