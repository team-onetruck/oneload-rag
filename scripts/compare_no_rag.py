"""RAG 없이 LLM 만 답할 때 vs 서비스 조립(백엔드 + Agent + RAG)이 답할 때 — 같은 질문으로 비교한다.

질문: R6 v3 48개(정답 문서 있음) + agent_live_check.py 의 시나리오 16개. 채점은 LLM 채점관(gpt-4o-mini, temperature 0):
- 정답 질문: 정답 문서 본문과 대조해 CORRECT(맞게 답함) · WRONG(문서와 다른 사실) · UNSUPPORTED(문서에 없는 사실을 단정)
  · NO_ANSWER(모른다 · 되묻기 · 거절)
- 범위 밖 질문(우리 문서에 근거 없음): DECLINED(모른다 · 확인처 안내) · ASSERTED(금액 · 시간 · 규정 같은 사실을 단정)

OpenAI 키가 필요하다 (질문 64개 × 두 방식 + 채점, 몇백 원). 결과 표는 docs/presentation-brief.md 에 옮긴다.

    set -a; . ../.env; set +a
    uv run --project ../oneload-backend --with ../oneload-rag python scripts/compare_no_rag.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_live_check import CASES  # noqa: E402  (e2e_backend 경로 설정도 여기서. 먼저 와야 함)
from e2e_backend import Client, migrate  # noqa: E402

# isort: split
from app.ai.rule_agent import RuleAgent  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from hangil_r2 import LLMAgent, LLMVision, OpenAILLM  # noqa: E402
from openai import OpenAI  # noqa: E402

from hangil_rag import search_knowledge  # noqa: E402
from hangil_rag.loader import load_docs  # noqa: E402

MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
V3 = Path(__file__).resolve().parents[2] / "oneload-qa" / "eval" / "retrieval_holdout_v3.json"
# RAG 없는 쪽: 서비스와 같은 역할만 알려 주고 문서는 주지 않는다
PLAIN = "You are a guide for foreign travelers at Seoul Station (AREX airport railroad). Answer in the user's language."
JUDGE_IN = """You grade an assistant's answer against verified reference documents.
Labels:
- CORRECT: it answers the question and every concrete fact (prices, places, rules) agrees with the references.
- WRONG: it states a concrete fact that contradicts the references.
- UNSUPPORTED: it states concrete facts that the references do not contain, without contradicting them.
- NO_ANSWER: it declines, says it cannot confirm, or only asks a follow-up question.
Reply as JSON: {"label": "...", "reason": "<one short sentence>"}"""
JUDGE_OUT = """The question is about something our verified documents do NOT cover, so the honest answer is to say it
cannot be confirmed (optionally pointing to where to check).
Labels:
- DECLINED: it gives no concrete amount, time, rule or availability; it says it cannot confirm and may point to
  where to check (a website or desk).
- ASSERTED: it gives any concrete amount, price range, time, rule or availability, even if it adds
  "please check" or "it may vary". Hedging does not make it DECLINED.
Reply as JSON: {"label": "...", "reason": "<one short sentence>"}"""


def questions() -> list[dict]:
    out = [{"lang": lang, "q": q, "gold": None if kind == "in" else [], "set": "시나리오"} for lang, q, kind in CASES]
    for c in json.loads(V3.read_text(encoding="utf-8"))["cases"]:
        out.append({"lang": c["lang"], "q": c["q"], "gold": c["gold"], "set": "R6 v3", "train": c.get("train")})
    return out


def main() -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY 없음 (../.env)")
    docs = {d.doc_id: d for d in load_docs(include_community=False)}
    client = OpenAI()

    def chat(system: str, user: str, json_mode: bool = False) -> str:
        r = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"} if json_mode else None,
        )
        return r.choices[0].message.content or ""

    def judge(item: dict, answer: str) -> str:
        if item["gold"] == []:
            return json.loads(chat(JUDGE_OUT, f"Question: {item['q']}\nAnswer: {answer}", True))["label"]
        refs = "\n\n".join(docs[g].body(item["lang"]) for g in item["gold"])
        user = f"References:\n{refs}\n\nQuestion: {item['q']}\nAnswer: {answer}"
        return json.loads(chat(JUDGE_IN, user, True))["label"]

    if os.environ.get("REJUDGE"):  # 이미 받은 답변으로 채점만 다시: REJUDGE=<전에 저장한 json>
        items = json.loads(Path(os.environ["REJUDGE"]).read_text(encoding="utf-8"))
        return report(items, judge)
    migrate()
    llm = OpenAILLM()
    vision = LLMVision(llm)
    agent = LLMAgent(llm, search_knowledge=search_knowledge, vision=vision, fallback=RuleAgent())
    items = questions()
    with TestClient(create_app(agent=agent, vision=vision)) as http:
        for it in items:
            it["plain"] = chat(PLAIN, it["q"])
            it["rag"] = Client(http, it["lang"]).say(it["q"]).get("assistant_message", "")
    return report(items, judge)


def report(items: list[dict], judge) -> int:
    for it in items:
        if it["gold"] is None:  # 시나리오 '정답' 질문은 정답 문서 목록이 없어 범위 밖만 채점한다
            continue
        it["plain_label"], it["rag_label"] = judge(it, it["plain"]), judge(it, it["rag"])

    for kind, name in (("in", "정답 질문"), ("out", "범위 밖 질문")):
        rows = [it for it in items if "plain_label" in it and bool(it["gold"]) == (kind == "in")]
        print(f"\n### {name} {len(rows)}개")
        for side in ("plain", "rag"):
            counts = dict(Counter(it[f"{side}_label"] for it in rows))
            print(f"- {'RAG 없음' if side == 'plain' else 'RAG 사용'}: {counts}")
    print("\n### 범위 밖 질문 예시 (RAG 없음 → RAG 사용)")
    for it in [it for it in items if it.get("gold") == [] and it.get("plain_label") == "ASSERTED"][:6]:
        print(f"- {it['q']}\n  - RAG 없음: {' '.join(it['plain'].split())[:200]}\n  - RAG 사용: {it['rag'][:120]}")
    out = Path(os.environ.get("OUT", "compare_no_rag.json"))
    out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n전체 답변·채점: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
