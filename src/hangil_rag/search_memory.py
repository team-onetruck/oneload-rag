"""DB 없이 도는 키워드 검색 — MockKnowledgeSearch 자리에 바로 넣는 1차 구현 (테스트 · 로컬 시연용).

질문과 문서를 같은 규칙으로 토큰으로 나눠 겹치는 비율로 점수를 매긴다.
- 한글 낱말은 글자 2-gram ("직통열차는" → 직통 · 통열 · 열차 · 차는) 이라 조사가 붙어도 맞는다.
- 영어 · 숫자는 낱말 단위 (흔한 기능어 제외, 끝의 s 제거).
- 제목에 있으면 1점, 본문에만 있으면 0.5점. 두 언어 절을 모두 보므로 영어 질문도 한국어 문서를 찾고,
  돌려주는 제목 · 발췌는 language 에 맞춘다.
- 범위 판정 (RAG #3): 문서에 없는 주제(호텔 · 식당 · 날씨 · 항공권 ...)는 "서울역" 같은 흔한 낱말만 겹쳐도
  걸리지 않게, 질문의 정보량(드문 낱말일수록 무겁게, 문서에 아예 없는 낱말은 가장 무겁게) 중 가장 잘 맞는
  문서가 덮는 비율이 MIN_COVERAGE 보다 낮으면 빈 결과. 실시간 현황(빈 좌석 등)을 묻는 질문도 빈 결과.
- 가격 질문 (RAG #3 후속): 가격은 요금 문서가 값을 매긴 것에 대해서만 답할 범위다. 위 비율 대신 이것으로 판정한다.
  머리말 priced 의 대상이 있거나 열차를 이미 골랐으면 안. 아니면 질문의 내용어가 모두 요금 문서에 있는 말일
  때만 안 ("인천공항까지 얼마예요?" 는 안, "택시 기본요금" · "KTX 가격" 은 밖).
"""

from __future__ import annotations

import logging
import math
import re
from pathlib import Path

from .loader import TRAIN_TYPES, Doc, chunks, load_docs
from .schemas import KnowledgeHit

log = logging.getLogger("hangil_rag")

TOP_K = 3  # Agent 도 상위 3개만 쓴다 (agent.py _search)
MIN_SCORE = 0.25  # eval/retrieval.py --sweep 기준 (2026-10-22, 평가셋 44문항). R6 가 확정
RELATIVE_CUTOFF = 0.5  # 1위 점수의 절반 미만은 뺀다 ("ticket" 같은 흔한 낱말 하나로 엉뚱한 문서가 근거로 붙지 않게)
# 범위 판정 기준 (RAG #3). R3 44문항 · R6 개발 16문항으로 정함: 범위 밖 최고 0.242, 정답 최저 0.257 (2026-10-23)
MIN_COVERAGE = 0.25

