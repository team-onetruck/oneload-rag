"""localization/ 임시 위치 데이터가 지도와 맞는지 · 매처 결과가 기대대로인지. 옆 레포가 없으면 skip."""

import importlib.util
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "evaluate", Path(__file__).resolve().parents[1] / "localization/evaluate.py"
)
evaluate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluate)

try:
    PROBLEMS, ROWS = evaluate.run()
except (FileNotFoundError, ImportError) as exc:
    if os.environ.get("RAG_REQUIRE_CONTRACT") == "1":
        pytest.fail(str(exc), pytrace=False)
    pytest.skip(str(exc), allow_module_level=True)


def test_cards_and_cases_match_the_map():
    assert PROBLEMS == []


def test_clean_cases_hit_top1_with_agent_ranker():
    """카드의 문구를 그대로 읽은 사진은 1위여야 한다 (카드 · 케이스 오타 검사)."""
    missed = [r["case"]["id"] for r in ROWS if r["case"]["kind"] == "clean" and not r["agent·카드"][1]]
    assert missed == []


def test_no_match_cases_give_no_candidates():
    for r in ROWS:
        if r["case"].get("expect") == "NO_MATCH":
            assert all(not r[name][0] for name in ("backend·현재지도", "backend·카드", "agent·카드")), r["case"]["id"]


def test_cards_improve_on_current_map_landmarks():
    hits = {name: sum(r[name][2] for r in ROWS) for name in ("backend·현재지도", "backend·카드")}
    assert hits["backend·카드"] > hits["backend·현재지도"]
