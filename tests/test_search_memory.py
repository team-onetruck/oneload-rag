from datetime import date

import pytest

from hangil_rag import MemorySearch, search_knowledge
from hangil_rag.loader import load_docs
from hangil_rag.search_memory import tokens


@pytest.fixture(scope="module")
def search() -> MemorySearch:
    return MemorySearch()


def ids(hits) -> list[str]:
    return [h.document_id for h in hits]


def ctx(train_type: str | None = None) -> dict:
    """Agent 가 넘기는 모양 그대로: {"map_id", "slots": Slots.model_dump()} (agent.py _search)."""
    return {"map_id": "seoul-station", "slots": {"train_type": train_type or "unknown", "has_transit_card": "unknown"}}


def test_allstop_slot_drops_express_only_doc(search):  # A-21
    hits = search("일반열차 승차권 구매 방법", "ko", ctx("allstop"))
    assert "doc-allstop-ticket" in ids(hits) and "doc-express-ticket" not in ids(hits)


def test_express_slot_drops_allstop_only_doc(search):
    hits = search("직통열차 승차권 구매 방법", "ko", ctx("express"))
    assert ids(hits)[0] == "doc-express-ticket" and "doc-allstop-ticket" not in ids(hits)


@pytest.mark.parametrize("context", [ctx(), {}, {"slots": None}])
def test_unknown_train_keeps_all_docs(context):
    hits = MemorySearch(docs=load_docs(include_community=False))("승차권 구매 직통열차 일반열차", "ko", context)
    assert {"doc-express-ticket", "doc-allstop-ticket"} <= set(ids(hits))


def test_train_types_doc_answers_the_difference(search):  # Agent _explain_options 의 검색어
    assert ids(search("직통열차 일반열차 차이", "ko", ctx()))[0] == "doc-arex-train-types"
    assert ids(search("Express vs All-stop difference", "en", ctx()))[0] == "doc-arex-train-types"


def test_language_picks_title_and_excerpt(search):
    ko = search("보증금 환급", "ko", ctx())[0]
    en = search("보증금 환급", "en", ctx())[0]
    assert ko.document_id == en.document_id == "doc-deposit-refund"
    assert ko.title == "1회용 교통카드 보증금 환급" and "보증금 환급기" in ko.excerpt
    assert en.title == "Getting the single-journey ticket deposit back" and "deposit refund machine" in en.excerpt


def test_english_question(search):
    assert ids(search("How do I get my deposit back?", "en", ctx()))[0] == "doc-deposit-refund"
    express = ids(search("Express how to buy a ticket", "en", ctx("express")))  # Agent A-14 의 검색어
    assert express[0] == "doc-express-ticket" and "doc-deposit-refund" not in express  # "ticket" 하나로 붙지 않음


@pytest.mark.parametrize("query", ["내일 날씨 어때?", "", "?!", "the a to"])
def test_nothing_relevant_is_empty(search, query):
    assert search(query, "ko", ctx()) == []


def test_hit_fields(search):
    for h in search("직통열차 일반열차 승차권 보증금", "ko", ctx()):
        assert date.fromisoformat(h.verified_at) and h.scope in {"ticket", "card"}  # 다시 확인하면 날짜가 바뀐다
        assert h.source_url and h.source_url.startswith("http")


@pytest.mark.parametrize(
    ("query", "train", "fare_doc"),
    [
        ("직통열차 요금 얼마야?", "express", "doc-fare-arex-express"),
        ("인천공항까지 일반열차 요금은?", "allstop", "doc-fare-arex-allstop"),
        ("How much is the Climate Card 3-day pass?", None, "doc-fare-passes-cards"),
    ],
)
def test_fare_docs_are_scope_fare_and_follow_train_filter(search, query, train, fare_doc):
    lang = "en" if query.isascii() else "ko"
    fares = [h for h in search(query, lang, ctx(train)) if h.scope == "fare"]
    assert fares and fares[0].document_id == fare_doc
    other = {"express": "doc-fare-arex-allstop", "allstop": "doc-fare-arex-express"}.get(train)
    assert other not in [h.document_id for h in fares]


def test_fare_doc_is_marked_fare(fixture_docs):
    hits = MemorySearch(directory=fixture_docs)("직통열차 요금 얼마야?", "ko", ctx())
    assert hits[0].document_id == "doc-fare" and hits[0].scope == "fare"


def test_fixture_filter_and_top_k(fixture_docs):
    s = MemorySearch(directory=fixture_docs, k=2)
    hits = s("일반열차 직통열차 승차권 요금 종류", "ko", ctx("allstop"))
    assert len(hits) == 2 and "doc-exp" not in ids(hits)


