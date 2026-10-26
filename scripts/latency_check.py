"""메시지 하나의 응답 시간을 단계별로 잰다: 백엔드 /messages 전체 · RAG 검색 · LLM 호출(이해 · 답변 · 검증).

agent_live_check.py 와 같은 조립·질문 16개를 쓰고, 다른 레포 코드는 바꾸지 않는다(측정용으로 감싸기만 함).
OpenAI 키가 필요하다. 결과는 docs/optimization-log.md 에 옮겨 적는다.

    set -a; . ../.env; set +a
    uv run --project ../oneload-backend --with ../oneload-rag python scripts/latency_check.py
"""

from __future__ import annotations

import os
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_live_check import CASES  # noqa: E402  (e2e_backend 경로 설정도 여기서. 먼저 와야 함)
from e2e_backend import Client, migrate  # noqa: E402

# isort: split
from app.ai.rule_agent import RuleAgent  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from hangil_r2 import LLMAgent, LLMVision, OpenAILLM  # noqa: E402

from hangil_rag import search_knowledge  # noqa: E402

spent: dict[str, list[float]] = defaultdict(list)  # 단계 → 이번 메시지에서 쓴 ms 목록
sent: list[int] = []  # 이번 메시지에서 LLM 에 넘긴 발췌 글자 수


def search_counting(query, language, context):
    hits = search_knowledge(query, language, context)
    sent.append(sum(len(h.excerpt) for h in hits[:3]))  # Agent 는 상위 3개만 쓴다
    return hits


def timed(name, fn):
    def wrapper(*args, **kwargs):
        t = time.perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            spent[name].append((time.perf_counter() - t) * 1000)

    return wrapper


def main() -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY 없음 (../.env)")
    migrate()
    llm = OpenAILLM()
    for name in ("understand", "compose", "verify"):
        setattr(llm, name, timed(f"LLM {name}", getattr(llm, name)))
    vision = LLMVision(llm)
    agent = LLMAgent(llm, search_knowledge=timed("RAG 검색", search_counting), vision=vision, fallback=RuleAgent())
    rows = []
    with TestClient(create_app(agent=agent, vision=vision)) as http:
        Client(http, "ko").say("안녕하세요")  # 첫 호출의 연결 준비 시간은 빼고 잰다
        for lang, q, _ in CASES:
            spent.clear()
            sent.clear()
            c = Client(http, lang)
            t = time.perf_counter()
            r = c.say(q)
            total = (time.perf_counter() - t) * 1000
            rows.append((q, r["status"], total, {k: (len(v), sum(v)) for k, v in spent.items()}, sum(sent)))

    stages = ["RAG 검색", "LLM understand", "LLM compose", "LLM verify"]
    print("| 질문 | 상태 | 전체 ms | 발췌 자 | " + " | ".join(stages) + " |\n|---|---|---|---|" + "---|" * len(stages))
    for q, status, total, s, chars in rows:
        cells = [f"{s[k][1]:.0f} ({s[k][0]}회)" if k in s else "-" for k in stages]
        print(f"| {q[:28]} | {status} | {total:.0f} | {chars or '-'} | " + " | ".join(cells) + " |")
    totals = [r[2] for r in rows]
    med, avg = statistics.median(totals), statistics.mean(totals)
    print(f"\n- 전체: 중앙값 {med:.0f}ms · 평균 {avg:.0f}ms · 최대 {max(totals):.0f}ms")
    for k in stages:
        per = [r[3][k][1] for r in rows if k in r[3]]
        share = sum(per) / sum(totals)
        if per:
            print(f"- {k}: {len(per)}개 메시지에서 중앙값 {statistics.median(per):.1f}ms · 전체 시간의 {share:.0%}")
    rest = sum(totals) - sum(r[3][k][1] for r in rows for k in stages if k in r[3])
    print(f"- 그 밖(백엔드 · DB · 그래프 처리): 전체 시간의 {rest / sum(totals):.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
