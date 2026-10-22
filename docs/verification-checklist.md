# 공식 문서 사람 재확인 체크리스트

모든 공식 문서는 지금 `verified_by: claude-draft`입니다. 초안 작성 도구가 출처 페이지를 열어 옮겨 적었다는 뜻이고, 사람이 대조하지는 않았습니다.

**확인하는 방법**
1. 각 문서의 출처 URL을 브라우저로 엽니다.
2. `knowledge/<doc_id>.md`의 `## ko` 본문과 한 줄씩 대조합니다.
3. 영어 절은 국문과 뜻이 같은지만 봅니다. 대부분 국문 공식 안내를 옮긴 것입니다.
4. 맞으면 머리말을 `verified_by: <이름>`, `verified_at: <확인한 날짜>`로 바꿉니다.
5. 틀린 부분은 고치고, 확인이 안 되는 부분은 `<!-- TODO(R3): ... -->`로 옮깁니다.
6. 마친 뒤 `uv run pytest -q`로 형식 검사를 돌립니다.

**순서**: 숫자가 많은 문서(오타가 곧 오답)와 자동으로 읽기 어려웠던 문서부터 배치했습니다.

## 1. 숫자가 많은 요금 문서 (먼저)

- [ ] **doc-fare-arex-allstop**: 공항철도 일반열차 요금 (서울역 출발)
  - <https://www.airportrailroad.com/train/normal/fare>
  - **주의**: 요금표(삼각형 표)를 텍스트로 풀어 읽었습니다. "역간 기준운임" 표의 **서울 열**을 위에서 아래로 따라가며 확인하세요.
    - 공덕·홍대입구·DMC 1,550
    - 마곡나루·김포공항 1,750
    - 계양 1,950, 검암 2,050, 청라국제도시 2,150
    - 영종 3,350, 운서 3,850, 공항화물청사 4,450
    - 인천공항1터미널 4,750, 2터미널 5,350
  - 표 아래 주석: 1회용 +100원, 보증금 500원
  - 어린이·청소년 운임 규칙(기본운임 550원/900원, 추가운임 50%/80%)
- [x] **doc-fare-arex-express**: 공항철도 직통열차 요금
  - <https://www.airportrailroad.com/train/express/introduce>
  - "열차운임": 어른 13,000, 정상운임 18,500(1터미널)/19,100(2터미널), 어린이 9,500
  - "직통열차 할인 정보" 표: 할인 대상, 중복 불가
- [ ] **doc-fare-passes-cards**: 패스·카드 가격과 수수료
  - 기후동행카드 단기권 1/2/3/5/7일권 5,000/8,000/10,000/15,000/20,000, 실물카드 3,000
    - <https://news.seoul.go.kr/traffic/archives/510651>
    - <https://pay.tmoney.co.kr/ncs/pct/ugd/ReadClmtAcmpCardFrgnGd.dev>
  - 해외 카드 수수료 평균 3.7%: <https://news.seoul.go.kr/traffic/archives/516544>
  - 엠패스 가격표, 오후 5시 이후 가격, 보증금 5,000 / 반납 4,500
    - <https://pay.tmoney.co.kr/ncs/pct/tmnyintd/ReadFrgnMpassIntd.dev>
  - 티머니트래블카드 4,000, 트래블카드+ 6,000
    - <https://pay.tmoney.co.kr/ncs/pct/tmnyintd/ReadFrgnKoreaTourCardIntd.dev>
  - 티머니 충전 1,000~90,000원, 최대 잔액 500,000원, 환불 수수료 500원
    - <https://pay.tmoney.co.kr/ncs/pct/ugd/ReadFrgnGd.dev>
  - WOWPASS 출금 수수료 1,000원, 1회 10만 원: <https://www.wowpass.io/ko/guide>

## 2. 자동으로 읽지 못해 사람 확인이 꼭 필요한 문서

- [x] **doc-wowpass**: WOWPASS 사용법
  - <https://www.wowpass.io/ko/guide>
  - 페이지가 스크립트로 그려져 자동 수집이 안 됐습니다. **붙여 넣은 텍스트**를 기준으로 썼습니다.
  - 확인할 것: 두 잔액이 별개라는 점, 16종 통화 목록, 티머니 환불 금액 구간(2만/3만/5만 원), 잔액 유효기간 6년
- [x] **doc-seoul-help-desks**: 서울역 공항철도에서 도움받을 곳
  - B3 고객안내센터, B2 Express Train Tickets·Travel Center·City Airport Terminal
    - <https://www.airportrailroad.com/static/file/emergency_seoul.pdf> (안내도)
    - <https://www.airportrailroad.com/train/normal/info/010/0> (페이지 아래 층별 설명)
  - 도심공항터미널 시간(탑승수속 05:20~19:00, 마감 18:50, 출국심사 05:30~19:00, 3시간 / 3시간 20분 전)
    - <https://www.airportrailroad.com/train/express/city/info>
  - 콜센터 1599-7788 (06:30~23:00): <https://www.airportrailroad.com/help/faq> (냉난방 질문 답변 안)
  - 1330 설명: <https://www.gongju.go.kr/en/sub02_01_02.do>
    - 한국관광공사 원문을 못 열어서 지자체 안내 기준으로 썼습니다. 가능하면 한국관광공사 페이지로 교체해 주세요.
  - 120 → 9번 외국어 상담: <https://pay.tmoney.co.kr/ncs/pct/ugd/ReadFrgnGd.dev> (페이지 맨 위)
  - 유실물센터 032-745-7777, 역무실 032-745-7400: 서울역 안내 페이지 아래 "문의안내"