_WORD = re.compile(r"[0-9a-z]+|[가-힣]+")
_STOP = {
    "a", "an", "the", "i", "me", "my", "you", "is", "are", "am", "do", "does", "can", "could", "how", "what",
    "where", "which", "when", "to", "of", "in", "on", "at", "for", "it", "this", "that", "and", "or", "please",
}  # fmt: skip
# 질문에 흔히 붙는 군말의 2-gram (어디서 · 어떻게 · 되는데 · 받아요 · 알려주세요 ...)과 뜻 없는 한 글자 낱말.
# shortcut: 손으로 고른 목록. 실제 질문 로그가 쌓이면 R6 평가셋으로 다시 고른다
_STOP_KO = {
    "어디", "디서", "디에", "어떻", "떻게", "어떡", "떡해", "해요", "하나", "나요", "되나", "돼요", "되는", "는데",
    "받아", "아요", "있어", "어요", "없어", "알려", "려줘", "주세", "세요", "싶어", "예요", "인가", "가요",
    "안", "좀", "거", "수", "뭐", "왜", "또", "더", "잘", "꼭", "다", "이", "그", "저", "제", "내",
}  # fmt: skip
# 낱말 끝 조사. '도' · '로' 는 철도 · 통로처럼 명사 끝에도 와서 빼지 않는다 ('로도' · '으로도' 는 뺀다: 발매기로도)
_PARTICLE = re.compile(r"(으로도|로도|에서|에게|까지|부터|이랑|을|를|은|는|에)$")
# 가격을 묻는 말. 있으면 '요금 · fare' 문서도 찾고("얼마예요?" 에 요금 문서가 나오게), 가격 질문으로 판정한다
_PRICE_ASK_KO = ("얼마", "가격", "금액", "비용", "요금", "운임", "수수료", "값")
_PRICE_ASK_EN = {"much", "price", "cost", "fee", "fare", "charge"}
# 질문 낱말 → 문서에 쓰인 말 (같은 뜻 · 숫자 낱말). shortcut: 손으로 고른 목록, 질문 로그가 쌓이면 보강
_SYNONYM = {
    "purchase": "buy", "purchasing": "buy", "nonstop": "non stop",
    "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8",
    "nine": "9", "ten": "10",
}  # fmt: skip
# 범위 판정에서 '모르는 낱말'로 세지 않는 말: 의문사 · 지시어 · 영어 기능어 (문서에 없어도 주제가 아님).
# 영어 this · that 은 _STOP 에 있으므로 한국어 지시어도 같이 뺀다
_ASK_KO = {
    "몇",
    "무슨",
    "언제",
    "얼마나",
    "이거",
    "이것",
    "이건",
    "저거",
    "저것",
    "그거",
    "그것",
    "여기",
    "거기",
    "저기",
    "말고",
    "대신",
}
_FILLER_EN = {
    "why", "should", "now", "have", "has", "was", "were", "will", "would", "there", "any", "get", "go", "want",
    "need", "tell", "let", "know", "be", "with", "from", "by", "your", "our", "we", "if", "vs", "versus",
    "make", "instead", "also", "still",
}  # fmt: skip
# 가격 질문에서 '무엇의 가격인지'로 치지 않는 말: 때 ("How much is the fare right now?") · 가는 길 · 표.
# "인천공항 가는 표 얼마예요?" 의 대상은 인천공항까지 가는 것이다. shortcut: 손으로 고른 목록, 질문 로그로 보강
_WHEN = {"right", "today", "currently", "지금", "현재", "오늘"}
_TRIP_KO = {"가는", "가려면", "가면", "갈", "가요", "타는", "타려면", "타면", "들어요", "드나요", "드는", "표", "데"}
# 실시간 현황은 문서로 답할 수 없다 (잔여석 · 빈 좌석 · 실시간). shortcut: 표현 목록, 질문 로그가 쌓이면 보강
_REALTIME = re.compile(
    r"실시간|매진|잔여\s*(좌석|석)|(빈|남은)\s*(좌석|자리|석)|자리\s*(가\s*)?남|real[- ]?time|sold out"
    r"|seats?\s+((are|is)\s+)?(left|available|remaining)|(empty|free|available)\s+seats?",
    re.I,
)


def words(text: str) -> list[str]:
    """소문자 낱말 목록. 영어 동의어 · 숫자 낱말은 문서에 쓰인 말로 바꾼다 (purchase → buy, seven → 7)."""
    return [w for word in _WORD.findall(text.lower()) for w in _SYNONYM.get(word, word).split()]


def _stem(word: str) -> str:
    return word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word


def _grams(word: str) -> set[str]:
    return ({word} if len(word) == 1 else {word[i : i + 2] for i in range(len(word) - 1)}) - _STOP_KO


def tokens(text: str) -> set[str]:
    out: set[str] = set()
    for word in words(text):
        if word.isascii():
            if word in _STOP:
                continue
            out.add(_stem(word))
        else:
            for w in {word, _PARTICLE.sub("", word) or word}:  # "표를" → 표를 · 표 둘 다
                out |= _grams(w)
    return out


def _price_flags(ws: list[str]) -> list[bool]:
    """낱말마다 가격을 묻는 말인가. '얼마나 걸려요' · 'how much time' 은 시간을 묻는 말이라 뺀다."""
    out = []
    for i, w in enumerate(ws):
        if w.isascii():
            out.append(_stem(w) in _PRICE_ASK_EN and not (w == "much" and ws[i + 1 : i + 2] == ["time"]))
        else:
            out.append(any(p in w for p in _PRICE_ASK_KO) and not w.startswith("얼마나"))
    return out


