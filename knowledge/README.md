# 지식 문서 작성 규칙

문서 1건 = Markdown 파일 1개 (`<doc_id>.md`). 이 폴더의 모든 `*.md`(이 README 제외)가 검색 대상이고, `pytest`가 형식을 검사한다.

## 머리말 (YAML)

```yaml
---
doc_id: doc-express-ticket          # 필수. doc-소문자-하이픈. 바꾸면 백엔드·Agent·QA가 깨진다
title_ko: 직통열차 승차권 구매 (서울역)  # 필수
title_en: Buying an Express train ticket at Seoul Station  # 필수. ':' 가 있으면 따옴표로 감싼다
scope: ticket                       # 필수. ticket | card | fare | help(도움받을 곳) | transit(지하철·버스 이용 일반)
train_type: express                 # 그 열차 전용 문서만. express | allstop. 공통 문서는 이 줄을 쓰지 않는다
source_url: https://...             # 필수 키. 대표 출처. field_check 이면 null
source_kind: official               # 필수. official(공식 자료) | field_check(현장·전화 확인) | community(이용자 후기, 미확인)
other_sources:                      # 선택. 함께 확인한 다른 출처
  - https://...
verified_at: 2026-10-22             # 필수. 출처를 열어 내용을 확인한 날 (YYYY-MM-DD)
verified_by: R3                     # 필수. 확인한 사람
---
```

- `scope: fare`: 요금 문서는 반드시 이 값으로 둔다. Agent는 요금 질문에 `scope=fare` 문서만 근거로 쓴다.
- `train_type`: `context.slots.train_type`이 `express`나 `allstop`이면, 다른 열차 전용 문서는 검색에서 빠진다(Agent A-21).
- `verified_by: claude-draft`: 초안 작성 도구가 공식 페이지를 읽고 쓴 문서라는 뜻이다. 사람이 출처를 다시 열어 확인한 뒤 이름과 날짜로 바꾼다.

## 본문

`## ko`와 `## en` 두 절이 한 번씩 있어야 한다. 다른 `##` 제목은 쓰지 않는다.

- 절 안에서 `### 소제목`을 쓰면 그 단위로 나뉘어 검색된다(pgvector 청크).
- 영어 절이 국문 공식 자료를 옮긴 것이면 TODO 주석으로 표시한다.

## 지어내지 않기

- 요금, 운행 시간, 버튼 이름, 위치, 결제 수단은 **출처를 열어 확인한 내용만** 쓴다.
- 확인하지 못한 부분은 본문에 쓰지 않고 HTML 주석으로 남긴다.

  ```markdown
  <!-- TODO(R3): 공식 자료 확인 필요 - 승차권 발매기 화면의 버튼 이름 -->
  ```

  주석은 검색과 발췌에서 빠지므로 사용자에게 보이지 않는다. `grep -rn "TODO(R3)" knowledge/`로 남은 일을 볼 수 있다.
- 이용자 후기(Reddit, 커뮤니티, 블로그)는 `source_kind: community` 문서에만 쓴다.
  - 이런 문서는 `RAG_INCLUDE_COMMUNITY=1`일 때만 검색되는 **초기 개발용 미확인 정보**다.
  - 제목에 `(이용자 후기, 미확인)`을 붙인다.
  - 본문에는 출처 수와 날짜를 적는다.
  - 공식 자료나 현장에서 확인되면 공식 문서로 옮기고 community 문서에서는 지운다.
- 그 밖의 블로그, 여행 플랫폼, 영상은 공식 문서의 출처로 쓰지 않는다. 현장에서 확인한 내용이면 `source_kind: field_check`, `source_url: null`로 두고, 누가 언제 어디서 봤는지 `verified_by`/`verified_at`에 남긴다.
- 사람 얼굴, 이름, 연락처 같은 개인정보는 넣지 않는다. 이 레포는 공개 예정이다.

## 문서를 추가하거나 고친 뒤

```sh
uv run pytest -q                                # 형식 검사 + 검색 테스트
uv run python -m hangil_rag.ingest --dry-run    # 분할 결과 확인
uv run python -m hangil_rag.ingest              # pgvector 를 쓰는 환경이면 다시 적재
```

새 `doc_id`를 Agent나 백엔드가 직접 참조해야 한다면(예: 요금 문서), R2·R4와 먼저 합의한다.
