# R3 남은 할 일 (2026-10-22 기준)

크게 세 갈래입니다.

- **A. RAG 문서의 사실 확인:** `knowledge/*.md` 안의 `TODO(R3)` 19개. 같은 질문끼리 묶어 15개 항목으로 정리했습니다.
- **B. 사람이 다시 봐야 할 초안:** 초안 도구가 넣은 내용
- **C. R3의 다른 일:** 팀 결정이나 권한이 필요한 것

## A. RAG 문서 사실 확인

### 1순위: 시연 핵심, 지금은 답을 못 함

| # | 확인할 것 | 문서 | 방법 |
|---|---|---|---|
| 1 | 직통열차 승차권 결제 수단 (현금, 국내 카드, 해외 카드, 발매기와 창구 차이) | express-ticket, fare-arex-express | ☎ 공항철도 1599-7788 |
| 2 | 공항철도 1회용 교통카드의 해외 카드 범위(비자·마스터·아멕스·유니온페이)와 시작일 (**보류 중인 allstop-ticket**) | allstop-ticket | ☎ 1599-7788 |
| 3 | 서울역 보증금 환급기 위치 (층, 개찰구 안/밖) | deposit-refund | ☎ 1599-7788 또는 현장 |
| 4 | 직통·일반열차 개찰구 위치와 표지판 문구 | arex-train-types, allstop-ticket | 현장 (임시로는 구글 스트리트뷰) |

### 2순위: 시연에 나오지만 "확인되지 않음"으로 버틸 수 있음

| # | 확인할 것 | 문서 | 방법 |
|---|---|---|---|
| 5 | 발매기 화면 버튼 이름과 순서 (QA Q11) | express-ticket, allstop-ticket | 현장 사진 |
| 6 | B3 고객안내센터 운영 시간, 외국어 응대, 하는 일 | seoul-help-desks | ☎ 1599-7788 |
| 7 | B2 트래블센터가 하는 일과 운영 시간 | seoul-help-desks | ☎ 1599-7788 |

### 3순위: 정확성 보완

| # | 확인할 것 | 문서 | 방법 |
|---|---|---|---|
| 8 | 공항철도 콜센터의 외국어 응대 여부 | seoul-help-desks | 1599-7788에 전화하면 바로 확인 |
| 9 | 환급기 오류 때의 공식 안내 | deposit-refund | ☎ 1599-7788 |
| 10 | 엠패스 현재 판매 여부와 이용 노선 | foreigner-transit-cards | ☎ 티머니 1644-0088 |
| 11 | 코리아투어카드를 지금도 교통카드로 쓸 수 있는지 | foreigner-transit-cards | ☎ 1644-0088 |
| 12 | 1330 언어별 운영 시간 | seoul-help-desks | 한국관광공사 (언어 목록과 번호는 확인함) |

### 4순위: 낮음

| # | 확인할 것 | 문서 |
|---|---|---|
| 13 | 버스 앞문 승차·뒷문 하차, 버스 현금 | seoul-transit-basics |
| 14 | 서울역 근처 WOWPASS 환전기 위치, WOWPASS 발급 비용 | wowpass, fare-passes-cards |
| 15 | 역 이름 공식 영문 표기, 보증금 문서 영문 | arex-train-types, deposit-refund |

**전화 한 번으로 많이 풀립니다.**
- 공항철도 1599-7788: #1, 2, 3, 6, 7, 8, 9
- 티머니 1644-0088: #10, 11

전화로 확인한 내용은 `source_kind: field_check`로 바꾸고, 확인한 사람·날짜·"콜센터 문의"를 남기면 됩니다.

### 오늘 해결한 것

- 기후동행카드를 직통열차에 쓸 수 있는지: **안 됨.** 티머니 안내의 "기본운임 1,550원 이하 대중교통만" 규칙 때문
- 1330 지원 언어 8개와 해외 번호: 한국관광공사 안내로 확인
- 티머니를 해외 카드로 충전할 수 있는지: **안 됨.** 선불카드 충전은 현금만 (서울시 2025-09)

## B. 다시 봐야 할 초안 (`docs/verification-checklist.md`의 미체크 항목)

- [ ] fare-arex-allstop: 역간 운임 전체 표 (서울 열 말고 나머지 칸)
- [ ] fare-passes-cards: 청소년 요금
- [ ] seoul-help-desks: 1330 언어·번호, 112/119 (확인 뒤 추가됨)
- [ ] climate-card-short-term: 직통열차 사용 불가 문장 (확인 뒤 추가됨)
- [ ] allstop-ticket: 보류 (A-2 확인 뒤)

## C. R3의 다른 일

| 할 일 | 필요한 것 | 비고 |
|---|---|---|
| pgvector 로컬 검증 | `brew install pgvector` 또는 Docker 허락 | CI(GitHub)의 실제 pgvector DB에서는 적재·검색 테스트 통과함 |
| 실제 임베딩으로 적재·평가 | OpenAI 키, 비용 승인 | 적재 후 `RAG_BACKEND=pgvector uv run python eval/retrieval.py` |
| 버전 태그 `v0.1.0` | 공개 시점 결정 | R4가 `pip install ...@v0.1.0`로 연결 (RQ-02) |
| CI 계약 테스트 켜기 | 레포 관리자가 `TEAM_REPO_TOKEN` 등록 (RQ-14) | 지금은 옆 레포가 없어서 skip |
| 별칭 사전 지도 반영 | R4 (RQ-27) | `poi/` 초안 완성 |
| 검색 임계값 확정 | R6 (RQ-12) | 평가셋 기준 0.25 적용 |
| QA 정답 근거 반영 | R6 (RQ-13) | `docs/qa-source-map.md` |
| 촬영·개인정보 절차 결정 | 팀 (RQ-29) | `docs/photo-privacy.md` 초안 |
| 현장 답사 | 촬영 허가 (R1) | 개찰구, 버튼, 환급기, 실제 표지판 사진 → `localization/` 카드를 `status: field`로 |
| 출처 재확인 | 정기적으로 | `tests/test_freshness.py`가 요금 90일, 그 밖 180일이 지나면 실패해서 알려 줌 |
