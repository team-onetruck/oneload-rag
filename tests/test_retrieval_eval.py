"""eval/retrieval.yaml 평가셋이 실제 문서와 맞는지, 검색 품질이 크게 떨어지지 않았는지."""

import importlib.util
from pathlib import Path

from hangil_rag.loader import load_docs
from hangil_rag.search_memory import MemorySearch

spec = importlib.util.spec_from_file_location("retrieval", Path(__file__).resolve().parents[1] / "eval/retrieval.py")
retrieval = importlib.util.module_from_spec(spec)
spec.loader.exec_module(retrieval)


def test_gold_ids_exist():
    ids = {d.doc_id for d in load_docs(include_community=False)}
    unknown = {g for c in retrieval.CASES for g in c["gold"]} - ids
    assert unknown == set()


def test_quality_does_not_drop():
    """2026-10-23 (RAG #3 이후) top-3 38/40, 범위 밖 빈 결과 4/4. 문서를 추가하다 크게 떨어지면 알린다."""
    r = retrieval.score(MemorySearch(docs=load_docs(include_community=False)))
    assert r["hit3"] >= 37 and r["empty"] == 4, (r["hit3"], r["empty"])
