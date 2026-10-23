# 실제 LLM으로 Agent 답변 확인 (2026-10-23)

RQ-32("문서에 답이 없으면 답하지 않기, 인용한 자료만 출처로")가 실제로 어떻게 동작하는지 보려고, 백엔드 API + R2 Agent + R3 검색을 조립하고 LLM만 OpenAI로 바꿔 돌렸습니다.

- 조합: backend `b1aa5f5`, agent `eca420e`, rag `0138208`(v0.3.0 문서), 지도 `2026-10-23.1`
- 모델: gpt-4o-mini (agent 기본값). 질문 16개 + 대화 4개, 비용은 몇십 원 수준
- 재현: `set -a; . ../.env; set +a; uv run --project ../oneload-backend --with ../oneload-rag python scripts/agent_live_check.py`
- 한 번씩 돌린 결과입니다(12번만 3번 돌려 같은 결과 확인). LLM 답변은 실행마다 조금 다를 수 있습니다.

## 1. 질문 16개

`out` = 문서에 답이 없는 질문(금액을 말하지 않고 관련 없는 출처를 붙이지 않아야 함), `in` = 문서에 답이 있는 질문

| # | 기대 | 질문 | 상태 | 금액 언급 | 출처 | 답변 |
| 1 | out | 서울역에서 인천공항 가는 리무진버스 승차권은 얼마인가요? | cannot_answer | - | - | 확인된 자료가 없어서 추측하지 않을게요. 역 안내센터에 문의해 주세요. |
| 2 | out | What does a KTX ticket from Seoul Station to Busan cost? | cannot_answer | - | - | I don't have verified information on that, so I won't guess. Please ask the information center. |
| 3 | out | 택시 기본요금이 얼마예요? | cannot_answer | - | - | 확인된 자료가 없어서 추측하지 않을게요. 역 안내센터에 문의해 주세요. |
| 4 | out | 인천공항에서 항공사 위탁수하물 추가 요금을 조회해 주세요. | cannot_answer | - | - | 확인된 자료가 없어서 추측하지 않을게요. 역 안내센터에 문의해 주세요. |
| 5 | out | What is the passport replacement fee near Seoul Station? | cannot_answer | - | - | I don't have verified information on that, so I won't guess. Please ask the information center. |
| 6 | out | 서울에서 출발하는 항공권 가격을 조회해 줘 | cannot_answer | - | - | 확인된 자료가 없어서 추측하지 않을게요. 역 안내센터에 문의해 주세요. |
| 7 | out | 공항 라운지 이용하는 방법 알려줘 | cannot_answer | - | - | 확인된 자료가 없어서 추측하지 않을게요. 역 안내센터에 문의해 주세요. |
| 8 | out | 서울역 근처 호텔 객실 가격 알려줘 | out_of_scope | - | - | 지금은 서울역 공항철도 구역을 도와드려요. 승차권 · 교통카드 · 가는 길을 물어보세요. |
| 9 | in | 직통열차 표는 발매기에서 해외 카드로 살 수 있어요? | answered | - | express-ticket, climate-card-short-term, seoul-help-desks | 직통열차 표는 발매기에서 해외 발행 신용카드로 구매할 수 있습니다[1]. |
| 10 | in | Can I pay for the Express train ticket with a foreign credit card? | answered | - | express-ticket, climate-card-short-term, allstop-ticket | Yes, you can pay for the Express train ticket with a foreign credit card. Accepted foreign-issued cards include Visa, Mastercard, JCB, Diners Club, American Express, and UnionPay [1]. |
| 11 | in | 공항철도에서 내려서 1호선 타려면 어디로 가요? | needs_clarification | - | - | 지금 1회용 교통카드를 가지고 있나요? |
| 12 | in | How do I get to the KTX from the AREX platform at Seoul Station? | cannot_answer | - | - | I don't have verified information on that, so I won't guess. Please ask the information center. |
| 13 | in | 직통열차 표로 지하철 탈 수 있어요? | answered | - | arex-train-types, express-ticket, fare-arex-express | 직통열차 승차권으로 지하철을 탈 수 없습니다. 직통열차는 타기 전에 승차권을 따로 사야 하며, 교통카드로 개찰구를 지나는 방식이 아닙니다[3]. 따라서 지하철 이용 시 별도의 승차권이나 교통카드를 구매해야 합니다[3]. |
| 14 | in | 보증금 환급은 어떻게 해? | answered | - | deposit-refund, allstop-ticket | 보증금 환급은 1회용 교통카드를 이용한 후, 도착역에서 개찰구를 나간 뒤에 있는 「보증금 환급기」에 카드를 넣으면 된다[1]. 카드를 잃어버리거나 훼손하지 않았다면 언제든지 보증금을 돌려받을 수 있다[1]. 단, 본인 부주의로 잃어버리거나 훼손한 경우에는 환급이 불가능하다[1]. |
| 15 | in | 직통열차 요금 얼마야? | answered | 있음 | fare-arex-express | 직통열차 요금은 어른 13,000원, 어린이(만 6세 이상 13세 미만) 9,500원입니다[1]. 정상운임은 서울역~인천공항1터미널 18,500원, 서울역~인천공항2터미널 19,100원입니다[1]. 할인 요금은 9,500원으로, 어린이, 경로, 장애인등록증 소지자, 국가유공자 증명서 소지자가 대상입니다[1]. |
| 16 | in | 서울역 공항철도 승강장은 몇 층이에요? | answered | - | arex-train-types, seoul-arex-transfer, seoul-help-desks | 서울역 공항철도 승강장은 지하 7층에 있습니다 [2]. |