## 3. 시연 시나리오 핵심 문서

- [x] **doc-express-ticket**: 직통열차 승차권 구매 (서울역)
  - <https://www.airportrailroad.com/train/express/introduce> ("승차권 구입 및 타는 곳")
  - <https://www.airportrailroad.com/train/normal/info/010/0> (지하 2층 설명: 트레블센터 근처 발매기, 도심공항터미널)
  - <https://www.airportrailroad.com/static/file/emergency_seoul.pdf> (영문 시설명)
  - 참고: 역 안내 페이지는 "트레블센터", 안내도는 "트래블센터"로 표기가 다릅니다. 문서는 안내도 표기를 따랐습니다.
- [ ] (보류) **doc-allstop-ticket**: 일반열차 타는 방법
  - <https://www.airportrailroad.com/train/normal/introduce> ("승차권 구입 및 타는 곳")
  - <https://www.airportrailroad.com/train/normal/info/010/0> (지하 3층 설명)
  - <https://www.airportrailroad.com/static/file/emergency_seoul.pdf> (영문 시설명)
  - 해외 신용카드로 1회용 교통카드 구매 (2025-02): <https://english.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=221111>
- [x] **doc-arex-train-types**: 공항철도 열차 종류
  - 직통열차 노선, 무정차, 지정좌석, 43분/51분: <https://www.airportrailroad.com/train/express/introduce>
  - 일반열차 정차역, 59분/66분(+2~6분): <https://www.airportrailroad.com/train/normal/introduce>
  - 승강장 지하 7층: <https://www.airportrailroad.com/train/normal/info/010/0>, <https://www.airportrailroad.com/static/file/emergency_seoul.pdf>
- [x] **doc-deposit-refund**: 1회용 교통카드 보증금 환급
  - 보증금 500원, 환급기, 분실·훼손 시 환급 불가, 수도권 도시철도만: <https://news.seoul.go.kr/traffic/archives/1763>
  - 발급·태그·환급 순서: <http://www.seoulmetro.co.kr/kr/page.do?menuIdx=355> (영문: <http://www.seoulmetro.co.kr/en/page.do?menuIdx=644>)
  - 서울역 보증금 환급기 3대: <https://www.airportrailroad.com/train/normal/info/010/0> ("역무자동화 설비". 원문 오타 "보증급")
  - 개찰구 나간 뒤 환급기: <https://english.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=221111>

## 4. 교통카드·패스 문서

- [x] **doc-climate-card-short-term**: 기후동행카드 단기권
  - 권종, 이용 범위(2026-10-01부터), 인천공항역은 내리기만, 판매처: <https://news.seoul.go.kr/traffic/archives/510651>
  - 미리 충전 불가, 애플페이 불가, 외국인 구매: <https://news.seoul.go.kr/traffic/public/climatecard-faq/faq-short> (Q14·Q15·Q71·Q95·Q98)
  - 30일권 종료, 단기권 계속: <https://news.seoul.go.kr/traffic/public/climatecard-faq/faq-stop> (Q3·Q5)
  - 기후동행패스는 서울시민용: <https://news.seoul.go.kr/traffic/archives/518138>
  - 해외 카드 구매·충전 (2026-03-17~): <https://news.seoul.go.kr/traffic/archives/516544>
  - 공항철도 서울역~김포공항 구간, **공항철도·코레일 역에서 충전 불가**, 환불 절차, 편의점 결제 불가: <https://pay.tmoney.co.kr/ncs/pct/ugd/ReadClmtAcmpCardFrgnGd.dev>
- [x] **doc-foreigner-transit-cards**: 티머니트래블카드, 엠패스, 코리아투어카드
  - 트래블카드·트래블카드+ 특징과 판매처, 코리아투어카드 판매 중단: <https://pay.tmoney.co.kr/ncs/pct/tmnyintd/ReadFrgnKoreaTourCardIntd.dev>
  - 엠패스 이용 범위(공항철도 일반열차, 급행 제외), 하루 20회, 티머니타운 발급(평일 09~18시), 하루 계산 방식: <https://pay.tmoney.co.kr/ncs/pct/tmnyintd/ReadFrgnMpassIntd.dev>
- [x] **doc-tmoney-card**: 티머니 충전과 환불
  - <https://pay.tmoney.co.kr/ncs/pct/ugd/ReadFrgnGd.dev> (Top-up, Refund 절)