def test_tokens():
    assert {"직통", "통열", "열차", "차는"} <= tokens("직통열차는")
    assert tokens("How do I buy tickets?") == {"buy", "ticket"}


def test_entry_point_uses_memory_search_by_default(monkeypatch):
    monkeypatch.delenv("RAG_BACKEND", raising=False)
    assert ids(search_knowledge("보증금 환급", "ko", ctx()))[0] == "doc-deposit-refund"


@pytest.mark.parametrize(
    ("query", "lang"),
    [("카드 결제가 안 되는데 어디서 도움 받아요?", "ko"), ("Where can I get help at the station?", "en")],
)
def test_help_desks_doc(search, query, lang):
    hits = {h.document_id: h for h in search(query, lang, ctx())}
    assert hits["doc-seoul-help-desks"].scope == "help"


def test_particles_do_not_hide_words(search):
    assert {"표", "표를"} <= tokens("표를") and "철도" in tokens("철도")  # '도' 는 떼지 않음
    official = MemorySearch(docs=load_docs(include_community=False))
    got = ids(official("서울역에 도착했는데 공항철도 표를 어디서 사요?", "ko", ctx()))
    assert "doc-arex-train-types" in got


def test_help_order_puts_station_desks_before_phone_lines(search):
    """창구(고객안내센터 · B2) → 1330(외국인용) → 공항철도 콜센터 → 분실물 · 긴급전화는 마지막."""
    for lang, desk in (("ko", "고객안내센터"), ("en", "Customer Information Center")):
        text = search("도움받을 곳", lang, ctx())[0].excerpt
        order = [text.index(s) for s in (desk, "1330", "1599-7788", "032-745-7777", "032-745-7400")]
        assert order == sorted(order), lang


@pytest.mark.parametrize(
    ("query", "lang", "doc"),
    [
        ("기후동행카드 단기권은 어디서 사요?", "ko", "doc-climate-card-short-term"),
        ("Can I use the Climate Card to Incheon Airport?", "en", "doc-climate-card-short-term"),
        ("버스에서 지하철로 환승 할인 받으려면?", "ko", "doc-seoul-transit-basics"),
        ("How do I transfer between bus and subway?", "en", "doc-seoul-transit-basics"),
    ],
)
def test_transit_and_pass_docs(search, query, lang, doc):
    assert doc in ids(search(query, lang, ctx()))


def test_community_docs_only_when_enabled(monkeypatch):
    query = "해외카드로 직통열차 표를 살 수 있어요?"
    monkeypatch.delenv("RAG_INCLUDE_COMMUNITY", raising=False)
    assert not any(i.startswith("doc-community-") for i in ids(MemorySearch()(query, "ko", ctx())))
    monkeypatch.setenv("RAG_INCLUDE_COMMUNITY", "1")
    assert "doc-community-arex-payments" in ids(MemorySearch()(query, "ko", ctx()))


def test_community_takes_at_most_the_last_slot(monkeypatch):
    monkeypatch.setenv("RAG_INCLUDE_COMMUNITY", "1")
    got = ids(MemorySearch()("승차권 구매 직통열차 일반열차", "ko", ctx()))
    community = [i for i in got if i.startswith("doc-community-")]
    assert len(community) <= 1 and (not community or got[-1] == community[0])


# ── RAG #3: 범위 밖 · 실시간 질문은 빈 결과, 기존 정답은 유지 ─────────────────────────────
@pytest.mark.parametrize(
    "query",
    [
        "서울역 근처 호텔 객실 가격 알려줘",  # RAG #3 재현 질문 1
        "지금 서울역 직통열차 빈 좌석이 몇 개 남았나요?",  # RAG #3 재현 질문 2
        "서울역에서 저녁 먹을 식당을 예약해 줘",
        "인천공항 내일 날씨 알려주세요",
    ],
)
def test_out_of_scope_questions_are_empty(query):
    assert MemorySearch(docs=load_docs(include_community=False))(query, "ko", {"slots": {}}) == []


@pytest.mark.parametrize(
    "query",
    [
        "Are there seats left on the Express?",
        "How many seats are left?",
        "직통열차 잔여석",
        "실시간 좌석 현황",
        "남은 자리 있어요?",
    ],
)
def test_realtime_questions_are_empty(query):
    assert MemorySearch(docs=load_docs(include_community=False))(query, "ko", {"slots": {}}) == []


def test_price_words_find_fare_docs():
    """'얼마' 처럼 요금이라는 낱말이 없어도 요금 문서를 찾는다."""
    got = ids(MemorySearch()("서울역에서 직통열차 성인 승차권은 얼마인가요?", "ko", ctx("express")))
    assert "doc-fare-arex-express" in got


