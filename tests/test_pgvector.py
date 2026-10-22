"""pgvector 검색 · 적재. 유료 API 없이: 임베딩은 가짜(토큰 해시), DB 는 RAG_TEST_DATABASE_URL 이 있을 때만."""

import hashlib
import math
import os
from datetime import date

import pytest

psycopg = pytest.importorskip("psycopg")

from hangil_rag.ingest import ingest, main  # noqa: E402
from hangil_rag.loader import chunks, load_docs  # noqa: E402
from hangil_rag.search_memory import tokens  # noqa: E402
from hangil_rag.search_pgvector import PgVectorSearch, connect  # noqa: E402

TEST_DSN = os.environ.get("RAG_TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DSN, reason="RAG_TEST_DATABASE_URL 없음 (CI 는 pgvector 서비스로 실행)")


class FakeEmbedder:
    """토큰을 해시해 고정 차원에 뿌린 bag-of-words 벡터. 같은 낱말이 많을수록 가깝다."""

    dim = 64

    def __init__(self):
        self.calls = 0

    def embed(self, texts):
        self.calls += 1
        out = []
        for text in texts:
            v = [0.0] * self.dim
            for t in tokens(text):
                v[int(hashlib.md5(t.encode()).hexdigest(), 16) % self.dim] += 1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


def row(doc_id, lang, score, content="c"):
    return {
        "doc_id": doc_id,
        "lang": lang,
        "content": content,
        "title_ko": f"{doc_id} 제목",
        "title_en": f"{doc_id} title",
        "scope": "ticket",
        "source_url": None,
        "verified_at": date(2026, 10, 22),
        "score": score,
    }


def test_pick_ranks_docs_and_uses_language_chunk():
    s = PgVectorSearch(dsn="unused", embedder=FakeEmbedder(), k=2, min_score=0.3)
    rows = [
        row("a", "en", 0.9, "a-en"),
        row("b", "ko", 0.8, "b-ko"),
        row("a", "ko", 0.7, "a-ko"),
        row("c", "ko", 0.5),
        row("b", "en", 0.1, "b-en"),
    ]
    hits = s._pick(rows, "ko")
    assert [(h.document_id, h.excerpt, h.title) for h in hits] == [("a", "a-ko", "a 제목"), ("b", "b-ko", "b 제목")]
    assert hits[0].verified_at == "2026-10-22"


def test_pick_threshold_gives_empty():
    s = PgVectorSearch(dsn="unused", embedder=FakeEmbedder(), min_score=0.95)
    assert s._pick([row("a", "ko", 0.9)], "ko") == [] and s._pick([], "ko") == []


def test_dry_run_needs_no_db_or_api(capsys):
    assert main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "doc-express-ticket\tko" in out and "doc-express-ticket\ten" in out


@needs_db
def test_ingest_then_search():
    emb = FakeEmbedder()
    with connect(TEST_DSN) as conn:
        docs = load_docs()
        expected = sum(len(chunks(d)) for d in docs)  # 언어 절 × 소제목 수 (문서가 늘어도 맞게)
        assert ingest(conn, docs, emb) == expected
        assert ingest(conn, docs, emb) == expected  # 다시 적재해도 중복 없음
        assert conn.execute("SELECT count(*) AS n FROM rag.chunks").fetchone()["n"] == expected
    s = PgVectorSearch(dsn=TEST_DSN, embedder=emb, min_score=0.2)

    hits = s("일반열차 승차권 구매 방법", "ko", {"slots": {"train_type": "allstop"}})  # A-21
    got = [h.document_id for h in hits]
    assert "doc-allstop-ticket" in got and "doc-express-ticket" not in got

    en = s("How do I get my deposit back?", "en", {"slots": {"train_type": "unknown"}})
    assert en[0].document_id == "doc-deposit-refund" and "deposit refund machine" in en[0].excerpt
    assert en[0].title == "Getting the single-journey ticket deposit back" and en[0].scope == "card"

    assert all(h.scope != "fare" for h in s("직통열차 요금 얼마야?", "ko", {}))  # 요금 문서는 아직 없음
