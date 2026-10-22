"""장소 별칭 사전 검사: 별칭을 넣은 지도로 백엔드 search_pois 를 돌려 질문(queries.yaml)이 맞는 POI 로 가는지 본다.

    uv run python poi/check.py

옆 폴더의 oneload-data · oneload-backend 를 쓴다 (RAG_DATA_DIR · RAG_BACKEND_DIR). 지도는 바꾸지 않는다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("evaluate", HERE.parent / "localization" / "evaluate.py")
_evaluate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_evaluate)
find = _evaluate.find  # 옆 레포 찾기 규칙은 localization/evaluate.py 와 같다


def load() -> tuple[dict, list[dict]]:
    aliases = yaml.safe_load((HERE / "seoul-station.aliases.yaml").read_text(encoding="utf-8"))
    queries = yaml.safe_load((HERE / "queries.yaml").read_text(encoding="utf-8"))["queries"]
    return aliases, queries


def check(aliases: dict, raw_map: dict) -> list[str]:
    ids = {p["poi_id"] for p in raw_map["pois"]}
    problems = [f"지도에 없는 POI: {pid}" for pid in aliases["pois"] if pid not in ids]
    if aliases["map_version"] != raw_map["version"]:
        problems.append(f"지도 버전 다름: 사전 {aliases['map_version']} / 지도 {raw_map['version']}")
    for pid, entry in aliases["pois"].items():
        texts = [a["text"] for a in entry["add"]]
        problems += [f"{pid}: 별칭 중복 {t}" for t in {t for t in texts if texts.count(t) > 1}]
        problems += [f"{pid}: 대문자 포함 {t} (search_pois 는 별칭을 소문자로 비교)" for t in texts if t != t.lower()]
    return problems


def with_aliases(raw_map: dict, aliases: dict) -> dict:
    pois = []
    for p in raw_map["pois"]:
        extra = [a["text"] for a in aliases["pois"].get(p["poi_id"], {}).get("add", [])]
        pois.append({**p, "aliases": list(dict.fromkeys(p.get("aliases", []) + extra))})
    return {**raw_map, "pois": pois}


def run() -> tuple[list[str], list[dict]]:
    data, backend = find("RAG_DATA_DIR", "oneload-data"), find("RAG_BACKEND_DIR", "oneload-backend")
    if not (data and backend):
        raise FileNotFoundError(f"옆 레포 없음: data={data} backend={backend}")
    sys.path.insert(0, str(backend))
    from app.domain.mapdata import MapData

    raw = json.loads((data / "maps" / "seoul-station.json").read_text(encoding="utf-8"))
    aliases, queries = load()
    current, proposed = MapData(**raw), MapData(**with_aliases(raw, aliases))
    rows = []
    for q in queries:
        want = set(q["expect"])
        row = {"q": q}
        for name, m in (("현재", current), ("별칭 추가", proposed)):
            got = [p.poi_id for p in m.search_pois(q["q"])]
            row[name] = (got, set(got) == want)
        rows.append(row)
    return check(aliases, raw), rows


def report(rows: list[dict]) -> str:
    lines = ["| 질문 | 기대 | 현재 지도 | 별칭 추가 후 |", "|---|---|---|---|"]
    for r in rows:
        q = r["q"]
        want = ", ".join(q["expect"]) or ("(제안 POI, 지도에 없음)" if q.get("proposed") else "(없음)")
        cells = [f"{'✅' if ok else '❌'} {', '.join(got) or '-'}" for got, ok in (r["현재"], r["별칭 추가"])]
        lines.append(f"| {q['q']} | {want} | " + " | ".join(cells) + " |")
    for name in ("현재", "별칭 추가"):
        lines.append(f"\n- {name}: {sum(r[name][1] for r in rows)}/{len(rows)} 정확히 기대한 POI 만 찾음")
    return "\n".join(lines)


def main() -> int:
    problems, rows = run()
    for p in problems:
        print(f"[데이터 문제] {p}")
    print(report(rows))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