def test_demonstratives_do_not_make_a_question_out_of_scope():
    """'이거 뭐 눌러?' 의 '이거' 는 영어 this 처럼 기능어다 (발매기 사진 질문)."""
    assert MemorySearch()("직통열차 이거 뭐 눌러?", "ko", ctx("express"))


# ── RAG #3 후속: 가격 질문은 우리 문서가 값을 매긴 대상(priced)일 때만 ──────────────────────
def official() -> MemorySearch:
    return MemorySearch(docs=load_docs(include_community=False))


@pytest.mark.parametrize(
    ("query", "lang"),
    [
        ("택시 기본요금이 얼마예요?", "ko"),  # 택시는 문서에 있지만 값을 매기지 않는다
        ("부산 가는 KTX 요금 얼마예요?", "ko"),  # KTX 는 환승 문서에만 있다
        ("공항버스 요금은 얼마인가요?", "ko"),
        ("How much is the taxi fare to the airport?", "en"),
        ("What is the fee for a lost passport?", "en"),
    ],
)
def test_price_of_something_we_do_not_price_is_empty(query, lang):
    assert official()(query, lang, {"slots": {}}) == []


@pytest.mark.parametrize(
    ("query", "lang", "train", "doc"),
    [
        ("직통열차 요금 얼마야?", "ko", None, "doc-fare-arex-express"),
        ("얼마예요?", "ko", "allstop", "doc-fare-arex-allstop"),  # 열차를 이미 골랐으면 그 열차 요금
        ("공덕에서 김포공항까지 얼마예요?", "ko", "allstop", "doc-fare-arex-allstop"),
        ("기후동행카드 1일권 가격", "ko", None, "doc-fare-passes-cards"),
        ("How much is a 3-day Climate Card?", "en", None, "doc-fare-passes-cards"),
        ("What does the AREX Express cost for adults?", "en", None, "doc-fare-arex-express"),
        ("How much is the fare right now?", "en", None, "doc-fare-arex-express"),  # 대상 없이 요금만 물으면 공항철도
        # 열차를 고르기 전, 요금표에 있는 역 이름으로 묻는 질문
        ("인천공항까지 얼마예요?", "ko", None, "doc-fare-arex-allstop"),
        ("서울역에서 인천공항 가는 표 얼마예요?", "ko", None, "doc-fare-arex-allstop"),
        ("인천공항 가려면 얼마 들어요?", "ko", None, "doc-fare-arex-allstop"),
        ("How much is it to Incheon Airport?", "en", None, "doc-fare-arex-allstop"),
        ("How much is the airport train?", "en", None, "doc-fare-arex-allstop"),
    ],
)
def test_price_of_what_we_price_still_finds_fare_doc(query, lang, train, doc):
    assert doc in ids(official()(query, lang, ctx(train)))


def test_every_fare_doc_says_what_it_prices():
    assert all(d.priced for d in load_docs() if d.scope == "fare")


@pytest.mark.parametrize(
    ("query", "lang", "doc"),
    [
        ("Can I purchase an Express ticket from a machine?", "en", "doc-express-ticket"),  # purchase → buy
        ("What is the price of a seven-day Climate Card?", "en", "doc-fare-passes-cards"),  # seven → 7
        ("Is the nonstop train faster?", "en", "doc-arex-train-types"),  # nonstop → non-stop
    ],
)
def test_synonyms_reach_document_words(query, lang, doc):
    assert doc in ids(official()(query, lang, ctx()))


@pytest.mark.parametrize(
    ("query", "lang"),
    [
        ("인천공항까지 얼마나 걸려요?", "ko"),
        ("직통열차는 얼마나 걸려요?", "ko"),
        ("How much time does it take to the airport?", "en"),
    ],
)
def test_how_long_is_not_a_price_question(query, lang):
    """'얼마나 걸려요' · 'how much time' 은 시간 질문: 가격 판정에 걸리지 않고 열차 종류 문서(소요 시간)를 찾는다."""
    assert "doc-arex-train-types" in ids(official()(query, lang, ctx()))


def test_excerpt_is_the_matching_section_not_the_whole_doc(search):
    """소제목을 가리키는 질문은 그 소제목만 발췌한다 (LLM 에 넘기는 글을 줄임).

    문서 전체를 묻는 질문은 본문 전체: test_help_order_puts_station_desks_before_phone_lines"""
    hit = MemorySearch()("직통열차 발매기에서 해외 신용카드로 결제할 수 있어요?", "ko", ctx())[0]
    assert hit.document_id == "doc-express-ticket" and "비자" in hit.excerpt  # '결제 수단' 소제목
    assert "고객안내센터" not in hit.excerpt  # 첫 소제목(사는 곳)은 빠짐
