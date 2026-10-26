"""검색 평가: eval/retrieval.yaml 로 상위 3개 적중률과 '범위 밖이면 빈 결과' 비율을 잰다.

    uv run python eval/retrieval.py            # 지금 설정 (기본: 메모리 검색, RAG_BACKEND=pgvector 면 pgvector)
    uv run python eval/retrieval.py --sweep    # 메모리 검색 임계값 후보 비교
    uv run python eval/retrieval.py --holdout  # R3 보류 검증 28문항 (RAG #3 때 실행 전 고정, 지금은 회귀용)

여러 평가셋 · 발췌 크기 · 메모리를 한 번에 보려면 eval/measure.py.

공식 문서만 본다 (RAG_INCLUDE_COMMUNITY 는 끈다).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

os.environ.pop("RAG_INCLUDE_COMMUNITY", None)

from hangil_rag import search_knowledge, search_memory  # noqa: E402
from hangil_rag.search_memory import MemorySearch  # noqa: E402

HERE = Path(__file__).resolve().parent
CASES = yaml.safe_load((HERE / "retrieval.yaml").read_text(encoding="utf-8"))["cases"]


def score(search, cases=CASES) -> dict:
    found = [c for c in cases if c["gold"]]
    none = [c for c in cases if not c["gold"]]
    rows, hit1, hit3, empty = [], 0, 0, 0
    for c in cases:
        ids = [h.document_id for h in search(c["q"], c["lang"], {"slots": {"train_type": c.get("train")}})][:3]
        ok1 = bool(ids) and ids[0] in c["gold"] if c["gold"] else not ids
        ok3 = bool(set(ids) & set(c["gold"])) if c["gold"] else not ids
        hit1 += ok1 and bool(c["gold"])
        hit3 += ok3 and bool(c["gold"])
        empty += ok3 and not c["gold"]
        rows.append((c, ids, ok1, ok3))
    return {"rows": rows, "hit1": hit1, "hit3": hit3, "found": len(found), "empty": empty, "none": len(none)}


def report(r: dict) -> str:
    lines = ["| id | 질문 | 정답 | 상위 3개 | top-1 | top-3 |", "|---|---|---|---|---|---|"]
    for c, ids, ok1, ok3 in r["rows"]:
        gold = ", ".join(g.removeprefix("doc-") for g in c["gold"]) or "(없어야 함)"
        got = ", ".join(i.removeprefix("doc-") for i in ids) or "-"
        lines.append(f"| {c['id']} | {c['q']} | {gold} | {got} | {'✅' if ok1 else '❌'} | {'✅' if ok3 else '❌'} |")
    lines.append(
        f"\n- 정답이 있는 질문 {r['found']}개: top-1 {r['hit1']}, top-3 {r['hit3']}"
        f"\n- 범위 밖 질문 {r['none']}개: 빈 결과 {r['empty']}"
    )
    return "\n".join(lines)


def sweep() -> str:
    lines = ["| 최소 점수 | 1위 대비 비율 | top-1 | top-3 | 범위 밖 빈 결과 |", "|---|---|---|---|---|"]
    default = search_memory.RELATIVE_CUTOFF
    for min_score in (0.1, 0.15, 0.2, 0.25, 0.3, 0.35):
        for rel in (0.3, 0.5, 0.7):
            search_memory.RELATIVE_CUTOFF = rel
            r = score(MemorySearch(min_score=min_score))
            mark = " (지금)" if (min_score, rel) == (search_memory.MIN_SCORE, default) else ""
            lines.append(
                f"| {min_score}{mark} | {rel} | {r['hit1']}/{r['found']} | {r['hit3']}/{r['found']} "
                f"| {r['empty']}/{r['none']} |"
            )
    search_memory.RELATIVE_CUTOFF = default
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sweep", action="store_true", help="메모리 검색 임계값 후보 비교")
    ap.add_argument("--holdout", action="store_true", help="고정된 보류 검증 질문(retrieval_holdout.yaml)으로 실행")
    a = ap.parse_args(argv)
    if a.holdout:
        holdout = yaml.safe_load((HERE / "retrieval_holdout.yaml").read_text(encoding="utf-8"))["cases"]
        print(report(score(search_knowledge, holdout)))
    else:
        print(sweep() if a.sweep else report(score(search_knowledge)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
