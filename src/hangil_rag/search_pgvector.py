"""pgvector 하이브리드 검색 (초안): 범위 판정 → 메타데이터 필터 → 벡터 + 키워드 점수 → 임계값 → 상위 k.

색인은 ingest.py 가 만든 `rag.chunks` (백엔드 테이블과 섞이지 않게 별도 스키마, 같은 Postgres).
환경 변수: RAG_DATABASE_URL · RAG_EMBEDDING_MODEL · RAG_EMBEDDING_DIM · RAG_MIN_SCORE (.env.example).
임베딩은 Embedder 로 주입한다. 테스트는 가짜 임베더를 쓰므로 유료 API 를 부르지 않는다.
DB · 임베딩 장애는 unavailable() 예외로 바꿔 Agent 가 cannot_answer 로 보류하게 한다.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

import psycopg
from psycopg.rows import dict_row

from .loader import TRAIN_TYPES
from .schemas import KnowledgeHit, unavailable
from .search_memory import MemorySearch

log = logging.getLogger("hangil_rag")

DEFAULT_DSN = "postgresql://hangil:hangil@localhost:54329/hangil"  # 백엔드 compose.yaml 의 로컬 DB
DEFAULT_MODEL, DEFAULT_DIM = "text-embedding-3-small", 1536
TOP_K = 3
MIN_SCORE = 0.3  # 초기값. R3 · R6 가 평가셋으로 정한다
KEYWORD_WEIGHT = 0.5  # eval/retrieval.py 실측(2026-10-23): 0.3 보다 범위 밖 차단 2/4 → 4/4.
# "직통" · "AREX" · "T-money" 같은 고유명사는 키워드가 강하다 (설계서 4장)
TIMEOUT_S = 3  # /messages 15초 예산 안에서 검색이 오래 붙잡지 않게

# shortcut: 모든 청크에 점수를 매기는 전체 스캔. 청크가 수천 개를 넘으면 벡터 인덱스 후보 + 키워드 후보 합치기로
_SQL = """
SELECT doc_id, lang, content, title_ko, title_en, scope, source_url, verified_at,
       (1 - %(kw)s) * (1 - (embedding <=> %(vec)s::vector))
       + %(kw)s * word_similarity(%(q)s, title_ko || ' ' || title_en || ' ' || content) AS score
FROM rag.chunks
WHERE %(train)s::text IS NULL OR train_type IS NULL OR train_type = %(train)s
ORDER BY score DESC
"""


class Embedder(Protocol):
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class OpenAIEmbedder:
    """`[openai]` extra 필요. 키는 OPENAI_API_KEY (백엔드 서버 설정과 같은 이름)."""

    def __init__(self, model: str | None = None, dim: int | None = None):
        from openai import OpenAI

        self.model = model or _env("RAG_EMBEDDING_MODEL", DEFAULT_MODEL)
        self.dim = int(dim or _env("RAG_EMBEDDING_DIM", DEFAULT_DIM))
        self._client = OpenAI(timeout=TIMEOUT_S)

    def embed(self, texts: list[str]) -> list[list[float]]:
        res = self._client.embeddings.create(model=self.model, input=texts, dimensions=self.dim)
        return [d.embedding for d in res.data]


def _env(name: str, default):
    """빈 값도 '설정 안 함'으로 본다 (.env.example 을 복사해 일부만 채운 경우)."""
    return os.environ.get(name) or default


def database_url() -> str:
    return _env("RAG_DATABASE_URL", DEFAULT_DSN)


def vector_literal(vector: list[float]) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in vector) + "]"


def connect(dsn: str) -> psycopg.Connection:
    return psycopg.connect(
        dsn, connect_timeout=TIMEOUT_S, options=f"-c statement_timeout={TIMEOUT_S * 1000}", row_factory=dict_row
    )


class PgVectorSearch:
    def __init__(
        self,
        dsn: str | None = None,
        embedder: Embedder | None = None,
        k: int = TOP_K,
        min_score: float | None = None,
        keyword_weight: float = KEYWORD_WEIGHT,
        gate: MemorySearch | None = None,
    ):
        self.dsn = dsn or database_url()
        self.embedder = embedder or OpenAIEmbedder()
        self.k, self.keyword_weight = k, keyword_weight
        self.min_score = min_score if min_score is not None else float(_env("RAG_MIN_SCORE", MIN_SCORE))
        # RAG #3 범위 판정은 메모리 검색과 같게, 패키지에 든 knowledge/ 문서로 한다 (임베딩 · DB 를 부르기 전).
        # shortcut: DB 에 적재한 문서와 패키지 문서가 같다고 본다. 다른 폴더를 적재하면 gate 에 같은 문서를 넘긴다
        self.gate = gate or MemorySearch()

    def __call__(self, query: str, language: str, context: dict) -> list[KnowledgeHit]:
        train = (context.get("slots") or {}).get("train_type")
        if reason := self.gate.scope_reason(query, train):
            log.info("rag_empty reason=%s", reason)
            return []
        params = {"q": query, "kw": self.keyword_weight, "train": train if train in TRAIN_TYPES else None}
        try:
            params["vec"] = vector_literal(self.embedder.embed([query])[0])
        except Exception as exc:  # 외부 API: 키 없음 · 시간 초과 · 요금 한도 등 무엇이든 장애로 본다
            raise unavailable(f"embedding failed: {exc}") from exc
        try:
            with connect(self.dsn) as conn:
                rows = conn.execute(_SQL, params).fetchall()
        except psycopg.Error as exc:
            raise unavailable(f"rag db failed: {exc}") from exc
        return self._pick(rows, "en" if language == "en" else "ko")

    def _pick(self, rows: list[dict], lang: str) -> list[KnowledgeHit]:
        """문서마다 가장 높은 청크 점수로 순위를 매기고, 발췌는 그 문서의 language 청크 중 가장 높은 것."""
        best: dict[str, dict] = {}  # rows 는 점수 내림차순
        for row in rows:
            entry = best.setdefault(row["doc_id"], {"score": row["score"], "row": row, "excerpt": None})
            if entry["excerpt"] is None and row["lang"] == lang:
                entry["excerpt"] = row["content"]
        ranked = list(best.values())
        hits = [e for e in ranked if e["score"] >= self.min_score][: self.k]
        if not hits:  # 반환은 둘 다 빈 목록, 구분은 로그로만 (임계값 조정용)
            top = ranked[0]["score"] if ranked else 0.0
            log.info("rag_empty reason=%s top_score=%.2f", "below_threshold" if ranked else "no_match", top)
        return [
            KnowledgeHit(
                document_id=e["row"]["doc_id"],
                title=e["row"]["title_en" if lang == "en" else "title_ko"],
                excerpt=e["excerpt"] or e["row"]["content"],
                source_url=e["row"]["source_url"],
                verified_at=e["row"]["verified_at"].isoformat(),
                scope=e["row"]["scope"],
            )
            for e in hits
        ]
