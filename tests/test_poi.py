"""poi/ 장소 별칭 사전이 지도와 맞고, 질문이 기대한 POI 로 가는지. 옆 레포가 없으면 skip."""

import importlib.util
import os
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("poi_check", Path(__file__).resolve().parents[1] / "poi/check.py")
poi_check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(poi_check)

try:
    PROBLEMS, ROWS = poi_check.run()
except (FileNotFoundError, ImportError) as exc:
    if os.environ.get("RAG_REQUIRE_CONTRACT") == "1":
        pytest.fail(str(exc), pytrace=False)
    pytest.skip(str(exc), allow_module_level=True)


def test_aliases_match_the_map():
    assert PROBLEMS == []


def test_every_query_finds_exactly_the_expected_pois():
    missed = [(r["q"]["q"], r["별칭 추가"][0]) for r in ROWS if not r["별칭 추가"][1]]
    assert missed == []
