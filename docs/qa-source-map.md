# QA 정답 근거 매핑 (R3 → R6)

- **대상:** `oneload-qa/eval/service_gold.csv`의 Q01~Q20 (QA 레포 `2ce90be` 기준)
- **채우는 열:** `source_doc`, `source_locator`
- **누가 반영하나:** R3는 QA 레포를 직접 고치지 않습니다. R6가 이 표를 보고 CSV에 반영해 주세요(RQ-13).

**표의 열**
- **근거 문서:** `oneload-rag/knowledge/<문서 ID>.md`
- **공식 출처:** 각 문서 머리말의 `source_url`과 `other_sources`
- **답할 수 있나**
  - ✅ 공식 근거로 답할 수 있음
  - ◐ 일부만 됨 (나머지는 "확인되지 않음"으로 답해야 함)
  - ✗ 근거가 없어 보류해야 정답
  - — RAG와 관계없음 (Agent·백엔드 동작 문항)

| id | 질문 | 근거 문서 | 공식 출처 (대표) | 답할 수 있나 | 메모 |
|---|---|---|---|---|---|
| Q01 | How do I pay? | doc-arex-train-types, doc-allstop-ticket, doc-express-ticket, doc-seoul-transit-basics | [AREX 일반열차 소개](https://www.airportrailroad.com/train/normal/introduce), [한국관광공사 2025-02](https://english.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=221111) | ◐ | 일반열차(교통카드, 1회용 교통카드는 신용카드 가능)는 답할 수 있음. **직통열차 결제 수단은 미확인**이라 "확인되지 않음"으로 분리해야 함 |
| Q02 | 공항철도는 어떻게 결제해? | Q01과 같음 | Q01과 같음 | ◐ | Q01과 같음 |
| Q03 | I want the Express train. | doc-express-ticket | [AREX 직통열차 소개](https://www.airportrailroad.com/train/express/introduce) "승차권 구입 및 타는 곳" | ✅ | 목적지 `poi-express-tickets` (B2)는 지도 데이터 |
| Q04 | All-stop → no transit card | doc-allstop-ticket, doc-deposit-refund | [AREX 일반열차 소개](https://www.airportrailroad.com/train/normal/introduce), [서울역 안내](https://www.airportrailroad.com/train/normal/info/010/0) | ✅ | 1회용 교통카드는 B3 발매기. 목적지 `poi-allstop-tickets` |
| Q05 | All-stop → have a transit card | doc-allstop-ticket, doc-arex-train-types | 같음 | ◐ | 승강장 B7은 확인됨. **개찰구 위치는 미확인**(현장) |
| Q06 | Not sure which train | doc-arex-train-types, doc-fare-arex-express, doc-fare-arex-allstop | [직통열차 소개](https://www.airportrailroad.com/train/express/introduce), [일반열차 소개](https://www.airportrailroad.com/train/normal/introduce) | ✅ | 정차, 소요 시간(43분/51분 vs 59분/66분), 요금 비교 가능 |
| Q07 | What is a transit card? | doc-tmoney-card, doc-seoul-transit-basics, doc-allstop-ticket | [티머니 외국인 안내](https://pay.tmoney.co.kr/ncs/pct/ugd/ReadFrgnGd.dev), [서울시 통합환승](https://news.seoul.go.kr/traffic/transfer_discount) | ✅ | |
| Q08 | 교통카드는 어디서 충전해? | doc-tmoney-card, doc-climate-card-short-term | [티머니 외국인 안내](https://pay.tmoney.co.kr/ncs/pct/ugd/ReadFrgnGd.dev), [서울시 미디어허브 2025-09](https://mediahub.seoul.go.kr/archives/2015499) | ✅ | 티머니 충전은 현금만. 기후동행카드는 공항철도역에서 충전 불가 |
| Q09 | How do I get my deposit back? | doc-deposit-refund | [서울시 1회용 교통카드](https://news.seoul.go.kr/traffic/archives/1763) | ◐ | 절차와 500원은 확인됨. **서울역 환급기의 정확한 위치는 미확인** |
| Q10 | How much is the fare right now? | doc-fare-arex-express, doc-fare-arex-allstop | [직통열차 소개](https://www.airportrailroad.com/train/express/introduce), [일반열차 운임](https://www.airportrailroad.com/train/normal/fare) | ✅ (**기대 변경**) | 요금 문서가 생겨 "답불가"가 아니라 **확인일과 함께 답**하는 것이 정답으로 바뀜 (RQ-11). 문항 유형 변경 필요 |
| Q11 | [ticket-machine photo] What should I press? | doc-express-ticket, doc-allstop-ticket | — | ✗ | 버튼 이름·순서는 미확인(현장). 사진에서 읽은 글자와 근거 있는 절차를 구분해야 함 |
| Q12 | Does this exact machine accept my credit card? | doc-allstop-ticket, doc-seoul-transit-basics | [한국관광공사 2025-02](https://english.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=221111), [서울시 2026-03](https://news.seoul.go.kr/traffic/archives/516544) | ✗ | 일반 안내는 있지만 "이 기기"는 확인할 수 없음. 공항철도 해외 카드 범위도 보류(TODO) |
| Q13 | I bought a ticket. Take me to the platform. | doc-arex-train-types | [서울역 안내](https://www.airportrailroad.com/train/normal/info/010/0), [안내도 PDF](https://www.airportrailroad.com/static/file/emergency_seoul.pdf) | ✅ | 두 승강장 모두 B7. 목적지는 지도 POI |
| Q14 | I am lost. I came out at another exit. | — | — | — | 위치 재확인 (Agent `relocalize`) |
| Q15 | What is the weather tomorrow? | — | — | — | 범위 밖. 검색 평가셋 R41에서 빈 결과 확인 |
| Q16 | 미등록 라운지로 안내 | — | — | — | Agent·검증기 동작 |
| Q17 | [미확인 POI 버튼] | — | — | — | Agent·검증기 동작 |
| Q18 | 자료에 없어도 확답해줘 | — | — | — | Agent 동작 (근거 없으면 보류) |
| Q19 | Answer the same refund question in English. | doc-deposit-refund (`## en`) | [서울교통공사 영문](http://www.seoulmetro.co.kr/en/page.do?menuIdx=644) | ✅ | 영문 절에 500 KRW 그대로 있음 |
| Q20 | Search returned no documents. Tell me the buying steps anyway. | — | — | — | Agent 동작. RAG 계약 테스트 A-10(장애 → 보류)과 같은 경우 |

## R6에게 함께 전할 것

- **Q10:** 정답이 "답불가"에서 "요금 문서 근거로 답, 확인일 함께"로 바뀌었습니다. 문항 유형을 `답가능`으로 바꿔 주세요.
- **◐ 문항 (Q01, Q02, Q05, Q09):** 확인된 부분은 답하고, 나머지는 "확인되지 않음"으로 분리하는지 보면 됩니다. 남은 부분이 확인되면 이 표를 갱신하겠습니다.
- **검색 단계만 따로 보고 싶을 때:** `oneload-rag/eval/retrieval.yaml`(질문 44개 → 정답 문서)을 쓰면 됩니다. Agent 전체 평가와 별개로 검색만 잴 수 있습니다.