- [x] **doc-seoul-transit-basics**: 서울 지하철·버스 타는 법
  - 환승 할인 대상(공항철도 포함), 30분/60분, 최대 4회, 하차 태그, 5시간/1시간 규칙: <https://news.seoul.go.kr/traffic/transfer_discount>
  - 1~8호선 신형 발매기 해외 카드: <https://news.seoul.go.kr/traffic/archives/516544>
  - 1회용 교통카드는 도시철도만: <https://news.seoul.go.kr/traffic/archives/1763>
  - 개찰구 오른쪽 단말기: <http://www.seoulmetro.co.kr/kr/page.do?menuIdx=355>

## 확인하지 않아도 되는 것

- `doc-community-*` 문서 2개는 이용자 후기 기반 미확인 문서입니다(`source_kind: community`). 사실 확인 대상이 아니라 공식 확인이 되면 공식 문서로 옮길 후보입니다.

## 확인 기록

### 2026-10-22 R3 1차 확인

**확인 완료 (`verified_by: R3`)**: fare-arex-express, wowpass, seoul-help-desks, express-ticket, arex-train-types, deposit-refund, climate-card-short-term

**확인 중 반영한 수정**
- fare-arex-express: 할인 요금 9,500원(어린이·경로·장애인·국가유공자)
- wowpass: 무인환전기 화폐·권종, 출금 안내(10만 원씩, 1회 1,000원), 6년 유효, 1,000원 미만 동전 출금 불가, 티머니 잔액은 따로 환급
- seoul-help-desks·climate-card: 다산콜 외국어 상담은 평일 09:00~18:00, 지원 언어 5개 ([서울시 미디어허브](https://mediahub.seoul.go.kr/archives/2019488))

**R3 확인 뒤 초안 도구가 새로 넣은 내용 (`claude-draft` 유지, 다시 봐야 함)**
- [ ] fare-arex-allstop: **역간 기준운임 전체 표** 추가 (서울 열은 R3 확인 완료, 나머지 칸은 같은 공식 표에서 옮김)
- [ ] fare-passes-cards: 청소년 요금 추가
  - 기후동행카드 청소년 7일권 13,000원, 2026-09-01부터, 청소년 인증 필요 ([FAQ](https://news.seoul.go.kr/traffic/public/climatecard-faq/faq-short))
  - 지하철 기본운임 어른 1,550원 / 청소년 900원 / 어린이 550원 ([미디어허브](https://mediahub.seoul.go.kr/archives/2017343))
  - 티머니 생년월일 등록 필요
  - 엠패스는 청소년 가격 안내 없음
- [x] tmoney-card
  - 충전처를 GS25·CU·세븐일레븐·이마트24 등으로 줄임 (미니스톱·365PLUS는 뺌)
  - 선불카드 충전은 현금만 ([미디어허브 2025-09](https://mediahub.seoul.go.kr/archives/2015499))
  - 환불 문구 일반화
  - 청소년·어린이 등록 추가
- [x] seoul-transit-basics: 하차 미태그 페널티 추가 (2026-03-07부터, 1,550/900/550원, 정기권·1회권·우대권 제외, [미디어허브](https://mediahub.seoul.go.kr/archives/2017343))
- [x] foreigner-transit-cards: 엠패스 최신 여부 TODO 추가

**보류**
- allstop-ticket: 공항철도 1회용 교통카드의 **해외 발행 카드 지원 범위**를 자세히 확인해야 함.
  - 시작일이 자료마다 다름: 2024-12-19, 2024-12-27
  - 공항철도 공지사항은 검색되지 않았음
  - 한국관광공사(2025-02)는 "본국 신용카드로 가능"이라고 함
  - 다음 단계: 공항철도 콜센터 1599-7788

- 2026-10-22: R3 확인 완료 추가 (foreigner-transit-cards, tmoney-card, seoul-transit-basics). allstop-ticket은 해외 카드 확인 전까지 보류

### 2026-10-22 R3 확인 뒤 초안 도구가 추가한 내용 (다시 봐야 함)

- [ ] seoul-help-desks
  - 1330 지원 언어 8개와 해외 번호 +82-2-1330, 긴급 번호 경찰 112·화재/구급 119
  - 출처: [한국관광공사 Emergency Situations](https://english.visitkorea.or.kr/svc/contents/contentsView.do?vcontsId=140042&menuSn=376)
- [ ] climate-card-short-term
  - "기본운임 1,550원 이하 대중교통만(심야버스 예외)" → 직통열차(13,000원)에는 사용 불가
  - 출처: [티머니 기후동행카드 안내](https://pay.tmoney.co.kr/ncs/pct/ugd/ReadClmtAcmpCardFrgnGd.dev) "Usage" 절
- 온라인 재시도 실패: 공항철도 역 이름 공식 영문 표기 (AREX 영문 페이지 경로를 찾지 못함), 서울역 근처 WOWPASS 무인환전기 위치 (WOWPASS 사이트가 스크립트로만 표시)
