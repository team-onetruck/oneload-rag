"""DB 없이 도는 키워드 검색 — MockKnowledgeSearch 자리에 바로 넣는 1차 구현 (테스트 · 로컬 시연용).

질문과 문서를 같은 규칙으로 토큰으로 나눠 겹치는 비율로 점수를 매긴다.
- 한글 낱말은 글자 2-gram ("직통열차는" → 직통 · 통열 · 열차 · 차는) 이라 조사가 붙어도 맞는다.
- 영어 · 숫자는 낱말 단위 (흔한 기능어 제외, 끝의 s 제거).
- 제목에 있으면 1점, 본문에만 있으면 0.5점. 두 언어 절을 모두 보므로 영어 질문도 한국어 문서를 찾고,
  돌려주는 제목 · 발췌는 language 에 맞춘다.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .loader import Doc, load_docs
from .schemas import KnowledgeHit

log = logging.getLogger("hangil_rag")

TOP_K = 3  # Agent 도 상위 3개만 쓴다 (agent.py _search)
MIN_SCORE = 0.2  # 초기값. R3 · R6 가 평가셋으로 정한다
RELATIVE_CUTOFF = 0.5  # 1위 점수의 절반 미만은 뺀다 ("ticket" 같은 흔한 낱말 하나로 엉뚱한 문서가 근거로 붙지 않게)

_WORD = re.compile(r"[0-9a-z]+|[가-힣]+")
_STOP = {
    "a", "an", "the", "i", "me", "my", "you", "is", "are", "am", "do", "does", "can", "could", "how", "what",
    "where", "which", "when", "to", "of", "in", "on", "at", "for", "it", "this", "that", "and", "or", "please",
}  # fmt: skip


def tokens(text: str) -> set[str]:
    out: set[str] = set()
    for word in _WORD.findall(text.lower()):
        if word.isascii():
            if word in _STOP:
                continue
            out.add(word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word)
        else:
            out |= {word} if len(word) == 1 else {word[i : i + 2] for i in range(len(word) - 1)}
    return out


class MemorySearch:
    def __init__(
        self, docs: list[Doc] | None = None, directory: Path | None = None, k: int = TOP_K, min_score: float = MIN_SCORE
    ):
        self.docs = docs if docs is not None else load_docs(directory)
        self.k, self.min_score = k, min_score
        self._index = [(d, tokens(f"{d.title_ko} {d.title_en}"), tokens(f"{d.body_ko} {d.body_en}")) for d in self.docs]

    def __call__(self, query: str, language: str, context: dict) -> list[KnowledgeHit]:
        train = (context.get("slots") or {}).get("train_type")
        q = tokens(query)
        if not q:
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
        hits = [(s, d) for s, d in scored if s >= cutoff][: self.k]
        if not hits:  # 반환은 둘 다 빈 목록, 구분은 로그로만 (임계값 조정용)
            log.info("rag_empty reason=%s top_score=%.2f", "below_threshold" if scored else "no_match", top(scored))
        return [to_hit(d, language, d.body(language)) for _, d in hits]


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
