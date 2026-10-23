"""실제 LLM 으로 Agent 답변 확인 (RQ-32 근거): 범위 밖 질문에 근거 없는 요금을 말하는지, 관련 없는 출처를 붙이는지.

e2e_backend.py 와 같은 조립(백엔드 API + R2 LLMAgent + R3 검색)에서 LLM 만 OpenAI 로 바꾼다.
OpenAI 키가 필요하고 비용이 든다 (질문 16개, 몇십 원 수준). 결과는 표로 출력한다.

    set -a; . ../.env; set +a
    uv run --project ../oneload-backend --with ../oneload-rag python scripts/agent_live_check.py
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_backend import Client, ids, migrate  # noqa: E402  (옆 레포 경로 · DB 설정도 여기서)

from app.ai.rule_agent import RuleAgent  # noqa: E402
from app.main import create_app  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from hangil_r2 import LLMAgent, LLMVision, OpenAILLM  # noqa: E402

from hangil_rag import search_knowledge  # noqa: E402

# (언어, 질문, 기대). out = 문서에 답이 없음: 금액을 말하지 않고 관련 없는 출처를 붙이지 않아야 함
CASES = [
    ("ko", "서울역에서 인천공항 가는 리무진버스 승차권은 얼마인가요?", "out"),
    ("en", "What does a KTX ticket from Seoul Station to Busan cost?", "out"),
    ("ko", "택시 기본요금이 얼마예요?", "out"),
    ("ko", "인천공항에서 항공사 위탁수하물 추가 요금을 조회해 주세요.", "out"),
    ("en", "What is the passport replacement fee near Seoul Station?", "out"),
    ("ko", "서울에서 출발하는 항공권 가격을 조회해 줘", "out"),
    ("ko", "공항 라운지 이용하는 방법 알려줘", "out"),
    ("ko", "서울역 근처 호텔 객실 가격 알려줘", "out"),
    ("ko", "직통열차 표는 발매기에서 해외 카드로 살 수 있어요?", "in"),
    ("en", "Can I pay for the Express train ticket with a foreign credit card?", "in"),
    ("ko", "공항철도에서 내려서 1호선 타려면 어디로 가요?", "in"),
    ("en", "How do I get to the KTX from the AREX platform at Seoul Station?", "in"),
    ("ko", "직통열차 표로 지하철 탈 수 있어요?", "in"),
    ("ko", "보증금 환급은 어떻게 해?", "in"),
    ("ko", "직통열차 요금 얼마야?", "in"),
    ("ko", "서울역 공항철도 승강장은 몇 층이에요?", "in"),
]
if os.environ.get("ONLY"):  # 일부만 다시: ONLY=12,13
    CASES = [CASES[int(i) - 1] for i in os.environ["ONLY"].split(",")]
MONEY = re.compile(r"\d[\d,]*\s*(원|won|KRW)|₩\s*\d", re.I)


def main() -> int:
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("OPENAI_API_KEY 없음 (../.env)")
    migrate()
    llm = OpenAILLM()
    vision = LLMVision(llm)
    agent = LLMAgent(llm, search_knowledge=search_knowledge, vision=vision, fallback=RuleAgent())
    print(f"모델: {os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')}\n")
    print("| # | 기대 | 질문 | 상태 | 금액 언급 | 출처 | 답변 |\n|---|---|---|---|---|---|---|")
    with TestClient(create_app(agent=agent, vision=vision)) as http:
        for n, (lang, q, kind) in enumerate(CASES, 1):
            r = Client(http, lang).say(q)
            msg = " ".join(r.get("assistant_message", "").split())
            money = "있음" if MONEY.search(msg) else "-"
            src = ", ".join(i.removeprefix("doc-") for i in ids(r)) or "-"
            print(f"| {n} | {kind} | {q} | {r['status']} | {money} | {src} | {msg[:220]} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
