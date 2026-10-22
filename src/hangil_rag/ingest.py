"""knowledge/*.md → 헤딩 단위 분할 → 임베딩 → `rag.chunks` 전체 재적재.

    python -m hangil_rag.ingest             # RAG_DATABASE_URL 로 적재 (OPENAI_API_KEY 필요)
    python -m hangil_rag.ingest --dry-run   # 분할 결과만 출력 (DB · API 불필요)

색인은 knowledge/ 로 언제든 다시 만들 수 있는 파생 데이터라 마이그레이션 이력 없이 매번 새로 만든다.
백엔드 alembic 은 public 스키마만 비교하므로(include_schemas 없음) rag 스키마를 건드리지 않는다.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loader import Chunk, Doc, chunks, load_docs
from .search_pgvector import Embedder, connect, database_url, vector_literal


def ddl(dim: int) -> list[str]:
    return [
        "CREATE EXTENSION IF NOT EXISTS vector",
        "CREATE EXTENSION IF NOT EXISTS pg_trgm",
        "CREATE SCHEMA IF NOT EXISTS rag",
        "DROP TABLE IF EXISTS rag.chunks",
        f"""CREATE TABLE rag.chunks (
            id bigserial PRIMARY KEY,
            doc_id text NOT NULL,
            lang text NOT NULL CHECK (lang IN ('ko', 'en')),
            heading text NOT NULL,
            content text NOT NULL,
            title_ko text NOT NULL,
            title_en text NOT NULL,
            scope text NOT NULL,
            train_type text,
            source_url text,
            verified_at date NOT NULL,
            embedding vector({int(dim)}) NOT NULL
        )""",
    ]


def embed_text(c: Chunk) -> str:
    title = c.doc.title(c.lang)
    return f"{title}\n{c.text}" if c.heading == title else f"{title}\n{c.heading}\n{c.text}"


def ingest(conn, docs: list[Doc], embedder: Embedder) -> int:
    """한 트랜잭션 안에서 테이블을 새로 만들고 채운다. 중간에 실패하면 이전 색인이 그대로 남는다."""
    rows = [c for d in docs for c in chunks(d)]
    vectors = embedder.embed([embed_text(c) for c in rows])
    if len(vectors) != len(rows) or any(len(v) != embedder.dim for v in vectors):
        raise ValueError(f"임베딩 개수 · 차원이 맞지 않음 (청크 {len(rows)}, dim {embedder.dim})")
    with conn.transaction():
        for stmt in ddl(embedder.dim):
            conn.execute(stmt)
        with conn.cursor() as cur:
            cur.executemany(
                """INSERT INTO rag.chunks (doc_id, lang, heading, content, title_ko, title_en, scope, train_type,
                                           source_url, verified_at, embedding)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector)""",
                [_row(c, v) for c, v in zip(rows, vectors, strict=True)],
            )
    return len(rows)


def _row(c: Chunk, vector: list[float]) -> tuple:
    d = c.doc
    return (
        d.doc_id,
        c.lang,
        c.heading,
        c.text,
        d.title_ko,
        d.title_en,
        d.scope,
        d.train_type,
        d.source_url,
        d.verified_at,
        vector_literal(vector),
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m hangil_rag.ingest", description=__doc__.splitlines()[0])
    ap.add_argument("--dsn", default=None, help="기본: RAG_DATABASE_URL")
    ap.add_argument("--knowledge-dir", type=Path, default=None, help="기본: RAG_KNOWLEDGE_DIR 또는 패키지 문서")
    ap.add_argument("--dry-run", action="store_true", help="분할 결과만 출력")
    a = ap.parse_args(argv)

    docs = load_docs(a.knowledge_dir)
    if a.dry_run:
        for d in docs:
            for c in chunks(d):
                print(f"{d.doc_id}\t{c.lang}\t{c.heading}\t{len(c.text)}자")
        return 0

    from .search_pgvector import OpenAIEmbedder

    with connect(a.dsn or database_url()) as conn:
        n = ingest(conn, docs, OpenAIEmbedder())
    print(f"적재 완료: 문서 {len(docs)}개, 청크 {n}개")
    return 0


if __name__ == "__main__":
    sys.exit(main())