## 2. 메인 시나리오 대화

### (ko)
- 사용자: 공항철도에서 내려서 1호선 타려면 어디로 가요?
  - needs_clarification / 출처 [] / 목적지 None / 버튼 ['가지고 있어요', '없어요']
  - 답: 지금 1회용 교통카드를 가지고 있나요?
- 사용자: 교통카드 있어요
  - cannot_answer / 출처 [] / 목적지 None / 버튼 []
  - 답: 확인된 자료가 없어서 추측하지 않을게요. 역 안내센터에 문의해 주세요.

### (en)
- 사용자: I just arrived on the AREX. How do I transfer to Line 4?
  - answered / 출처 ['seoul-arex-transfer', 'seoul-transit-basics', 'allstop-ticket'] / 목적지 None / 버튼 []
  - 답: To transfer to Line 4 from the AREX, go to B3 (basement level 3) and follow the signs for "Transfer to Line 1, Line 4." A moving walkway will take you to Line 4, but if you have heavy luggage, it's recommended to use the elevator instead [1].
- 사용자: I have a T-money card
  - answered / 출처 ['fare-passes-cards', 'tmoney-card', 'wowpass'] / 목적지 None / 버튼 []
  - 답: You can use your T-money card for subway and bus rides in Korea, but make sure to register your birth date to access youth or child fares if applicable [2]. You can top up your card with Korean won cash at designated convenience stores or subway station machines [2]. If you need to refund your balan

### (en)
- 사용자: I want to go to Incheon Airport. Where do I buy an Express ticket?
  - destination_set / 출처 ['express-ticket', 'arex-train-types', 'fare-arex-express'] / 목적지 poi-express-tickets / 버튼 []
  - 답: You need to buy the ticket or travel card first. You can buy an Express ticket at the "Express Train Tickets" customer service center on B2 of Seoul Station [1]. Alternatively, there are ticket machines near the Travel Center in the middle of B2 [1]. I'll take you to the Express ticket counter, on B
- 사용자: Can I pay with my Visa card?
  - destination_set / 출처 ['express-ticket', 'arex-train-types', 'fare-arex-express'] / 목적지 poi-express-tickets / 버튼 []
  - 답: You need to buy the ticket or travel card first. Yes, you can pay with your Visa card at the Express ticket machines. Both Korean and foreign-issued credit cards, including Visa, are accepted for purchasing tickets [1]. I'll take you to the Express ticket counter, on B2. First, take a photo of a nea

### (ko)
- 사용자: 공항 가는 일반열차 타고 싶어요
  - needs_clarification / 출처 [] / 목적지 None / 버튼 ['구입했어요', '아직 안 샀어요']
  - 답: 승강장으로 안내하기 전에 확인할게요. 필요한 승차권이나 교통카드를 이미 구입했나요?
- 사용자: 교통카드 없어요
  - needs_clarification / 출처 [] / 목적지 None / 버튼 ['구입했어요', '아직 안 샀어요']
  - 답: 승강장으로 안내하기 전에 확인할게요. 필요한 승차권이나 교통카드를 이미 구입했나요?

## 3. 정리

**잘 되는 것**
- **범위 밖 8개 모두 안전:** 금액을 말하지 않았고 출처도 붙이지 않았습니다. R2가 Agent에 넣은 답변 검증(LLM이 "이 답이 질문에 맞는가"를 다시 판단, `response_relevance_rejected`)이 걸러 냅니다. RQ-32의 1·3번은 이미 반영된 셈입니다.
- 직통열차 결제 수단(해외 카드), 보증금 환급, 직통열차 요금, 승강장 층, 영어로 묻는 4호선 환승은 문서대로 답합니다.
- 직통열차 표 사는 곳은 목적지(B2)까지 잡고, 같은 대화에서 Visa 결제 질문에도 답합니다.

**문제 (담당)**
1. **"공항철도에서 내려서 1호선 타려면?"(한국어 대화) → 되묻기 뒤 "자료 없음" (R4·R2):** Agent가 길 안내(`navigate_to_poi`)로 처리하려는데 지도에 1·4호선·KTX 목적지(POI)가 없어 막히는 것으로 보입니다. 같은 내용을 영어로 물으면(길 안내 아님) 환승 문서로 잘 답합니다. "How do I get to the KTX ..." 도 같은 이유로 "자료 없음"(12번, 3회 재현). 메인 시나리오의 핵심 질문이라 우선순위가 높습니다.
2. **되묻기 버튼과 다른 자유 답변이면 같은 질문 반복 (R2):** "필요한 승차권이나 교통카드를 이미 구입했나요? [구입했어요 / 아직 안 샀어요]"에 "교통카드 없어요"라고 답하면 같은 질문이 다시 나옵니다.
3. **인용하지 않은 문서도 출처로 붙음 (R2, RQ-32 2번):** 9·10번은 [1]만 인용했는데 기후동행카드 문서 등 3개가 출처로 붙습니다.
4. **"직통열차 표로 지하철 탈 수 있어요?" (R3):** 검색이 환승 문서(약관 제42조)를 못 찾습니다. 질문은 "표", 문서는 "승차권"이라 낱말이 안 겹칩니다. 문서에 "표"를 넣어 봤지만 다른 질문이 흔들려 되돌렸습니다. 대신 Agent가 다른 문서를 근거로 "탈 수 없다"고 추론했습니다(결론은 맞지만 근거 문서가 다름). Agent가 검색어를 다듬어 보내면(`knowledge_query`) 풀릴 수 있습니다.
