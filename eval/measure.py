"""개선 전후 비교용 측정 한 번에: 검색 평가셋 · LLM 에 넘기는 발췌 크기 · 검색기 메모리 · 검색 시간.

    uv run python eval/measure.py            # 결과를 docs/optimization-log.md 의 표에 옮겨 적는다

R6 평가셋은 옆 폴더 oneload-qa 가 있으면 함께 잰다. R6 가 판정에 쓴 뒤 공개한 셋(v2 · v3 · v4)만 넣는다.
아직 판정 전인 새 셋은 넣지 않는다 (결과를 보고 고치면 독립 판정이 안 된다).
공식 문서만 본다 (RAG_INCLUDE_COMMUNITY 는 끈다).
"""

from __future__ import annotations

import json
import os
import statistics
import sys
import time
import tracemalloc
from pathlib import Path

import yaml

os.environ.pop("RAG_INCLUDE_COMMUNITY", None)
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from retrieval import score  # noqa: E402

from hangil_rag.search_memory import MemorySearch  # noqa: E402

QA = HERE.parents[1] / "oneload-qa" / "eval"


def sets() -> dict[str, list[dict]]:
    out = {
        "R3 47": yaml.safe_load((HERE / "retrieval.yaml").read_text(encoding="utf-8"))["cases"],
        "R3 보류 28": yaml.safe_load((HERE / "retrieval_holdout.yaml").read_text(encoding="utf-8"))["cases"],
    }
    r6 = (
        ("R6 32", "retrieval_cases.json"),
        ("R6 v2 40", "retrieval_holdout_v2.json"),
        ("R6 v3 48", "retrieval_holdout_v3.json"),
        ("R6 v4 48", "split_holdout_v4.json"),
    )
    for name, file in r6:
        if (QA / file).is_file():
            out[name] = json.loads((QA / file).read_text(encoding="utf-8"))["cases"]
    return out


def main() -> int:
    tracemalloc.start()
    search = MemorySearch()
    memory_kb = tracemalloc.get_traced_memory()[0] / 1024
    tracemalloc.stop()

    print("| 평가셋 | 정답 상위 3개 | 범위 밖 빈 결과 |\n|---|---|---|")
    all_cases = []
    for name, cases in sets().items():
        r = score(search, cases)
        print(f"| {name} | {r['hit3']}/{r['found']} | {r['empty']}/{r['none']} |")
        all_cases += cases

    sent, ms = [], []
    for c in all_cases:
        t = time.perf_counter()
        hits = search(c["q"], c["lang"], {"slots": {"train_type": c.get("train")}})
        ms.append((time.perf_counter() - t) * 1000)
        if hits:
            sent.append(sum(len(h.excerpt) for h in hits))
    print(
        f"\n- LLM 에 넘기는 발췌 (질문당 상위 3개 합계, 결과가 있는 {len(sent)}개): "
        f"중앙값 {statistics.median(sent):.0f}자 · 평균 {statistics.mean(sent):.0f}자 · 최대 {max(sent)}자"
        f"\n- 검색 1회: 중앙값 {statistics.median(ms):.1f}ms · 최대 {max(ms):.1f}ms"
        f"\n- 검색기 메모리: 약 {memory_kb:.0f}KB (공식 문서 {len(search.docs)}개)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