def asks_price(text: str) -> bool:
    return any(_price_flags(words(text)))


def _is_content(word: str) -> bool:
    """가격 대상이 될 수 있는 낱말인가 (기능어 · 의문사 · 때를 나타내는 말 · 숫자가 아님)."""
    if word.isascii():
        return not (word in _STOP or word in _FILLER_EN or word in _WHEN or word.isdigit())
    s = _PARTICLE.sub("", word) or word
    return bool(_grams(s)) and s not in _ASK_KO and s not in _WHEN and s not in _TRIP_KO


def _squash(text: str) -> str:
    """띄어쓰기 · 하이픈 차이를 없앤다 (all-stop · all stop · allstop)."""
    return re.sub(r"[\s\-]", "", text.lower())


class MemorySearch:
    def __init__(
        self, docs: list[Doc] | None = None, directory: Path | None = None, k: int = TOP_K, min_score: float = MIN_SCORE
    ):
        self.docs = docs if docs is not None else load_docs(directory)
        self.k, self.min_score = k, min_score
        self._index = [(d, tokens(f"{d.title_ko} {d.title_en}"), tokens(f"{d.body_ko} {d.body_en}")) for d in self.docs]
        self._df: dict[str, int] = {}  # 토큰 → 들어 있는 문서 수
        for _, title, body in self._index:
            for t in title | body:
                self._df[t] = self._df.get(t, 0) + 1
        self._priced = {_squash(p) for d in self.docs for p in d.priced}
        # 발췌는 문서 전체가 아니라 질문에 맞는 '###' 소제목 하나 (LLM 에 넘기는 글을 줄인다)
        self._chunks: dict[tuple[str, str], list[tuple[set[str], str]]] = {}
        for c in (c for d in self.docs for c in chunks(d)):
            self._chunks.setdefault((c.doc.doc_id, c.lang), []).append((tokens(f"{c.heading} {c.text}"), c.text))
        self._fare_vocab = set().union(*(title | body for d, title, body in self._index if d.scope == "fare"))

    def _idf(self, t: str) -> float:
        return math.log((len(self._index) + 1) / (self._df.get(t, 0) + 1))

    def _unknown_words(self, query: str) -> int:
        """문서 어디에도 없는 낱말 수 (어미 조각 · 의문사 · 영어 기능어는 빼고 낱말 단위로 센다)."""
        return sum(self._unknown(w) for w in words(query))

    def _unknown(self, w: str) -> bool:
        if w.isascii():
            return not (w in _STOP or w in _FILLER_EN or w.isdigit() or _stem(w) in self._df)
        s = _PARTICLE.sub("", w) or w
        grams = _grams(s)
        return bool(grams) and s not in _ASK_KO and s[0] not in self._df and not grams & self._df.keys()

    def price_reason(self, query: str, train: str | None) -> str | None:
        """가격 질문인데 우리 문서가 값을 매긴 대상이 아니면 빈 결과 사유, 아니면 None."""
        ws = words(query)
        flags = _price_flags(ws)
        if not any(flags):
            return None
        # 값을 매기는 대상을 말했거나 열차를 골랐으면 답할 범위. 질문을 꾸미는 말(비교·저녁·플라스틱 ...)이
        # 문서에 없어도 거절하지 않는다(R6 v3: 이 규칙이 정상 가격 질문 7개를 막음). 그 대상의 어떤 비용인지
        # (좌석 변경 · 재발급 수수료)까지는 낱말로 가리지 못해 Agent 의 근거 판단에 맡긴다 (RQ-32)
        if train in TRAIN_TYPES or any(p in _squash(query) for p in self._priced):
            return None
        rest = [w for w, price in zip(ws, flags, strict=True) if not price and w not in _TRIP_KO]
        # priced 를 직접 말하지 않았으면 질문의 내용어가 모두 요금 문서에 있는 말이어야 한다.
        # "인천공항까지 얼마예요?" (요금표의 역 이름) 는 안, "택시 기본요금" · "KTX 가격" (요금 문서에 없음) 은 밖
        return "price_not_priced" if any(_is_content(w) and not self._in_fare_docs(w) for w in rest) else None

    def _in_fare_docs(self, w: str) -> bool:
        if w.isascii():
            return _stem(w) in self._fare_vocab
        return _grams(_PARTICLE.sub("", w) or w) <= self._fare_vocab

    def coverage(self, query: str, train: str | None) -> float:
        """가장 잘 맞는 문서가 덮는 질문 정보량의 비율 (0~1). 범위 밖 판정에 쓴다."""
        known = [t for t in _expand(tokens(query), query) if t in self._df]
        total = sum(self._idf(t) for t in known) + self._unknown_words(query) * math.log(len(self._index) + 1)
        best = max(
            (
                sum(self._idf(t) * (1.0 if t in title else 0.5 if t in body else 0.0) for t in known)
                for doc, title, body in self._index
                if doc.allowed(train)
            ),
            default=0.0,
        )
        return best / total if total else 0.0

    def scope_reason(self, query: str, train: str | None) -> str | None:
        """RAG #3: 답할 범위 밖이면 빈 결과 사유, 아니면 None. pgvector 검색도 같은 판정을 쓴다."""
        if _REALTIME.search(query):  # 실시간 현황은 근거 문서가 없다
            return "realtime"
        if asks_price(query):  # 가격 질문은 값을 매긴 대상인지로 판정한다
            return self.price_reason(query, train)
        if (cov := self.coverage(query, train)) < MIN_COVERAGE:  # 문서에 없는 주제
            return f"out_of_scope coverage={cov:.2f}"
        return None

    def __call__(self, query: str, language: str, context: dict) -> list[KnowledgeHit]:
        train = (context.get("slots") or {}).get("train_type")
        q = _expand(tokens(query), query)
        if not q:
            return []
        if reason := self.scope_reason(query, train):
            log.info("rag_empty reason=%s", reason)
            return []
        scored = []
        for doc, title, body in self._index:
            if not doc.allowed(train):
                continue
            score = sum(1.0 if t in title else 0.5 if t in body else 0.0 for t in q) / len(q)
            if score > 0:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        cutoff = max(self.min_score, top(scored) * RELATIVE_CUTOFF)
        passed = [(s, d) for s, d in scored if s >= cutoff]
        # 이용자 후기(미확인, RAG_INCLUDE_COMMUNITY=1 일 때만 있음)는 공식 문서 뒤 마지막 한 자리까지만
        official = [x for x in passed if x[1].source_kind != "community"]
        community = [x for x in passed if x[1].source_kind == "community"][:1]
        hits = official[: self.k - len(community)] + community if community else official[: self.k]
        if not hits:  # 반환은 둘 다 빈 목록, 구분은 로그로만 (임계값 조정용)
            log.info("rag_empty reason=%s top_score=%.2f", "below_threshold" if scored else "no_match", top(scored))
        return [to_hit(d, language, self.excerpt(d, language, q)) for _, d in hits]

    def excerpt(self, doc: Doc, language: str, q: set[str]) -> str:
        """질문 낱말이 가장 많이 겹치는 소제목 하나. 제목 낱말만 겹치면(문서 전체를 묻는 질문) 본문 전체."""
        parts = self._chunks.get((doc.doc_id, "en" if language == "en" else "ko"), [])
        specific = q - tokens(f"{doc.title_ko} {doc.title_en}")
        best, text = max(((len(specific & ct), text) for ct, text in parts), key=lambda x: x[0], default=(0, ""))
        return text if best and len(parts) > 1 else doc.body(language)


def _expand(q: set[str], query: str) -> set[str]:
    return q | {"요금", "fare"} if asks_price(query) else q


def top(scored: list[tuple[float, Doc]]) -> float:
    return scored[0][0] if scored else 0.0


def to_hit(doc: Doc, language: str, excerpt: str) -> KnowledgeHit:
    return KnowledgeHit(
        document_id=doc.doc_id,
        title=doc.title(language),
        excerpt=excerpt,
        source_url=doc.source_url,
        verified_at=doc.verified_at.isoformat(),
        scope=doc.scope,
    )
