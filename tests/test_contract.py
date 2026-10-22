"""옆 레포와의 계약: oneload_agent (R2) · oneload-backend (R4) 를 실제로 import 해서 확인한다.

찾는 순서: RAG_AGENT_DIR · RAG_BACKEND_DIR → 옆 폴더 (oneload_agent, oneload-backend, zip 이면 *-main).
없으면 skip. CI 는 RAG_REQUIRE_CONTRACT=1 로 skip 대신 실패하게 한다.
"""

import os
import re
import sys
from pathlib import Path

import pytest

from hangil_rag import search_knowledge
from hangil_rag.loader import load_docs
from hangil_rag.schemas import KnowledgeHit, SearchUnavailable, unavailable

HERE = Path(__file__).resolve().parents[1]


def _find(env: str, name: str) -> Path | None:
    if os.environ.get(env):
        return Path(os.environ[env])
    for base in (HERE.parent, HERE):
        for candidate in (base / name, base / f"{name}-main"):
            if candidate.is_dir():
                return candidate
    return None


AGENT, BACKEND = _find("RAG_AGENT_DIR", "oneload_agent"), _find("RAG_BACKEND_DIR", "oneload-backend")


def _skip(reason: str):
    if os.environ.get("RAG_REQUIRE_CONTRACT") == "1":
        pytest.fail(reason, pytrace=False)
    pytest.skip(reason, allow_module_level=True)


if not (AGENT and BACKEND):
    _skip(f"옆 레포 없음: agent={AGENT} backend={BACKEND}")
sys.path[:0] = [str(BACKEND), str(AGENT)]
try:
    from app.ai.contracts import Source
    from app.ai.rule_agent import _SOURCES
    from hangil_r2 import FakeLLM, LLMAgent
    from hangil_r2.backend.contracts import AgentContext, Slots
    from hangil_r2.backend.guard import guard
    from hangil_r2.backend.mapdata import MapStore
    from hangil_r2.knowledge import KnowledgeHit as AgentHit
    from hangil_r2.knowledge import ToolUnavailable
except ImportError as exc:  # Agent 의존성(langgraph 등) 미설치
    _skip(f"옆 레포 import 실패: {exc} (pip install -r oneload_agent/requirements.txt)")

SEOUL = MapStore.load(AGENT / "mocks" / "maps").get("seoul-station")
QUERIES = [
    "직통열차 일반열차 차이",
    "직통열차 승차권",
    "일반열차 교통카드",
    "보증금 환급",
    "How do I get my deposit back?",
]


def all_hits() -> list[KnowledgeHit]:
    hits = [h for q in QUERIES for lang in ("ko", "en") for h in search_knowledge(q, lang, {})]
    assert {h.document_id for h in hits} == {d.doc_id for d in load_docs()}
    return hits


# ── 모양 ────────────────────────────────────────────────────────────────
def test_same_fields_as_agent_knowledge_hit():
    assert list(KnowledgeHit.model_fields) == list(AgentHit.model_fields)


def test_hits_convert_to_agent_hit_and_backend_source():
    for h in all_hits():
        agent_hit = AgentHit.model_validate(h.model_dump())
        assert agent_hit.model_dump() == h.model_dump()
        Source(document_id=h.document_id, title=h.title, source_url=h.source_url, verified_at=h.verified_at)


def test_doc_ids_match_backend_rule_agent_demo_docs():
    backend_docs = {v[0] for v in _SOURCES.values() if v[0].startswith("doc-")}
    assert backend_docs <= {d.doc_id for d in load_docs()}  # 백엔드가 인용하는 ID 는 모두 있어야 한다


def test_outage_exception_is_caught_by_agent():
    exc = unavailable("down")
    assert isinstance(exc, ToolUnavailable) and isinstance(exc, SearchUnavailable)


# ── Agent 흐름에 실제로 끼워서 (oneload_agent tests/test_agent.py 의 같은 번호) ─────────────
def ctx(lang="ko", slots=None, here=None) -> AgentContext:
    return AgentContext(
        language=lang,
        map=SEOUL,
        state="idle",
        destination_poi_id=None,
        confirmed_node_id=here,
        slots=slots or Slots(),
        recent_messages=[],
    )


def ask(c, message, search=search_knowledge):
    a = LLMAgent(FakeLLM(), search_knowledge=search)
    return guard(a.handle_message(c, message, None, None), c.map, c.language)


def test_a21_allstop_does_not_cite_express_doc():
    r = ask(ctx(slots=Slots(train_type="allstop")), "없어요")
    got = [s.document_id for s in r.sources]
    assert r.destination.poi_id == "poi-allstop-tickets" and "doc-allstop-ticket" in got
    assert "doc-express-ticket" not in got


def test_a02_express_cites_express_doc():
    r = ask(ctx(), "직통열차")
    assert r.status == "destination_set" and any(s.document_id == "doc-express-ticket" for s in r.sources)


def test_a04_unsure_cites_train_types_first():
    r = ask(ctx(), "잘 모르겠어요")
    assert r.status == "needs_clarification" and r.sources[0].document_id == "doc-arex-train-types"


def test_a07_usage_answer_cites_deposit_doc():
    r = ask(ctx(), "보증금 환급은 어떻게 해?")
    assert r.status == "answered" and r.sources[0].document_id == "doc-deposit-refund"


def test_a08_fare_is_not_invented():
    r = ask(ctx(), "직통열차 요금 얼마야?")
    assert r.status == "cannot_answer" and not re.search(r"\d", r.assistant_message) and r.sources == []


def test_a10_outage_means_cannot_answer():
    def down(*_):
        raise unavailable("rag down")

    assert ask(ctx(), "보증금 환급은 어떻게 해?", search=down).status == "cannot_answer"


def test_a14_english():
    r = ask(ctx(lang="en"), "Where do I buy an express ticket?")
    assert r.destination.poi_id == "poi-express-tickets"
    assert r.sources[0].title == "Buying an Express train ticket at Seoul Station"
    assert "doc-deposit-refund" not in [s.document_id for s in r.sources]  # "ticket" 하나로 붙지 않음
