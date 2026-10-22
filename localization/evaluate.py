"""임시 위치 데이터 평가: 특징 카드(seoul-station.landmarks.yaml) × 합성 케이스(cases.yaml) → 매처 비교.

    uv run python localization/evaluate.py

옆 폴더의 oneload-data · oneload-backend · oneload_agent 를 쓴다 (RAG_DATA_DIR · RAG_BACKEND_DIR · RAG_AGENT_DIR).
비교 대상: 백엔드 match_location(현재 지도 landmarks / 특징 카드) · R2 rank_location(특징 카드).
사진 · 모델 없이 '읽힌 글자 → 위치' 단계만 본다. 실제 사진 정확도는 현장 사진으로만 잴 수 있다.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
STATUSES = {"desk", "placeholder", "field"}


def find(env: str, name: str) -> Path | None:
    if os.environ.get(env):
        return Path(os.environ[env])
    for base in (HERE.parents[1], HERE.parent):
        for candidate in (base / name, base / f"{name}-main"):
            if candidate.is_dir():
                return candidate
    return None


def load_inputs() -> tuple[dict, list[dict]]:
    cards = yaml.safe_load((HERE / "seoul-station.landmarks.yaml").read_text(encoding="utf-8"))
    cases = yaml.safe_load((HERE / "cases.yaml").read_text(encoding="utf-8"))["cases"]
    return cards, cases


def check(cards: dict, cases: list[dict], raw_map: dict) -> list[str]:
    """카드 · 케이스가 지도와 맞는지. 문제 목록을 돌려준다 (비면 정상)."""
    nodes = {n["id"] for n in raw_map["nodes"]}
    problems = []
    if cards["map_version"] != raw_map["version"]:
        problems.append(f"지도 버전 다름: 카드 {cards['map_version']} / 지도 {raw_map['version']}")
    seen = set()
    for card in cards["nodes"]:
        if card["node_id"] not in nodes:
            problems.append(f"지도에 없는 노드: {card['node_id']}")
        for lm in card["landmarks"]:
            if lm["landmark_id"] in seen:
                problems.append(f"landmark_id 중복: {lm['landmark_id']}")
            seen.add(lm["landmark_id"])
            if lm["source"] not in cards["sources"]:
                problems.append(f"{lm['landmark_id']}: 정의되지 않은 source {lm['source']}")
            if lm["status"] not in STATUSES:
                problems.append(f"{lm['landmark_id']}: status 는 {sorted(STATUSES)} 중 하나")
            if not lm["sign_texts"]:
                problems.append(f"{lm['landmark_id']}: sign_texts 비어 있음")
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        problems.append("케이스 id 중복")
    for c in cases:
        expected = c.get("any_of") or [c.get("expect")]
        problems += [f"{c['id']}: 지도에 없는 정답 {e}" for e in expected if e != "NO_MATCH" and e not in nodes]
    return problems


def with_landmarks(raw_map: dict, cards: dict) -> dict:
    landmarks = [
        {"landmark_id": lm["landmark_id"], "node_id": card["node_id"], "sign_texts": lm["sign_texts"]}
        for card in cards["nodes"]
        for lm in card["landmarks"]
    ]
    return {**raw_map, "landmarks": landmarks}


def grade(case: dict, ids: list[str]) -> tuple[bool, bool]:
    """(top-1 정답, top-3 정답). NO_MATCH 는 후보가 없어야 정답."""
    if case.get("expect") == "NO_MATCH":
        return not ids, not ids
    wanted = set(case.get("any_of") or [case["expect"]])
    return bool(ids) and ids[0] in wanted, bool(wanted & set(ids[:3]))


def run() -> tuple[list[str], list[dict]]:
    data, backend, agent = (
        find("RAG_DATA_DIR", "oneload-data"),
        find("RAG_BACKEND_DIR", "oneload-backend"),
        find("RAG_AGENT_DIR", "oneload_agent"),
    )
    if not (data and backend and agent):
        raise FileNotFoundError(f"옆 레포 없음: data={data} backend={backend} agent={agent}")
    sys.path[:0] = [str(backend), str(agent)]
    from app.domain.localization import Hints, VisionFeatures, match_location
    from app.domain.mapdata import MapData
    from hangil_r2.backend.localization_types import Hints as AgentHints
    from hangil_r2.backend.localization_types import VisionFeatures as AgentFeatures
    from hangil_r2.backend.mapdata import MapData as AgentMapData
    from hangil_r2.ranker import rank_location

    raw = json.loads((data / "maps" / "seoul-station.json").read_text(encoding="utf-8"))
    cards, cases = load_inputs()
    problems = check(cards, cases, raw)
    proposed = with_landmarks(raw, cards)
    matchers = {
        "backend·현재지도": lambda f: match_location(VisionFeatures(**f), MapData(**raw), Hints(), "ko"),
        "backend·카드": lambda f: match_location(VisionFeatures(**f), MapData(**proposed), Hints(), "ko"),
        "agent·카드": lambda f: rank_location(AgentFeatures(**f), AgentMapData(**proposed), AgentHints(), "ko"),
    }
    rows = []
    for case in cases:
        features = {"image_quality": case.get("quality", "usable"), "texts": [{"text": t} for t in case["texts"]]}
        row = {"case": case}
        for name, match in matchers.items():
            ids = [c.node_id for c in match(features)]
            row[name] = (ids, *grade(case, ids))
        rows.append(row)
    return problems, rows


def report(rows: list[dict]) -> str:
    names = [k for k in rows[0] if k != "case"]
    lines = ["| 케이스 | 종류 | 정답 | " + " | ".join(names) + " |", "|---|---|---|" + "---|" * len(names)]
    for r in rows:
        c = r["case"]
        cells = []
        for n in names:
            ids, top1, top3 = r[n]
            mark = "✅" if top1 else "🟡" if top3 else "❌"
            cells.append(f"{mark} {', '.join(ids[:3]) or '(없음)'}")
        lines.append(
            f"| {c['id']} | {c['kind']} | {c.get('expect') or '/'.join(c['any_of'])} | " + " | ".join(cells) + " |"
        )
    lines.append("")
    lines.append("✅ top-1 정답 · 🟡 top-3 안에 정답 · ❌ 틀림 (NO_MATCH 는 후보가 없어야 정답)")
    lines.append("")
    for n in names:
        found = [r[n] for r in rows if r["case"].get("expect") != "NO_MATCH"]
        none = [r[n] for r in rows if r["case"].get("expect") == "NO_MATCH"]
        lines.append(
            f"- {n}: top-1 {sum(x[1] for x in found)}/{len(found)}, top-3 {sum(x[2] for x in found)}/{len(found)}, "
            f"no_match {sum(x[1] for x in none)}/{len(none)}"
        )
    return "\n".join(lines)


def main() -> int:
    problems, rows = run()
    for p in problems:
        print(f"[데이터 문제] {p}")
    print(report(rows))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
